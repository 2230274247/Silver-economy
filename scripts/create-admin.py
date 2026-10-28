"""Create a separate local operator without printing or committing credentials."""

import json
import secrets
import sys
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services/api"))
from app.core.database import get_engine
from app.core.security import hasher
from app.models.entities import User


def main():
    path = ROOT / ".cache/admin-account.json"
    with Session(get_engine()) as db:
        existing = db.scalar(select(User).where(User.login_name == "admin"))
        if existing:
            if existing.is_admin and path.exists():
                print("Local admin already exists; credentials unchanged")
                return
            raise SystemExit(
                "Existing admin name or credential ownership differs; refusing overwrite"
            )
        if path.exists():
            raise SystemExit("Credential file already exists; refusing overwrite")
        account = {"login_name": "admin", "password": secrets.token_urlsafe(24)}
        user = User(
            login_name=account["login_name"],
            password_hash=hasher.hash(account["password"]),
            is_admin=True,
            memory_enabled=True,
        )
        db.add(user)
        db.flush()
        path.parent.mkdir(exist_ok=True)
        with path.open("x", encoding="utf-8") as output:
            json.dump(account, output, indent=2)
        db.commit()
    print(
        "Created local operator; credentials only in ignored .cache/admin-account.json"
    )


if __name__ == "__main__":
    main()
