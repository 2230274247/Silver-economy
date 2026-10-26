"""Validate model suggestions against verbatim user evidence before persistence."""

import json
import re
from datetime import UTC, datetime
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator


class MemoryCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal[
        "health", "relationship", "work", "habit", "interest", "travel", "date", "event", "place"
    ]
    key: str = Field(min_length=1, max_length=128)
    value: str = Field(min_length=1, max_length=1000)
    source_excerpt: str = Field(min_length=1, max_length=2000)
    time_expression: str = Field(default="", max_length=120)
    state_text: str = Field(default="", max_length=80)

    @field_validator("key", "value", "source_excerpt")
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError("Evidence cannot be blank")
        return value


class MemoryEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reply: str = Field(min_length=1, max_length=4000, pattern=r"\S")
    memories: list[dict] = Field(max_length=3)


class MemoryExtractor:
    def parse(self, raw: str, source: str):
        envelope = MemoryEnvelope.model_validate_json(raw)
        candidates, rejected = [], 0
        for value in envelope.memories:
            try:
                if any(
                    word in source
                    for word in (
                        "如果",
                        "假如",
                        "假设",
                        "要是",
                        "别记",
                        "不要记",
                        "编造",
                        "没有受伤",
                        "没受伤",
                    )
                ):
                    raise ValueError("Hypothetical, negated or declined memory")
                item = MemoryCandidate.model_validate(value)
                if item.source_excerpt not in source or not item.source_excerpt.strip():
                    raise ValueError("No source evidence")
                # Persist only directly supported spans, never a free-form LLM life detail.
                for field in (item.key, item.value, item.time_expression, item.state_text):
                    if field and field not in item.source_excerpt:
                        raise ValueError("Unsupported detail")
                candidates.append(item)
            except (ValidationError, ValueError):
                rejected += 1
        return envelope.reply, candidates, rejected


def event_time(expression: str, reference: datetime):
    """Month/year anchors retain precision; never display them as exact event days."""
    local = reference.replace(tzinfo=UTC).astimezone(ZoneInfo("Asia/Hong_Kong"))

    def anchor(year, month=1, day=1):
        return (
            datetime(year, month, day, tzinfo=ZoneInfo("Asia/Hong_Kong"))
            .astimezone(UTC)
            .replace(tzinfo=None)
        )

    if expression == "上个月":
        year, month = (local.year - 1, 12) if local.month == 1 else (local.year, local.month - 1)
        return anchor(year, month), "month"
    if expression == "去年":
        return anchor(local.year - 1), "year"
    for pattern, precision in (
        (r"(\d{4})\s*年", "year"),
        (r"(\d{4})\s*年\s*(\d{1,2})\s*月", "month"),
        (r"(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日", "day"),
    ):
        if match := re.fullmatch(pattern, expression):
            try:
                parts = [int(value) for value in match.groups()]
                if not 1001 <= parts[0] <= 9998:
                    raise ValueError("Unsupported MySQL calendar range")
                return anchor(*parts), precision
            except ValueError:
                return None, "unknown"
    return None, "unknown"


def mock_envelope(source: str):
    """Deterministic synthetic test fixture, not a real extraction-quality claim."""
    candidates = []
    if (
        "我" in source
        and "膝盖" in source
        and any(word in source for word in ("受伤", "好了", "恢复"))
    ):
        state = next(word for word in ("受伤", "好了", "恢复") if word in source)
        candidates.append(
            {
                "kind": "health",
                "key": "膝盖",
                "value": source[:1000],
                "source_excerpt": source,
                "time_expression": "上个月" if "上个月" in source else "",
                "state_text": state,
            }
        )
    return json.dumps(
        {
            "reply": "【Mock 测试回复】已收到你的消息；这不是 DeepSeek 的真实回答。",
            "memories": candidates,
        },
        ensure_ascii=False,
    )
