"""Preprocessing worker: validates job, creates thumbnail, advances to generator queue."""
import sys
import os
import json
import time
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pika
from PIL import Image
import io

from core.config import get_settings
from core.database import SessionLocal
from models.job import Job
from services.storage import get_client, settings as storage_settings, ensure_buckets
from services.queue import QUEUE_PREPROC, QUEUE_GENERATOR, QUEUE_DLQ

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("preproc_worker")

settings = get_settings()


def _preproc_template_job(job_id: str, job, db):
    """Create a placeholder thumbnail for template-based jobs."""
    img = Image.new("RGB", (360, 640), color=(30, 30, 30))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    thumb_key = f"thumbs/{job_id}.jpg"

    client = get_client()
    client.put_object(
        Bucket=storage_settings.r2_bucket_uploads,
        Key=thumb_key,
        Body=buf.getvalue(),
        ContentType="image/jpeg",
    )
    logger.info(f"Job {job_id} template: placeholder thumb created")


def _preproc_custom_job(job_id: str, job, db):
    """Validate that user photos exist in R2 for custom jobs."""
    options = job.options or {}
    photo_1_path = options.get("photo_1_path")
    if not photo_1_path:
        raise ValueError("Custom job missing photo_1_path in options")

    client = get_client()
    try:
        client.head_object(Bucket=storage_settings.r2_bucket_uploads, Key=photo_1_path)
    except Exception:
        raise ValueError(f"photo_1 not found in storage: {photo_1_path}")

    photo_2_path = options.get("photo_2_path")
    if photo_2_path:
        try:
            client.head_object(Bucket=storage_settings.r2_bucket_uploads, Key=photo_2_path)
        except Exception:
            raise ValueError(f"photo_2 not found in storage: {photo_2_path}")

    logger.info(f"Job {job_id} custom: photos validated (photo_2={'yes' if photo_2_path else 'no'})")


def process_job(job_id: str):
    db = SessionLocal()
    try:
        job = db.query(Job).filter(Job.id == job_id).first()
        if not job:
            logger.error(f"Job {job_id} not found")
            return

        logger.info(f"Processing job {job_id}, type={getattr(job, 'job_type', 'template')}")

        job_type = getattr(job, 'job_type', 'template') or 'template'
        if job_type == "custom":
            _preproc_custom_job(job_id, job, db)
        else:
            _preproc_template_job(job_id, job, db)

        job.status = "processing"
        job.progress = 10
        db.commit()
        logger.info(f"Job {job_id} status=processing, progress=10")

        # Publish to generator
        params = pika.URLParameters(settings.rabbitmq_url)
        conn = pika.BlockingConnection(params)
        channel = conn.channel()
        channel.queue_declare(queue=QUEUE_GENERATOR, durable=True)
        channel.basic_publish(
            exchange="",
            routing_key=QUEUE_GENERATOR,
            body=json.dumps({"job_id": job_id}),
            properties=pika.BasicProperties(delivery_mode=2),
        )
        conn.close()
        logger.info(f"Job {job_id} published to {QUEUE_GENERATOR}")

    except Exception as e:
        logger.error(f"Error processing job {job_id}: {e}")
        db.rollback()
        try:
            job = db.query(Job).filter(Job.id == job_id).first()
            if job:
                job.status = "failed"
                job.error = str(e)
                db.commit()
        except Exception:
            pass
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
            channel.queue_declare(queue=QUEUE_PREPROC, durable=True)
            channel.queue_declare(queue=QUEUE_DLQ, durable=True)
            channel.basic_qos(prefetch_count=1)
            channel.basic_consume(queue=QUEUE_PREPROC, on_message_callback=callback)
            logger.info(f"Waiting for messages on {QUEUE_PREPROC}")
            channel.start_consuming()
        except Exception as e:
            logger.error(f"Connection error: {e}, retrying in 5s")
            time.sleep(5)


if __name__ == "__main__":
    main()
