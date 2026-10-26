"""Reproducible fictional L0/L1 fixtures. No model, network or database imports."""

import hashlib
import json
import random
import uuid
from collections import Counter
from datetime import date, datetime, timedelta

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.memory.extractor import event_time

VERSION = "synthetic/v1"
KINDS = ("relationship", "work", "habit", "interest", "travel", "date", "health", "event", "place")
CITIES = (
    "苏州",
    "杭州",
    "青岛",
    "厦门",
    "成都",
    "南京",
    "昆明",
    "大连",
    "武汉",
    "西安",
    "福州",
    "长沙",
)
NAMES = ("林文", "陈宁", "周华", "许芳", "刘青", "沈悦", "何明", "宋安", "吴平", "赵芸")
JOBS = ("图书管理员", "木工", "会计", "教师", "电工", "园艺师", "维修员", "售货员")
ACTIVITIES = ("太极", "书法", "围棋", "散步", "摄影", "种花", "剪纸", "朗读", "京剧", "钓鱼")
STREETS = ("青松路", "文华街", "荷风巷", "竹影路", "春和街", "松柏巷", "海棠路", "桂香街")
ORG = ("春风书店", "青禾合作社", "文心学校", "新桥工厂", "松林社区", "书香图书馆")


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


class SyntheticConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    users: int = Field(2, ge=1, le=1000)
    memories: int = Field(100, ge=1, le=100000)
    seed: int = 20261027
    start_year: int = Field(2006, ge=1900, le=9997)
    end_year: int = Field(2026, ge=1900, le=9997)
    categories: tuple[str, ...] = KINDS
    duplicate_ratio: float = Field(0.1, ge=0, le=1)
    conflict_ratio: float = Field(0.1, ge=0, le=1)
    invalid_ratio: float = Field(0.1, ge=0, le=1)
    reference_date: date = date(2026, 10, 26)

    @model_validator(mode="after")
    def coherent(self):
        if self.users > self.memories:
            raise ValueError("Each synthetic user must receive at least one memory")
        if not self.start_year <= self.end_year <= self.reference_date.year:
            raise ValueError("Year range must end no later than the reference year")
        if (
            not self.categories
            or len(set(self.categories)) != len(self.categories)
            or not set(self.categories) <= set(KINDS)
        ):
            raise ValueError("Categories must be a nonempty unique selection of supported kinds")
        if self.conflict_ratio + self.invalid_ratio > 1:
            raise ValueError("Conflict and invalid fractions must not overlap")
        if self.memories - int(self.memories * self.conflict_ratio) // 2 < self.users:
            raise ValueError("Not enough independent records/pairs to populate all users")
        if self.reference_date <= date(self.start_year, 1, 3):
            raise ValueError("Reference date needs room for historical source records")
        return self

    @property
    def dataset_id(self):
        return str(
            uuid.uuid5(uuid.NAMESPACE_URL, VERSION + canonical(self.model_dump(mode="json")))
        )


def identity(config, label):
    return str(uuid.uuid5(uuid.UUID(config.dataset_id), label))


def users_for(config):
    return [
        {"id": identity(config, f"user:{i}"), "login_name": f"syn-{config.dataset_id[:12]}-{i}"}
        for i in range(config.users)
    ]


def fictional_body(rng, kind):
    city, name, street, org = (rng.choice(pool) for pool in (CITIES, NAMES, STREETS, ORG))
    number, duration = rng.randint(1, 399), rng.randint(1, 12)
    activity, job = rng.choice(ACTIVITIES), rng.choice(JOBS)
    match kind:
        case "relationship":
            relation = rng.choice(("邻居", "同学", "同事", "棋友", "表妹", "侄子"))
            return name, f"我的{relation}{name}在{city}的{org}做{job}，我们在{street}见面"
        case "work":
            return (
                org,
                f"我在{city}的{org}担任{job}，参与第{number}期项目，这段经历持续{duration}年",
            )
        case "habit":
            return (
                activity,
                f"我每周{rng.choice('一二三四五六日')}在{city}{street}练{activity}，"
                f"每次{duration * 10}分钟",
            )
        case "interest":
            return activity, f"我喜欢{activity}，和{name}在{city}完成了第{number}次练习"
        case "travel":
            return (
                city,
                f"我第{number}次去{city}旅游，和{name}游览了"
                f"{rng.choice(('古城', '湖边', '山林', '博物馆', '植物园'))}，住了{duration}天",
            )
        case "date":
            return (
                name,
                f"{name}的生日是{rng.randint(1, 12)}月{rng.randint(1, 28)}日，"
                f"我在{city}{org}为他庆祝第{number}次活动",
            )
        case "health":
            body = rng.choice(("左膝盖", "右膝盖", "左肩膀", "右脚踝", "手腕"))
            return body, f"我的{body}在{city}{street}第{number}次骑行时受伤了，休息了{duration}天"
        case "event":
            return (
                org,
                f"我和{name}约在{city}{org}参加第{number}场{activity}活动，"
                f"开始时间是{rng.randint(8, 18)}点",
            )
        case "place":
            return (
                street,
                f"我常去的{rng.choice(('读书室', '菜市场', '活动室', '小店'))}"
                f"在{city}{street}{number}号，"
                f"门前有{rng.choice(('桂花树', '石桥', '公交站', '小广场'))}",
            )
    raise ValueError("Unsupported synthetic kind")


def metadata(config):
    return {
        "record_type": "metadata",
        "generator": VERSION,
        "synthetic": True,
        "dataset_id": config.dataset_id,
        "config": config.model_dump(mode="json"),
    }


def generate_records(config):
    rng = random.Random(config.seed)
    people = users_for(config)
    pairs = int(config.memories * config.conflict_ratio) // 2
    conflict_n = pairs * 2
    invalid_n = int(config.memories * config.invalid_ratio)
    invalid = set(rng.sample(range(conflict_n, config.memories), invalid_n))
    duplicates = set(
        rng.sample(range(config.memories), int(config.memories * config.duplicate_ratio))
    )
    first = date(config.start_year, 1, 1)
    last = min(date(config.end_year, 12, 30), config.reference_date - timedelta(days=2))
    seen, pair_bodies = set(), {}
    for i in range(config.memories):
        pair = i // 2 if i < conflict_n else None
        owner_index = (
            pair % config.users if pair is not None else (pairs + i - conflict_n) % config.users
        )
        owner = people[owner_index]["id"]
        kind = (
            ("health" if "health" in config.categories else config.categories[0])
            if pair is not None
            else config.categories[(i - conflict_n) % len(config.categories)]
        )
        source_day = first + timedelta(days=rng.randint(0, (last - first).days))
        recorded = datetime.combine(source_day, datetime.min.time()).replace(hour=8)
        expression = (
            f"{source_day.year}年",
            f"{source_day.year}年{source_day.month}月",
            f"{source_day.year}年{source_day.month}月{source_day.day}日",
            "很多年前",
            "",
            "上个月",
        )[i % 6]
        if expression == "上个月":
            if config.end_year == config.reference_date.year:
                recorded = datetime.combine(config.reference_date, datetime.min.time()).replace(
                    hour=8
                )
            previous_month = recorded.date().replace(day=1) - timedelta(days=1)
            if previous_month.year < config.start_year:
                expression = f"{recorded.year}年{recorded.month}月"
        role = None
        if pair is not None:
            role = "before" if i % 2 == 0 else "after"
            if role == "before":
                key, body = fictional_body(rng, kind)
                # The named occasion makes episodes distinct, not repeated filler rows.
                body += f"，这是第{pair + 1}次相关经历"
                pair_bodies[pair] = (key, body, recorded, expression)
            else:
                key, before, prior_date, expression = pair_bodies[pair]
                recorded = prior_date + timedelta(days=1)
                if kind == "health":
                    body = f"我的{key}在第{pair + 1}次相关经历后已经恢复了"
                else:
                    _, replacement = fictional_body(rng, kind)
                    body = f"更正{key}相关的那次经历：{replacement}，请以这条第{pair + 1}次说明为准"
        else:
            key, body = fictional_body(rng, kind)
        text = f"【Synthetic】{expression}{body}"
        while text in seen:
            key, body = fictional_body(rng, kind)
            text = f"【Synthetic】{expression}{body}"
        seen.add(text)
        when, precision = event_time(expression, recorded)
        state = "historical" if role == "before" else "confirmed"
        invalid_type = None
        if i in invalid:
            invalid_type = ("deleted", "inactive", "permission_denied", "expired")[i % 4]
            if invalid_type in {"deleted", "inactive"}:
                state = invalid_type
        sources = []
        for n in range(2 if i in duplicates else 1):
            at = recorded + timedelta(hours=n)
            sources.append(
                {
                    "id": identity(config, f"source:{i}:{n}"),
                    "message_id": identity(config, f"message:{i}:{n}"),
                    "conversation_id": identity(config, f"conversation:{owner}:{at:%Y-%m}"),
                    "created_at": at.isoformat(),
                    "text": text,
                }
            )
        yield {
            "record_type": "memory",
            "ordinal": i,
            "id": identity(config, f"memory:{i}"),
            "user_id": owner,
            "kind": kind,
            "key": key,
            "value": text,
            "time_expression": expression or None,
            "event_at": when.isoformat() if when else None,
            "event_precision": precision,
            "recorded_at": recorded.isoformat(),
            "status": state,
            "invalid_type": invalid_type,
            "conflict_pair": identity(config, f"conflict:{pair}") if pair is not None else None,
            "conflict_role": role,
            "is_synthetic": True,
            "sources": sources,
        }


def dataset_lines(config):
    yield canonical(metadata(config)) + "\n"
    for record in generate_records(config):
        yield canonical(record) + "\n"


def validate_lines(lines):
    header = json.loads(next(lines))
    config = SyntheticConfig.model_validate(header["config"])
    if header != metadata(config):
        raise ValueError("Synthetic manifest/version mismatch")
    records = []
    for expected in generate_records(config):
        try:
            actual = json.loads(next(lines))
        except StopIteration:
            raise ValueError("Truncated synthetic dataset") from None
        if actual != expected:
            raise ValueError("Synthetic record differs from its reproducible manifest")
        records.append(actual)
    if next(lines, None) is not None:
        raise ValueError("Unexpected extra synthetic records")
    return config, records


def corpus_summary(config, records):
    return {
        "dataset_id": config.dataset_id,
        "generator": VERSION,
        "synthetic": True,
        "users": config.users,
        "memories": len(records),
        "source_messages": sum(len(r["sources"]) for r in records),
        "duplicate_observations": sum(len(r["sources"]) - 1 for r in records),
        "categories": dict(Counter(r["kind"] for r in records)),
        "precision": dict(Counter(r["event_precision"] for r in records)),
        "statuses": dict(Counter(r["status"] for r in records)),
        "invalid": dict(Counter(r["invalid_type"] for r in records if r["invalid_type"])),
        "conflict_records": sum(r["conflict_pair"] is not None for r in records),
        "per_user_memories": dict(Counter(r["user_id"] for r in records)),
        "unique_values": len({r["value"] for r in records}),
        "model_calls": 0,
    }
