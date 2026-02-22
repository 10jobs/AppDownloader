from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def app_ctx(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    data_dir = tmp_path / "data"
    files_dir = data_dir / "apk"
    tmp_dir = data_dir / "tmp"

    monkeypatch.setenv("APP_NAME", "Test APK Hub")
    monkeypatch.setenv("APP_SECRET_KEY", "test-secret-key")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{(data_dir / 'app.db').as_posix()}")
    monkeypatch.setenv("FILES_ROOT", files_dir.as_posix())
    monkeypatch.setenv("TMP_ROOT", tmp_dir.as_posix())
    monkeypatch.setenv("AUTO_BOOTSTRAP_ADMIN", "true")
    monkeypatch.setenv("ADMIN_USERNAME", "admin")
    monkeypatch.setenv("ADMIN_PASSWORD", "admin1234")

    for name in list(sys.modules.keys()):
        if name == "appdownloader" or name.startswith("appdownloader."):
            del sys.modules[name]

    app_main = importlib.import_module("appdownloader.main")
    db_mod = importlib.import_module("appdownloader.db")
    models_mod = importlib.import_module("appdownloader.models")

    with TestClient(app_main.app) as client:
        yield client, db_mod, models_mod
