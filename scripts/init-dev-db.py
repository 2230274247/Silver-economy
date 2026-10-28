"""Start only this project's isolated MySQL; never use an existing database service."""

import os
import secrets
import socket
import subprocess
from pathlib import Path

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
COMPOSE = ["docker", "compose", "-f", str(ROOT / "docker-compose.dev.yml")]


def main():
    path = ROOT / ".env"
    if not path.exists():
        password, root_password = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        base = f"mysql+pymysql://silver_demo:{password}@127.0.0.1:13306/"
        with path.open("x", encoding="utf-8") as file:
            file.write(
                f"MYSQL_DATABASE=silver_memory_demo_v01\nMYSQL_USER=silver_demo\n"
                f"MYSQL_PASSWORD={password}\nMYSQL_ROOT_PASSWORD={root_password}\nMYSQL_PORT=13306\n"
                f"DATABASE_URL={base}silver_memory_demo_v01?charset=utf8mb4\n"
                f"TEST_DATABASE_URL={base}silver_memory_demo_v01_test?charset=utf8mb4\n"
                "LLM_PROVIDER=mock\nDEEPSEEK_API_KEY=\nDEEPSEEK_MODEL=deepseek-flash\n"
            )
        print("Created ignored local .env with random credentials (values suppressed)")
    values = dotenv_values(path)
    if (
        values.get("MYSQL_DATABASE") != "silver_memory_demo_v01"
        or values.get("MYSQL_USER") != "silver_demo"
        or values.get("MYSQL_PORT") != "13306"
        or not values.get("MYSQL_PASSWORD")
        or not values.get("MYSQL_ROOT_PASSWORD")
    ):
        raise SystemExit(
            "Local MySQL config must use this project's isolated database and port"
        )
    env = dict(os.environ)
    env.update(
        {
            key: value
            for key, value in values.items()
            if key.startswith("MYSQL_") and value
        }
    )
    running = subprocess.check_output(
        COMPOSE + ["ps", "-q", "mysql"], cwd=ROOT, env=env
    ).strip()
    if not running:
        with socket.socket() as probe:
            try:
                probe.bind(("127.0.0.1", 13306))
            except OSError:
                raise SystemExit(
                    "Port 13306 is occupied; refusing to touch its service"
                ) from None
    subprocess.run(COMPOSE + ["config", "--quiet"], cwd=ROOT, env=env, check=True)
    subprocess.run(
        COMPOSE + ["up", "-d", "--wait", "--wait-timeout", "180", "mysql"],
        cwd=ROOT,
        env=env,
        check=True,
    )
    sql = (
        "CREATE DATABASE IF NOT EXISTS silver_memory_demo_v01_test "
        "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;\n"
        "GRANT ALL ON silver_memory_demo_v01_test.* TO 'silver_demo'@'%';\n"
    )
    subprocess.run(
        COMPOSE
        + [
            "exec",
            "-T",
            "mysql",
            "sh",
            "-c",
            'export MYSQL_PWD="$MYSQL_ROOT_PASSWORD"; exec mysql -uroot',
        ],
        input=sql,
        text=True,
        cwd=ROOT,
        env=env,
        check=True,
    )
    print(
        "Isolated development/test schemas ready on 127.0.0.1:13306; no other service used"
    )


if __name__ == "__main__":
    main()
