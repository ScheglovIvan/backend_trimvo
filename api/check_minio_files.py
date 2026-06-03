"""
Проверяет, существуют ли физически файлы thumb/preview/gif в MinIO
для каждого шаблона, у которого путь прописан в БД.
Запуск:
  docker compose exec api python check_minio_files.py
"""
from minio.error import S3Error

from core.database import SessionLocal
from core.config import get_settings
from models.template import Template
from services.storage import get_client

settings = get_settings()


def _exists(bucket: str, path: str) -> bool:
    if not path:
        return False
    try:
        get_client().stat_object(bucket, path.lstrip("/"))
        return True
    except S3Error:
        return False


def main():
    db = SessionLocal()
    bucket = settings.minio_bucket_templates
    try:
        templates = db.query(Template).all()
        print(f"Проверка файлов в bucket '{bucket}' для {len(templates)} шаблонов\n")

        missing = []
        for t in templates:
            checks = {
                "thumb": t.thumb_path,
                "preview": t.preview_path,
                "gif": t.gif_path,
            }
            absent = [
                name for name, path in checks.items()
                if path and not _exists(bucket, path)
            ]
            if absent:
                missing.append((t, absent))

        if not missing:
            print("✅ Все файлы на месте в MinIO")
        else:
            print(f"⚠️  Шаблоны с отсутствующими файлами: {len(missing)}\n")
            for t, absent in missing:
                print(f"  id={t.id} | {t.title}")
                print(f"    отсутствуют файлы: {', '.join(absent)}")
                print()
    finally:
        db.close()


if __name__ == "__main__":
    main()
