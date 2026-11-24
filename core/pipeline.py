# -*- coding: utf-8 -*-
"""Agent 核心链路：分类器打分 → 门控 → 大模型抽取 → 时间归一化 → 过期判定。

四种模式对应实验的四个系统变体：
    rule        仅关键词规则（不调模型）
    llm_only    纯大模型零样本（分类与抽取都交给模型）
    rule_llm    规则门控 + 大模型抽取
    full        分类器门控 + 大模型抽取（本方案）
    simple      full 的消融版：去掉提示词中的规范与示例
"""
from __future__ import annotations

import re
import time
from datetime import datetime
from functools import lru_cache
from pathlib import Path

import joblib

from . import llm, rules, timeparse

BASE = Path(__file__).resolve().parent.parent
MODEL_PATH = BASE / "models" / "clf.pkl"
GATE_LOW, GATE_HIGH = 0.35, 0.60     # 低于 LOW 判噪声，介于两者之间需要人工确认

FULL_SYSTEM = """你是校园群聊待办抽取器。请判断消息是否要求群成员完成某个具体动作，并把信息抽成结构化字段。

【判定】
is_todo=1：消息要求群成员去做一件具体的事（提交、报名、领取、填写、缴费、参加、开会、回复确认），
          事项内容可定位。
is_todo=0：纯告知（假期安排、成绩已出）、闲聊、表情图片、链接转发、广告、机器人战报。
以消息发出时的语境判断，不因今天已过期而改判。

【抽取要求】
- task：一句话说清要做什么，保留关键名词（交什么、交到哪、报名什么），不超过 30 字。
- due：只摘录消息里**原文出现**的时间表达，如 "9月14日中午12:00前"、"明天13:00"、"本周日（9.27）中午十二点之前"；
  原文没有时间就填空串，**不要自己推算或补全日期**。
- category ∈ {学业, 事务, 活动, 生活, 其他}
- evidence：支撑判断的原文片段，不超过 20 字。

【示例】
输入：明天13:00-14:00在小程序订过书的来教学楼领书
输出：{"is_todo":1,"items":[{"task":"到教学楼领取在小程序预订的书","due":"明天13:00-14:00","category":"生活","evidence":"来教学楼领书"}]}

输入：叮～国庆中秋假期安排请查收！
输出：{"is_todo":0,"items":[]}

输入：@所有人 移动应用课程作业老师已经发在iclass了，9.28晚12点之前交给我
输出：{"is_todo":1,"items":[{"task":"提交移动应用课程作业","due":"9.28晚12点之前","category":"学业","evidence":"9.28晚12点之前交给我"}]}

输出必须是 JSON：{"is_todo":0或1,"items":[{"task":"","due":"","category":"","evidence":""}]}
"""

SIMPLE_SYSTEM = """判断消息是否包含待办事项。输出 JSON：{"is_todo":0或1,"items":[{"task":"","due":""}]}"""


@lru_cache(maxsize=1)
def load_clf():
    return joblib.load(MODEL_PATH)


@lru_cache(maxsize=1)
def load_cat():
    p = BASE / "models" / "cat.pkl"
    return joblib.load(p) if p.exists() else None


def _ref_time(sent_time: str | None) -> datetime:
    if sent_time:
        m = re.match(r"(\d{4})年(\d{1,2})月(\d{1,2})日\s*(\d{1,2}):(\d{2})", sent_time.strip())
        if m:
            y, mo, d, h, mi = map(int, m.groups())
            return datetime(y, mo, d, h, mi)
    return datetime.now()


def _tokens_before() -> dict:
    return llm.stats()


def _tokens_after(before: dict) -> dict:
    after = llm.stats()
    return {k: after[k] - before[k] for k in ("prompt_tokens", "completion_tokens", "calls")}


def analyze(text: str, sent_time: str | None = None, *, mode: str = "full",
            model: str | None = None) -> dict:
    t0 = time.time()
    ref = _ref_time(sent_time)
    used = _tokens_before()
    out = {
        "text": text,
        "sent_time": sent_time,
        "mode": mode,
        "is_todo": False,
        "items": [],
        "clf_prob": None,
        "need_review": False,
        "skipped_llm": False,
        "degraded": False,
        "error": None,
    }

    # 未配置 API Key 时自动降级为“分类器 + 规则”，保证访客也能跑通整个原型
    offline = not llm.API_KEY

    # ---------- 1) 判待办：三种门控方式 ----------
    if mode == "rule" or offline:
        if offline and mode != "rule":
            # 有分类器但没有 Key：仍然用分类器判断，字段退化为规则抽取
            prob = float(load_clf().predict_proba([text])[0, 1])
            out["clf_prob"] = round(prob, 3)
            out["gate"] = "clf"
            out["degraded"] = True
            out["need_review"] = GATE_LOW <= prob < GATE_HIGH
            pred = int(prob >= GATE_LOW)
        else:
            pred, conf = rules.rule_score(text)
            out["clf_prob"] = round(conf, 3)
            out["gate"] = "rule"
        out["is_todo"] = bool(pred)
        if pred:
            out["items"] = [_mk_item(_rule_task(text), _guess_due(text), rules_category(text), ref)]
        out["latency_ms"] = int((time.time() - t0) * 1000)
        out["tokens"] = _tokens_after(used)
        return out

    if mode == "llm_only":
        gate_pass, out["gate"] = True, "none"
    elif mode == "nogate":
        prob = float(load_clf().predict_proba([text])[0, 1])
        out["clf_prob"] = round(prob, 3)
        out["gate"] = "none"          # 消融：分类器只打分，不做门控
        gate_pass = True
    elif mode == "rule_llm":
        pred, conf = rules.rule_score(text)
        out["clf_prob"] = round(conf, 3)
        gate_pass, out["gate"] = bool(pred), "rule"
        if not pred:
            out["latency_ms"] = int((time.time() - t0) * 1000)
            out["tokens"] = _tokens_after(used)
            return out
    else:  # full / simple
        prob = float(load_clf().predict_proba([text])[0, 1])
        out["clf_prob"] = round(prob, 3)
        out["gate"] = "clf"
        gate_pass = prob >= GATE_LOW
        out["need_review"] = GATE_LOW <= prob < GATE_HIGH
        if not gate_pass:
            out["skipped_llm"] = True
            out["latency_ms"] = int((time.time() - t0) * 1000)
            out["tokens"] = _tokens_after(used)
            return out

    # ---------- 2) 大模型抽取 ----------
    system = SIMPLE_SYSTEM if mode == "simple" else FULL_SYSTEM
    user = f"消息发出时间：{ref:%Y年%m月%d日 %H:%M}\n消息内容：\n{text[:1200]}"
    try:
        data = llm.chat_json([{"role": "system", "content": system},
                              {"role": "user", "content": user}],
                             model=model, max_tokens=600)
        is_todo = bool(int(data.get("is_todo", 0)))
        items = []
        for it in (data.get("items") or [])[:5]:
            items.append(_mk_item(it.get("task") or text[:30], it.get("due", ""),
                                  it.get("category") or rules_category(text), ref,
                                  it.get("evidence", "")))
        out["is_todo"] = is_todo
        out["items"] = items if is_todo else []
    except Exception as e:  # noqa: BLE001
        out["error"] = str(e)[:200]
        out["need_review"] = True

    out["latency_ms"] = int((time.time() - t0) * 1000)
    out["tokens"] = _tokens_after(used)
    return out


def _mk_item(task: str, due_text: str, category: str, ref: datetime, evidence: str = "") -> dict:
    norm = timeparse.normalize(due_text, ref) if due_text else None
    return {
        "task": (task or "").strip()[:120],
        "due_text": (due_text or "").strip(),
        "due_iso": norm["due_iso"] if norm else None,
        "has_time": bool(norm and norm["has_time"]),
        "deadline": bool(norm and norm["deadline"]),
        "category": category,
        "evidence": evidence,
        "bucket": timeparse.freshness(norm["due_iso"] if norm else None),
    }


TIME_ATOM = re.compile(
    r"(?:\d{4}年)?\d{1,2}\s*[月.．]\s*\d{1,2}\s*[日号]?"
    r"|今天|今日|明天|明日|后天|大后天"
    r"|(?:本|这|下)(?:周|星期)[一二三四五六日天]"
    r"|(?:上午|中午|下午|晚上|晚|早上)?\s*\d{1,2}\s*[:：]\s*\d{2}"
    r"|(?:上午|中午|下午|晚上|晚|傍晚|早上)?\s*(?:[一二三四五六七八九十]{1,3}|\d{1,2})\s*[点時时]"
)
MERGE_GAP = re.compile(r"[\s\-—~～到至（）()、,，]{0,6}")
TAIL = re.compile(r"\s*(之前|以前|前|截止)")


def _guess_due(text: str) -> str:
    """规则模式：抓出第一段时间表达，并把相邻的时间原子合并（粗糙但可解释）。"""
    ms = list(TIME_ATOM.finditer(text))
    if not ms:
        return ""
    start, end = ms[0].start(), ms[0].end()
    for m in ms[1:]:
        gap = text[end:m.start()]
        if MERGE_GAP.fullmatch(gap):
            end = m.end()
        else:
            break
    seg = text[start:end]
    tail = TAIL.match(text[end:end + 4])
    if tail:
        seg += tail.group(0).strip()
    return seg.strip(" 　")


def _rule_task(text: str) -> str:
    """规则模式下的任务描述：去掉 @所有人、压平换行并截断。"""
    t = re.sub(r"^[@\s\u2005]*所有人[\s\u2005]*", "", text.strip())
    t = re.sub(r"\s+", " ", t).strip()
    return t[:60] + ("…" if len(t) > 60 else "")


def rules_category(text: str) -> str:
    for kws, cat in ((("作业", "实验", "考试", "选课", "成绩", "课", "学"), "学业"),
                     (("报名", "提交", "材料", "证件", "缴费", "核对", "推荐表", "医保"), "事务"),
                     (("讲座", "宣讲", "招聘", "活动", "投票", "志愿", "会"), "活动"),
                     (("领", "取", "宿舍", "安全", "地点"), "生活")):
        if any(k in text for k in kws):
            return cat
    return "其他"


def sort_items(items: list[dict]) -> list[dict]:
    order = {"已过期": 0, "今天": 1, "三天内": 2, "一周内": 3, "更晚": 4, "未知": 5}
    return sorted(items, key=lambda x: (order.get(x["bucket"], 9), x["due_iso"] or "9999"))
