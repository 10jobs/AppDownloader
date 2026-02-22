from __future__ import annotations

import getpass

from appdownloader.auth import hash_password
from appdownloader.db import SessionLocal, init_db
from appdownloader.models import AdminUser


def main() -> None:
    init_db()
    db = SessionLocal()
    try:
        username = input("Admin username: ").strip()
        if not username:
            raise ValueError("username is required")

        password = getpass.getpass("Admin password: ").strip()
        if not password:
            raise ValueError("password is required")

        existing = db.query(AdminUser).filter(AdminUser.username == username).first()
        if existing:
            existing.password_hash = hash_password(password)
            db.commit()
            print(f"Updated admin password for '{username}'.")
            return

        admin = AdminUser(username=username, password_hash=hash_password(password))
        db.add(admin)
        db.commit()
        print(f"Created admin user '{username}'.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
