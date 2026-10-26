import json

import pytest

from app.memory.eval_report import render_report, write_report


def sample_report():
    metrics = dict.fromkeys(
        (
            "recall_at_5",
            "top1_accuracy",
            "answer_accuracy_mock",
            "conflict_accuracy_mock",
            "unsupported_answer_rate_mock",
            "retrieval_p95_ms",
            "retrieval_p50_ms",
            "cross_user_leakage",
            "deleted_memory_recall",
            "chat_api_p95_ms_mock",
            "sql_queries",
            "sql_total_ms",
            "max_prompt_bytes",
            "max_evidence_items",
            "real_model_calls",
            "errors",
        ),
        0,
    )
    return {
        "label": '<img src=x onerror="alert(1)">',
        "created_at_hk": "2026-10-27T06:00:00+08:00",
        "status": "measured",
        "suite_questions": 1,
        "unique_question_texts": 1,
        "suite_sha256": "synthetic-test-sha",
        "scales": [
            {
                "scale": 100,
                "per_user_memories_before": 50,
                "preparation_seconds": 1,
                "metrics": metrics,
                "gates": {"recall": False},
                "groups": {},
                "initial_snapshot": {"memories": 100},
                "final_snapshot": {"memories": 100},
                "concurrency": {
                    "workers": 4,
                    "requests": 80,
                    "retrieval_p95_ms": 5,
                    "cross_user_leakage": 0,
                },
                "resources": {
                    "python_allocated_peak_bytes": 1000,
                    "python_cpu_seconds": 1,
                    "evaluation_wall_seconds": 2,
                },
                "cases": [
                    {
                        "id": "Q1",
                        "actor": "A",
                        "group": "unknown",
                        "question": "<script>bad()</script>",
                        "expected": [],
                        "retrieved": [],
                        "reply": "related quote",
                        "answer_correct": False,
                        "error": None,
                    }
                ],
            }
        ],
    }


def test_report_escapes_case_text_and_preserves_failure_and_mock_limits():
    report = sample_report()
    page = render_report(report)
    assert "<img src=x" not in page and "&lt;img" in page
    assert "<script>bad()" not in page and "&lt;script&gt;bad()" in page
    assert "未达全部门禁" in page and "不能当作真实 DeepSeek" in page
    assert "related quote" in page and "未正确回答的用例（1）" in page
    assert "https://" not in page and "fetch(" not in page


def test_report_is_repeatable_and_does_not_overwrite_prior_evidence(tmp_path):
    path = tmp_path / "report.json"
    report = sample_report()
    path.write_text(json.dumps(report), encoding="utf-8")
    target = write_report(path)
    original = target.read_bytes()
    assert write_report(path).read_bytes() == original
    report["label"] = "changed-run"
    path.write_text(json.dumps(report), encoding="utf-8")
    with pytest.raises(ValueError, match="Preserve prior"):
        write_report(path)
    assert target.read_bytes() == original


def test_comparison_discloses_changed_factual_dataset():
    report = sample_report()
    previous = sample_report()
    previous["scales"][0]["initial_snapshot"] = {"memories": 101}
    assert "不同，不能当作相同数据上的排序对比" in render_report(report, previous)


def test_population_is_actual_sql_distribution_not_assumed_even_split():
    report = sample_report()
    assert "人均 50" in render_report(report)
    report["scales"][0]["per_user_memory_counts"] = {"A": 51, "B": 49}
    assert "A 51 / B 49" in render_report(report)
