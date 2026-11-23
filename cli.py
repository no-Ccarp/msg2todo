# -*- coding: utf-8 -*-
"""命令行入口：批量评测（实验）、单条分析、数据集统计。

用法：
    python cli.py experiment            # 跑 5 组对照实验
    python cli.py analyze "消息内容"     # 单条分析
    python cli.py stats                 # 数据集统计
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from core import llm, pipeline  # noqa: E402
from core.parse import load_jsonl  # noqa: E402

BASE = Path(__file__).resolve().parent
# 价格假设（元 / 百万 token），deepseek 低价档量级；报告中会注明这是估计值
PRICE_IN, PRICE_OUT = 1.0, 2.0

MODES = ["rule", "llm_only", "rule_llm", "full", "nogate"]
MODE_NAME = {
    "rule": "A 规则基线",
    "llm_only": "B 纯大模型零样本",
    "rule_llm": "C 规则门控+大模型",
    "full": "D 分类器门控+大模型（本方案）",
    "nogate": "E 消融：去掉分类器门控",
}

DATE_TOKEN = re.compile(r"\d{1,2}\s*[月.．]\s*\d{1,2}|\d{1,2}\s*[:：]\s*\d{2}|明天|今天|后天|本周|下周")


def tokens_in_text(s: str) -> set[str]:
    return {re.sub(r"\s", "", t) for t in DATE_TOKEN.findall(s or "")}


def due_hit(gold_due: str, pred_due: str) -> bool | None:
    """金标准 due 里的日期数字是否被预测覆盖；金标准无日期则返回 None（不计入）。"""
    g = tokens_in_text(gold_due)
    if not g:
        return None
    p = re.sub(r"\s", "", pred_due or "")
    return any(t in p for t in g)


def prf(tp: int, fp: int, fn: int) -> dict:
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    f = 2 * p * r / (p + r) if p + r else 0.0
    return {"precision": round(p, 4), "recall": round(r, 4), "f1": round(f, 4)}


def run_mode(mode: str, rows: list[dict], gold: dict) -> dict:
    llm.reset_stats()

    def work(r):
        return pipeline.analyze(r["text"], r["time"], mode=mode)

    preds = llm.pmap(work, rows, workers=6)

    tp = fp = fn = tn = 0
    due_ok = due_n = 0
    for r, p in zip(rows, preds):
        g = gold[r["id"]]["actionable"]
        pred = 1 if p["is_todo"] else 0
        tp += pred == 1 and g == 1
        fp += pred == 1 and g == 0
        fn += pred == 0 and g == 1
        tn += pred == 0 and g == 0
        if g == 1:
            hit = due_hit(gold[r["id"]]["due"], " ".join(i["due_text"] for i in p["items"]))
            if hit is not None:
                due_n += 1
                due_ok += hit
    st = llm.stats()
    cost = (st["prompt_tokens"] / 1e6 * PRICE_IN) + (st["completion_tokens"] / 1e6 * PRICE_OUT)
    return {
        "mode": mode,
        "name": MODE_NAME[mode],
        "n": len(rows),
        "confusion": {"tp": tp, "fp": fp, "fn": fn, "tn": tn},
        "acc": round((tp + tn) / len(rows), 4),
        **prf(tp, fp, fn),
        "due_acc": round(due_ok / due_n, 4) if due_n else None,
        "due_n": due_n,
        "latency_ms_avg": round(sum(p["latency_ms"] for p in preds) / len(preds), 1),
        "calls": st["calls"],
        "cache_hits": st["cache_hits"],
        "prompt_tokens": st["prompt_tokens"],
        "completion_tokens": st["completion_tokens"],
        "cost_yuan": round(cost, 4),
        "errors": sum(1 for p in preds if p["error"]),
        "preds": preds,
    }


def experiment() -> None:
    rows_all = load_jsonl(BASE / "data" / "messages.jsonl")
    gold = {l["id"]: l for l in load_jsonl(BASE / "data" / "labels.jsonl")}
    split = json.loads((BASE / "data" / "split.json").read_text(encoding="utf-8"))
    by_id = {r["id"]: r for r in rows_all}
    rows = [by_id[i] for i in split["test"]]
    print(f"实验测试集：{len(rows)} 条，其中待办 {sum(gold[r['id']]['actionable'] for r in rows)} 条\n")

    results = []
    for mode in MODES:
        res = run_mode(mode, rows, gold)
        results.append(res)
        print(f"{res['name']:<26} P={res['precision']:.3f} R={res['recall']:.3f} "
              f"F1={res['f1']:.3f} Acc={res['acc']:.3f} 日期={res['due_acc']} "
              f"延迟={res['latency_ms_avg']}ms 调用={res['calls']} 成本=¥{res['cost_yuan']}")

    out = BASE / "results" / "experiment.json"
    slim = []
    for r in results:
        preds = r.pop("preds")
        (BASE / "results" / f"preds_{r['mode']}.json").write_text(
            json.dumps(preds, ensure_ascii=False, indent=1), encoding="utf-8")
        slim.append(r)
    out.write_text(json.dumps(slim, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n已保存 {out}")


def stats() -> None:
    rows = load_jsonl(BASE / "data" / "messages.jsonl")
    gold = {l["id"]: l for l in load_jsonl(BASE / "data" / "labels.jsonl")}
    from collections import Counter
    print("消息总数:", len(rows))
    print("按群:", dict(Counter(r["group"] for r in rows)))
    print("待办数:", sum(gold[r["id"]]["actionable"] for r in rows))
    print("类别:", dict(Counter(gold[r["id"]]["category"] for r in rows if gold[r["id"]]["actionable"])))


def main() -> None:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "stats"
    if cmd == "experiment":
        experiment()
    elif cmd == "analyze":
        text = sys.argv[2]
        res = pipeline.analyze(text, mode="full")
        print(json.dumps(res, ensure_ascii=False, indent=1))
    else:
        stats()


if __name__ == "__main__":
    main()
