from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session, joinedload

from ..db import get_db
from ..models import ApkFile, ApkVersion, AppType, Notice
from ..ui import templates
from ..utils import get_client_ip, write_download_log


router = APIRouter()


@router.get("/")
def home(request: Request, db: Session = Depends(get_db)):
    notices = (
        db.query(Notice)
        .filter(Notice.is_visible.is_(True))
        .order_by(Notice.is_pinned.desc(), Notice.created_at.desc())
        .all()
    )

    app_types = (
        db.query(AppType)
        .filter(AppType.is_active.is_(True))
        .order_by(AppType.name.asc())
        .all()
    )

    latest_map: dict[int, ApkVersion | None] = {}
    for app_type in app_types:
        latest_version = (
            db.query(ApkVersion)
            .options(joinedload(ApkVersion.current_file))
            .filter(ApkVersion.app_type_id == app_type.id)
            .order_by(ApkVersion.created_at.desc())
            .first()
        )
        latest_map[app_type.id] = latest_version

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "notices": notices,
            "app_types": app_types,
            "latest_map": latest_map,
        },
    )


@router.get("/apps/{slug}")
def app_detail(slug: str, request: Request, db: Session = Depends(get_db)):
    app_type = (
        db.query(AppType)
        .filter(AppType.slug == slug, AppType.is_active.is_(True))
        .first()
    )
    if not app_type:
        raise HTTPException(status_code=404, detail="App type not found")

    versions = (
        db.query(ApkVersion)
        .options(joinedload(ApkVersion.current_file))
        .filter(ApkVersion.app_type_id == app_type.id)
        .order_by(ApkVersion.created_at.desc())
        .all()
    )

    return templates.TemplateResponse(
        "app_detail.html",
        {
            "request": request,
            "app_type": app_type,
            "versions": versions,
        },
    )


@router.get("/download/{file_id}")
def download(file_id: int, request: Request, db: Session = Depends(get_db)):
    apk_file = (
        db.query(ApkFile)
        .options(joinedload(ApkFile.apk_version).joinedload(ApkVersion.app_type))
        .filter(ApkFile.id == file_id)
        .first()
    )
    if not apk_file:
        raise HTTPException(status_code=404, detail="File not found")

    path = Path(apk_file.stored_path)
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="Stored file not found")

    app_type = apk_file.apk_version.app_type
    write_download_log(
        db,
        apk_file_id=apk_file.id,
        app_type_id=app_type.id,
        version=apk_file.apk_version.version,
        ip=get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )

    return FileResponse(
        path=path,
        filename=apk_file.original_filename,
        media_type="application/vnd.android.package-archive",
    )
