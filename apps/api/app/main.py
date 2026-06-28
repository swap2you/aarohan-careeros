from contextlib import asynccontextmanager

from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal, engine
from app.routers import (
    applications,
    auth,
    career_vault,
    companies,
    connectors,
    consulting,
    documents,
    integrations,
    interviews,
    jobs,
    matching,
    ops,
    validation,
    workflows,
)
from app.routers.auth import bootstrap_admin_from_env
from app.services.career_vault import sync_evidence_registry


def run_migrations() -> None:
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", settings.database_url)
    command.upgrade(cfg, "head")


@asynccontextmanager
async def lifespan(_: FastAPI):
    if settings.database_url:
        run_migrations()
        db: Session = SessionLocal()
        try:
            bootstrap_admin_from_env(db)
            sync_evidence_registry(db)
        finally:
            db.close()
    yield


app = FastAPI(title="Aarohan CareerOS API", version="1.1.0-local-first", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api")
app.include_router(jobs.router, prefix="/api")
app.include_router(matching.router, prefix="/api")
app.include_router(connectors.router, prefix="/api")
app.include_router(companies.router, prefix="/api")
app.include_router(applications.router, prefix="/api")
app.include_router(interviews.router, prefix="/api")
app.include_router(consulting.router, prefix="/api")
app.include_router(career_vault.router, prefix="/api")
app.include_router(documents.router, prefix="/api")
app.include_router(ops.router, prefix="/api")
app.include_router(integrations.router, prefix="/api")
app.include_router(workflows.router, prefix="/api")
app.include_router(validation.router, prefix="/api")


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "api", "scheduling_enabled": settings.scheduling_enabled}


@app.get("/ready")
def ready() -> dict:
    db: Session = SessionLocal()
    try:
        db.execute(text("SELECT 1"))
        return {"status": "ready"}
    except Exception as exc:
        return {"status": "not_ready", "detail": str(exc)}
    finally:
        db.close()
