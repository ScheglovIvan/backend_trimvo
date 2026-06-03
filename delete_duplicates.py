#!/usr/bin/env python3
"""
Delete duplicate templates (by title) and their files from MinIO.
Keeps the oldest (first uploaded) template for each title.
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "api"))

from core.database import SessionLocal
from core.config import get_settings
from models.template import Template
from services.storage import get_client
from minio.error import S3Error

settings = get_settings()


def delete_minio_folder(client, bucket: str, prefix: str):
    """Delete all objects under a prefix in MinIO."""
    try:
        objects = client.list_objects(bucket, prefix=prefix, recursive=True)
        deleted = 0
        for obj in objects:
            try:
                client.remove_object(bucket, obj.object_name)
                print(f"    Deleted file: {obj.object_name}")
                deleted += 1
            except S3Error as e:
                print(f"    Failed to delete {obj.object_name}: {e}")
        return deleted
    except Exception as e:
        print(f"    Error listing {prefix}: {e}")
        return 0


def main():
    db = SessionLocal()
    client = get_client()
    bucket = settings.minio_bucket_templates

    try:
        # Find all duplicates — keep oldest (min created_at) per title
        all_templates = db.query(Template).order_by(Template.created_at.asc()).all()

        seen_titles = {}
        to_delete = []

        for t in all_templates:
            if t.title not in seen_titles:
                seen_titles[t.title] = t.id
            else:
                to_delete.append(t)

        if not to_delete:
            print("No duplicates found.")
            return

        print(f"Found {len(to_delete)} duplicates to delete:\n")

        total_files_deleted = 0
        total_templates_deleted = 0

        for t in to_delete:
            print(f"  Deleting duplicate: '{t.title}' (id={t.id}, created={t.created_at})")

            # Delete files from MinIO
            prefix = f"templates/{t.id}/"
            files_deleted = delete_minio_folder(client, bucket, prefix)
            total_files_deleted += files_deleted
            print(f"    Deleted {files_deleted} files from MinIO")

            # Delete from DB (cascade will handle category_templates, reports)
            db.delete(t)
            total_templates_deleted += 1

        db.commit()

        print(f"\n{'='*50}")
        print(f"Done!")
        print(f"  Templates deleted: {total_templates_deleted}")
        print(f"  Files deleted from MinIO: {total_files_deleted}")

        # Verification
        from sqlalchemy import text
        print(f"\nVerification:")
        result = db.execute(text(
            "SELECT title, COUNT(*) as cnt FROM templates "
            "GROUP BY title HAVING COUNT(*) > 1 ORDER BY cnt DESC"
        )).fetchall()

        if result:
            print(f"  Still has duplicates:")
            for row in result:
                print(f"    '{row[0]}': {row[1]} copies")
        else:
            print(f"  No duplicates remaining!")

        total = db.execute(text("SELECT COUNT(*) FROM templates")).scalar()
        print(f"  Total templates remaining: {total}")

    finally:
        db.close()


if __name__ == "__main__":
    main()
