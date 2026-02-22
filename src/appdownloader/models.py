from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class AdminUser(Base):
    __tablename__ = "admin_users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(80), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class AppType(Base):
    __tablename__ = "app_types"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    slug: Mapped[str] = mapped_column(String(120), unique=True, nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())

    versions: Mapped[list["ApkVersion"]] = relationship(
        "ApkVersion",
        back_populates="app_type",
        cascade="all, delete-orphan",
    )


class ApkVersion(Base):
    __tablename__ = "apk_versions"
    __table_args__ = (UniqueConstraint("app_type_id", "version", name="uq_apk_versions_app_type_version"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    app_type_id: Mapped[int] = mapped_column(ForeignKey("app_types.id", ondelete="CASCADE"), nullable=False)
    version: Mapped[str] = mapped_column(String(64), nullable=False)
    release_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    current_file_id: Mapped[int | None] = mapped_column(ForeignKey("apk_files.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    app_type: Mapped["AppType"] = relationship("AppType", back_populates="versions")
    files: Mapped[list["ApkFile"]] = relationship(
        "ApkFile",
        back_populates="apk_version",
        foreign_keys="ApkFile.apk_version_id",
        cascade="all, delete-orphan",
    )
    current_file: Mapped["ApkFile | None"] = relationship(
        "ApkFile",
        foreign_keys=[current_file_id],
        post_update=True,
    )


class ApkFile(Base):
    __tablename__ = "apk_files"
    __table_args__ = (UniqueConstraint("apk_version_id", "revision_no", name="uq_apk_files_version_revision"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    apk_version_id: Mapped[int] = mapped_column(ForeignKey("apk_versions.id", ondelete="CASCADE"), nullable=False)
    revision_no: Mapped[int] = mapped_column(Integer, nullable=False)
    stored_path: Mapped[str] = mapped_column(String(500), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    uploaded_by: Mapped[int] = mapped_column(ForeignKey("admin_users.id", ondelete="SET NULL"), nullable=True)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())

    apk_version: Mapped["ApkVersion"] = relationship(
        "ApkVersion",
        back_populates="files",
        foreign_keys=[apk_version_id],
    )


class Notice(Base):
    __tablename__ = "notices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    is_pinned: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    is_visible: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")
    created_by: Mapped[int] = mapped_column(ForeignKey("admin_users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    actor_type: Mapped[str] = mapped_column(String(20), nullable=False)
    actor_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    target_type: Mapped[str] = mapped_column(String(80), nullable=False)
    target_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ip: Mapped[str | None] = mapped_column(String(100), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())


class DownloadLog(Base):
    __tablename__ = "download_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    apk_file_id: Mapped[int | None] = mapped_column(
        ForeignKey("apk_files.id", ondelete="SET NULL"),
        nullable=True,
    )
    app_type_id: Mapped[int | None] = mapped_column(
        ForeignKey("app_types.id", ondelete="SET NULL"),
        nullable=True,
    )
    version: Mapped[str] = mapped_column(String(64), nullable=False)
    ip: Mapped[str | None] = mapped_column(String(100), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
