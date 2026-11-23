# -*- coding: utf-8 -*-
"""中文时间表达的归一化。

支持：9月14日 / 9.27 / 明天 / 今天 / 后天 / 本周三 / 下周二 / 12:00 / 中午十二点 / 晚上8点
只做规则解析，不追求覆盖全部写法，解析失败返回 None（由上层标注“需人工确认”）。
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta

CN_NUM = {"零": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6,
          "七": 7, "八": 8, "九": 9, "十": 10, "十一": 11, "十二": 12}

WEEKDAY = {"一": 0, "二": 1, "三": 2, "四": 3, "五": 4, "六": 5, "日": 6, "天": 6}

DATE_MD = re.compile(r"(\d{1,2})\s*[月.．]\s*(\d{1,2})\s*[日号]?")
REL_DAY = re.compile(r"(今天|今日|明天|明日|后天|大后天)")
WEEK = re.compile(r"(本周|这周|下周|下星期|本周内)\s*[周星期]?\s*([一二三四五六日天])")
TIME_HM = re.compile(r"(\d{1,2})\s*[:：]\s*(\d{2})")
TIME_CN = re.compile(r"(上午|中午|下午|晚上|傍晚|早上|凌晨)?\s*([一二三四五六七八九十]{1,3}|\d{1,2})\s*[点時时]\s*(半|(\d{1,2})\s*分)?")
DEADLINE = re.compile(r"(截止|之前|以前|前完成|前|截至)")


def _cn2int(s: str) -> int | None:
    if s.isdigit():
        return int(s)
    if s in CN_NUM:
        return CN_NUM[s]
    if s.startswith("十"):
        return 10 + CN_NUM.get(s[1:], 0)
    if "十" in s:
        a, b = s.split("十")
        return CN_NUM.get(a, 1) * 10 + CN_NUM.get(b, 0)
    return None


def normalize(text: str, ref: datetime) -> dict | None:
    """返回 {'due_iso':..., 'date_iso':..., 'has_time':bool, 'has_date':bool, 'deadline':bool}"""
    if not text:
        return None
    has_date = False
    day = None

    m = DATE_MD.search(text)
    if m:
        mo, d = int(m.group(1)), int(m.group(2))
        if 1 <= mo <= 12 and 1 <= d <= 31:
            year = ref.year
            try:
                cand = datetime(year, mo, d)
            except ValueError:
                return None
            if (ref - cand).days > 200:           # 明显是明年的时间表达
                cand = datetime(year + 1, mo, d)
            day = cand
            has_date = True

    if day is None:
        m = REL_DAY.search(text)
        if m:
            day = ref + timedelta(days={"今天": 0, "今日": 0, "明天": 1, "明日": 1,
                                        "后天": 2, "大后天": 3}[m.group(1)])
            has_date = True

    if day is None:
        m = WEEK.search(text)
        if m:
            delta = {"本周": 0, "这周": 0, "下周": 1, "下星期": 1, "本周内": 0}[m.group(1)]
            target = WEEKDAY[m.group(2)]
            monday = ref - timedelta(days=ref.weekday())
            day = monday + timedelta(days=7 * delta + target)
            if day < ref - timedelta(days=1) and delta == 0:   # “本周三”已过 → 顺延一周
                day += timedelta(days=7)
            has_date = True

    has_time = False
    hour = minute = None
    m = TIME_HM.search(text)
    if m:
        h, mi = int(m.group(1)), int(m.group(2))
        if 0 <= h <= 23 and 0 <= mi <= 59:
            hour, minute, has_time = h, mi, True
    else:
        m = TIME_CN.search(text)
        if m:
            period, num, half = m.group(1), _cn2int(m.group(2)), m.group(3)
            if num is not None and 0 <= num <= 24:
                h = num
                if period in ("下午", "晚上", "傍晚") and h < 12:
                    h += 12
                if period == "中午" and h < 11:
                    h += 12
                hour, minute, has_time = h, 30 if half == "半" else 0, True

    if day is None and hour is None:
        return None
    base = day or ref
    dt = base.replace(hour=hour or 0, minute=minute or 0, second=0, microsecond=0)
    return {
        "due_iso": dt.isoformat(timespec="minutes"),
        "date_iso": base.date().isoformat(),
        "has_date": has_date,
        "has_time": has_time,
        "deadline": bool(DEADLINE.search(text)),
    }


def freshness(due_iso: str | None, now: datetime | None = None) -> str:
    """把截止时间映射成可排序的分组：已过期 / 今天 / 三天内 / 一周内 / 更晚 / 未知"""
    if not due_iso:
        return "未知"
    now = now or datetime.now()
    try:
        dt = datetime.fromisoformat(due_iso)
    except ValueError:
        return "未知"
    days = (dt.date() - now.date()).days
    if dt < now and days <= 0:
        return "已过期"
    if days <= 0:
        return "今天"
    if days <= 3:
        return "三天内"
    if days <= 7:
        return "一周内"
    return "更晚"
