"""Run the sealed Synthetic benchmark using Mock and the isolated MySQL TEST schema."""

import argparse
import hashlib
import json
import os
import platform
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

# This process cannot inherit the operator's live provider or browser-test identity mode.
os.environ["LLM_PROVIDER"] = "mock"
os.environ["UI_TEST_MODE"] = "false"
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services/api"))

import httpx
from alembic import command
from alembic.config import Config
from app.core.config import get_settings, validated_database_url
from app.core.database import build_engine
from app.memory.eval_dataset import load_suite
from app.memory.evaluator import MemoryEvaluator
from sqlalchemy import text


def deny_http(*args, **kwargs):
    raise RuntimeError("Bulk memory evaluation cannot call a real HTTP/model service")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--label", required=True)
    parser.add_argument(
        "--scales", nargs="+", type=int, default=[100, 1000, 10000, 20000]
    )
    parser.add_argument("--limit", type=int)
    parser.add_argument("--require-targets", action="store_true")
    args = parser.parse_args()
    if (
        not re.fullmatch(r"[a-z0-9-]{1,40}", args.label)
        or args.limit is not None
        and args.limit < 1
    ):
        parser.error("Use a simple label and a positive optional pilot limit")
    output = ROOT / "docs/testing/memory-eval-v1" / f"{args.label}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        raise SystemExit("Preserve prior results; choose a new run label")
    httpx.HTTPTransport.handle_request = deny_http
    get_settings.cache_clear()
    suite, sha = load_suite()
    value = get_settings().test_database_url.get_secret_value()
    validated_database_url(value, test_only=True)
    migration = Config(str(ROOT / "services/api/alembic.ini"))
    migration.attributes.update(database_url=value, test_only=True)
    command.upgrade(migration, "head")
    engine = build_engine(value, test_only=True)
    tracked = [
        "prompts/chat-memory-v3.txt",
        "prompts/chat-memory-v4.txt",
        "prompts/chat-v2.txt",
        "prompts/task-intent-v2.txt",
        "prompts/task-intent-v3.txt",
        "scripts/evaluate-memory.py",
        "services/api/app/memory/eval_dataset.py",
        "services/api/app/memory/evaluator.py",
        "services/api/app/memory/query.py",
        "services/api/app/memory/extractor.py",
        "services/api/app/memory/retriever.py",
        "services/api/app/memory/context.py",
        "services/api/app/services/model_chat.py",
    ]
    with engine.connect() as connection:
        mysql_version = connection.scalar(text("SELECT VERSION()"))
    report = {
        "version": "memory-eval/1",
        "label": args.label,
        "synthetic": True,
        "provider": "mock",
        "runtime": {"python": platform.python_version(), "mysql": mysql_version},
        "real_model_calls": 0,
        "created_at_hk": datetime.now(ZoneInfo("Asia/Hong_Kong")).isoformat(
            timespec="seconds"
        ),
        "suite_sha256": sha,
        "suite_questions": len(suite["questions"]),
        "unique_question_texts": len({q["text"] for q in suite["questions"]}),
        "pilot_limit": args.limit,
        "scales_requested": args.scales,
        "status": "running",
        "parent_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "code_sha256_utf8_lf": {
            p: hashlib.sha256(
                (ROOT / p).read_text(encoding="utf-8").encode()
            ).hexdigest()
            for p in tracked
        },
        "definitions": {
            "recall": "All required source memories must occur in top 5; denominator is positive cases only.",
            "top1": "First retrieved source must be one of the independently expected sources.",
            "answer": "Closed answer groups plus persisted source references; unknown questions require explicit uncertainty.",
            "hallucination_proxy": "Unknown/unsupported questions answered without explicit uncertainty; conservative Mock proxy, not LLM semantic grading.",
            "resources": "Python allocation peak is incremental evaluation allocation. RSS/peak RSS covers process lifetime, including preparation.",
            "live": "This batch performs no real DeepSeek calls. Earlier live samples are separate evidence.",
        },
        "scales": [],
    }
    with output.open("x", encoding="utf-8") as file:
        json.dump(report, file, ensure_ascii=False, indent=2)
    try:
        evaluator = MemoryEvaluator(engine, suite, sha)
        for scale in args.scales:
            result = evaluator.run_scale(scale, args.limit)
            report["scales"].append(result)
            output.write_text(
                json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            print(
                json.dumps(
                    {
                        "scale": scale,
                        "metrics": result["metrics"],
                        "gates": result["gates"],
                    },
                    ensure_ascii=False,
                ),
                flush=True,
            )
        report["status"] = "measured"
        report["targets_passed"] = all(
            all(result["gates"].values()) for result in report["scales"]
        )
    except BaseException as failure:
        report["status"] = (
            "interrupted" if isinstance(failure, KeyboardInterrupt) else "failed"
        )
        report["error_type"] = type(failure).__name__
        report["targets_passed"] = False
        raise
    finally:
        engine.dispose()
        output.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    if args.require_targets and not report["targets_passed"]:
        raise SystemExit("Measured results did not meet the declared gates")


if __name__ == "__main__":
    main()
