"""Project-only logical backups; automated restore can target only the test schema."""

import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services/api"))
from app.core.config import validated_database_url

TEST_SCHEMA = "silver_memory_demo_v01_test"
SCHEMAS = {"dev": "silver_memory_demo_v01", "test": TEST_SCHEMA}
COMPOSE = ["docker", "compose", "-f", str(ROOT / "docker-compose.dev.yml")]


def backup_path(value):
    base = (ROOT / "backups").resolve()
    result = (ROOT / value).resolve()
    if (
        not base.is_relative_to(ROOT)
        or not result.is_relative_to(base)
        or result.suffix != ".sql"
    ):
        raise ValueError(
            "Backup must be a .sql file inside this project's backups directory"
        )
    return result


def checked_environment(schema):
    values = dotenv_values(ROOT / ".env")
    field = "TEST_DATABASE_URL" if schema == TEST_SCHEMA else "DATABASE_URL"
    url = validated_database_url(values.get(field, ""), test_only=schema == TEST_SCHEMA)
    if url.database != schema:
        raise ValueError("Configured schema does not match the selected backup target")
    if (
        values.get("MYSQL_USER") != "silver_demo"
        or values.get("MYSQL_PASSWORD") != url.password
        or values.get("MYSQL_PORT") != "13306"
    ):
        raise ValueError(
            "Local Compose credentials or port do not match the project database"
        )
    env = dict(os.environ)
    env.update({k: v for k, v in values.items() if k.startswith("MYSQL_") and v})
    container = (
        subprocess.check_output(COMPOSE + ["ps", "-q", "mysql"], cwd=ROOT, env=env)
        .decode()
        .strip()
    )
    if not container or "\n" in container:
        raise ValueError("Exactly one project MySQL container must already be running")
    labels_text, ports_text = (
        subprocess.check_output(
            [
                "docker",
                "inspect",
                "--format",
                "{{json .Config.Labels}}|{{json .NetworkSettings.Ports}}",
                container,
            ],
            env=env,
        )
        .decode()
        .split("|", 1)
    )
    info = json.loads(labels_text)
    ports = json.loads(ports_text)
    if (
        info.get("com.docker.compose.project") != "silver-memory-demo-v01"
        or info.get("com.docker.compose.service") != "mysql"
        or ports.get("3306/tcp") != [{"HostIp": "127.0.0.1", "HostPort": "13306"}]
    ):
        raise ValueError("Refusing to use a container belonging to another project")
    return env


def mysql_command(schema, *, dump=False):
    tool = (
        "mysqldump --single-transaction --skip-lock-tables --no-tablespaces "
        "--set-gtid-purged=OFF --column-statistics=0 --hex-blob --skip-comments"
        if dump
        else "mysql --binary-mode=1"
    )
    return COMPOSE + [
        "exec",
        "-T",
        "mysql",
        "sh",
        "-c",
        f'export MYSQL_PWD="$MYSQL_PASSWORD"; exec {tool} -u"$MYSQL_USER" {schema}',
    ]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    save = sub.add_parser("backup")
    save.add_argument("--schema", choices=SCHEMAS, default="dev")
    save.add_argument("--output", required=True)
    restore = sub.add_parser("restore-test")
    restore.add_argument("--input", required=True)
    restore.add_argument("--replace-test-data", action="store_true", required=True)
    args = parser.parse_args()
    path = backup_path(args.output if args.action == "backup" else args.input)
    manifest_path = path.with_suffix(".manifest.json")
    if args.action == "backup":
        schema = SCHEMAS[args.schema]
        env = checked_environment(schema)
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() or manifest_path.exists():
            raise ValueError("Backup output already exists; choose a new filename")
        partial = path.with_suffix(".sql.partial")
        with partial.open("xb") as output:
            subprocess.run(
                mysql_command(schema, dump=True),
                stdout=output,
                env=env,
                cwd=ROOT,
                check=True,
                stderr=subprocess.PIPE,
            )
        if partial.stat().st_size == 0:
            raise ValueError("Empty backup was not promoted to a completed file")
        partial.rename(path)
        manifest = {
            "format": "silver-memory-mysql-backup/v1",
            "source_schema": schema,
            "created_at_hk": datetime.now(ZoneInfo("Asia/Hong_Kong")).isoformat(),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
        with manifest_path.open("x", encoding="utf-8") as output:
            json.dump(manifest, output, indent=2)
        print("Backup saved inside ignored backups directory; credentials suppressed")
    else:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if (
            manifest.get("format") != "silver-memory-mysql-backup/v1"
            or manifest.get("source_schema") not in SCHEMAS.values()
            or manifest.get("sha256") != hashlib.sha256(path.read_bytes()).hexdigest()
        ):
            raise ValueError("Backup manifest or checksum does not match")
        env = checked_environment(TEST_SCHEMA)
        with path.open("rb") as source:
            subprocess.run(
                mysql_command(TEST_SCHEMA),
                stdin=source,
                env=env,
                cwd=ROOT,
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
            )
        print("Restored only silver_memory_demo_v01_test; development schema untouched")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        # Neither SQL contents, container environment nor provider credentials are printed.
        raise SystemExit(
            f"Backup operation failed ({type(error).__name__}); inspect local setup"
        ) from None
