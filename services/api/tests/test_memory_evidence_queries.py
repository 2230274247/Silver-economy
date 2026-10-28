"""Independent counterexamples to topical matching and accepting questions as events."""

import json

import pytest

from app.memory.context import CONTEXT_MARKER, mock_memory_answer
from app.memory.extractor import MemoryExtractor, mock_envelope
from app.memory.query import supports_requested_fields
from app.memory.retriever import historical_query, query_terms


def test_latest_state_takes_precedence_over_that_event_wording():
    assert not historical_query("河滨步道那次脚踝的最新恢复状态是什么？")
    assert historical_query("河滨步道那次脚踝受伤时发生了什么？")


def test_short_chinese_question_retains_topic_word():
    assert "午休" in query_terms("午休多久？")[1]


def test_related_address_is_not_evidence_of_floor_area():
    evidence = [{"ref": "M1", "text": "我住在桂花巷9号", "event_time": "未明确"}]
    messages = [
        {"role": "system", "content": CONTEXT_MARKER + json.dumps(evidence)},
        {"role": "user", "content": "桂花巷9号那套房子面积有多少平方米？"},
    ]
    reply = json.loads(mock_memory_answer(messages))
    assert "不知道" in reply["reply"] and reply["memory_refs"] == []


def test_compound_question_does_not_create_an_injury_fact():
    question = "你还记得吗，我的膝盖受伤的事情？"
    _, candidates, rejected = MemoryExtractor().parse(mock_envelope(question), question)
    assert candidates == [] and rejected == 1


@pytest.mark.parametrize(
    "question,known,unrelated",
    [
        ("姐姐秋云的生日是哪天？", "姐姐秋云生日是6月2日", "女儿明月生日是8月7日"),
        ("我和建平去哪旅游了？", "我和建平去过丽江", "我和文轩去过丽江"),
        ("这套房的面积是多少？", "这套房的面积是90平方米", "这套房在桂花巷9号"),
        ("我午休多久？", "我午休四十分钟", "我每天晚上练太极四十分钟"),
        ("我用相机拍什么？", "我摄影时爱拍山水", "我喜欢围棋"),
        ("姐姐秋云同去丽江的年份是？", "我和姐姐秋云去过丽江", "我和姐姐文轩去过丽江"),
        ("给女儿明月过生日是哪天？", "女儿明月生日是8月7日", "女儿秋云生日是6月2日"),
        ("郑叔叔最爱养什么花？", "郑叔叔最爱养月季", "郑叔叔爱晨练"),
        ("在文华书屋参加读书会是哪天？", "我在文华书屋读书", "我在明湖书屋读书"),
        ("我吃过哪道主菜？", "我吃了烧鱼", "我去菜市场买花盆"),
        ("郑叔叔家是几号门牌？", "郑叔叔住在荷塘街31号", "郑叔叔喜欢养月季"),
        ("翻旧事，秋云同行的丽江之旅是哪年？", "我和秋云去了丽江", "我和文轩去了丽江"),
        ("帮我找找建平一起去广州的日子？", "我和建平去了广州", "我和文轩去了广州"),
        ("哪位同事住在我隔壁？", "我的同事宋安住在我隔壁", "我的同事宋安在广州任职"),
    ],
)
def test_field_constraints_reject_related_but_insufficient_evidence(question, known, unrelated):
    assert supports_requested_fields(question, known)
    assert not supports_requested_fields(question, unrelated)
