"""Attach independent, read-only SQL population/snapshot checks; preserve raw metrics."""

import argparse
import hashlib
import json
import os
import re
import sys
import uuid
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

os.environ["LLM_PROVIDER"] = "mock"
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services/api"))

from app.core.config import get_settings
from app.core.database import build_engine
from app.memory.eval_dataset import CACHE, data_snapshot, load_suite
from app.memory.synthetic_import import assert_test_session
from app.models.entities import MemoryFact
from sqlalchemy import func, select
from sqlalchemy.orm import Session


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("label")
    args = parser.parse_args()
    if not re.fullmatch(r"[a-z0-9-]{1,30}", args.label):
        parser.error("Use an existing report label")
    directory = ROOT / "docs/testing/memory-eval-v1"
    raw_path = directory / f"{args.label}.json"
    raw = raw_path.read_bytes()
    report = json.loads(raw)
    _, suite_sha = load_suite()
    if report["status"] != "measured" or report["suite_sha256"] != suite_sha:
        raise ValueError("Only a finished run of the sealed suite can be audited")
    output = directory / f"{args.label}-verified.json"
    if output.exists():
        raise ValueError("Preserve prior verification evidence")
    engine = build_engine(
        get_settings().test_database_url.get_secret_value(), test_only=True
    )
    try:
        with Session(engine) as db:
            assert_test_session(db)
            for run in report["scales"]:
                namespace = uuid.uuid5(
                    uuid.NAMESPACE_URL, f"{suite_sha}:{run['scale']}"
                )
                state = json.loads(
                    (CACHE / f"benchmark-{namespace}/state.json").read_text()
                )
                actors = state["actors"]
                snapshot = data_snapshot(db, list(actors.values()))
                if (
                    snapshot != run["initial_snapshot"]
                    or snapshot != run["final_snapshot"]
                ):
                    raise ValueError(
                        "Current facts do not match the measured snapshots"
                    )
                rows = dict(
                    db.execute(
                        select(MemoryFact.user_id, func.count())
                        .where(MemoryFact.user_id.in_(actors.values()))
                        .group_by(MemoryFact.user_id)
                    ).all()
                )
                counts = {
                    actor: rows.get(user_id, 0) for actor, user_id in actors.items()
                }
                if sum(counts.values()) != run["scale"]:
                    raise ValueError("SQL population does not match the declared scale")
                run["per_user_memory_counts"] = counts
    finally:
        engine.dispose()
    report["label"] += "-verified"
    report["definitions"]["per_user_memories_before"] = (
        "Legacy field is arithmetic mean, not an assertion of equal actor counts; "
        "per_user_memory_counts is independently verified SQL distribution."
    )
    report["metadata_verification"] = {
        "checked_at_hk": datetime.now(ZoneInfo("Asia/Hong_Kong")).isoformat(
            timespec="seconds"
        ),
        "raw_report": raw_path.name,
        "raw_sha256": hashlib.sha256(raw).hexdigest(),
        "method": "Read-only test-schema SQL GROUP BY; initial/final source snapshots match",
        "metrics_grades_questions_and_fixtures_changed": False,
        "model_calls": 0,
    }
    with output.open("x", encoding="utf-8") as file:
        json.dump(report, file, ensure_ascii=False, indent=2)
        file.write("\n")
    print(
        json.dumps(
            {
                "output": output.name,
                "counts": {
                    run["scale"]: run["per_user_memory_counts"]
                    for run in report["scales"]
                },
            }
        )
    )


if __name__ == "__main__":
    main()
