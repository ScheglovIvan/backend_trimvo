from fastapi import APIRouter, Depends, BackgroundTasks
from sqlalchemy.orm import Session
from core.database import get_db
from core.dependencies import get_admin_user
from models.job import Job
from models.admin_config import AdminConfig
from models.user import User
from services.queue import publish_job

router = APIRouter(prefix="/v1/admin/stub", tags=["admin-stub"])


@router.post("/test-job")
def create_test_job(
    db: Session = Depends(get_db),
    admin: User = Depends(get_admin_user),
):
    from models.template import Template
    template = db.query(Template).first()
    if not template:
        return {"error": "No templates found. Run seed first."}

    job = Job(
        user_id=admin.id,
        template_id=template.id,
        options={"test": True},
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    try:
        publish_job(str(job.id))
    except Exception as e:
        job.status = "failed"
        job.error = f"Queue error: {str(e)}"
        db.commit()

    return {"job_id": str(job.id), "status": job.status}
