"""Single-call task hints and verbatim grounding; never creates a scheduled reminder."""

import json
import re
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select

from app.core.config import PROJECT_ROOT
from app.memory.context import MAX_CONTEXT_BYTES
from app.models.entities import TaskDraft
from app.schemas.tasks import TaskCandidate
from app.tasks.time_parse import CLOCK_PATTERN, parse_target, relative_target, time_parts

TASK_MARKER = "\nTASK_DRAFT_CONTEXT_JSON="
TASK_PROMPT = (PROJECT_ROOT / "prompts/task-intent-v3.txt").read_text(encoding="utf-8").strip()
MODES = {
    "taxi": ("打车", "出租车"),
    "driving": ("开车", "自驾"),
    "transit": ("公交", "地铁"),
    "walking": ("步行", "走路"),
    "cycling": ("骑车", "骑行"),
}
DECLINED = re.compile(
    r"如果|假如|假设|举例|比如|不要提醒|不用提醒|别提醒|不要安排|(?:他|她|别人)说"
)
NEW_TASK = re.compile(
    r"提醒|闹钟|安排.{0,10}(?:出行|出门|行程)|(?:明天|后天|今天|下周|\d+月\d+[日号]).*(?:去|出发|出门|拜访|开(?:个)?会|会议)"
)
ARRIVAL = re.compile(r"到达|抵达|(?:点|时|:\d{2}|：\d{2}).{0,3}到(?!时候)")
DEPARTURE = re.compile(r"(?:点|时|:\d{2}|：\d{2}).{0,4}(?:出发|出门)")
TEXT_FIELDS = ("date_text", "clock_text", "period_text", "origin", "destination")


def negated_modes(text):
    return {
        mode
        for mode, words in MODES.items()
        for word in words
        if re.search(
            r"(?:不|没|别|不要|不用|不想|不打算)(?:自己|坐|乘|骑|开)?" + re.escape(word), text
        )
    }


def explicit_modes(text):
    denied = negated_modes(text)
    return [
        mode
        for mode, words in MODES.items()
        if mode not in denied and any(word in text for word in words)
    ]


@dataclass
class TaskContext:
    prompt: str
    revisions: dict[str, int]


def task_context(db, item, base_prompt):
    source = item.content
    if DECLINED.search(source):
        return None
    date, clock, period = time_parts(source)
    requested_at = parse_target(date, clock, period, item.created_at)
    future = (
        bool(re.search(r"明天|后天|下周|明早|明晚", source))
        or bool(requested_at and requested_at > item.created_at)
        or date == "今天"
        and bool(clock)
    )
    if re.search(r"上次|以前|当年|曾经|去年|前年|昨天|上个月|刚才", source) and not future:
        return None  # “提醒我上次…” is memory recall, not a request to schedule a new task.
    new_task = bool(NEW_TASK.search(source))
    continuation = (
        bool(re.search(CLOCK_PATTERN, source))
        or any(word in source for words in MODES.values() for word in words)
        or bool(re.search(r"从.{1,50}出发", source))
    )
    if not new_task and not continuation:
        return None
    pending = db.scalars(
        select(TaskDraft)
        .where(
            TaskDraft.user_id == item.user_id,
            TaskDraft.conversation_id == item.conversation_id,
            TaskDraft.status == "draft",
        )
        .order_by(TaskDraft.created_at.desc(), TaskDraft.id.desc())
        .limit(3)
    ).all()
    if not pending and not new_task:
        return None
    prompt = base_prompt + "\n" + TASK_PROMPT
    remaining = MAX_CONTEXT_BYTES - len(prompt.encode()) - len(source.encode()) - 192
    data, revisions = [], {}
    for draft in pending:
        row = {
            "id": draft.id,
            "kind": draft.kind,
            "date_text": draft.date_text,
            "clock_text": draft.clock_text,
            "period_text": draft.period_text,
            "origin": draft.origin,
            "destination": draft.destination,
            "time_semantics": draft.time_semantics,
            "transport": draft.transport,
        }
        encoded = json.dumps([*data, row], ensure_ascii=False, separators=(",", ":"))
        if len(encoded.encode()) <= min(2000, remaining):
            data.append(row)
            revisions[draft.id] = draft.revision
    return TaskContext(
        prompt + TASK_MARKER + json.dumps(data, ensure_ascii=False, separators=(",", ":")),
        revisions,
    )


def grounded(candidate: TaskCandidate, source):
    if (
        DECLINED.search(source)
        or not candidate.source_excerpt.strip()
        or candidate.source_excerpt not in source
    ):
        return None
    item = candidate.model_copy(deep=True)
    relative = relative_target(item.source_excerpt, datetime.min)
    for field in TEXT_FIELDS:
        value = getattr(item, field)
        if value and value not in item.source_excerpt:
            setattr(item, field, "")  # Inferred details become missing fields, never facts.
    # Keep literal calendar parts when a model combines them as "明天下午".
    for value in (item.date_text, item.clock_text):
        date, clock, period = time_parts(value)
        if date:
            item.date_text = date
        if clock:
            item.clock_text = clock
        if period and not item.period_text:
            item.period_text = period
    if relative and not re.search(CLOCK_PATTERN, item.source_excerpt):
        item.date_text, item.clock_text, item.period_text = relative[0], "", ""
        if "提醒" in item.source_excerpt:
            item.kind = "reminder"
    if item.destination and not relative and re.search(r"去|到达|拜访", item.source_excerpt):
        item.kind = "outing"
    modes = explicit_modes(item.source_excerpt)
    if item.transport != "unknown" and modes != [item.transport]:
        item.transport = "unknown"
    arrival = bool(ARRIVAL.search(item.source_excerpt))
    departure = bool(DEPARTURE.search(item.source_excerpt))
    if item.time_semantics == "arrival" and (not arrival or departure):
        item.time_semantics = "unknown"
    if item.time_semantics == "departure" and (not departure or arrival):
        item.time_semantics = "unknown"
    if item.kind == "outing" and item.time_semantics == "at":
        item.time_semantics = "unknown"
    return item


def mock_task_output(messages, base):
    source = messages[-1]["content"]
    payload = messages[0]["content"].split(TASK_MARKER, 1)[1].split("\nMEMORY_CONTEXT_JSON=", 1)[0]
    pending = json.loads(payload)
    result = json.loads(base)
    from app.memory.extractor import mock_envelope

    # Preserve an explicit current fact alongside an arrangement without calling a second model.
    result["memories"] = [
        candidate
        for clause in re.split(r"[，。；;]", source)
        for candidate in json.loads(mock_envelope(clause))["memories"]
    ][:3]
    result["outings"] = []
    if DECLINED.search(source):
        return json.dumps(result, ensure_ascii=False)
    parts = re.split(r"[；;]|(?:另外|还有一件事)", source)
    for part in parts[:3]:
        if not part.strip():
            continue
        old = pending[0] if len(pending) == 1 and not NEW_TASK.search(part) else None
        date, clock, period = time_parts(part)
        destination = re.search(
            r"(?:去|到达|到)([^，。！？\n]{1,100}?)(?=做客|拜访|吃饭|，|。|！|？|$)", part
        )
        origin = re.search(r"从([^，。！？\n]{1,100}?)(?:出发|出门)", part)
        modes = explicit_modes(part)
        mode = modes[0] if len(modes) == 1 else "unknown"
        semantics = (
            "arrival"
            if ARRIVAL.search(part)
            else "departure"
            if DEPARTURE.search(part)
            else "unknown"
        )
        kind = (
            old["kind"]
            if old
            else "outing"
            if re.search(r"去|出门|出发|拜访|到达", part)
            else "reminder"
        )
        result["outings"].append(
            {
                "draft_id": old["id"] if old else "",
                "kind": kind,
                "source_excerpt": part,
                "date_text": date,
                "clock_text": clock,
                "period_text": period,
                "origin": origin[1] if origin else "",
                "destination": destination[1] if destination else "",
                "transport": mode,
                "time_semantics": semantics,
            }
        )
    return json.dumps(result, ensure_ascii=False)
