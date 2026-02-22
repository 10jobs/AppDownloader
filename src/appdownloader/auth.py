from __future__ import annotations

import time

from passlib.context import CryptContext
from sqlalchemy.orm import Session

from .config import settings
from .models import AdminUser


pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")


def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)


def verify_password(plain: str, password_hash: str) -> bool:
    return pwd_context.verify(plain, password_hash)


def authenticate_admin(db: Session, username: str, password: str) -> AdminUser | None:
    admin = db.query(AdminUser).filter(AdminUser.username == username).first()
    if not admin:
        return None
    if not verify_password(password, admin.password_hash):
        return None
    return admin


def get_session_admin(db: Session, session_data: dict) -> AdminUser | None:
    admin_user_id = session_data.get("admin_user_id")
    last_seen = session_data.get("last_seen")
    if not admin_user_id or not last_seen:
        return None

    now_ts = int(time.time())
    if now_ts - int(last_seen) > settings.session_max_age_seconds:
        return None

    session_data["last_seen"] = now_ts
    return db.query(AdminUser).filter(AdminUser.id == int(admin_user_id)).first()


def bootstrap_admin_if_needed(db: Session) -> None:
    if not settings.auto_bootstrap_admin:
        return

    exists = db.query(AdminUser).first()
    if exists:
        return

    admin = AdminUser(
        username=settings.admin_username,
        password_hash=hash_password(settings.admin_password),
    )
    db.add(admin)
    db.commit()
