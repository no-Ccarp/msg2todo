# -*- coding: utf-8 -*-
"""DeepSeek API 客户端：重试、磁盘缓存、并发、调用统计。

只用标准库 urllib，避免额外依赖。
"""
from __future__ import annotations

import hashlib
import json
import os
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
CACHE_DIR = BASE / "results" / "cache"


def _load_env() -> None:
    if os.environ.get("LLM_API_KEY"):
        return
    env = BASE / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_env()

API_BASE = os.environ.get("LLM_BASE_URL", "https://api.deepseek.com").rstrip("/")
API_KEY = os.environ.get("LLM_API_KEY", "")
MODEL = os.environ.get("LLM_MODEL", "deepseek-chat")
CACHE_ON = os.environ.get("LLM_CACHE", "1") == "1"

_lock = threading.Lock()
STATS = {"calls": 0, "cache_hits": 0, "fail": 0, "prompt_tokens": 0, "completion_tokens": 0}


def stats() -> dict:
    with _lock:
        return dict(STATS)


def reset_stats() -> None:
    with _lock:
        for k in STATS:
            STATS[k] = 0


def _cache_path(body: dict) -> Path:
    h = hashlib.sha1(json.dumps(body, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    return CACHE_DIR / (h + ".json")


def chat(messages: list[dict], *, model: str | None = None, temperature: float = 0.0,
         max_tokens: int = 800, json_mode: bool = False, retries: int = 3,
         timeout: int = 90) -> str:
    """返回模型输出的文本内容；失败抛异常。"""
    body = {
        "model": model or MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if json_mode:
        body["response_format"] = {"type": "json_object"}

    cp = _cache_path(body)
    if CACHE_ON and cp.exists():
        hit = json.loads(cp.read_text(encoding="utf-8"))
        usage = hit.get("usage", {})
        with _lock:
            STATS["cache_hits"] += 1
            # token 用量照常累计：成本比较用的是“若真调用需多少 token”
            STATS["prompt_tokens"] += usage.get("prompt_tokens", 0)
            STATS["completion_tokens"] += usage.get("completion_tokens", 0)
        return hit["content"]

    if not API_KEY:
        raise RuntimeError("未设置 LLM_API_KEY（放在 .env 或环境变量里）")

    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(
                API_BASE + "/chat/completions",
                data=json.dumps(body).encode("utf-8"),
                headers={"Authorization": "Bearer " + API_KEY,
                         "Content-Type": "application/json"},
            )
            t0 = time.time()
            with urllib.request.urlopen(req, timeout=timeout) as r:
                data = json.loads(r.read().decode("utf-8"))
            content = data["choices"][0]["message"]["content"]
            usage = data.get("usage", {})
            with _lock:
                STATS["calls"] += 1
                STATS["prompt_tokens"] += usage.get("prompt_tokens", 0)
                STATS["completion_tokens"] += usage.get("completion_tokens", 0)
            if CACHE_ON:
                CACHE_DIR.mkdir(parents=True, exist_ok=True)
                cp.write_text(json.dumps({"content": content, "usage": usage,
                                          "latency_ms": int((time.time() - t0) * 1000)},
                                         ensure_ascii=False), encoding="utf-8")
            return content
        except Exception as e:  # noqa: BLE001
            last = e
            if isinstance(e, urllib.error.HTTPError) and e.code in (400, 401, 402, 422):
                break
            time.sleep(1.5 * (attempt + 1))
    with _lock:
        STATS["fail"] += 1
    raise RuntimeError(f"LLM 调用失败: {last}")


def chat_json(messages: list[dict], **kw) -> dict:
    txt = chat(messages, json_mode=True, **kw)
    txt = txt.strip()
    if txt.startswith("```"):
        txt = txt.split("```")[1]
        txt = txt[4:] if txt.startswith("json") else txt
    return json.loads(txt)


def pmap(fn, items, workers: int = 6):
    with ThreadPoolExecutor(max_workers=workers) as ex:
        return list(ex.map(fn, items))
