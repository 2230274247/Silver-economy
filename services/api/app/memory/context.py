import json
from dataclasses import dataclass
from datetime import UTC
from zoneinfo import ZoneInfo

from pydantic import Field

from app.memory.extractor import MemoryEnvelope, mock_envelope
from app.memory.query import supports_requested_fields

MAX_CONTEXT_BYTES = 12000
CONTEXT_MARKER = "\nMEMORY_CONTEXT_JSON="


class MemoryAnswerEnvelope(MemoryEnvelope):
    memory_refs: list[str] = Field(default_factory=list, max_length=5)


@dataclass
class MemoryContext:
    system_prompt: str
    selected: dict


class ContextBuilder:
    def build(self, base_prompt, retrieved, current_text):
        # Always reserve the full current user input; older history is expendable.
        budget = MAX_CONTEXT_BYTES - len(base_prompt.encode()) - len(current_text.encode()) - 128
        selected, data = {}, []
        for memory in retrieved[:5]:
            fact = memory.fact
            event_label = fact.time_expression or "时间未明确"
            if fact.event_at and fact.event_precision in {"year", "month", "day"}:
                event = fact.event_at.replace(tzinfo=UTC).astimezone(ZoneInfo(fact.event_timezone))
                event_label = event.strftime(
                    {"year": "%Y年", "month": "%Y年%m月", "day": "%Y年%m月%d日"}[
                        fact.event_precision
                    ]
                )
            label = f"M{len(data) + 1}"
            entry = {
                "ref": label,
                "text": fact.value,
                "event_time": event_label,
                "precision": fact.event_precision,
                "status": fact.fact_status,
                "confirmed": fact.confirmed_at is not None,
                "synthetic": fact.is_synthetic,
                "authority": fact.value_origin,
                "revision": fact.revision,
            }
            proposed = json.dumps([*data, entry], ensure_ascii=False, separators=(",", ":"))
            if len(proposed.encode()) > min(3500, budget):
                continue
            data.append(entry)
            selected[label] = memory
        payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
        return MemoryContext(base_prompt + CONTEXT_MARKER + payload, selected)


def mock_memory_answer(messages):
    source = messages[-1]["content"]
    result = json.loads(mock_envelope(source))
    memories = json.loads(messages[0]["content"].split(CONTEXT_MARKER, 1)[1])
    memories = [m for m in memories if supports_requested_fields(source, m["text"])]
    result["memory_refs"] = []
    if memories:
        first = memories[0]
        result["reply"] = (
            f"【Mock 检索测试】你曾说：{first['text']}。"
            f"记录时间范围：{first['event_time']}。这是有来源的历史表述，不代表目前状态已核实。"
        )
        result["memory_refs"] = [first["ref"]]
    elif any(
        word in source
        for word in ("记得", "记住", "哪年", "曾经", "膝盖怎么样", "什么", "哪里", "？", "?")
    ):
        result["reply"] = "【Mock 检索测试】没有找到足以回答的长期记忆，我不知道，不能替你编造。"
    return json.dumps(result, ensure_ascii=False)
