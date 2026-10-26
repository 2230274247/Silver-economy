"""Objective, source-aware evaluation against real MySQL and actual chat endpoints."""

import json
import math
import os
import re
import subprocess
import sys
import time
import tracemalloc
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from contextvars import ContextVar

from fastapi.testclient import TestClient
from sqlalchemy import event, func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_session
from app.main import app
from app.memory.context import ContextBuilder
from app.memory.eval_dataset import data_snapshot, prepare_dataset
from app.memory.retriever import MemoryRetriever
from app.models.entities import MemoryFact, ModelUsage
from app.services.model_chat import MEMORY_PROMPT

ACTIVE_STATS = ContextVar("memory_eval_sql", default=None)
UNKNOWN = re.compile(
    r"不知道|不确定|没有.{0,12}(?:记录|找到|资料)|未记录|无法(?:确定|查到|找到)|尚无"
)


def percentile(values, fraction):
    if not values:
        return None
    ordered = sorted(values)
    return round(ordered[max(0, math.ceil(len(ordered) * fraction) - 1)], 3)


def process_memory():
    if sys.platform == "win32":
        try:
            command = (
                f"Get-Process -Id {os.getpid()} | "
                "Select-Object WorkingSet64,PeakWorkingSet64 | ConvertTo-Json -Compress"
            )
            raw = subprocess.check_output(
                ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command],
                timeout=5,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            data = json.loads(raw)
            return {
                "rss_bytes": data["WorkingSet64"],
                "peak_rss_lifetime_bytes": data["PeakWorkingSet64"],
            }
        except (OSError, subprocess.SubprocessError, ValueError, KeyError):
            return {"rss_bytes": None, "peak_rss_lifetime_bytes": None}
    import resource

    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return {
        "rss_bytes": None,
        "peak_rss_lifetime_bytes": peak * (1 if sys.platform == "darwin" else 1024),
    }


def attach_sql_metrics(engine):
    def before(conn, cursor, statement, parameters, context, executemany):
        if ACTIVE_STATS.get() is not None:
            context._silver_eval_started = time.perf_counter()

    def after(conn, cursor, statement, parameters, context, executemany):
        stats = ACTIVE_STATS.get()
        if stats is not None and hasattr(context, "_silver_eval_started"):
            stats["queries"] += 1
            stats["sql_ms"] += (time.perf_counter() - context._silver_eval_started) * 1000

    event.listen(engine, "before_cursor_execute", before)
    event.listen(engine, "after_cursor_execute", after)
    return lambda: (
        event.remove(engine, "before_cursor_execute", before),
        event.remove(engine, "after_cursor_execute", after),
    )


@contextmanager
def sql_stats():
    stats = {"queries": 0, "sql_ms": 0.0}
    token = ACTIVE_STATS.set(stats)
    try:
        yield stats
    finally:
        ACTIVE_STATS.reset(token)


def normalized(value):
    value = re.sub(r"\s+", "", value)
    return re.sub(r"0(\d)([月日])", r"\1\2", value)


def grade_answer(
    definition, expected, reply, *, error=False, leak=False, deleted_hit=False, forbidden_hit=False
):
    answer = reply.get("content", "")
    references = reply.get("memory_refs", [])
    used = {ref["memory_id"] for ref in references}
    if expected:
        correct = (
            all(
                any(normalized(option) in normalized(answer) for option in group)
                for group in definition["answer_groups"]
            )
            and expected <= used
        )
        if definition.get("expected_origin"):
            correct = correct and all(
                any(
                    ref["memory_id"] == mid
                    and ref.get("evidence_origin") == definition["expected_origin"]
                    for ref in references
                )
                for mid in expected
            )
    else:
        correct = bool(UNKNOWN.search(answer))
    return bool(correct and not error and not leak and not deleted_hit and not forbidden_hit)


class MemoryEvaluator:
    def __init__(self, engine, suite, suite_sha):
        if get_settings().llm_provider != "mock":
            raise ValueError("Bulk evaluation must use Mock")
        self.engine, self.suite, self.suite_sha = engine, suite, suite_sha

    def retrieve(self, user_id, text):
        started = time.perf_counter()
        with Session(self.engine) as db, sql_stats() as stats:
            results = MemoryRetriever().retrieve(db, user_id, text, provider="mock")
            elapsed = (time.perf_counter() - started) * 1000
            context = ContextBuilder().build(MEMORY_PROMPT, results, text)
            items = [
                {
                    "id": m.fact.id,
                    "user_id": m.fact.user_id,
                    "deleted": m.fact.deleted_at is not None,
                    "source_user_id": m.message.user_id,
                }
                for m in results
            ]
        return {
            "items": items,
            "ms": round(elapsed, 3),
            "queries": stats["queries"],
            "sql_ms": round(stats["sql_ms"], 3),
            "prompt_bytes": len(context.system_prompt.encode()) + len(text.encode()) + 64,
            "selected": len(context.selected),
        }

    def run_scale(self, scale, limit=None):
        preparation = time.perf_counter()
        state, credentials = prepare_dataset(self.engine, scale, self.suite, self.suite_sha)
        preparation_seconds = time.perf_counter() - preparation
        actors = state["actors"]
        mapping = state["mapping"]
        reverse = {v: k for k, v in mapping.items()}
        with Session(self.engine) as db:
            owners = {
                row[0]: row[1]
                for row in db.execute(
                    select(MemoryFact.id, MemoryFact.user_id).where(
                        MemoryFact.user_id.in_(actors.values())
                    )
                )
            }
            deleted = set(
                db.scalars(
                    select(MemoryFact.id).where(
                        MemoryFact.user_id.in_(actors.values()), MemoryFact.deleted_at.is_not(None)
                    )
                )
            )
            text_bytes = db.scalar(
                select(func.sum(func.octet_length(MemoryFact.value))).where(
                    MemoryFact.user_id.in_(actors.values())
                )
            )
            before = data_snapshot(db, list(actors.values()))

        def session_override():
            with Session(self.engine, expire_on_commit=False) as db:
                yield db

        previous = app.dependency_overrides.get(get_session)
        app.dependency_overrides[get_session] = session_override
        clients = {}

        def login(actor):
            client = TestClient(app)
            if client.post("/api/v1/auth/login", json=credentials[actor]).status_code != 200:
                raise ValueError("Synthetic benchmark login failed")
            return client

        detach = attach_sql_metrics(self.engine)
        cases = []
        started = time.perf_counter()
        cpu = time.process_time()
        tracemalloc.start()
        try:
            clients = {actor: login(actor) for actor in actors}
            for definition in self.suite["questions"][:limit]:
                actor = definition["actor"]
                user_id = actors[actor]
                if definition["group"] == "cross_session":
                    clients[actor].post("/api/v1/auth/logout")
                    clients[actor].close()
                    clients[actor] = login(actor)
                retrieved = self.retrieve(user_id, definition["text"])
                expected = {mapping[key] for key in definition["expected"]}
                forbidden = {mapping[key] for key in definition.get("forbidden", [])}
                found = [m["id"] for m in retrieved["items"]]
                reply = {}
                error = None
                api_ms = None
                try:
                    client = clients[actor]
                    conversation = client.post("/api/v1/conversations").json()["id"]
                    began = time.perf_counter()
                    response = client.post(
                        f"/api/v1/conversations/{conversation}/messages",
                        json={
                            "content": definition["text"],
                            "client_request_id": str(uuid.uuid4()),
                        },
                    )
                    api_ms = round((time.perf_counter() - began) * 1000, 3)
                    if response.status_code != 200:
                        raise ValueError("Chat endpoint rejected benchmark request")
                    reply = response.json()["assistant_message"]
                    if reply["status"] != "completed":
                        error = reply.get("error_code") or reply["status"]
                    # A reload is a database read, not a second model request.
                    history = client.get(f"/api/v1/conversations/{conversation}/messages").json()[
                        "items"
                    ]
                    if (
                        history[-1]["id"] != reply["id"]
                        or history[-1]["content"] != reply["content"]
                        or history[-1]["memory_refs"] != reply["memory_refs"]
                    ):
                        error = "RELOAD_MISMATCH"
                except (
                    AssertionError,
                    RuntimeError,
                    ValueError,
                    TypeError,
                    KeyError,
                    SQLAlchemyError,
                ) as failure:
                    error = type(failure).__name__
                used = {ref["memory_id"] for ref in reply.get("memory_refs", [])}
                missing = used - set(owners)
                if missing:
                    with Session(self.engine) as db:
                        owners.update(
                            dict(
                                db.execute(
                                    select(MemoryFact.id, MemoryFact.user_id).where(
                                        MemoryFact.id.in_(missing)
                                    )
                                ).all()
                            )
                        )
                leak = any(
                    m["user_id"] != user_id or m["source_user_id"] != user_id
                    for m in retrieved["items"]
                ) or any(owners.get(mid) != user_id for mid in used)
                deleted_hit = bool((set(found) | used) & deleted)
                forbidden_hit = bool((set(found) | used) & forbidden)
                answer = reply.get("content", "")
                answer_ok = grade_answer(
                    definition,
                    expected,
                    reply,
                    error=error,
                    leak=leak,
                    deleted_hit=deleted_hit,
                    forbidden_hit=forbidden_hit,
                )
                cases.append(
                    {
                        "id": definition["id"],
                        "actor": actor,
                        "group": definition["group"],
                        "question": definition["text"],
                        "expected": definition["expected"],
                        "retrieved": [reverse.get(mid, mid) for mid in found],
                        "used": [reverse.get(mid, mid) for mid in sorted(used)],
                        "recall_at_5": expected <= set(found) if expected else None,
                        "top1_correct": bool(found and found[0] in expected) if expected else None,
                        "answer_correct": answer_ok,
                        "unsupported_answer": not expected and not answer_ok and not error,
                        "conflict_correct": answer_ok and not forbidden_hit
                        if definition["group"] == "conflict"
                        else None,
                        "cross_user_leakage": leak,
                        "deleted_recall": deleted_hit,
                        "forbidden_recall": forbidden_hit,
                        "retrieval_ms": retrieved["ms"],
                        "sql_queries": retrieved["queries"],
                        "sql_ms": retrieved["sql_ms"],
                        "chat_api_ms_mock": api_ms,
                        "prompt_bytes": retrieved["prompt_bytes"],
                        "evidence_items": retrieved["selected"],
                        "error": error,
                        "reply": answer[:500],
                    }
                )
            concurrent = self.concurrency(state, self.suite["questions"][:20])
            memory_current, memory_peak = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()
            detach()
            for client in clients.values():
                client.close()
            if previous is None:
                app.dependency_overrides.pop(get_session, None)
            else:
                app.dependency_overrides[get_session] = previous
        with Session(self.engine) as db:
            after = data_snapshot(db, list(actors.values()))
            paid = db.scalar(
                select(func.count())
                .select_from(ModelUsage)
                .where(ModelUsage.user_id.in_(actors.values()), ModelUsage.provider == "deepseek")
            )
        positive = [c for c in cases if c["expected"]]
        conflicts = [c for c in cases if c["group"] == "conflict"]
        unknown = [c for c in cases if not c["expected"]]

        def ratio(values, key):
            return round(sum(bool(c[key]) for c in values) / len(values), 6) if values else None

        metrics = {
            "recall_at_5": ratio(positive, "recall_at_5"),
            "top1_accuracy": ratio(positive, "top1_correct"),
            "answer_accuracy_mock": ratio(cases, "answer_correct"),
            "unsupported_answer_rate_mock": ratio(
                [c for c in unknown if not c["error"]], "unsupported_answer"
            ),
            "unsupported_answer_denominator": sum(not c["error"] for c in unknown),
            "conflict_accuracy_mock": ratio(conflicts, "conflict_correct"),
            "cross_user_leakage": sum(c["cross_user_leakage"] for c in cases),
            "deleted_memory_recall": sum(c["deleted_recall"] for c in cases),
            "retrieval_p50_ms": percentile([c["retrieval_ms"] for c in cases], 0.5),
            "retrieval_p95_ms": percentile([c["retrieval_ms"] for c in cases], 0.95),
            "chat_api_p95_ms_mock": percentile(
                [c["chat_api_ms_mock"] for c in cases if c["chat_api_ms_mock"] is not None], 0.95
            ),
            "sql_queries": sum(c["sql_queries"] for c in cases),
            "sql_total_ms": round(sum(c["sql_ms"] for c in cases), 3),
            "errors": sum(bool(c["error"]) for c in cases),
            "real_model_calls": paid,
            "max_prompt_bytes": max(c["prompt_bytes"] for c in cases),
            "max_evidence_items": max(c["evidence_items"] for c in cases),
        }
        targets = self.suite["targets"]
        gates = {
            "recall": metrics["recall_at_5"] >= targets["recall_at_5"],
            "top1": metrics["top1_accuracy"] >= targets["top1_accuracy"],
            "conflict": metrics["conflict_accuracy_mock"] is not None
            and metrics["conflict_accuracy_mock"] >= targets["conflict_accuracy"],
            "isolation": metrics["cross_user_leakage"] == 0,
            "deleted": metrics["deleted_memory_recall"] == 0,
            "unknown_policy": bool(unknown) and all(c["answer_correct"] for c in unknown),
            "latency": metrics["retrieval_p95_ms"] <= targets["retrieval_p95_ms"],
            "no_bulk_paid_calls": paid == 0,
            "context_bound": metrics["max_prompt_bytes"] <= 12000
            and metrics["max_evidence_items"] <= 5,
            "no_data_drift": before == after,
            "complete_suite": len(cases) == len(self.suite["questions"]),
            "no_errors": metrics["errors"] == 0,
        }
        return {
            "scale": scale,
            "per_user_memory_counts": {
                actor: sum(owner == user_id for owner in owners.values())
                for actor, user_id in actors.items()
            },
            # Retained for old report readers; this field is the arithmetic mean.
            "per_user_memories_before": scale // 2,
            "preparation_seconds": round(preparation_seconds, 3),
            "suite_sha256": self.suite_sha,
            "initial_snapshot": before,
            "final_snapshot": after,
            "metrics": metrics,
            "gates": gates,
            "groups": {
                g: {
                    "cases": len([c for c in cases if c["group"] == g]),
                    "answer_accuracy_mock": ratio(
                        [c for c in cases if c["group"] == g], "answer_correct"
                    ),
                }
                for g in sorted({c["group"] for c in cases})
            },
            "resources": {
                "evaluation_wall_seconds": round(time.perf_counter() - started, 3),
                "python_cpu_seconds": round(time.process_time() - cpu, 3),
                "python_allocated_current_bytes": memory_current,
                "python_allocated_peak_bytes": memory_peak,
                "fact_text_bytes": int(text_bytes or 0),
                **process_memory(),
            },
            "concurrency": concurrent,
            "cases": cases,
        }

    def concurrency(self, state, questions):
        all_questions = self.suite["questions"]
        tasks = (
            [q for q in all_questions if q["actor"] == "A"][:10]
            + [q for q in all_questions if q["actor"] == "B"][:10]
        ) * 4

        def execute(definition):
            actor = state["actors"][definition["actor"]]
            result = self.retrieve(actor, definition["text"])
            return {"ms": result["ms"], "leak": any(r["user_id"] != actor for r in result["items"])}

        started = time.perf_counter()
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(execute, tasks))
        return {
            "workers": 4,
            "requests": len(results),
            "wall_seconds": round(time.perf_counter() - started, 3),
            "retrieval_p95_ms": percentile([r["ms"] for r in results], 0.95),
            "cross_user_leakage": sum(r["leak"] for r in results),
        }
