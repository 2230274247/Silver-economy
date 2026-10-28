"""SQL baseline with a small documented Chinese alias set, no paid query rewrite."""

import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, case, func, literal, or_, select

from app.memory.extractor import event_time
from app.memory.query import RELATIVES, evidence_constraints, expanded_terms
from app.models.entities import MemoryFact, MemorySource, Message, User

ALIASES = {
    "work": ("工作", "上班", "任职", "打工", "就业", "职场", "工龄", "单位"),
    "health": ("受伤", "恢复", "膝盖", "身体", "健康", "好了"),
    "travel": ("旅游", "旅行", "去过", "游玩", "出游"),
    "relationship": ("亲戚", "亲属", "家人", "朋友", "关系"),
    "interest": ("喜欢", "爱好", "兴趣"),
    "habit": ("习惯", "平时", "每天", "经常"),
    "date": ("生日", "纪念日", "重要日期"),
    "place": ("住址", "住哪", "地址", "住在"),
}
STOP_TERMS = {
    "我是",
    "我的",
    "你是",
    "你的",
    "什么",
    "怎么",
    "哪里",
    "哪年",
    "多少",
    "时候",
    "记得",
    "记忆",
    "以前",
    "曾经",
    "现在",
    "一下",
    "过几",
    "几年",
    "我曾",
    "经在",
    "在哪",
    "座城",
    "城市",
    "我在",
    "我和",
    "我去",
    "你还",
    "还记",
    "得我",
    "帮我",
    "找找",
    "找回",
    "说过",
    "过的",
    "哪种",
    "哪天",
    "是哪",
    "那种",
    "哪位",
    "哪家",
    "多久",
    "了什",
    "时我",
    "过哪",
    "一条",
    "关于",
    "目前",
    "当前",
    "最新",
    "那次",
}


@dataclass
class RetrievedMemory:
    fact: MemoryFact
    source: MemorySource
    message: Message
    score: int
    evidence_snapshot: tuple


def evidence_signature(fact):
    return (
        fact.value,
        fact.fact_status,
        fact.event_at,
        fact.time_expression,
        fact.event_precision,
        fact.confirmed_at,
        fact.retrieval_allowed,
        fact.is_synthetic,
        fact.extractor_provider,
        fact.revision,
    )


def query_terms(query):
    compact = re.sub(r"\s+", "", query.lower())[:200]
    kinds = [kind for kind, words in ALIASES.items() if any(word in compact for word in words)]
    if "work" not in kinds and re.search(r"上.{0,6}班", compact):
        kinds.append("work")
    words = re.findall(r"[a-z]{2,}|[0-9]{4}|[\u4e00-\u9fff]+", compact)
    terms = expanded_terms(compact)
    for word in words:
        candidates = (
            [word]
            if word.isascii() or len(word) <= 2
            else [word[i : i + 2] for i in range(len(word) - 1)]
        )
        for term in candidates:
            if (
                term not in STOP_TERMS
                and term not in terms
                and (
                    len(term) >= 2
                    or (
                        re.fullmatch(r"[\u4e00-\u9fff]", term)
                        and term not in "我你他她的了是吗么在哪有个年月日"
                    )
                )
            ):
                terms.append(term)
    if not words and compact:
        terms.append(compact)  # Literal punctuation search remains parameterized/escaped.
    return compact, terms[:40], kinds


def historical_query(query):
    return not any(word in query for word in ("现在", "目前", "当前", "最新")) and any(
        word in query for word in ("以前", "当时", "上次", "那次", "曾经", "发生过", "之前")
    )


def valid_context_fact(fact, now=None, *, include_historical=False):
    now = now or datetime.now(UTC).replace(tzinfo=None)
    return (
        fact.deleted_at is None
        and fact.retrieval_allowed
        and fact.fact_status
        in (
            {"candidate", "active", "confirmed", "historical"}
            if include_historical
            else {"candidate", "active", "confirmed"}
        )
        and (fact.valid_from is None or fact.valid_from <= now)
        and (
            fact.valid_to is None
            or fact.valid_to > now
            or (include_historical and fact.fact_status == "historical")
        )
    )


class MemoryRetriever:
    def retrieve(self, db, user_id, query, *, provider="mock", limit=5, for_context=True):
        if for_context and not db.scalar(select(User.memory_enabled).where(User.id == user_id)):
            return []
        compact, terms, kinds = query_terms(query)
        if not compact:
            return []
        now = datetime.now(UTC).replace(tzinfo=None)
        exact_key = func.instr(literal(compact), MemoryFact.key) > 0
        name_key = func.regexp_replace(MemoryFact.key, rf"^(?:我的)?(?:{RELATIVES})", "")
        partial_name = and_(
            name_key != MemoryFact.key,
            func.length(name_key) >= 2,
            func.instr(literal(compact), name_key) > 0,
        )
        matches = [
            exact_key,
            partial_name,
            *[MemoryFact.value.contains(term, autoescape=True) for term in terms],
        ]
        if kinds:
            matches.append(MemoryFact.kind.in_(kinds))
        score = case((exact_key, 20), (partial_name, 16), else_=0)
        for term in terms:
            score += case((MemoryFact.value.contains(term, autoescape=True), 1), else_=0)
        if kinds:
            score += case((MemoryFact.kind.in_(kinds), 8), else_=0)
        statement = select(MemoryFact, score.label("score")).where(
            MemoryFact.user_id == user_id,
            MemoryFact.deleted_at.is_(None),
            or_(*matches),
            select(MemorySource.id)
            .join(
                Message,
                and_(
                    Message.id == MemorySource.message_id, Message.user_id == MemorySource.user_id
                ),
            )
            .where(
                MemorySource.memory_id == MemoryFact.id,
                MemorySource.user_id == user_id,
                Message.role == "user",
                Message.content != "",
            )
            .exists(),
        )
        if for_context:
            # Necessary field/subject evidence prevents a broad kind match from
            # substituting another person's birthday or a trip for its unknown hotel.
            patterns, scopes = evidence_constraints(compact)
            for pattern in patterns:
                statement = statement.where(MemoryFact.value.regexp_match(pattern))
            for scope in scopes:
                statement = statement.where(MemoryFact.value.contains(scope, autoescape=True))
        if date_query := re.search(r"(?:\d{4}年|去年|今年|前年)\d{1,2}月\d{1,2}[日号]", compact):
            day, precision = event_time(date_query[0], now)
            if precision != "day":
                return []
            statement = statement.where(
                MemoryFact.event_precision == "day",
                MemoryFact.event_at >= day,
                MemoryFact.event_at < day + timedelta(days=1),
            )
        if re.search(r"吃.{0,5}(?:什么|哪道|哪种)|主菜|[早午晚](?:饭|餐)", compact):
            statement = statement.where(
                or_(
                    *[
                        MemoryFact.value.contains(word)
                        for word in (
                            "吃",
                            "用餐",
                            "午餐",
                            "晚餐",
                            "早餐",
                            "午饭",
                            "晚饭",
                            "早饭",
                            "喝粥",
                        )
                    ]
                )
            )
        if for_context:
            include_history = historical_query(query)
            statement = statement.where(
                MemoryFact.retrieval_allowed.is_(True),
                MemoryFact.fact_status.in_(
                    ["candidate", "active", "confirmed", "historical"]
                    if include_history
                    else ["candidate", "active", "confirmed"]
                ),
                or_(MemoryFact.valid_from.is_(None), MemoryFact.valid_from <= now),
                or_(
                    MemoryFact.valid_to.is_(None),
                    MemoryFact.valid_to > now,
                    and_(MemoryFact.fact_status == "historical", literal(include_history)),
                ),
            )
        if provider == "mock":
            statement = statement.where(
                or_(
                    MemoryFact.extractor_provider.in_(["mock", "synthetic", "manual"]),
                    MemoryFact.extractor_provider.is_(None),
                )
            )
        else:
            statement = statement.where(
                or_(
                    MemoryFact.extractor_provider != "mock", MemoryFact.extractor_provider.is_(None)
                )
            )
        rows = db.execute(
            statement.order_by(
                score.desc(), MemoryFact.recorded_at.desc(), MemoryFact.id.desc()
            ).limit(min(max(limit, 1), 30))
        ).all()
        result = []
        for fact, rank in rows:
            source = db.scalar(
                select(MemorySource)
                .where(MemorySource.user_id == user_id, MemorySource.memory_id == fact.id)
                .order_by(MemorySource.created_at.desc(), MemorySource.id.desc())
                .limit(1)
            )
            if source is None:
                continue  # Never send an untraceable fact to the model.
            message = db.scalar(
                select(Message).where(
                    Message.id == source.message_id,
                    Message.user_id == user_id,
                    Message.role == "user",
                )
            )
            if message is not None:
                result.append(
                    RetrievedMemory(fact, source, message, int(rank), evidence_signature(fact))
                )
        return result
