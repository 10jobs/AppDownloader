from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from .auth import bootstrap_admin_if_needed
from .config import PROJECT_ROOT, settings
from .db import SessionLocal, init_db
from .routes.admin import router as admin_router
from .routes.public import router as public_router
from .utils import ensure_dir


app = FastAPI(title=settings.app_name)


app.add_middleware(
    SessionMiddleware,
    secret_key=settings.secret_key,
    max_age=settings.session_max_age_seconds,
    same_site="lax",
    https_only=False,
)


def _ensure_sqlite_dir() -> None:
    if settings.database_url.startswith("sqlite:///"):
        db_file = settings.database_url.replace("sqlite:///", "")
        db_path = Path(db_file)
        if not db_path.is_absolute():
            db_path = PROJECT_ROOT / db_path
        ensure_dir(db_path.parent)


@app.on_event("startup")
def on_startup() -> None:
    _ensure_sqlite_dir()
    ensure_dir(settings.files_root)
    ensure_dir(settings.tmp_root)
    ensure_dir(settings.static_dir)
    init_db()

    db = SessionLocal()
    try:
        bootstrap_admin_if_needed(db)
    finally:
        db.close()


app.mount("/static", StaticFiles(directory=str(settings.static_dir)), name="static")
app.include_router(public_router)
app.include_router(admin_router)
