# -*- coding: utf-8 -*-
"""微信聊天记录解析 + 脱敏。

输入格式（微信 PC 端复制出来的纯文本）：
    昵称
    2026年09月11日 21:06
    正文（可能多行）
    ...
"""
from __future__ import annotations

import json
import re
from pathlib import Path

TS_RE = re.compile(r"^\d{4}年\d{1,2}月\d{1,2}日\s+\d{1,2}:\d{2}$")

# 正文里的“媒体占位符”
MEDIA_TAGS = ("[图片]", "[表情]", "[动画表情]", "[视频]", "[语音]", "[文件]", "[链接]",
              "[小程序]", "[位置]", "[名片]", "[转账]", "[红包]", "[聊天记录]", "[收藏]")

URL_RE = re.compile(r"https?://[^\s]+")
PHONE_RE = re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")
SID_RE = re.compile(r"(?<!\d)0\d{2}1\d{6}(?!\d)|(?<!\d)\d{9}(?!\d)")  # 028123240 这类 9 位学号
NAME_AT_RE = re.compile(r"@([\u4e00-\u9fa5A-Za-z0-9_\-]{1,12})")
SPACE_RE = re.compile(r"[\u2005\u200b\u00a0\u3000]")


def parse_file(path: Path) -> list[dict]:
    raw = path.read_text(encoding="utf-8-sig", errors="replace")
    lines = [SPACE_RE.sub(" ", l.rstrip()) for l in raw.splitlines()]
    ts_idx = [i for i, l in enumerate(lines) if TS_RE.match(l.strip())]
    msgs = []
    for k, i in enumerate(ts_idx):
        end = (ts_idx[k + 1] - 1) if k + 1 < len(ts_idx) else len(lines)
        body = "\n".join(x for x in lines[i + 1:end]).strip()
        sender = lines[i - 1].strip() if i - 1 >= 0 else ""
        msgs.append({
            "sender": sender,
            "time": lines[i].strip(),
            "text": body,
            "source": path.stem,
        })
    return msgs


def _mask_names(text: str, mapping: dict[str, str]) -> str:
    """把 @昵称 与出现过的成员昵称替换成代号。"""
    for name, alias in sorted(mapping.items(), key=lambda kv: -len(kv[0])):
        if len(name) < 2:
            continue
        text = text.replace("@" + name, "@" + alias)
        text = text.replace(name, alias)
    return text


DAT_RE = re.compile(r"(微信)?(图片|视频|文件)_?\d{8,}[_\d]*\.\w{2,5}")


def desensitize(msg: dict, group_alias: str, mapping: dict[str, str]) -> dict:
    text = msg["text"]
    # 0) 微信附件自动文件名（纯数字串）对任务无信息量，去掉
    text = DAT_RE.sub("", text).strip()
    # 1) 长链接压成占位符（既降噪又去隐私）
    text = URL_RE.sub("[链接]", text)
    # 2) 手机号 / 学号
    text = PHONE_RE.sub("[手机号]", text)
    text = SID_RE.sub("[学号]", text)
    # 3) 昵称 → 成员代号
    text = _mask_names(text, mapping)
    out = dict(msg)
    out["text"] = text
    out["sender"] = mapping.get(msg["sender"], "[成员]")
    out["group"] = group_alias
    return out


def build_groups(raw_dir: Path) -> list[dict]:
    """把目录下所有 txt 解析成统一的记录列表，并做脱敏。"""
    files = sorted(raw_dir.glob("*.txt"))
    groups = []
    for gi, path in enumerate(files, start=1):
        msgs = parse_file(path)
        aliases = {}
        for m in msgs:
            s = m["sender"]
            if s and s not in aliases:
                aliases[s] = "[成员%d]" % (len(aliases) + 1)
        g_alias = "[群%d]" % gi
        for m in msgs:
            d = desensitize(m, g_alias, aliases)
            d["group_name"] = path.stem
            groups.append(d)
    for i, m in enumerate(groups, start=1):
        m["id"] = "M%03d" % i
    return groups


def media_kind(text: str) -> str:
    for tag in MEDIA_TAGS:
        if text.startswith(tag) and len(text) <= len(tag) + 30:
            return tag.strip("[]")
    return "文本"


def save_jsonl(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def load_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


if __name__ == "__main__":
    base = Path(__file__).resolve().parent.parent
    rows = build_groups(base / "data" / "raw")
    save_jsonl(rows, base / "data" / "messages.jsonl")
    print("解析消息数:", len(rows))
    from collections import Counter
    print("按群:", dict(Counter(r["group_name"] for r in rows)))
    print("按类型:", dict(Counter(media_kind(r["text"]) for r in rows)))
    print("--- 脱敏后样例 ---")
    for r in rows[:6]:
        print(r["id"], r["group"], r["sender"], r["time"], "|", r["text"][:60].replace("\n", " / "))
