"""Generate/import reproducible Synthetic corpora without a model or external API."""

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services/api"))

from alembic import command
from alembic.config import Config
from alembic.util.exc import CommandError
from app.core.config import get_settings, validated_database_url
from app.core.database import build_engine
from app.memory.synthetic_data import (
    SyntheticConfig,
    corpus_summary,
    dataset_lines,
    validate_lines,
)
from app.memory.synthetic_import import import_dataset
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

CACHE = ROOT / ".cache/memory-eval"


def cache_path(value):
    path = Path(value).resolve()
    if not path.is_relative_to(CACHE.resolve()):
        raise ValueError("Synthetic files must stay in project .cache/memory-eval")
    return path


def generate(config, output=None):
    path = cache_path(output or CACHE / f"{config.memories}-{config.dataset_id}.jsonl")
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        with path.open(encoding="utf-8") as file:
            previous, _ = validate_lines(iter(file))
        if previous != config:
            raise ValueError(
                "Existing output has different configuration; not overwritten"
            )
    else:
        with path.open("x", encoding="utf-8", newline="\n") as file:
            file.writelines(dataset_lines(config))
    return path


def load(path):
    with cache_path(path).open(encoding="utf-8") as file:
        return validate_lines(iter(file))


def run_import(path):
    config, records = load(path)  # Validate all records before opening the database.
    value = get_settings().test_database_url.get_secret_value()
    validated_database_url(value, test_only=True)
    migration = Config(str(ROOT / "services/api/alembic.ini"))
    migration.attributes.update(database_url=value, test_only=True)
    command.upgrade(migration, "head")
    engine = build_engine(value, test_only=True)
    started = time.monotonic()
    try:
        with Session(engine) as db, db.begin():
            result = import_dataset(db, config, records)
    finally:
        engine.dispose()
    result.update(
        import_seconds=round(time.monotonic() - started, 4),
        schema="silver_memory_demo_v01_test",
        file_sha256=hashlib.sha256(Path(path).read_bytes()).hexdigest(),
    )
    report = CACHE / f"import-{config.dataset_id}.json"
    report.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["generate", "import", "presets"])
    parser.add_argument("--input", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--users", type=int, default=2)
    parser.add_argument("--memories", type=int, default=100)
    parser.add_argument("--seed", type=int, default=20261027)
    parser.add_argument("--start-year", type=int, default=2006)
    parser.add_argument("--end-year", type=int, default=2026)
    parser.add_argument("--categories", default=",".join(SyntheticConfig().categories))
    parser.add_argument("--duplicate-ratio", type=float, default=0.1)
    parser.add_argument("--conflict-ratio", type=float, default=0.1)
    parser.add_argument("--invalid-ratio", type=float, default=0.1)
    parser.add_argument("--reference-date", default="2026-10-26")
    args = parser.parse_args()
    try:
        if args.action == "import":
            if args.input is None:
                parser.error(
                    "import needs --input (only the project test schema is supported)"
                )
            print(json.dumps(run_import(args.input), ensure_ascii=False))
            return
        values = {
            key: getattr(args, key)
            for key in (
                "users",
                "memories",
                "seed",
                "start_year",
                "end_year",
                "duplicate_ratio",
                "conflict_ratio",
                "invalid_ratio",
                "reference_date",
            )
        }
        values["categories"] = tuple(
            word.strip() for word in args.categories.split(",")
        )
        reports = []
        for size in (
            (100, 1000, 10000) if args.action == "presets" else (args.memories,)
        ):
            config = SyntheticConfig(**{**values, "memories": size})
            path = generate(config, args.output if args.action == "generate" else None)
            if args.action == "presets":
                reports.append(run_import(path))
            else:
                _, records = load(path)
                print(
                    json.dumps(
                        {**corpus_summary(config, records), "path": str(path)},
                        ensure_ascii=False,
                    )
                )
        if reports:
            (CACHE / "presets-report.json").write_text(
                json.dumps(reports, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            print(json.dumps(reports, ensure_ascii=False))
    except (
        ValueError,
        TypeError,
        KeyError,
        OSError,
        StopIteration,
        SQLAlchemyError,
        CommandError,
    ) as error:
        # SQL/Pydantic errors can embed input or credentials. Never echo them.
        print(
            f"Synthetic operation failed ({type(error).__name__}); existing data was not overwritten.",
            file=sys.stderr,
        )
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
