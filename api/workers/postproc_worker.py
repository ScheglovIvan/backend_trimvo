"""Post-processing worker: extract thumb early, then generate full previews."""
import sys
import os
import json
import time
import logging
import tempfile

import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pika

from core.config import get_settings
from core.database import SessionLocal
from models.job import Job
from models.user import User
from services.storage import get_client, settings as storage_settings, ensure_buckets, get_signed_url
from services import media_processor
from services.gems import refund_gems
from services.queue import QUEUE_POSTPROC, QUEUE_DLQ

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("postproc_worker")

settings = get_settings()

_SIGNED_URL_EXPIRES = 604800  # 7 days


def _result_url(key: str) -> str:
    return get_signed_url(storage_settings.r2_bucket_results, key, expires=_SIGNED_URL_EXPIRES)


def _download_bytes(url: str) -> bytes:
    logger.info(f"Downloading: {url[:80]}...")
    resp = requests.get(url, timeout=180, stream=True)
    resp.raise_for_status()
    data = b"".join(resp.iter_content(chunk_size=65536))
    logger.info(f"Downloaded {len(data) // 1024} KB")
    return data


def _save_original(job_id: str, video_bytes: bytes, fmt: str = "mp4") -> str:
    key = f"{job_id}/original.{fmt}"
    get_client().put_object(
        Bucket=storage_settings.r2_bucket_results,
        Key=key,
        Body=video_bytes,
        ContentType=f"video/{fmt}",
    )
    logger.info(f"Saved original: {key}")
    return key


def _download_from_r2(key: str) -> bytes:
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
        tmp_path = tmp.name
    try:
        get_client().download_file(storage_settings.r2_bucket_results, key, tmp_path)
        with open(tmp_path, "rb") as f:
            return f.read()
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


def _upload_early_thumb(job_id: str, video_bytes: bytes) -> str | None:
    """Extract first frame and upload immediately so client has something to show."""
    bucket = storage_settings.r2_bucket_results
    key = f"{job_id}/thumb.jpg"
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            inp = os.path.join(tmpdir, "input.mp4")
            out = os.path.join(tmpdir, "thumb.jpg")
            with open(inp, "wb") as f:
                f.write(video_bytes)
            media_processor.extract_thumb(inp, out)
            with open(out, "rb") as f:
                data = f.read()
        get_client().put_object(
            Bucket=bucket,
            Key=key,
            Body=data,
            ContentType="image/jpeg",
        )
        logger.info(f"Early thumb uploaded: {key} ({len(data)} bytes)")
        return key
    except Exception as e:
        logger.warning(f"Early thumb failed (non-fatal): {e}")
        return None


def process_job(job_id: str):
    db = SessionLocal()
    try:
        job = db.query(Job).filter(Job.id == job_id).first()
        if not job:
            logger.error(f"Job {job_id} not found")
            return

        if job.status in ("done", "failed"):
            logger.info(f"Job {job_id} already terminal ({job.status}), skipping")
            return

        if not job.result_path:
            job.status = "failed"
            job.error = "No result path set by generator"
            db.commit()
            return

        result_path = job.result_path
        logger.info(f"Job {job_id}: postproc started, result_path={result_path[:80]}...")

        # ── Download video ──────────────────────────────────────────────────
        if result_path.startswith("http"):
            video_bytes = _download_bytes(result_path)
            fmt = "mov" if result_path.endswith(".mov") else "mp4"
        else:
            video_bytes = _download_from_r2(result_path)
            fmt = "mp4"

        bucket = storage_settings.r2_bucket_results

        # ── Fast thumb: first frame → DB update → Flutter shows it immediately
        thumb_key = _upload_early_thumb(job_id, video_bytes)
        if thumb_key:
            job.thumb_url = _result_url(thumb_key)
            db.commit()
            logger.info(f"Job {job_id}: early thumb set, client can show preview frame")

        # ── Save original + full FFmpeg processing ──────────────────────────
        logger.info(f"Job {job_id}: generating previews via FFmpeg...")
        original_key = _save_original(job_id, video_bytes, fmt)
        media_result = media_processor.process_video(video_bytes, job_id, bucket)

        # ── Mark done with final URLs ───────────────────────────────────────
        db.expire(job)
        job = db.query(Job).filter(Job.id == job_id).first()

        job.status = "done"
        job.progress = 100
        job.original_url = _result_url(original_key)

        if media_result.get("preview_compressed_path"):
            job.preview_url = _result_url(media_result["preview_compressed_path"])

        if media_result.get("thumb_path"):
            job.thumb_url = _result_url(media_result["thumb_path"])

        job.result_path = job.preview_url or job.original_url
        db.commit()

        logger.info(
            f"Job {job_id}: done. "
            f"preview={job.preview_url[:60] if job.preview_url else 'none'} "
            f"thumb={job.thumb_url[:60] if job.thumb_url else 'none'}"
        )

    except Exception as e:
        logger.error(f"Error in postproc for job {job_id}: {e}")
        db.rollback()
        try:
            job = db.query(Job).filter(Job.id == job_id).first()
            if job and job.status != "done":
                job.status = "failed"
                job.error = str(e)[:400]
                db.commit()
                if job.gems_cost and job.gems_cost > 0:
                    user = db.query(User).filter(User.id == job.user_id).first()
                    if user:
                        refund_gems(db, user, job.gems_cost, str(job.id))
        except Exception as inner:
            logger.error(f"Failed to mark job failed: {inner}")
    finally:
        db.close()


def callback(ch, method, properties, body):
    data = json.loads(body)
    job_id = data.get("job_id")
    logger.info(f"Received job_id={job_id}")
    try:
        process_job(job_id)
        ch.basic_ack(delivery_tag=method.delivery_tag)
    except Exception as e:
        logger.error(f"Unhandled error: {e}")
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)


def main():
    ensure_buckets()
    while True:
        try:
            params = pika.URLParameters(settings.rabbitmq_url)
            params.heartbeat = 600
            conn = pika.BlockingConnection(params)
            channel = conn.channel()
            channel.queue_declare(queue=QUEUE_POSTPROC, durable=True)
            channel.queue_declare(queue=QUEUE_DLQ, durable=True)
            channel.basic_qos(prefetch_count=1)
            channel.basic_consume(queue=QUEUE_POSTPROC, on_message_callback=callback)
            logger.info(f"Waiting for messages on {QUEUE_POSTPROC}")
            channel.start_consuming()
        except Exception as e:
            logger.error(f"Connection error: {e}, retrying in 5s")
            time.sleep(5)


if __name__ == "__main__":
    main()
