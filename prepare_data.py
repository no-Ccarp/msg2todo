# -*- coding: utf-8 -*-
"""把 LLM 预标注 + 人工复核的结果固化为金标准，并生成数据划分。

人工复核记录：逐条核对 300 条，修正 7 条（一致率 97.7%），修正项见 OVERRIDES。
"""
from __future__ import annotations

import json
import random
from collections import Counter, defaultdict
from pathlib import Path

from core.parse import load_jsonl, save_jsonl

BASE = Path(__file__).resolve().parent
SEED = 20261123

# 人工复核后对 LLM 预标注的修正（原因写在注释里）
OVERRIDES = {
    "M125": (1, "其他", ""),   # “对标自查…尽快完成”属明确行动要求，原判 0 偏保守
    "M126": (1, "活动", ""),   # “积极报名献血”是报名类动作
    "M129": (1, "事务", ""),   # “投递简历”为对群成员的指令
    "M141": (0, "其他", ""),   # 实习岗位介绍，无截止/无指令，属信息分享
    "M142": (0, "其他", ""),   # 同上
    "M145": (0, "生活", ""),   # 五一假期安排，纯告知
    "M201": (1, "事务", ""),   # “就业系统学生信息核对”含核对动作
}


def main() -> None:
    rows = load_jsonl(BASE / "data" / "messages.jsonl")
    auto = {l["id"]: l for l in load_jsonl(BASE / "data" / "labels_auto.jsonl")}

    labels = []
    for r in rows:
        a = auto[r["id"]]
        act, cat, due = a["actionable"], a["category"], a["due"]
        if r["id"] in OVERRIDES:
            act, cat, due = OVERRIDES[r["id"]]
        labels.append({"id": r["id"], "actionable": int(act), "category": cat, "due": due})
    save_jsonl(labels, BASE / "data" / "labels.jsonl")

    lab = {l["id"]: l for l in labels}
    pos = sum(l["actionable"] for l in labels)
    print(f"金标准：{len(labels)} 条，正例 {pos} 条（{pos/len(labels):.1%}）")
    print("按群正例率:", {g: f"{sum(lab[r['id']]['actionable'] for r in rows if r['group']==g)}/{sum(1 for r in rows if r['group']==g)}"
                        for g in dict.fromkeys(r["group"] for r in rows)})
    print("类别分布:", dict(Counter(l["category"] for l in labels if l["actionable"])))

    # ---- 划分 1：随机分层（主实验用，60 条测试集）----
    rnd = random.Random(SEED)
    buckets = defaultdict(list)
    for r in rows:
        buckets[(r["group"], lab[r["id"]]["actionable"])].append(r["id"])
    test_ids, train_ids = [], []
    for key, ids in sorted(buckets.items()):
        rnd.shuffle(ids)
        n_test = max(2, round(len(ids) * 0.2))
        test_ids += ids[:n_test]
        train_ids += ids[n_test:]
    test_ids.sort()
    train_ids.sort()

    # ---- 划分 2：跨群（年级+娱乐训练，班级测试）----
    cross_train = [r["id"] for r in rows if r["group"] in ("[群1]", "[群2]")]
    cross_test = [r["id"] for r in rows if r["group"] == "[群3]"]

    split = {
        "seed": SEED,
        "test": test_ids,
        "train": train_ids,
        "cross_train": cross_train,
        "cross_test": cross_test,
    }
    (BASE / "data" / "split.json").write_text(json.dumps(split, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"主实验划分：train {len(train_ids)} / test {len(test_ids)}"
          f"（test 正例 {sum(lab[i]['actionable'] for i in test_ids)}）")
    print(f"跨群划分：train {len(cross_train)} / test {len(cross_test)}"
          f"（跨群 test 正例 {sum(lab[i]['actionable'] for i in cross_test)}）")


if __name__ == "__main__":
    main()
