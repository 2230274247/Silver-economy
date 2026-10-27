"""Bounded calendar parsing, anchored to source time; no LLM arithmetic or guessed AM/PM."""

import re
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

ZONE = ZoneInfo("Asia/Hong_Kong")
DIGITS = dict(zip("零〇一二两三四五六七八九", (0, 0, 1, 2, 2, 3, 4, 5, 6, 7, 8, 9), strict=True))
NUMBER = r"[0-9零〇一二两三四五六七八九十]+"
DATE_PATTERN = (
    r"\d{4}-\d{1,2}-\d{1,2}|(?:\d{4}年)?\d{1,2}月\d{1,2}[日号]"
    r"|今天|明天|后天|下周[一二三四五六日天]"
)
CLOCK_PATTERN = rf"\d{{1,2}}[:：]\d{{2}}|{NUMBER}[点时](?:半|一刻|三刻|(?:{NUMBER})分?)?"
PERIOD_PATTERN = r"凌晨|早上|上午|中午|下午|晚上|傍晚"


def number(value):
    if value.isascii() and value.isdigit():
        return int(value)
    if "十" in value:
        left, right = value.split("十", 1)
        return DIGITS.get(left, 1 if not left else -100) * 10 + DIGITS.get(
            right, 0 if not right else -100
        )
    if len(value) == 2 and value[0] in "零〇":
        return DIGITS.get(value[1], -1)
    return DIGITS.get(value, -1)


def calendar_day(date_text, reference):
    local = reference.replace(tzinfo=UTC).astimezone(ZONE)
    day = None
    if date_text in {"今天", "明天", "后天"}:
        day = local.date() + timedelta(days={"今天": 0, "明天": 1, "后天": 2}[date_text])
    elif match := re.fullmatch(r"下周([一二三四五六日天])", date_text):
        weekday = "一二三四五六日".find(match[1].replace("天", "日"))
        day = local.date() + timedelta(days=7 - local.weekday() + weekday)
    else:
        match = re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})", date_text)
        parts = tuple(map(int, match.groups())) if match else None
        if not parts:
            match = re.fullmatch(r"(?:(\d{4})年)?(\d{1,2})月(\d{1,2})[日号]", date_text)
            if match:
                parts = (int(match[1] or local.year), int(match[2]), int(match[3]))
        if parts:
            try:
                day = datetime(*parts).date()
            except ValueError:
                return None
    if day is None or day.year < 1000:
        return None
    return day


def clock_value(clock_text, period_text):
    if period_text not in {"", "凌晨", "早上", "上午", "中午", "下午", "晚上", "傍晚"}:
        return None
    explicit_24h = False
    if match := re.fullmatch(r"(\d{1,2})[:：](\d{2})", clock_text):
        hour, minute = map(int, match.groups())
        explicit_24h = True
    elif match := re.fullmatch(rf"({NUMBER})[点时](半|一刻|三刻|(?:{NUMBER})分?)?", clock_text):
        hour = number(match[1])
        tail = match[2] or ""
        minute = {"": 0, "半": 30, "一刻": 15, "三刻": 45}.get(tail)
        if minute is None:
            minute = number(tail.rstrip("分"))
        explicit_24h = hour == 0 or hour > 12
    else:
        return None
    if not 0 <= hour <= 23 or not 0 <= minute <= 59:
        return None
    if period_text:
        if hour == 0 and period_text != "凌晨":
            return None
        if hour > 12:
            return None  # Contradictory period/hour needs the user's clarification.
        if period_text in {"早上", "上午", "晚上", "傍晚"} and hour == 12:
            return None  # Ambiguous noon/midnight; do not silently shift a day.
        if period_text in {"下午", "晚上", "傍晚"} and 1 <= hour < 12:
            hour += 12
        elif period_text == "凌晨" and hour == 12:
            hour = 0
        elif period_text == "中午":
            if hour in {1, 2}:
                hour += 12
            elif hour not in {11, 12}:
                return None
    elif not explicit_24h:
        return None
    return hour, minute


def parse_target(date_text, clock_text, period_text, reference):
    day = calendar_day(date_text, reference)
    clock = clock_value(clock_text, period_text)
    if day is None or clock is None:
        return None
    hour, minute = clock
    return (
        datetime(day.year, day.month, day.day, hour, minute, tzinfo=ZONE)
        .astimezone(UTC)
        .replace(tzinfo=None)
    )


def time_parts(text):
    def first(pattern):
        match = re.search(pattern, text)
        return match[0] if match else ""

    return first(DATE_PATTERN), first(CLOCK_PATTERN), first(PERIOD_PATTERN)
