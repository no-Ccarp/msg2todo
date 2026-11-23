# -*- coding: utf-8 -*-
"""特征表示消融：验证 TfidfVectorizer 的 analyzer 选择对中文群消息的影响。

背景：scikit-learn 的 TfidfVectorizer 默认 analyzer='word'，按空白切词。
中文没有空格，默认配置会把整句当成一个 token，等价于“整句哈希”。
本实验把默认配置与 char/char_wb 对比，作为“复用组件适配工作”的实证。
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold, cross_val_score
from sklearn.pipeline import Pipeline

BASE = Path(__file__).resolve().parent

CONFIGS = [
    ("word（默认，按空白切词）", dict(analyzer="word", ngram_range=(1, 2), min_df=1)),
    ("char（1-2 字）", dict(analyzer="char", ngram_range=(1, 2), min_df=1)),
    ("char_wb（1-3 字，本方案）", dict(analyzer="char_wb", ngram_range=(1, 3), min_df=1, max_features=30000)),
    ("char_wb（1-4 字）", dict(analyzer="char_wb", ngram_range=(1, 4), min_df=1, max_features=30000)),
]


def main() -> None:
    import sys
    sys.path.insert(0, str(BASE))
    from core.parse import load_jsonl

    rows = {r["id"]: r for r in load_jsonl(BASE / "data" / "messages.jsonl")}
    labels = {l["id"]: l for l in load_jsonl(BASE / "data" / "labels.jsonl")}
    split = json.loads((BASE / "data" / "split.json").read_text(encoding="utf-8"))

    X = [rows[i]["text"] for i in split["train"]]
    y = np.array([labels[i]["actionable"] for i in split["train"]])

    # 展示默认配置在中文上的实际行为
    v = TfidfVectorizer(analyzer="word", ngram_range=(1, 2))
    v.fit(["明天13:00-14:00在小程序订过书的来教学楼领书"])
    print("默认 analyzer='word' 切出的词表:", v.get_feature_names_out().tolist())

    out = []
    for name, kw in CONFIGS:
        pipe = Pipeline([("tfidf", TfidfVectorizer(sublinear_tf=True, **kw)),
                         ("clf", LogisticRegression(C=3.0, class_weight="balanced", max_iter=3000))])
        cv = StratifiedKFold(5, shuffle=True, random_state=42)
        f1 = cross_val_score(pipe, X, y, cv=cv, scoring="f1").mean()
        acc = cross_val_score(pipe, X, y, cv=cv, scoring="accuracy").mean()
        n_feat = len(pipe.named_steps["tfidf"].fit(X, y).vocabulary_)
        out.append({"config": name, "cv_f1": round(float(f1), 4),
                    "cv_acc": round(float(acc), 4), "n_features": n_feat})
        print(f"{name:<26} CV-F1={f1:.4f}  Acc={acc:.4f}  特征数={n_feat}")

    (BASE / "results" / "feature_ablation.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
