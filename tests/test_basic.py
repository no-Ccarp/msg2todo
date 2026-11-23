# -*- coding: utf-8 -*-
"""离线自检（不调用大模型）：数据解析、时间归一化、规则、导出。

运行：python tests/test_basic.py
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))

from core import rules, timeparse  # noqa: E402
from core.parse import load_jsonl  # noqa: E402

passed = failed = 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global passed, failed
    if cond:
        passed += 1
        print(f"  PASS  {name}")
    else:
        failed += 1
        print(f"  FAIL  {name}  {detail}")


def main() -> None:
    ref = datetime(2026, 9, 12, 17, 54)   # 周六

    print("[时间归一化]")
    cases = [
        ("明天13:00-14:00在小程序订过书的来教学楼领书", "2026-09-13T13:00"),
        ("9.28晚12点之前交给我", "2026-09-28T12:00"),
        ("本周日（9.27）中午十二点之前填写", "2026-09-27T12:00"),
        ("下周二12:00截止", "2026-09-15T12:00"),
        ("今天下午3点来领", "2026-09-12T15:00"),
        ("11月16日（下周一）上午八点前进入教室", "2026-11-16T08:00"),
    ]
    for text, want in cases:
        got = timeparse.normalize(text, ref)
        check(f"{text[:18]}", bool(got) and got["due_iso"] == want,
              f"得到 {got and got['due_iso']}，期望 {want}")

    print("[时间分组]")
    now = datetime(2026, 9, 12, 18, 0)
    check("已过期", timeparse.freshness("2026-09-12T13:00", now) == "已过期")
    check("今天", timeparse.freshness("2026-09-12T23:00", now) == "今天")
    check("三天内", timeparse.freshness("2026-09-14T10:00", now) == "三天内")
    check("未知", timeparse.freshness(None, now) == "未知")

    print("[规则基线]")
    check("闲聊判否", rules.rule_score("哈哈哈哈笑死我了")[0] == 0)
    check("机器人战报判否", rules.rule_score("╔═══部落战═══")[0] == 0)
    check("待办判是", rules.rule_score("明天13:00前把表交给我")[0] == 1)

    print("[数据文件]")
    rows = load_jsonl(BASE / "data" / "messages.jsonl")
    labels = load_jsonl(BASE / "data" / "labels.jsonl")
    check("消息 300 条", len(rows) == 300, str(len(rows)))
    check("标签与消息一一对应", {r["id"] for r in rows} == {l["id"] for l in labels})
    check("三个群各 100 条", all(sum(1 for r in rows if r["group"] == g) == 100
                                for g in ("[群1]", "[群2]", "[群3]")))
    import re
    check("无残留手机号", not any(re.search(r"1[3-9]\d{9}", r["text"]) for r in rows))
    check("消息非空", all(r["text"].strip() for r in rows))

    print("[导出]")
    from app.main import export_docx, export_xlsx
    items = [{"task": "提交作业", "due_text": "9.28前", "due_iso": "2026-09-28T12:00",
              "category": "学业", "bucket": "已过期", "need_review": False, "source_text": "原文"}]
    xb = export_xlsx(items)
    db = export_docx(items)
    check("xlsx 为 ZIP 容器", xb[:2] == b"PK" and len(xb) > 3000, str(len(xb)))
    check("docx 为 ZIP 容器", db[:2] == b"PK" and len(db) > 30000, str(len(db)))

    print(f"\n通过 {passed} 项，失败 {failed} 项")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
