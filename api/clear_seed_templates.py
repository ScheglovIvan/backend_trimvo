import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from core.database import SessionLocal
from models.template import Template

db = SessionLocal()

# Get IDs of templates to delete
no_video_ids = [t.id for t in db.query(Template).filter(Template.video_path.is_(None)).all()]
broken_ids = [t.id for t in db.query(Template).filter(Template.video_path.like("%/None/%")).all()]
all_ids = no_video_ids + broken_ids

if all_ids:
    # Delete FK-constrained child records first
    from sqlalchemy import text
    for tid in all_ids:
        db.execute(text("DELETE FROM reports WHERE template_id = :tid"), {"tid": tid})
        db.execute(text("DELETE FROM trends WHERE template_id = :tid"), {"tid": tid})
        db.execute(text("DELETE FROM category_templates WHERE template_id = :tid"), {"tid": tid})
    db.commit()

    deleted = db.query(Template).filter(Template.id.in_(all_ids)).delete(synchronize_session=False)
    db.commit()
    print(f"Deleted {deleted} templates (no video / broken path)")
else:
    print("No templates to delete")

remaining = db.query(Template).count()
print(f"Remaining templates: {remaining}")
db.close()
