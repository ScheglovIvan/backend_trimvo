import io
import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from core.config import get_settings

settings = get_settings()

_client = None


def get_client():
    global _client
    if _client is None:
        _client = boto3.client(
            "s3",
            endpoint_url=settings.r2_endpoint,
            aws_access_key_id=settings.r2_access_key_id,
            aws_secret_access_key=settings.r2_secret_access_key,
            config=Config(signature_version="s3v4"),
            region_name="auto",
        )
    return _client


def ensure_buckets():
    client = get_client()
    for bucket in [
        settings.r2_bucket_uploads,
        settings.r2_bucket_results,
        settings.r2_bucket_templates,
    ]:
        try:
            client.head_bucket(Bucket=bucket)
            print(f"Bucket OK: {bucket}")
        except ClientError as e:
            code = e.response["Error"]["Code"]
            if code in ("404", "NoSuchBucket"):
                print(f"WARNING: Bucket not found: {bucket} — create it in Cloudflare R2 dashboard")
            else:
                print(f"Bucket check warning for {bucket}: {e}")


def upload_mock_video():
    client = get_client()
    bucket = settings.r2_bucket_templates
    key = "mock_result.mp4"
    try:
        client.head_object(Bucket=bucket, Key=key)
    except ClientError:
        mp4_bytes = bytes([
            0x00, 0x00, 0x00, 0x20, 0x66, 0x74, 0x79, 0x70,
            0x69, 0x73, 0x6F, 0x6D, 0x00, 0x00, 0x02, 0x00,
            0x69, 0x73, 0x6F, 0x6D, 0x69, 0x73, 0x6F, 0x32,
            0x61, 0x76, 0x63, 0x31, 0x6D, 0x70, 0x34, 0x31,
        ])
        client.put_object(
            Bucket=bucket,
            Key=key,
            Body=mp4_bytes,
            ContentType="video/mp4",
        )
        print(f"Uploaded mock video: {bucket}/{key}")


def upload_file(bucket: str, key: str, file_bytes: bytes, content_type: str) -> str:
    get_client().put_object(
        Bucket=bucket,
        Key=key,
        Body=file_bytes,
        ContentType=content_type,
    )
    return f"/{bucket}/{key}"


def get_signed_url(bucket: str, key: str, expires: int = 604800) -> str:
    return get_client().generate_presigned_url(
        "get_object",
        Params={"Bucket": bucket, "Key": key},
        ExpiresIn=expires,
    )


def download_file(bucket: str, key: str) -> bytes:
    response = get_client().get_object(Bucket=bucket, Key=key)
    return response["Body"].read()


def copy_object(src_bucket: str, src_key: str, dst_bucket: str, dst_key: str):
    get_client().copy_object(
        CopySource={"Bucket": src_bucket, "Key": src_key},
        Bucket=dst_bucket,
        Key=dst_key,
    )
