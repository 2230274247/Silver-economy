import pytest

from app.memory.eval_dataset import load_suite
from app.memory.evaluator import grade_answer, percentile


def test_sealed_suite_has_independent_answers_and_all_required_scenarios():
    suite, sha = load_suite()
    assert sha == "a15c8558b7416f6985aa0afa4301ee3788fe05cc15a9a945bdb70cf9747193c4"
    assert len(suite["facts"]) == 100
    assert len(suite["questions"]) == 310
    assert len({q["text"] for q in suite["questions"]}) >= 200
    facts = {f["id"]: f for f in suite["facts"]}
    assert len(facts) == 100 and len({q["id"] for q in suite["questions"]}) == 310
    assert {
        "exact",
        "semantic",
        "cross_session",
        "conflict",
        "unknown",
        "deleted",
        "isolation",
        "performance",
    } <= {q["group"] for q in suite["questions"]}
    for question in suite["questions"]:
        assert question["text"].endswith("？") and len(question["text"]) <= 200
        assert bool(question["expected"]) == bool(question["answer_groups"])
        assert all(facts[key]["actor"] == question["actor"] for key in question["expected"])


@pytest.mark.parametrize("references", [[], [{"memory_id": "wrong"}]])
def test_right_year_without_the_right_source_does_not_pass(references):
    assert not grade_answer(
        {"answer_groups": [["2019"]]}, {"correct"}, {"content": "2019年", "memory_refs": references}
    )


def test_closed_answer_needs_every_fact_group_and_correct_edit_authority():
    case = {"answer_groups": [["杭州"], ["三年", "3年"]], "expected_origin": "user_edit"}
    reply = {
        "content": "你曾说在杭州工作三年",
        "memory_refs": [{"memory_id": "correct", "evidence_origin": "user_edit"}],
    }
    assert grade_answer(case, {"correct"}, reply)
    assert not grade_answer(case, {"correct"}, {**reply, "content": "在杭州待过"})
    assert not grade_answer(
        case,
        {"correct"},
        {**reply, "memory_refs": [{"memory_id": "correct", "evidence_origin": "chat"}]},
    )


@pytest.mark.parametrize("flag", ["error", "leak", "deleted_hit", "forbidden_hit"])
def test_unsafe_or_failed_answers_cannot_pass_by_containing_the_expected_text(flag):
    assert not grade_answer(
        {"answer_groups": [["2019"]]},
        {"correct"},
        {"content": "2019", "memory_refs": [{"memory_id": "correct"}]},
        **{flag: True},
    )


def test_unknown_question_requires_explicit_uncertainty_not_a_related_fact_quote():
    assert grade_answer(
        {"answer_groups": []}, set(), {"content": "没有找到足够记录，我不知道。", "memory_refs": []}
    )
    assert not grade_answer(
        {"answer_groups": []},
        set(),
        {"content": "你去过菜市场。", "memory_refs": [{"memory_id": "market"}]},
    )
    assert percentile([1, 2, 3, 4, 100], 0.95) == 100
    assert percentile([], 0.95) is None
