from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PACKAGE_DIR = Path(__file__).resolve().parent

load_dotenv(PROJECT_ROOT / ".env")


def _to_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


@dataclass(frozen=True)
class Settings:
    app_name: str = os.getenv("APP_NAME", "Internal APK Hub")
    secret_key: str = os.getenv("APP_SECRET_KEY", "change-this-secret-key")
    host: str = os.getenv("APP_HOST", "0.0.0.0")
    port: int = int(os.getenv("APP_PORT", "8080"))

    database_url: str = os.getenv("DATABASE_URL", "sqlite:///data/app.db")
    files_root: Path = PROJECT_ROOT / os.getenv("FILES_ROOT", "data/apk")
    tmp_root: Path = PROJECT_ROOT / os.getenv("TMP_ROOT", "data/tmp")
    templates_dir: Path = PACKAGE_DIR / "templates"
    static_dir: Path = PACKAGE_DIR / "static"

    session_max_age_seconds: int = int(os.getenv("SESSION_MAX_AGE_SECONDS", "28800"))

    auto_bootstrap_admin: bool = _to_bool(os.getenv("AUTO_BOOTSTRAP_ADMIN"), True)
    admin_username: str = os.getenv("ADMIN_USERNAME", "admin")
    admin_password: str = os.getenv("ADMIN_PASSWORD", "ChangeMeNow!")


settings = Settings()
