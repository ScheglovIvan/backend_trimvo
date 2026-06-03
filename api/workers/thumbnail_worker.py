"""Thumbnail worker: generates thumb/preview/gif for templates via FFmpeg."""
import sys
import os
import json
import time
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pika

from core.config import get_settings
from core.database import SessionLocal
from models.template import Template
from services import storage as stor
from services import media_processor
from services.queue import QUEUE_THUMBNAIL

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("thumbnail_worker")

settings = get_settings()


def process_template(template_id: str, skip_thumb: bool = False):
    db = SessionLocal()
    try:
        t = db.query(Template).filter(Template.id == template_id).first()
        if not t:
            logger.error(f"Template {template_id} not found")
            return

        if not t.video_path:
            logger.warning(f"Template {template_id} has no video_path, skipping")
            t.status = "failed"
            db.commit()
            return

        logger.info(f"Processing template {template_id}: {t.video_path}")
        t.status = "processing"
        db.commit()

        bucket = stor.settings.r2_bucket_templates
        video_bytes = stor.download_file(bucket, t.video_path)

        base_key = f"templates/{t.id}"
        paths = media_processor.process_video(video_bytes, base_key, bucket)

        for field, val in paths.items():
            if field == "thumb_path" and skip_thumb:
                continue
            setattr(t, field, val)

        t.status = "ready"
        db.commit()
        logger.info(f"Template {template_id} done: {paths}")

    except Exception as e:
        logger.error(f"Error processing template {template_id}: {e}")
        try:
            t = db.query(Template).filter(Template.id == template_id).first()
            if t:
                t.status = "failed"
                db.commit()
        except Exception:
            pass
    finally:
        db.close()


def callback(ch, method, properties, body):
    data = json.loads(body)
    template_id = data.get("template_id")
    skip_thumb = data.get("skip_thumb", False)
    logger.info(f"Received template_id={template_id} skip_thumb={skip_thumb}")
    try:
        process_template(template_id, skip_thumb=skip_thumb)
        ch.basic_ack(delivery_tag=method.delivery_tag)
    except Exception as e:
        logger.error(f"Unhandled error: {e}")
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)


def main():
    stor.ensure_buckets()
    while True:
        try:
            params = pika.URLParameters(settings.rabbitmq_url)
            conn = pika.BlockingConnection(params)
            channel = conn.channel()
            channel.queue_declare(queue=QUEUE_THUMBNAIL, durable=True)
            channel.basic_qos(prefetch_count=1)
            channel.basic_consume(queue=QUEUE_THUMBNAIL, on_message_callback=callback)
            logger.info(f"Waiting for messages on {QUEUE_THUMBNAIL}")
            channel.start_consuming()
        except Exception as e:
            logger.error(f"Connection error: {e}, retrying in 5s")
            time.sleep(5)


if __name__ == "__main__":
    main()
