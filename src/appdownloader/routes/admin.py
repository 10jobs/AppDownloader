from __future__ import annotations

import time
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import RedirectResponse
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from ..auth import authenticate_admin, get_session_admin
from ..config import settings
from ..db import get_db
from ..models import AdminUser, ApkFile, ApkVersion, AppType, Notice
from ..ui import templates
from ..utils import ensure_dir, get_client_ip, sha256_bytes, slugify_name, write_audit_log


router = APIRouter(prefix="/admin", tags=["admin"])

ALLOWED_CONTENT_TYPES = {
    "application/vnd.android.package-archive",
    "application/octet-stream",
    "application/zip",
}


def admin_or_redirect(request: Request, db: Session) -> AdminUser | RedirectResponse:
    admin = get_session_admin(db, request.session)
    if not admin:
        request.session.clear()
        return RedirectResponse(url="/admin/login", status_code=303)
    return admin


def render_upload_page(
    request: Request,
    db: Session,
    *,
    message: str | None = None,
    error: str | None = None,
    overwrite_prompt: dict | None = None,
):
    app_types = (
        db.query(AppType)
        .filter(AppType.is_active.is_(True))
        .order_by(AppType.name.asc())
        .all()
    )
    versions = (
        db.query(ApkVersion)
        .options(joinedload(ApkVersion.app_type), joinedload(ApkVersion.current_file))
        .order_by(ApkVersion.updated_at.desc())
        .limit(20)
        .all()
    )
    return templates.TemplateResponse(
        "admin_upload.html",
        {
            "request": request,
            "app_types": app_types,
            "message": message,
            "error": error,
            "overwrite_prompt": overwrite_prompt,
            "versions": versions,
        },
    )


def store_file_bytes(base_dir: Path, app_slug: str, version: str, revision_no: int, filename: str, data: bytes) -> str:
    safe_name = "".join(c if c.isalnum() or c in {"-", "_", "."} else "_" for c in filename)
    target_dir = base_dir / app_slug / version
    ensure_dir(target_dir)
    target_path = target_dir / f"r{revision_no}_{int(time.time())}_{safe_name}"
    target_path.write_bytes(data)
    return str(target_path)


def remove_apk_version_files(version: ApkVersion) -> tuple[int, int]:
    removed = 0
    failed = 0
    for file_item in version.files:
        file_path = Path(file_item.stored_path)
        try:
            file_path.unlink(missing_ok=True)
            removed += 1
        except OSError:
            failed += 1

    return removed, failed


@router.get("/login")
def admin_login(request: Request, db: Session = Depends(get_db)):
    current = get_session_admin(db, request.session)
    if current:
        return RedirectResponse(url="/admin", status_code=303)
    return templates.TemplateResponse("admin_login.html", {"request": request, "error": None})


@router.post("/login")
def admin_login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    admin = authenticate_admin(db, username.strip(), password)
    if not admin:
        return templates.TemplateResponse(
            "admin_login.html",
            {"request": request, "error": "아이디 또는 비밀번호가 올바르지 않습니다."},
            status_code=401,
        )

    now_ts = int(time.time())
    request.session["admin_user_id"] = admin.id
    request.session["last_seen"] = now_ts

    write_audit_log(
        db,
        actor_type="admin",
        actor_id=admin.id,
        action="admin_login",
        target_type="session",
        target_id=admin.id,
        ip=get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )

    return RedirectResponse(url="/admin", status_code=303)


@router.post("/logout")
def admin_logout(request: Request, db: Session = Depends(get_db)):
    current = get_session_admin(db, request.session)
    if current:
        write_audit_log(
            db,
            actor_type="admin",
            actor_id=current.id,
            action="admin_logout",
            target_type="session",
            target_id=current.id,
            ip=get_client_ip(request),
            user_agent=request.headers.get("user-agent"),
        )
    request.session.clear()
    return RedirectResponse(url="/admin/login", status_code=303)


@router.get("")
def admin_dashboard(request: Request, db: Session = Depends(get_db)):
    current = admin_or_redirect(request, db)
    if isinstance(current, RedirectResponse):
        return current

    stats = {
        "app_type_count": db.query(func.count(AppType.id)).scalar() or 0,
        "version_count": db.query(func.count(ApkVersion.id)).scalar() or 0,
        "notice_count": db.query(func.count(Notice.id)).scalar() or 0,
    }

    recent_notices = db.query(Notice).order_by(Notice.created_at.desc()).limit(5).all()

    return templates.TemplateResponse(
        "admin_dashboard.html",
        {
            "request": request,
            "admin": current,
            "stats": stats,
            "recent_notices": recent_notices,
        },
    )


@router.get("/apps")
def manage_apps(request: Request, db: Session = Depends(get_db)):
    current = admin_or_redirect(request, db)
    if isinstance(current, RedirectResponse):
        return current

    app_types = db.query(AppType).order_by(AppType.name.asc()).all()
    return templates.TemplateResponse(
        "admin_apps.html",
        {
            "request": request,
            "admin": current,
            "app_types": app_types,
            "message": request.query_params.get("message"),
            "error": request.query_params.get("error"),
        },
    )


@router.post("/apps")
def upsert_app_type(
    request: Request,
    app_type_id: int | None = Form(default=None),
    name: str = Form(...),
    slug: str = Form(default=""),
    description: str = Form(default=""),
    is_active: str | None = Form(default=None),
    db: Session = Depends(get_db),
):
    current = admin_or_redirect(request, db)
    if isinstance(current, RedirectResponse):
        return current

    name = name.strip()
    if not name:
        return RedirectResponse(url="/admin/apps?error=앱+이름은+필수입니다.", status_code=303)

    slug_value = slugify_name(slug if slug.strip() else name)
    active = is_active == "on"

    if app_type_id:
        app_type = db.query(AppType).filter(AppType.id == app_type_id).first()
        if not app_type:
            return RedirectResponse(url="/admin/apps?error=대상을+찾을+수+없습니다.", status_code=303)

        conflict = (
            db.query(AppType)
            .filter(AppType.id != app_type.id)
            .filter((AppType.name == name) | (AppType.slug == slug_value))
            .first()
        )
        if conflict:
            return RedirectResponse(url="/admin/apps?error=이름+또는+슬러그가+중복됩니다.", status_code=303)

        app_type.name = name
        app_type.slug = slug_value
        app_type.description = description.strip() or None
        app_type.is_active = active
        db.commit()

        write_audit_log(
            db,
            actor_type="admin",
            actor_id=current.id,
            action="update_app_type",
            target_type="app_type",
            target_id=app_type.id,
            ip=get_client_ip(request),
            user_agent=request.headers.get("user-agent"),
        )
        return RedirectResponse(url="/admin/apps?message=앱+종류가+수정되었습니다.", status_code=303)

    conflict = db.query(AppType).filter((AppType.name == name) | (AppType.slug == slug_value)).first()
    if conflict:
        return RedirectResponse(url="/admin/apps?error=이름+또는+슬러그가+중복됩니다.", status_code=303)

    app_type = AppType(name=name, slug=slug_value, description=description.strip() or None, is_active=active)
    db.add(app_type)
    db.commit()

    write_audit_log(
        db,
        actor_type="admin",
        actor_id=current.id,
        action="create_app_type",
        target_type="app_type",
        target_id=app_type.id,
        ip=get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )

    return RedirectResponse(url="/admin/apps?message=앱+종류가+등록되었습니다.", status_code=303)


@router.get("/apks/upload")
def upload_apk_page(request: Request, db: Session = Depends(get_db)):
    current = admin_or_redirect(request, db)
    if isinstance(current, RedirectResponse):
        return current

    pending = request.session.get("pending_overwrite")
    return render_upload_page(request, db, overwrite_prompt=pending)


def validate_apk(upload: UploadFile, data: bytes) -> str | None:
    filename = (upload.filename or "").lower()
    if not filename.endswith(".apk"):
        return "APK 파일(.apk)만 업로드할 수 있습니다."

    if upload.content_type and upload.content_type not in ALLOWED_CONTENT_TYPES:
        return f"허용되지 않은 파일 타입입니다: {upload.content_type}"

    if len(data) < 4 or not data.startswith(b"PK"):
        return "APK 헤더 검증에 실패했습니다."

    return None


@router.post("/apks/upload")
async def upload_apk(
    request: Request,
    app_type_id: int = Form(...),
    version: str = Form(...),
    release_note: str = Form(default=""),
    apk_file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    current = admin_or_redirect(request, db)
    if isinstance(current, RedirectResponse):
        return current

    app_type = db.query(AppType).filter(AppType.id == app_type_id, AppType.is_active.is_(True)).first()
    if not app_type:
        return render_upload_page(request, db, error="유효한 앱 종류를 선택하세요.")

    version = version.strip()
    if not version:
        return render_upload_page(request, db, error="버전은 필수입니다.")

    data = await apk_file.read()
    err = validate_apk(apk_file, data)
    if err:
        return render_upload_page(request, db, error=err)

    existing_version = (
        db.query(ApkVersion)
        .options(joinedload(ApkVersion.current_file))
        .filter(ApkVersion.app_type_id == app_type.id, ApkVersion.version == version)
        .first()
    )

    if existing_version:
        ensure_dir(settings.tmp_root)
        token = str(uuid.uuid4())
        tmp_path = settings.tmp_root / f"{token}.apk"
        tmp_path.write_bytes(data)

        pending = {
            "token": token,
            "tmp_path": str(tmp_path),
            "app_type_id": app_type.id,
            "app_type_name": app_type.name,
            "version": version,
            "release_note": release_note,
            "original_filename": apk_file.filename or f"{app_type.slug}-{version}.apk",
        }
        request.session["pending_overwrite"] = pending

        return render_upload_page(
            request,
            db,
            error="동일 앱/버전이 이미 존재합니다. 덮어쓰기를 진행하려면 아래 확인 버튼을 누르세요.",
            overwrite_prompt=pending,
        )

    new_version = ApkVersion(app_type_id=app_type.id, version=version, release_note=release_note.strip() or None)
    db.add(new_version)
    db.flush()

    revision_no = 1
    stored_path = store_file_bytes(
        settings.files_root,
        app_type.slug,
        version,
        revision_no,
        apk_file.filename or f"{app_type.slug}-{version}.apk",
        data,
    )

    apk_record = ApkFile(
        apk_version_id=new_version.id,
        revision_no=revision_no,
        stored_path=stored_path,
        original_filename=apk_file.filename or f"{app_type.slug}-{version}.apk",
        file_size=len(data),
        sha256=sha256_bytes(data),
        uploaded_by=current.id,
        is_current=True,
    )
    db.add(apk_record)
    db.flush()

    new_version.current_file_id = apk_record.id
    db.commit()

    write_audit_log(
        db,
        actor_type="admin",
        actor_id=current.id,
        action="upload_apk",
        target_type="apk_version",
        target_id=new_version.id,
        ip=get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )

    request.session.pop("pending_overwrite", None)
    return render_upload_page(request, db, message="새 APK 버전이 등록되었습니다.")


@router.post("/apks/overwrite")
def overwrite_apk(
    request: Request,
    token: str = Form(...),
    db: Session = Depends(get_db),
):
    current = admin_or_redirect(request, db)
    if isinstance(current, RedirectResponse):
        return current

    pending = request.session.get("pending_overwrite")
    if not pending or pending.get("token") != token:
        return render_upload_page(request, db, error="유효하지 않은 덮어쓰기 요청입니다.")

    tmp_path = Path(pending.get("tmp_path", ""))
    if not tmp_path.exists():
        request.session.pop("pending_overwrite", None)
        return render_upload_page(request, db, error="임시 파일을 찾을 수 없습니다. 다시 업로드하세요.")

    app_type = db.query(AppType).filter(AppType.id == int(pending["app_type_id"])).first()
    if not app_type:
        tmp_path.unlink(missing_ok=True)
        request.session.pop("pending_overwrite", None)
        return render_upload_page(request, db, error="앱 종류 정보를 찾을 수 없습니다.")

    version = (
        db.query(ApkVersion)
        .options(joinedload(ApkVersion.files))
        .filter(ApkVersion.app_type_id == app_type.id, ApkVersion.version == pending["version"])
        .first()
    )
    if not version:
        tmp_path.unlink(missing_ok=True)
        request.session.pop("pending_overwrite", None)
        return render_upload_page(request, db, error="버전 정보를 찾을 수 없습니다.")

    data = tmp_path.read_bytes()
    revision_no = (max((f.revision_no for f in version.files), default=0)) + 1

    for file_item in version.files:
        file_item.is_current = False

    stored_path = store_file_bytes(
        settings.files_root,
        app_type.slug,
        version.version,
        revision_no,
        pending.get("original_filename") or f"{app_type.slug}-{version.version}.apk",
        data,
    )

    apk_record = ApkFile(
        apk_version_id=version.id,
        revision_no=revision_no,
        stored_path=stored_path,
        original_filename=pending.get("original_filename") or f"{app_type.slug}-{version.version}.apk",
        file_size=len(data),
        sha256=sha256_bytes(data),
        uploaded_by=current.id,
        is_current=True,
    )
    db.add(apk_record)
    db.flush()

    if pending.get("release_note"):
        version.release_note = pending["release_note"]
    version.current_file_id = apk_record.id

    db.commit()

    write_audit_log(
        db,
        actor_type="admin",
        actor_id=current.id,
        action="overwrite_apk",
        target_type="apk_version",
        target_id=version.id,
        ip=get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )

    tmp_path.unlink(missing_ok=True)
    request.session.pop("pending_overwrite", None)
    return render_upload_page(request, db, message="기존 버전을 새 리비전으로 덮어썼습니다.")


@router.post("/apks/delete")
def delete_apk_version(
    request: Request,
    apk_version_id: int = Form(...),
    db: Session = Depends(get_db),
):
    current = admin_or_redirect(request, db)
    if isinstance(current, RedirectResponse):
        return current

    version = (
        db.query(ApkVersion)
        .options(joinedload(ApkVersion.files), joinedload(ApkVersion.app_type))
        .filter(ApkVersion.id == apk_version_id)
        .first()
    )
    if not version:
        return render_upload_page(request, db, error="삭제할 버전을 찾을 수 없습니다.")

    version_id = version.id
    app_name = version.app_type.name
    version_text = version.version

    removed_count, failed_count = remove_apk_version_files(version)
    db.delete(version)
    db.commit()

    write_audit_log(
        db,
        actor_type="admin",
        actor_id=current.id,
        action="delete_apk_version",
        target_type="apk_version",
        target_id=version_id,
        ip=get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )

    message = f"{app_name} {version_text} 버전을 삭제했습니다. (파일 {removed_count}개 정리)"
    if failed_count:
        message += f" 파일 {failed_count}개는 수동 정리가 필요합니다."
    return render_upload_page(request, db, message=message)


@router.get("/notices")
def notices_page(request: Request, db: Session = Depends(get_db)):
    current = admin_or_redirect(request, db)
    if isinstance(current, RedirectResponse):
        return current

    notices = db.query(Notice).order_by(Notice.created_at.desc()).all()
    return templates.TemplateResponse(
        "admin_notices.html",
        {
            "request": request,
            "notices": notices,
            "message": request.query_params.get("message"),
            "error": request.query_params.get("error"),
        },
    )


@router.post("/notices")
def save_notice(
    request: Request,
    action: str = Form(default="create"),
    notice_id: int | None = Form(default=None),
    title: str = Form(default=""),
    content: str = Form(default=""),
    is_pinned: str | None = Form(default=None),
    is_visible: str | None = Form(default=None),
    db: Session = Depends(get_db),
):
    current = admin_or_redirect(request, db)
    if isinstance(current, RedirectResponse):
        return current

    ip = get_client_ip(request)
    ua = request.headers.get("user-agent")

    if action == "toggle_visibility":
        target = db.query(Notice).filter(Notice.id == notice_id).first()
        if not target:
            return RedirectResponse(url="/admin/notices?error=공지를+찾을+수+없습니다.", status_code=303)

        target.is_visible = not target.is_visible
        db.commit()

        write_audit_log(
            db,
            actor_type="admin",
            actor_id=current.id,
            action="toggle_notice_visibility",
            target_type="notice",
            target_id=target.id,
            ip=ip,
            user_agent=ua,
        )
        return RedirectResponse(url="/admin/notices?message=공지+노출상태가+변경되었습니다.", status_code=303)

    title = title.strip()
    content = content.strip()
    if not title or not content:
        return RedirectResponse(url="/admin/notices?error=제목과+내용은+필수입니다.", status_code=303)

    pinned_value = is_pinned == "on"
    visible_value = is_visible == "on"

    if action == "update" and notice_id:
        target = db.query(Notice).filter(Notice.id == notice_id).first()
        if not target:
            return RedirectResponse(url="/admin/notices?error=공지를+찾을+수+없습니다.", status_code=303)

        target.title = title
        target.content = content
        target.is_pinned = pinned_value
        target.is_visible = visible_value
        db.commit()

        write_audit_log(
            db,
            actor_type="admin",
            actor_id=current.id,
            action="update_notice",
            target_type="notice",
            target_id=target.id,
            ip=ip,
            user_agent=ua,
        )
        return RedirectResponse(url="/admin/notices?message=공지가+수정되었습니다.", status_code=303)

    notice = Notice(
        title=title,
        content=content,
        is_pinned=pinned_value,
        is_visible=visible_value,
        created_by=current.id,
    )
    db.add(notice)
    db.commit()

    write_audit_log(
        db,
        actor_type="admin",
        actor_id=current.id,
        action="create_notice",
        target_type="notice",
        target_id=notice.id,
        ip=ip,
        user_agent=ua,
    )
    return RedirectResponse(url="/admin/notices?message=공지가+등록되었습니다.", status_code=303)
