# -*- coding: utf-8 -*-
"""本地 Web 服务（只用标准库 http.server）。

启动：python -m app.main    或双击 启动.bat
访问：http://127.0.0.1:8000
"""
from __future__ import annotations

import io
import json
import mimetypes
import re
import sys
import threading
import time
import webbrowser
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))

from core import pipeline  # noqa: E402

STATIC = Path(__file__).resolve().parent / "static"
HOST, PORT = "127.0.0.1", 8000

TS_LINE = re.compile(r"^\d{4}年\d{1,2}月\d{1,2}日\s+\d{1,2}:\d{2}$")


def split_messages(text: str) -> list[dict]:
    """支持一次粘贴多条：含“时间行”时按微信格式切分，否则整体视为一条。"""
    lines = [l.rstrip() for l in text.splitlines()]
    idx = [i for i, l in enumerate(lines) if TS_LINE.match(l.strip())]
    if not idx:
        t = text.strip()
        return [{"text": t, "time": None}] if t else []
    out = []
    for k, i in enumerate(idx):
        end = idx[k + 1] if k + 1 < len(idx) else len(lines)
        body = "\n".join(lines[i + 1:end]).strip()
        if body:
            out.append({"text": body, "time": lines[i].strip()})
    return out


def run_analysis(text: str, sent_time: str | None) -> dict:
    msgs = split_messages(text) if sent_time is None else [{"text": text, "time": sent_time}]
    t0 = time.time()
    if len(msgs) == 1:
        results = [pipeline.analyze(msgs[0]["text"], msgs[0]["time"], mode="full")]
    else:
        with ThreadPoolExecutor(max_workers=4) as ex:
            results = list(ex.map(lambda m: pipeline.analyze(m["text"], m["time"], mode="full"), msgs))
    items = []
    for r in results:
        for it in r["items"]:
            it = dict(it)
            it["source_text"] = r["text"][:200]
            it["clf_prob"] = r["clf_prob"]
            it["need_review"] = r["need_review"] or bool(r["error"])
            items.append(it)
    items = pipeline.sort_items(items)
    return {
        "messages": len(msgs),
        "todos": len(items),
        "items": items,
        "elapsed_ms": int((time.time() - t0) * 1000),
        "review_count": sum(1 for i in items if i["need_review"]),
        "degraded": any(r.get("degraded") for r in results),
    }


def export_xlsx(items: list[dict]) -> bytes:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    wb = Workbook()
    ws = wb.active
    ws.title = "待办清单"
    headers = ["事项", "截止时间(原文)", "截止时间(归一化)", "分类", "状态", "需复核", "来源消息"]
    ws.append(headers)
    for c in ws[1]:
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor="4472C4")
        c.alignment = Alignment(horizontal="center", vertical="center")
    for it in items:
        ws.append([it["task"], it["due_text"], it["due_iso"] or "—", it["category"],
                   it["bucket"], "是" if it["need_review"] else "否", it["source_text"]])
    widths = [46, 24, 20, 10, 10, 8, 50]
    for i, w in enumerate(widths, start=1):
        ws.column_dimensions[chr(64 + i)].width = w
    for row in ws.iter_rows(min_row=2):
        for c in row:
            c.alignment = Alignment(vertical="top", wrap_text=True)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def export_docx(items: list[dict]) -> bytes:
    from docx import Document
    from docx.shared import Pt
    doc = Document()
    doc.add_heading("群消息待办清单", level=1)
    doc.add_paragraph(f"生成时间：{datetime.now():%Y-%m-%d %H:%M}    共 {len(items)} 条")
    table = doc.add_table(rows=1, cols=5)
    table.style = "Light Grid Accent 1"
    for i, h in enumerate(["事项", "截止时间", "分类", "状态", "需复核"]):
        table.rows[0].cells[i].text = h
    for it in items:
        cells = table.add_row().cells
        cells[0].text = it["task"]
        cells[1].text = it["due_text"] or "—"
        cells[2].text = it["category"]
        cells[3].text = it["bucket"]
        cells[4].text = "是" if it["need_review"] else "否"
    for row in table.rows:
        for c in row.cells:
            for p in c.paragraphs:
                for r in p.runs:
                    r.font.size = Pt(9)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


class Handler(BaseHTTPRequestHandler):
    server_version = "Msg2Todo/0.1"

    def log_message(self, fmt, *args):  # 精简日志
        sys.stderr.write("[%s] %s\n" % (datetime.now().strftime("%H:%M:%S"), fmt % args))

    # ---------- 基础工具 ----------
    def _send(self, code: int, body: bytes, ctype: str, extra: dict | None = None):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code: int, obj: dict):
        self._send(code, json.dumps(obj, ensure_ascii=False).encode("utf-8"),
                   "application/json; charset=utf-8")

    def _read_json(self) -> dict:
        n = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(n) if n else b"{}"
        return json.loads(raw.decode("utf-8") or "{}")

    # ---------- 路由 ----------
    def do_GET(self):
        path = self.path.split("?")[0]
        if path == "/api/health":
            return self._json(200, {"ok": True, "time": datetime.now().isoformat(timespec="seconds")})
        if path in ("/", "/index.html"):
            return self._file(STATIC / "index.html", "text/html; charset=utf-8")
        if path.startswith("/static/"):
            return self._file(STATIC / path[len("/static/"):])
        if path == "/favicon.ico":
            return self._send(204, b"", "image/x-icon")
        self._json(404, {"error": "not found"})

    def _file(self, p: Path, ctype: str | None = None):
        if not p.exists() or not p.is_file():
            return self._json(404, {"error": f"missing {p.name}"})
        ctype = ctype or mimetypes.guess_type(p.name)[0] or "application/octet-stream"
        if p.suffix in (".js", ".css", ".html"):
            ctype += "; charset=utf-8"
        self._send(200, p.read_bytes(), ctype)

    def do_POST(self):
        path = self.path.split("?")[0]
        try:
            if path == "/api/analyze":
                data = self._read_json()
                text = (data.get("text") or "").strip()
                if not text:
                    return self._json(400, {"error": "消息内容为空"})
                return self._json(200, run_analysis(text, data.get("sent_time")))
            if path == "/api/export":
                data = self._read_json()
                items = data.get("items") or []
                fmt = data.get("fmt") or "xlsx"
                if fmt == "docx":
                    body, name = export_docx(items), "待办清单.docx"
                    ctype = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                else:
                    body, name = export_xlsx(items), "待办清单.xlsx"
                    ctype = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                from urllib.parse import quote
                return self._send(200, body, ctype,
                                  {"Content-Disposition": f"attachment; filename*=UTF-8''{quote(name)}"})
            self._json(404, {"error": "not found"})
        except Exception as e:  # noqa: BLE001
            self._json(500, {"error": str(e)[:300]})


def main() -> None:
    if not (BASE / "models" / "clf.pkl").exists():
        print("! 未找到模型文件，请先运行 python train.py")
    srv = ThreadingHTTPServer((HOST, PORT), Handler)
    url = f"http://{HOST}:{PORT}"
    print(f"服务已启动：{url}   （Ctrl+C 停止）")
    threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止")
    finally:
        srv.server_close()


if __name__ == "__main__":
    main()
