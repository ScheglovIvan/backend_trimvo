import json
import pika
from core.config import get_settings

settings = get_settings()

QUEUE_PREPROC = "jobs.preproc"
QUEUE_GENERATOR = "jobs.generator"
QUEUE_POSTPROC = "jobs.postproc"
QUEUE_DLQ = "jobs.dlq"
QUEUE_THUMBNAIL = "templates.thumbnail"


def _get_connection():
    params = pika.URLParameters(settings.rabbitmq_url)
    return pika.BlockingConnection(params)


def publish(queue: str, message: dict):
    conn = _get_connection()
    channel = conn.channel()
    channel.queue_declare(queue=queue, durable=True)
    channel.basic_publish(
        exchange="",
        routing_key=queue,
        body=json.dumps(message),
        properties=pika.BasicProperties(delivery_mode=2),
    )
    conn.close()


def publish_job(job_id: str, queue: str = QUEUE_PREPROC):
    publish(queue, {"job_id": job_id})
