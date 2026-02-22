from __future__ import annotations

import re


def test_admin_login_and_guard(app_ctx):
    client, _db, _models = app_ctx

    response = client.get("/admin", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/admin/login"

    fail = client.post("/admin/login", data={"username": "admin", "password": "bad"})
    assert fail.status_code == 401

    ok = client.post(
        "/admin/login",
        data={"username": "admin", "password": "admin1234"},
        follow_redirects=False,
    )
    assert ok.status_code == 303
    assert ok.headers["location"] == "/admin"


def test_upload_download_and_notice(app_ctx):
    client, db_mod, models = app_ctx

    login = client.post(
        "/admin/login",
        data={"username": "admin", "password": "admin1234"},
        follow_redirects=False,
    )
    assert login.status_code == 303

    app_create = client.post(
        "/admin/apps",
        data={
            "name": "Sales App",
            "slug": "sales-app",
            "description": "field app",
            "is_active": "on",
        },
        follow_redirects=False,
    )
    assert app_create.status_code == 303

    db = db_mod.SessionLocal()
    try:
        app_type = db.query(models.AppType).filter(models.AppType.slug == "sales-app").first()
        assert app_type is not None
    finally:
        db.close()

    file_payload = b"PK\x03\x04dummy-apk-contents"
    upload = client.post(
        "/admin/apks/upload",
        data={"app_type_id": str(app_type.id), "version": "1.0.0", "release_note": "first"},
        files={"apk_file": ("sales.apk", file_payload, "application/vnd.android.package-archive")},
    )
    assert upload.status_code == 200
    assert "새 APK 버전이 등록되었습니다." in upload.text

    home = client.get("/")
    assert home.status_code == 200
    assert "Sales App" in home.text

    db = db_mod.SessionLocal()
    try:
        version = db.query(models.ApkVersion).filter(models.ApkVersion.version == "1.0.0").first()
        assert version is not None
        assert version.current_file_id is not None
        file_id = version.current_file_id
    finally:
        db.close()

    download = client.get(f"/download/{file_id}")
    assert download.status_code == 200
    assert download.content == file_payload

    notice = client.post(
        "/admin/notices",
        data={
            "action": "create",
            "title": "점검 공지",
            "content": "오늘 저녁 점검",
            "is_visible": "on",
            "is_pinned": "on",
        },
        follow_redirects=False,
    )
    assert notice.status_code == 303

    home2 = client.get("/")
    assert "점검 공지" in home2.text


def test_duplicate_upload_overwrite_flow(app_ctx):
    client, db_mod, models = app_ctx

    login = client.post(
        "/admin/login",
        data={"username": "admin", "password": "admin1234"},
        follow_redirects=False,
    )
    assert login.status_code == 303

    client.post(
        "/admin/apps",
        data={"name": "POS App", "slug": "pos-app", "is_active": "on"},
        follow_redirects=False,
    )

    db = db_mod.SessionLocal()
    try:
        app_type = db.query(models.AppType).filter(models.AppType.slug == "pos-app").first()
        assert app_type is not None
        app_type_id = app_type.id
    finally:
        db.close()

    first_payload = b"PK\x03\x04first-version"
    second_payload = b"PK\x03\x04second-version"

    first = client.post(
        "/admin/apks/upload",
        data={"app_type_id": str(app_type_id), "version": "2.0.0", "release_note": "r1"},
        files={"apk_file": ("pos.apk", first_payload, "application/vnd.android.package-archive")},
    )
    assert first.status_code == 200

    duplicate = client.post(
        "/admin/apks/upload",
        data={"app_type_id": str(app_type_id), "version": "2.0.0", "release_note": "r2"},
        files={"apk_file": ("pos.apk", second_payload, "application/vnd.android.package-archive")},
    )
    assert duplicate.status_code == 200
    assert "덮어쓰기" in duplicate.text

    token_match = re.search(r'name="token" value="([^"]+)"', duplicate.text)
    assert token_match is not None
    token = token_match.group(1)

    overwrite = client.post("/admin/apks/overwrite", data={"token": token})
    assert overwrite.status_code == 200
    assert "덮어썼습니다" in overwrite.text

    db = db_mod.SessionLocal()
    try:
        version = (
            db.query(models.ApkVersion)
            .filter(models.ApkVersion.app_type_id == app_type_id, models.ApkVersion.version == "2.0.0")
            .first()
        )
        assert version is not None

        files = (
            db.query(models.ApkFile)
            .filter(models.ApkFile.apk_version_id == version.id)
            .order_by(models.ApkFile.revision_no.asc())
            .all()
        )
        assert len(files) == 2
        assert files[0].is_current is False
        assert files[1].is_current is True
        assert version.current_file_id == files[1].id
    finally:
        db.close()
