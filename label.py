# -*- coding: utf-8 -*-
"""用大模型按统一标注规范批量预标注，产出 labels_auto.jsonl。

规范（同时是报告里“标注规范”一节的来源）：
1) actionable=1：消息要求群成员在某个时间点/截止时间前完成一个具体动作
   （提交、报名、领取、填写、缴费、参加、开会、回复确认），
   且动作对象可定位（有事项内容，并至少给出时间/地点/方式之一）。
2) actionable=0：其余情况——纯信息告知（如假期安排、成绩已出但无动作要求）、
   闲聊、表情/图片、链接转发、广告、机器人战报、无对象的感叹。
3) 判定以“消息发出时”的语境为准，不因今天已过期而改判（是否过期由运行时规则计算）。
4) category ∈ {学业, 事务, 活动, 生活, 其他}
5) due：原文中的时间表达（如“9月14日中午12:00前”），没有则空串。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import llm  # noqa: E402
from core.parse import load_jsonl, save_jsonl  # noqa: E402

BASE = Path(__file__).resolve().parent
BATCH = 20

SYSTEM = """你是高校学生群聊的标注员。请严格按下面的规范给每条消息打标，只输出 JSON。

【规范】
1) actionable=1：消息要求群成员在某个时间点或截止时间前完成一个具体动作（提交、报名、领取、填写、缴费、参加、开会、回复确认），且事项内容可定位，并至少给出时间/地点/方式之一。
2) actionable=0：其余情况——纯信息告知、闲聊、表情图片、链接转发、广告、机器人战报、无对象的感叹。
3) 以消息发出时的语境判断，不因今天已过期而改判。
4) category 只能是：学业（课程/作业/考试/成绩/选课/教材）、事务（报名/材料提交/证件/缴费/信息核对/就业手续）、活动（讲座/比赛/志愿服务/社团）、生活（取件/领书/地点/宿舍/安全提醒）、其他。
5) due 填原文中的时间表达（如“9月14日中午12:00前”），没有就填空串。

【输出格式】
{"items":[{"id":"M001","actionable":1,"category":"事务","due":"9月14日中午12:00前"}]}
"""


def batch_prompt(rows: list[dict]) -> str:
    lines = []
    for r in rows:
        txt = r["text"].replace("\n", " / ")[:400]
        lines.append(f'{r["id"]} | {r["time"]} | {txt}')
    return "请标注下列消息：\n" + "\n".join(lines)


def label_batches(rows: list[dict]) -> list[dict]:
    chunks = [rows[i:i + BATCH] for i in range(0, len(rows), BATCH)]

    def work(chunk):
        try:
            out = llm.chat_json([
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": batch_prompt(chunk)},
            ], max_tokens=2000)
            got = {str(it["id"]): it for it in out.get("items", [])}
            res = []
            for r in chunk:
                it = got.get(r["id"], {})
                res.append({
                    "id": r["id"],
                    "actionable": int(bool(it.get("actionable", 0))),
                    "category": it.get("category", "其他"),
                    "due": it.get("due", ""),
                })
            return res
        except Exception as e:  # noqa: BLE001
            print("批次失败:", chunk[0]["id"], repr(e)[:120])
            return [{"id": r["id"], "actionable": 0, "category": "其他", "due": ""} for r in chunk]

    print(f"共 {len(chunks)} 批，并发 4 ...")
    results = llm.pmap(work, chunks, workers=4)
    flat = [x for sub in results for x in sub]
    order = {r["id"]: i for i, r in enumerate(rows)}
    flat.sort(key=lambda d: order[d["id"]])
    return flat


def main() -> None:
    rows = load_jsonl(BASE / "data" / "messages.jsonl")
    labels = label_batches(rows)
    save_jsonl(labels, BASE / "data" / "labels_auto.jsonl")
    pos = sum(l["actionable"] for l in labels)
    print(f"完成 {len(labels)} 条，正例 {pos} 条 ({pos/len(labels):.0%})")
    print("用量:", llm.stats())


if __name__ == "__main__":
    main()
