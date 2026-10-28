"""Create synthetic local demo accounts without committing or printing passwords."""

import argparse
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
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--ui", action="store_true", help="Isolated Mock browser-test accounts"
    )
    args = parser.parse_args()
    filename = "ui-accounts.json" if args.ui else "demo-accounts.json"
    path = ROOT / ".cache" / filename
    names = ["ui_a", "ui_b"] if args.ui else ["demo_a", "demo_b"]
    with Session(get_engine()) as db:
        existing = db.scalars(
            select(User.login_name).where(User.login_name.in_(names))
        ).all()
        if existing:
            if set(existing) == set(names) and path.exists():
                print(
                    f"Synthetic users already exist; credentials unchanged in ignored .cache/{filename}"
                )
                return
            raise SystemExit(
                "Existing demo account state differs; refusing to overwrite passwords"
            )
        if path.exists():
            raise SystemExit(
                "Credential file exists without matching users; refusing to overwrite"
            )
        accounts = [
            {"login_name": name, "password": secrets.token_urlsafe(24)}
            for name in names
        ]
        for item in accounts:
            db.add(
                User(
                    login_name=item["login_name"],
                    password_hash=hasher.hash(item["password"]),
                )
            )
        path.parent.mkdir(exist_ok=True)
        with path.open("x", encoding="utf-8") as file:
            json.dump(accounts, file, indent=2)
        db.commit()
    print(f"Created two synthetic users; passwords only in ignored .cache/{filename}")


if __name__ == "__main__":
    main()
