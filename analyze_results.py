# -*- coding: utf-8 -*-
"""生成实验图表与错误分析清单。"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

BASE = Path(__file__).resolve().parent
RES = BASE / "results"
plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False
COLORS = ["#868e96", "#4dabf7", "#f59f00", "#3b5bdb", "#e64980"]


def load():
    exp = json.loads((RES / "experiment.json").read_text(encoding="utf-8"))
    labels = {l["id"]: l for l in (l for l in map(json.loads, (BASE / "data" / "labels.jsonl").read_text(encoding="utf-8").splitlines()))}
    rows = {r["id"]: r for r in map(json.loads, (BASE / "data" / "messages.jsonl").read_text(encoding="utf-8").splitlines())}
    split = json.loads((BASE / "data" / "split.json").read_text(encoding="utf-8"))
    preds = {m: json.loads((RES / f"preds_{m}.json").read_text(encoding="utf-8")) for m in
             [e["mode"] for e in exp]}
    return exp, labels, rows, split, preds


def fig_metrics(exp):
    names = [e["name"].split(" ")[0] for e in exp]
    metrics = ["precision", "recall", "f1"]
    cn = ["精确率", "召回率", "F1"]
    x = np.arange(len(exp))
    w = 0.26
    fig, ax = plt.subplots(figsize=(8.6, 4.2), dpi=170)
    for i, (m, c) in enumerate(zip(metrics, ["#3b5bdb", "#f59f00", "#2f9e44"])):
        vals = [e[m] for e in exp]
        bars = ax.bar(x + (i - 1) * w, vals, w, label=cn[i], color=c, alpha=.9)
        for b, v in zip(bars, vals):
            ax.text(b.get_x() + b.get_width() / 2, v + .012, f"{v:.3f}", ha="center", fontsize=7.5)
    ax.set_xticks(x, names)
    ax.set_ylim(0, 1.0)
    ax.set_ylabel("分数")
    ax.set_title("五种方案在 60 条测试消息上的检测指标", fontsize=11)
    ax.legend(frameon=False, ncol=3, loc="upper right", fontsize=9)
    ax.grid(axis="y", alpha=.25)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    fig.tight_layout()
    fig.savefig(RES / "fig_metrics.png")
    plt.close(fig)


def fig_cost(exp):
    fig, ax = plt.subplots(figsize=(6.4, 4.2), dpi=170)
    for i, (e, c) in enumerate(zip(exp, COLORS)):
        ax.scatter(e["cost_yuan"], e["f1"], s=90, color=c, zorder=3)
        dy = -14 if e["mode"] == "nogate" else 5
        ax.annotate(e["name"].split(" ")[0], (e["cost_yuan"], e["f1"]),
                    textcoords="offset points", xytext=(7, dy), fontsize=9)
    ax.set_xlabel("处理 60 条消息的模型成本（元）")
    ax.set_ylabel("F1")
    ax.set_title("效果—成本权衡（左上为佳）", fontsize=11)
    ax.grid(alpha=.25)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    fig.tight_layout()
    fig.savefig(RES / "fig_cost.png")
    plt.close(fig)


def fig_cm(exp, preds, labels, split):
    d = next(e for e in exp if e["mode"] == "full")
    c = d["confusion"]
    cm = np.array([[c["tn"], c["fp"]], [c["fn"], c["tp"]]], dtype=int)
    fig, ax = plt.subplots(figsize=(4.4, 3.9), dpi=170)
    im = ax.imshow(cm, cmap="Blues")
    for (i, j), v in np.ndenumerate(cm):
        ax.text(j, i, str(int(v)), ha="center", va="center", fontsize=13,
                color="white" if v > cm.max() / 2 else "#1d2433")
    ax.set_xticks([0, 1], ["预测非待办", "预测待办"])
    ax.set_yticks([0, 1], ["实际非待办", "实际待办"])
    ax.set_title("本方案（D）混淆矩阵", fontsize=11)
    fig.colorbar(im, ax=ax, fraction=.046)
    fig.tight_layout()
    fig.savefig(RES / "fig_cm.png")
    plt.close(fig)


def fig_data(labels, rows):
    groups = ["[群1]", "[群2]", "[群3]"]
    gname = {"[群1]": "娱乐群", "[群2]": "年级群", "[群3]": "班级群"}
    pos = [sum(1 for i in labels if rows[i]["group"] == g and labels[i]["actionable"]) for g in groups]
    neg = [sum(1 for i in labels if rows[i]["group"] == g and not labels[i]["actionable"]) for g in groups]
    fig, ax = plt.subplots(figsize=(5.6, 3.6), dpi=170)
    x = np.arange(3)
    ax.bar(x, pos, .5, label="待办", color="#3b5bdb")
    ax.bar(x, neg, .5, bottom=pos, label="非待办", color="#dee2e6")
    for i, (p, n) in enumerate(zip(pos, neg)):
        ax.text(i, p / 2, str(p), ha="center", color="white", fontsize=10)
        ax.text(i, p + n / 2, str(n), ha="center", color="#495057", fontsize=10)
    ax.set_xticks(x, [gname[g] for g in groups])
    ax.set_ylabel("消息数")
    ax.set_title("三个群的待办分布（共 300 条）", fontsize=11)
    ax.legend(frameon=False, fontsize=9)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    fig.tight_layout()
    fig.savefig(RES / "fig_data.png")
    plt.close(fig)


def error_cases(exp, preds, labels, rows, split):
    d = next(e for e in exp if e["mode"] == "full")
    ps = preds["full"]
    fn, fp = [], []
    for mid, p in zip(split["test"], ps):
        g = labels[mid]["actionable"]
        pred = 1 if p["is_todo"] else 0
        rec = {"id": mid, "group": rows[mid]["group"], "text": rows[mid]["text"][:160],
               "clf": p["clf_prob"], "skipped": p["skipped_llm"], "error": p["error"],
               "gold_due": labels[mid]["due"], "pred_due": [i["due_text"] for i in p["items"]]}
        if g == 1 and pred == 0:
            fn.append(rec)
        if g == 0 and pred == 1:
            fp.append(rec)

    lines = ["# 错误案例分析（本方案 D，60 条测试集）\n",
             f"漏报 {len(fn)} 条，误报 {len(fp)} 条。\n", "## 漏报（真实待办被判为否）\n"]
    for r in fn:
        cause = "分类器门控拦截" if r["skipped"] else "模型判为否"
        lines.append(f"- `{r['id']}`（{r['group']}，分类器 p={r['clf']}，{cause}）：{r['text']}")
    lines.append("\n## 误报（非待办被判为是）\n")
    for r in fp:
        lines.append(f"- `{r['id']}`（{r['group']}，分类器 p={r['clf']}）：{r['text']}")
    (RES / "error_cases.md").write_text("\n".join(lines), encoding="utf-8")
    return fn, fp


def main():
    exp, labels, rows, split, preds = load()
    fig_metrics(exp)
    fig_cost(exp)
    fig_cm(exp, preds, labels, split)
    fig_data(labels, rows)
    fn, fp = error_cases(exp, preds, labels, rows, split)
    print("figures:", [p.name for p in RES.glob("fig_*.png")])
    print(f"漏报 {len(fn)} / 误报 {len(fp)}")
    print("被门控拦截导致的漏报:", sum(1 for r in fn if r["skipped"]))
    print("调用模型仍漏报:", sum(1 for r in fn if not r["skipped"]))


if __name__ == "__main__":
    main()
