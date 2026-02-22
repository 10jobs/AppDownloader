from __future__ import annotations

import hashlib
import re
from pathlib import Path

from fastapi import Request
from sqlalchemy.orm import Session

from .models import AuditLog, DownloadLog


SLUG_RE = re.compile(r"[^a-z0-9]+")


def slugify_name(value: str) -> str:
    base = value.strip().lower()
    base = SLUG_RE.sub("-", base).strip("-")
    return base or "app"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def get_client_ip(request: Request) -> str | None:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return None


def write_audit_log(
    db: Session,
    *,
    actor_type: str,
    actor_id: int | None,
    action: str,
    target_type: str,
    target_id: int | None,
    ip: str | None,
    user_agent: str | None,
) -> None:
    db.add(
        AuditLog(
            actor_type=actor_type,
            actor_id=actor_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            ip=ip,
            user_agent=user_agent,
        )
    )
    db.commit()


def write_download_log(
    db: Session,
    *,
    apk_file_id: int,
    app_type_id: int,
    version: str,
    ip: str | None,
    user_agent: str | None,
) -> None:
    db.add(
        DownloadLog(
            apk_file_id=apk_file_id,
            app_type_id=app_type_id,
            version=version,
            ip=ip,
            user_agent=user_agent,
        )
    )
    db.commit()


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
