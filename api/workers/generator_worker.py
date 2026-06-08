"""Generator worker: AI generation via Replicate (image/video) and Wavespeed (face swap)."""
import sys
import os
import json
import time
import random
import logging
import io
import requests
import tempfile
from urllib.parse import urlparse

from PIL import Image
from deep_translator import GoogleTranslator

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pika

from core.config import get_settings
from core.database import SessionLocal
from models.job import Job
from models.user import User
from models.template import Template
from models.admin_config import AdminConfig
from services.storage import (
    get_client,
    settings as storage_settings,
    copy_object,
    download_file,
    ensure_buckets,
)
from services.queue import QUEUE_GENERATOR, QUEUE_POSTPROC, QUEUE_DLQ
from services.gems import refund_gems

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("generator_worker")

settings = get_settings()

# ---------------------------------------------------------------------------
# Replicate config
# ---------------------------------------------------------------------------

REPLICATE_API_TOKEN = os.environ.get("REPLICATE_API_TOKEN", "") or settings.replicate_api_token
REPLICATE_BASE = "https://api.replicate.com/v1"

WAVESPEED_API_KEY = os.environ.get("WAVESPEED_API_KEY", "") or settings.wavespeed_api_key
WAVESPEED_BASE = "https://api.wavespeed.ai/api/v3"

# minimax/video-01-live — video generation from prompt + reference image
MODEL_REF_VIDEO = "7574e16b8f1ad52c6332ecb264c0f132e555f46c222255a738131ec1bb614092"

# vidu/q3-pro — start-end-to-video, up to 16s at 1080p with audio
MODEL_INTERPOLATE = "vidu/q3-pro"

# black-forest-labs/flux-kontext-pro — instruction-based image editing, preserves identity
MODEL_IMAGE = "black-forest-labs/flux-kontext-pro"



def _auth_headers():
    return {"Authorization": f"Token {REPLICATE_API_TOKEN}"}


def _json_headers():
    return {**_auth_headers(), "Content-Type": "application/json"}


# ---------------------------------------------------------------------------
# Replicate Files API — upload local/MinIO files so Replicate can access them
# ---------------------------------------------------------------------------

def _upload_to_replicate(data: bytes, filename: str) -> str:
    """Upload raw bytes to Replicate Files API, return the hosted URL."""
    ext = os.path.splitext(filename)[1].lower()
    mime = "image/jpeg" if ext in (".jpg", ".jpeg") else "image/png" if ext == ".png" else "application/octet-stream"
    last_exc: Exception | None = None
    for attempt in range(3):
        try:
            resp = requests.post(
                f"{REPLICATE_BASE}/files",
                headers=_auth_headers(),
                files={"content": (filename, data, mime)},
                timeout=120,
            )
            resp.raise_for_status()
            url = resp.json()["urls"]["get"]
            logger.info(f"Uploaded to Replicate Files: {filename} ({len(data)} bytes) → {url[:60]}...")
            return url
        except (BrokenPipeError, ConnectionError, requests.exceptions.ConnectionError) as e:
            last_exc = e
            logger.warning(f"Upload attempt {attempt + 1}/3 failed: {e}, retrying...")
            time.sleep(2 ** attempt)
    raise RuntimeError(f"Replicate upload failed after 3 attempts: {last_exc}")


def _translate_prompt(text: str) -> str:
    """Translate prompt to English if it's in another language.

    Flux-dev is English-first; non-English prompts are poorly followed.
    Falls back to original text on any translation error.
    """
    try:
        translated = GoogleTranslator(source="auto", target="en").translate(text)
        if translated and translated.strip() and translated.strip() != text.strip():
            logger.info(f"Prompt translated: '{text[:60]}' → '{translated[:60]}'")
        return translated or text
    except Exception as e:
        logger.warning(f"Translation failed, using original prompt: {e}")
        return text


_ASPECT_RATIOS = {
    "1:1": (1, 1),
    "3:4": (3, 4),
    "4:3": (4, 3),
    "16:9": (16, 9),
    "9:16": (9, 16),
}


def _crop_to_aspect_ratio(image_bytes: bytes, aspect_ratio: str) -> bytes:
    """Center-crop image bytes to the target aspect ratio and return JPEG bytes.

    When flux-dev receives an input image it ignores aspect_ratio and inherits
    the input dimensions. Pre-cropping forces the correct output ratio.
    """
    w_ratio, h_ratio = _ASPECT_RATIOS.get(aspect_ratio, (1, 1))
    target = w_ratio / h_ratio

    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    orig_w, orig_h = img.size
    current = orig_w / orig_h

    if abs(current - target) < 0.02:
        return image_bytes  # Already close enough

    if current > target:
        new_w = int(orig_h * target)
        left = (orig_w - new_w) // 2
        img = img.crop((left, 0, left + new_w, orig_h))
    else:
        new_h = int(orig_w / target)
        top = (orig_h - new_h) // 2
        img = img.crop((0, top, orig_w, top + new_h))

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=92)
    return buf.getvalue()


def _ensure_public_url(url: str) -> str:
    """R2 URLs (public or presigned) are reachable from external APIs — return as-is."""
    return url


# ---------------------------------------------------------------------------
# Wavespeed.ai — akool/video-face-swap
# ---------------------------------------------------------------------------

def _wavespeed_faceswap(source_images: list, target_images: list, video_url: str,
                        poll_interval: int = 10, timeout: int = 900) -> str:
    """Call wavespeed.ai akool/video-face-swap, poll until done, return output video URL.

    source_images: user face photos (faces to swap IN)
    target_images: reference faces from template (faces to be REPLACED)
    """
    if not WAVESPEED_API_KEY:
        raise RuntimeError("WAVESPEED_API_KEY is not set")

    headers = {
        "Authorization": f"Bearer {WAVESPEED_API_KEY}",
        "Content-Type": "application/json",
    }
    resp = requests.post(
        f"{WAVESPEED_BASE}/akool/video-face-swap",
        headers=headers,
        json={
            "video": video_url,
            "source_image": source_images,
            "target_image": target_images,
            "face_enhance": True,
        },
        timeout=30,
    )
    resp.raise_for_status()
    body = resp.json()
    request_id = body["data"]["id"]
    logger.info(f"Wavespeed prediction started: {request_id}")

    elapsed = 0
    while elapsed < timeout:
        time.sleep(poll_interval)
        elapsed += poll_interval

        poll = requests.get(
            f"{WAVESPEED_BASE}/predictions/{request_id}/result",
            headers={"Authorization": f"Bearer {WAVESPEED_API_KEY}"},
            timeout=30,
        )
        poll.raise_for_status()
        body = poll.json()
        inner = body.get("data", {})
        status = inner.get("status")
        logger.info(f"Wavespeed {request_id}: status={status} elapsed={elapsed}s")

        if status == "completed":
            outputs = inner.get("outputs", [])
            if not outputs:
                raise RuntimeError("Wavespeed completed but returned no outputs")
            return outputs[0]

        if status in ("failed", "canceled", "error"):
            raise RuntimeError(f"Wavespeed {status}: {inner.get('error') or body}")

    raise RuntimeError(f"Wavespeed timed out after {timeout}s")





# ---------------------------------------------------------------------------
# Replicate prediction polling
# ---------------------------------------------------------------------------

def _replicate_run_model(model_path: str, input_data: dict,
                         poll_interval: int = 5, timeout: int = 600) -> str:
    """Call an official Replicate model deployment (no version hash).

    Uses /v1/models/{owner}/{model}/predictions.
    Returns the first output URL.
    """
    owner, model = model_path.split("/", 1)
    resp = requests.post(
        f"{REPLICATE_BASE}/models/{owner}/{model}/predictions",
        headers=_json_headers(),
        json={"input": input_data},
        timeout=30,
    )
    resp.raise_for_status()
    prediction_id = resp.json()["id"]
    logger.info(f"Replicate prediction started: {prediction_id} (model={model_path})")

    elapsed = 0
    while elapsed < timeout:
        time.sleep(poll_interval)
        elapsed += poll_interval

        poll = requests.get(
            f"{REPLICATE_BASE}/predictions/{prediction_id}",
            headers=_json_headers(), timeout=30,
        )
        poll.raise_for_status()
        data = poll.json()
        status = data.get("status")
        logger.info(f"Prediction {prediction_id}: status={status} elapsed={elapsed}s")

        if status == "succeeded":
            logs = data.get("logs", "") or ""
            if "NSFW" in logs or "black image will be returned" in logs:
                raise RuntimeError("NSFW content detected by Replicate safety filter.")
            output = data.get("output")
            if output is None:
                raise RuntimeError("Replicate succeeded but returned no output")
            return output[0] if isinstance(output, list) else output

        if status in ("failed", "canceled"):
            raise RuntimeError(f"Replicate {status}: {data.get('error', 'unknown error')}")

    raise RuntimeError(f"Replicate timed out after {timeout}s")


def _replicate_run(model_version: str, input_data: dict,
                   poll_interval: int = 5, timeout: int = 600) -> str:
    """Start a prediction, poll until done, return output URL."""
    resp = requests.post(
        f"{REPLICATE_BASE}/predictions",
        headers=_json_headers(),
        json={"version": model_version, "input": input_data},
        timeout=30,
    )
    resp.raise_for_status()
    prediction_id = resp.json()["id"]
    logger.info(f"Replicate prediction started: {prediction_id}")

    elapsed = 0
    while elapsed < timeout:
        time.sleep(poll_interval)
        elapsed += poll_interval

        poll = requests.get(
            f"{REPLICATE_BASE}/predictions/{prediction_id}",
            headers=_json_headers(), timeout=30,
        )
        poll.raise_for_status()
        data = poll.json()
        status = data.get("status")
        logger.info(f"Prediction {prediction_id}: status={status} elapsed={elapsed}s")

        if status == "succeeded":
            output = data.get("output")
            if output is None:
                raise RuntimeError(
                    "Replicate succeeded but returned no output "
                    "(model may not have detected required content, e.g. no face found)"
                )
            return output[0] if isinstance(output, list) else output

        if status in ("failed", "canceled"):
            raise RuntimeError(f"Replicate {status}: {data.get('error', 'unknown error')}")

    raise RuntimeError(f"Replicate timed out after {timeout}s")


def _replicate_run_list(model_version: str, input_data: dict,
                        poll_interval: int = 5, timeout: int = 600) -> list[str]:
    """Like _replicate_run but returns all outputs as a list (for multi-output models)."""
    resp = requests.post(
        f"{REPLICATE_BASE}/predictions",
        headers=_json_headers(),
        json={"version": model_version, "input": input_data},
        timeout=30,
    )
    resp.raise_for_status()
    prediction_id = resp.json()["id"]
    logger.info(f"Replicate prediction started: {prediction_id}")

    elapsed = 0
    while elapsed < timeout:
        time.sleep(poll_interval)
        elapsed += poll_interval

        poll = requests.get(
            f"{REPLICATE_BASE}/predictions/{prediction_id}",
            headers=_json_headers(), timeout=30,
        )
        poll.raise_for_status()
        data = poll.json()
        status = data.get("status")
        logger.info(f"Prediction {prediction_id}: status={status} elapsed={elapsed}s")

        if status == "succeeded":
            logs = data.get("logs", "") or ""
            if "NSFW" in logs or "black image will be returned" in logs:
                raise RuntimeError(
                    "NSFW content detected by Replicate safety filter. "
                    "Try a different prompt or lower prompt_strength."
                )
            output = data.get("output")
            if output is None:
                raise RuntimeError("Replicate succeeded but returned no output")
            return output if isinstance(output, list) else [output]

        if status in ("failed", "canceled"):
            raise RuntimeError(f"Replicate {status}: {data.get('error', 'unknown error')}")

    raise RuntimeError(f"Replicate timed out after {timeout}s")


# ---------------------------------------------------------------------------
# Download Replicate result → upload to MinIO
# ---------------------------------------------------------------------------

def _save_to_r2(url: str, bucket: str, key: str) -> str:
    logger.info(f"Downloading result: {url[:80]}...")
    resp = requests.get(url, timeout=180, stream=True)
    resp.raise_for_status()

    suffix = os.path.splitext(key)[1] or ".bin"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        for chunk in resp.iter_content(chunk_size=8192):
            tmp.write(chunk)
        tmp_path = tmp.name

    try:
        get_client().upload_file(tmp_path, bucket, key)
        logger.info(f"Saved to R2: {bucket}/{key}")
    finally:
        os.unlink(tmp_path)

    return key


# ---------------------------------------------------------------------------
# URL helpers
# ---------------------------------------------------------------------------

def _public_url(bucket: str, path: str) -> str:
    from services.storage import get_signed_url
    if bucket == storage_settings.r2_bucket_templates:
        return f"{settings.r2_public_url_templates}/{path}"
    if bucket == storage_settings.r2_bucket_results and settings.r2_public_url_results:
        return f"{settings.r2_public_url_results.rstrip('/')}/{path}"
    return get_signed_url(bucket, path, expires=86400)


def _resolve_photo(url: str) -> str:
    """Ensure photo URL is accessible from Replicate (upload if localhost)."""
    return _ensure_public_url(url)


def _primary_photo(options: dict) -> str:
    """Return the primary user photo URL, resolved for Replicate access."""
    raw = options.get("photo_url") or options.get("photo_url_male")
    if raw:
        return _resolve_photo(raw)
    path = options.get("photo_1_path")
    if path:
        return _resolve_photo(_public_url(storage_settings.r2_bucket_uploads, path))
    raise RuntimeError("No primary photo found in job options (expected photo_url, photo_url_male, or photo_1_path)")


def _secondary_photo(options: dict) -> str | None:
    """Return the secondary user photo URL if present, resolved for Replicate access."""
    raw = options.get("photo_url_2") or options.get("photo_url_female")
    if raw:
        return _resolve_photo(raw)
    path = options.get("photo_2_path")
    if path:
        return _resolve_photo(_public_url(storage_settings.r2_bucket_uploads, path))
    return None


# ---------------------------------------------------------------------------
# Job handlers
# ---------------------------------------------------------------------------

def _run_face_swap(job_id: str, job, db) -> str:
    """Face swap: replace face(s) on template VIDEO via wavespeed.ai akool/video-face-swap.

    source_image = user face photo(s) — swapped INTO the video.
    target_image = template thumbnail — reference of the face being REPLACED.

    1-face: single API call.
    2-face: two sequential calls — pass 1 swaps the primary face on the original
    template; pass 2 swaps the secondary face on the result of pass 1.
    """
    options = job.options or {}

    # Resolve template VIDEO URL
    raw_template = options.get("template_video_url") or options.get("video_url")
    template_obj = db.query(Template).filter(Template.id == job.template_id).first()
    if not raw_template and template_obj:
        if template_obj.video_path:
            raw_template = _public_url(storage_settings.r2_bucket_templates, template_obj.video_path)
        elif template_obj.thumb_path:
            raw_template = _public_url(storage_settings.r2_bucket_templates, template_obj.thumb_path)

    if not raw_template:
        raise RuntimeError("Face swap: no template video available (set video_path on template)")

    # Template thumbnail as target face reference (the face to be replaced)
    if not template_obj or not template_obj.thumb_path:
        raise RuntimeError("Face swap: template has no thumbnail — required as target_image for wavespeed")
    target_face_url = _public_url(storage_settings.r2_bucket_templates, template_obj.thumb_path)

    # Resolve user photos
    male_url   = options.get("photo_url") or options.get("photo_url_male")
    female_url = options.get("photo_url_female")
    if not male_url and not female_url:
        p1 = options.get("photo_1_path")
        p2 = options.get("photo_2_path")
        if p1:
            male_url = _public_url(storage_settings.r2_bucket_uploads, p1)
        if p2:
            female_url = _public_url(storage_settings.r2_bucket_uploads, p2)

    if not male_url and not female_url:
        raise RuntimeError("Face swap: no user photo provided")

    result_url = None

    # Pass 1 — primary (male) face on original template
    if male_url:
        logger.info(f"Job {job_id}: wavespeed face swap pass 1 (primary/male)")
        result_url = _wavespeed_faceswap(
            source_images=[_ensure_public_url(male_url)],
            target_images=[target_face_url],
            video_url=raw_template,
        )

    # Pass 2 — secondary (female) face on the result of pass 1 (or original if male-only skipped)
    if female_url:
        logger.info(f"Job {job_id}: wavespeed face swap pass 2 (secondary/female)")
        base_video = result_url if result_url else raw_template
        result_url = _wavespeed_faceswap(
            source_images=[_ensure_public_url(female_url)],
            target_images=[target_face_url],
            video_url=base_video,
        )

    logger.info(f"Job {job_id} face swap done → {result_url[:60]}...")
    return result_url


def _run_reference_video(job_id: str, options: dict, quality: str, duration: int, db) -> str:
    """Reference mode: generate video from prompt + reference photo via minimax/video-01-live."""
    photo_url = _primary_photo(options)
    prompt    = options.get("prompt", "A cinematic short video clip")

    input_data = {
        "prompt":            prompt,
        "first_frame_image": photo_url,
        "duration":          min(duration, 5),
    }

    photo2 = _secondary_photo(options)
    if photo2:
        input_data["subject_reference"] = photo2

    return _replicate_run(MODEL_REF_VIDEO, input_data, poll_interval=8, timeout=300)


_VIDU_QUALITY_MAP = {
    "standard": "720p",
    "high":     "1080p",
    "premium":  "1080p",  # vidu max is 1080p
}


def _run_interpolation(job_id: str, options: dict, quality: str, duration: int, db) -> str:
    """Start & End mode: generate video via vidu/q3-pro.

    Supports start-only (image-to-video) and start+end (interpolation) modes.
    quality: standard→720p, high/premium→1080p.
    duration: passed directly (1–16s supported by vidu).
    """
    raw_start = options.get("start_frame_url") or options.get("photo_url") or options.get("photo_url_male")
    if not raw_start:
        path = options.get("photo_1_path")
        raw_start = _public_url(storage_settings.r2_bucket_uploads, path) if path else None
    if not raw_start:
        raise RuntimeError("Interpolation mode requires start_frame_url or photo_url in options")

    start_url = _ensure_public_url(raw_start)
    prompt = options.get("prompt", "A smooth cinematic video")
    resolution = _VIDU_QUALITY_MAP.get(quality, "720p")
    duration_clamped = max(1, min(16, duration))

    input_data: dict = {
        "prompt":      prompt,
        "start_image": start_url,
        "duration":    duration_clamped,
        "resolution":  resolution,
        "audio":       False,
    }

    raw_end = options.get("end_frame_url") or options.get("photo_url_2")
    if not raw_end:
        path2 = options.get("photo_2_path")
        raw_end = _public_url(storage_settings.r2_bucket_uploads, path2) if path2 else None
    if raw_end:
        input_data["end_image"] = _ensure_public_url(raw_end)
        logger.info(f"Job {job_id}: vidu start+end mode duration={duration_clamped}s resolution={resolution}")
    else:
        logger.info(f"Job {job_id}: vidu start-only mode duration={duration_clamped}s resolution={resolution}")

    return _replicate_run_model(MODEL_INTERPOLATE, input_data, poll_interval=5, timeout=600)


def _run_create_image(job_id: str, job, options: dict, db) -> None:
    """Create Image: instruction-based photo editing via flux-kontext-pro.

    Generates `count` variants sequentially with the same prompt.
    Aspect ratio handled natively by the model — no pre-crop needed.
    """
    prompt = options.get("prompt", "")
    aspect = options.get("aspect_ratio", "1:1")
    count  = max(1, min(4, int(options.get("count", 1))))

    _allowed_aspects = {"1:1", "3:4", "4:3", "16:9", "9:16"}
    if aspect not in _allowed_aspects:
        aspect = "1:1"

    prompt = _translate_prompt(prompt)
    full_prompt = (
        f"Keep the person's face, skin tone, and identity exactly as in the original photo. "
        f"{prompt}"
    )
    logger.info(f"Job {job_id}: prompt='{full_prompt[:120]}' aspect={aspect} count={count}")

    raw_photo = options.get("photo_url") or options.get("photo_1_path")
    if not raw_photo:
        raise RuntimeError("Create Image mode requires a photo")

    if raw_photo.startswith("http"):
        photo_bytes = requests.get(raw_photo, timeout=60).content
    else:
        photo_bytes = download_file(storage_settings.r2_bucket_uploads, raw_photo)

    logger.info(f"Job {job_id}: uploading photo to Replicate Files...")
    photo_url = _upload_to_replicate(photo_bytes, "photo.jpg")

    bucket = storage_settings.r2_bucket_results
    public_urls: list[str] = []

    for i in range(count):
        logger.info(f"Job {job_id}: generating variant {i + 1}/{count}...")
        output_url = _replicate_run_model(
            MODEL_IMAGE,
            {
                "prompt":           full_prompt,
                "input_image":      photo_url,
                "aspect_ratio":     aspect,
                "output_format":    "png",
                "safety_tolerance": 5,
            },
            poll_interval=3,
            timeout=300,
        )

        resp = requests.get(output_url, timeout=60)
        resp.raise_for_status()
        img_bytes = resp.content
        logger.info(f"Job {job_id}: variant {i + 1} downloaded ({len(img_bytes) // 1024} KB)")

        key = f"{job_id}/image_{i + 1}.png"
        get_client().put_object(
            Bucket=bucket,
            Key=key,
            Body=img_bytes,
            ContentType="image/png",
        )
        public_urls.append(_public_url(bucket, key))
        logger.info(f"Saved variant {i + 1}: {key}")

        # Update progress incrementally so client sees activity
        db.expire(job)
        job = db.query(Job).filter(Job.id == job_id).first()
        job.progress = int(20 + 80 * (i + 1) / count)
        db.commit()

    db.expire(job)
    job = db.query(Job).filter(Job.id == job_id).first()
    job.result_path  = public_urls[0]  # first variant for backward compat
    job.thumb_url    = None
    job.preview_url  = None
    job.original_url = None

    updated_options = dict(options)
    updated_options["result_image_urls"] = public_urls
    job.options  = updated_options
    job.status   = "done"
    job.progress = 100
    db.commit()
    logger.info(f"Job {job_id}: image job done, {len(public_urls)} variant(s) saved")


# ---------------------------------------------------------------------------
# Admin config
# ---------------------------------------------------------------------------

def get_stub_settings(db):
    def cfg(key, default):
        row = db.query(AdminConfig).filter(AdminConfig.key == key).first()
        return row.value if row else default
    stub_mode    = cfg("STUB_MODE", "true").lower() == "true"
    latency_ms   = int(cfg("STUB_LATENCY_MS", str(settings.stub_latency_ms)))
    success_rate = float(cfg("STUB_SUCCESS_RATE", str(settings.stub_success_rate)))
    return stub_mode, latency_ms, success_rate


# ---------------------------------------------------------------------------
# Publish to postproc
# ---------------------------------------------------------------------------

def _publish_postproc(job_id: str):
    params  = pika.URLParameters(settings.rabbitmq_url)
    conn    = pika.BlockingConnection(params)
    channel = conn.channel()
    channel.queue_declare(queue=QUEUE_POSTPROC, durable=True)
    channel.basic_publish(
        exchange="",
        routing_key=QUEUE_POSTPROC,
        body=json.dumps({"job_id": job_id}),
        properties=pika.BasicProperties(delivery_mode=2),
    )
    conn.close()


def _refund(db, job):
    if job.gems_cost and job.gems_cost > 0:
        user = db.query(User).filter(User.id == job.user_id).first()
        if user:
            refund_gems(db, user, job.gems_cost, str(job.id))


# ---------------------------------------------------------------------------
# Main process_job
# ---------------------------------------------------------------------------

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

        stub_mode, latency_ms, success_rate = get_stub_settings(db)
        job_type    = getattr(job, "job_type", "template") or "template"
        options     = job.options or {}
        quality     = job.quality or "standard"
        duration    = job.duration_seconds or 5
        custom_mode = options.get("mode", "reference")

        logger.info(f"Job {job_id}: type={job_type} custom_mode={custom_mode} stub={stub_mode}")

        job.progress = 10
        db.commit()

        # ── STUB MODE ────────────────────────────────────────────────────
        if stub_mode:
            time.sleep(latency_ms / 1000.0)
            job.progress = 90
            db.commit()

            if random.random() < success_rate:
                fmt     = options.get("format", "mp4") if job_type in ("custom", "image") else "mp4"
                dst_key = f"results/{job_id}/output.{fmt}"
                copy_object(
                    storage_settings.r2_bucket_templates,
                    "mock_result.mp4",
                    storage_settings.r2_bucket_results,
                    dst_key,
                )
                job.result_path = dst_key
                job.status      = "processing"
                db.commit()
                logger.info(f"Job {job_id} stub OK → postproc")
                _publish_postproc(job_id)
            else:
                job.status = "failed"
                job.error  = "Stub failure simulation"
                db.commit()
                _refund(db, job)
            return

        # ── REAL AI MODE ─────────────────────────────────────────────────
        if job_type == "template" and not WAVESPEED_API_KEY:
            raise RuntimeError("WAVESPEED_API_KEY is not set")
        if job_type != "template" and not REPLICATE_API_TOKEN:
            raise RuntimeError("REPLICATE_API_TOKEN is not set")

        job.progress = 20
        db.commit()

        if job_type == "template":
            result_key = _run_face_swap(job_id, job, db)

        elif job_type == "image":
            _run_create_image(job_id, job, options, db)
            return  # Fully handled inside: status=done committed, no postproc needed

        elif job_type == "custom":
            if custom_mode == "interpolation":
                result_key = _run_interpolation(job_id, options, quality, duration, db)
            else:
                result_key = _run_reference_video(job_id, options, quality, duration, db)

        else:
            raise RuntimeError(f"Unknown job_type: {job_type}")

        job.result_path = result_key
        job.status      = "processing"
        job.progress    = 90
        db.commit()
        logger.info(f"Job {job_id} AI done → postproc")
        _publish_postproc(job_id)

    except Exception as e:
        logger.error(f"Error in generator job {job_id}: {e}")
        db.rollback()
        try:
            job = db.query(Job).filter(Job.id == job_id).first()
            if job:
                job.status = "failed"
                job.error  = str(e)[:400]
                db.commit()
                _refund(db, job)
        except Exception as inner:
            logger.error(f"Failed to mark job failed: {inner}")
    finally:
        db.close()


def callback(ch, method, properties, body):
    data   = json.loads(body)
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
            params.heartbeat = 600  # keep connection alive during long Replicate calls
            conn    = pika.BlockingConnection(params)
            channel = conn.channel()
            channel.queue_declare(queue=QUEUE_GENERATOR, durable=True)
            channel.queue_declare(queue=QUEUE_DLQ,       durable=True)
            channel.basic_qos(prefetch_count=1)
            channel.basic_consume(queue=QUEUE_GENERATOR, on_message_callback=callback)
            logger.info(f"Waiting for messages on {QUEUE_GENERATOR}")
            channel.start_consuming()
        except Exception as e:
            logger.error(f"Connection error: {e}, retrying in 5s")
            time.sleep(5)


if __name__ == "__main__":
    main()
