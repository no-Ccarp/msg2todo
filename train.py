# -*- coding: utf-8 -*-
"""训练消息分类器（待办 / 非待办），并输出交叉验证与跨群测试指标。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import joblib
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (accuracy_score, confusion_matrix, f1_score,
                             precision_score, recall_score, roc_auc_score)
from sklearn.model_selection import StratifiedKFold, cross_validate
from sklearn.pipeline import Pipeline

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.parse import load_jsonl  # noqa: E402

BASE = Path(__file__).resolve().parent


def build(c: float = 3.0) -> Pipeline:
    return Pipeline([
        ("tfidf", TfidfVectorizer(analyzer="char_wb", ngram_range=(1, 3), min_df=1,
                                  max_features=30000, sublinear_tf=True)),
        ("clf", LogisticRegression(C=c, class_weight="balanced", max_iter=3000)),
    ])


def evaluate(y, pred, prob) -> dict:
    return {
        "n": int(len(y)),
        "acc": round(accuracy_score(y, pred), 4),
        "precision": round(precision_score(y, pred, zero_division=0), 4),
        "recall": round(recall_score(y, pred, zero_division=0), 4),
        "f1": round(f1_score(y, pred, zero_division=0), 4),
        "auc": round(roc_auc_score(y, prob), 4) if len(set(y)) > 1 else None,
        "cm": confusion_matrix(y, pred).tolist(),
    }


def main() -> None:
    rows = load_jsonl(BASE / "data" / "messages.jsonl")
    labels = {l["id"]: l for l in load_jsonl(BASE / "data" / "labels.jsonl")}
    split = json.loads((BASE / "data" / "split.json").read_text(encoding="utf-8"))
    text = {r["id"]: r["text"] for r in rows}

    def xy(ids):
        return [text[i] for i in ids], np.array([labels[i]["actionable"] for i in ids])

    Xtr, ytr = xy(split["train"])
    Xte, yte = xy(split["test"])
    Xc, yc = xy(split["cross_train"])
    Xct, yct = xy(split["cross_test"])

    # ---- 1) 选 C（5 折 CV，只在训练集上）----
    report = {"cv": {}, "test": {}, "cross_group": {}, "baseline": {}}
    best_c, best_f1 = None, -1
    for c in (0.3, 1.0, 3.0, 10.0):
        cv = cross_validate(build(c), Xtr, ytr, cv=StratifiedKFold(5, shuffle=True, random_state=42),
                            scoring=("f1", "precision", "recall", "roc_auc"), n_jobs=4)
        m = {k: round(float(np.mean(v)), 4) for k, v in cv.items() if k.startswith("test_")}
        report["cv"][str(c)] = m
        print(f"C={c:<5} CV f1={m['test_f1']:.4f} p={m['test_precision']:.4f} r={m['test_recall']:.4f} auc={m['test_roc_auc']:.4f}")
        if m["test_f1"] > best_f1:
            best_f1, best_c = m["test_f1"], c

    model = build(best_c).fit(Xtr, ytr)
    report["best_C"] = best_c

    # ---- 2) 主测试集 ----
    prob = model.predict_proba(Xte)[:, 1]
    pred = (prob >= 0.5).astype(int)
    report["test"] = evaluate(yte, pred, prob)
    print("\n[主测试集] ", report["test"])

    # ---- 3) 跨群测试（类别分布完全不同）----
    mc = build(best_c).fit(Xc, yc)
    probc = mc.predict_proba(Xct)[:, 1]
    predc = (probc >= 0.5).astype(int)
    report["cross_group"] = evaluate(yct, predc, probc)
    print("[跨群测试] ", report["cross_group"])

    # ---- 4) 关键词规则基线（同一测试集）----
    from core.rules import rule_score
    rp = np.array([rule_score(t)[0] for t in Xte])
    report["baseline"] = evaluate(yte, rp, rp.astype(float))
    print("[规则基线] ", report["baseline"])

    # ---- 5) 保类别模型（辅助显示用）----
    cat_ids = [i for i in split["train"] if labels[i]["actionable"]]
    cat_model = build(3.0).fit([text[i] for i in cat_ids], [labels[i]["category"] for i in cat_ids])
    cat_test = [i for i in split["test"] if labels[i]["actionable"]]
    cat_acc = float(np.mean(cat_model.predict([text[i] for i in cat_test]) ==
                            np.array([labels[i]["category"] for i in cat_test]))) if cat_test else None
    report["category_acc"] = round(cat_acc, 4) if cat_acc is not None else None
    print(f"[类别模型] {len(cat_ids)} 训练样本，测试集 {len(cat_test)} 条，准确率 {cat_acc:.3f}")

    (BASE / "models").mkdir(exist_ok=True)
    joblib.dump(model, BASE / "models" / "clf.pkl")
    joblib.dump(cat_model, BASE / "models" / "cat.pkl")
    (BASE / "results").mkdir(exist_ok=True)
    (BASE / "results" / "clf_metrics.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print("\n模型已保存 models/clf.pkl，指标 results/clf_metrics.json")


if __name__ == "__main__":
    main()
