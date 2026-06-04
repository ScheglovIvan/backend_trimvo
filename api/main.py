from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from routers import auth, templates, jobs, payments, reports, gem_packages, subscription_plans, categories, me, uploads
from routers import config as public_config
from core.config import get_settings
from routers.admin import templates as admin_templates
from routers.admin import categories as admin_categories
from routers.admin import trends as admin_trends
from routers.admin import config as admin_config
from routers.admin import stub as admin_stub
from routers.admin import jobs as admin_jobs
from routers.admin import audit as admin_audit
from routers.admin import reports as admin_reports
from routers.admin import gem_packages as admin_gem_packages
from routers.admin import subscription_plans as admin_subscription_plans
from routers.admin import pricing as admin_pricing
from routers.admin import users as admin_users
from routers.admin import stats as admin_stats


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        from services.storage import ensure_buckets, upload_mock_video
        ensure_buckets()
        upload_mock_video()
    except Exception as e:
        print(f"Storage init warning: {e}")
    yield


app = FastAPI(title="Trimvo API", version="1.0.0", lifespan=lifespan)

_settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _settings.cors_origins.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(templates.router)
app.include_router(jobs.router)
app.include_router(payments.router)
app.include_router(reports.router)
app.include_router(gem_packages.router)
app.include_router(subscription_plans.router)
app.include_router(categories.router)
app.include_router(me.router)
app.include_router(uploads.router)
app.include_router(public_config.router)
app.include_router(admin_templates.router)
app.include_router(admin_categories.router)
app.include_router(admin_trends.router)
app.include_router(admin_config.router)
app.include_router(admin_stub.router)
app.include_router(admin_jobs.router)
app.include_router(admin_audit.router)
app.include_router(admin_reports.router)
app.include_router(admin_gem_packages.router)
app.include_router(admin_subscription_plans.router)
app.include_router(admin_pricing.router)
app.include_router(admin_users.router)
app.include_router(admin_stats.router)


@app.get("/health")
def health():
    return {"status": "ok"}
