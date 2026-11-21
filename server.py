"""
宏观数据跟踪 — 本地服务器
端口 4321, 提供静态文件 + API: POST /api/update 触发全流程更新
"""
import http.server
import subprocess
import sys
import os
import json
import socket
import threading
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PYTHON = sys.executable
UPDATE_LOG = os.path.join(BASE_DIR, "data", "update_log.json")
MANUAL_VIEWS = os.path.join(BASE_DIR, "assets", "manual_views.json")


def load_manual_views():
    if not os.path.exists(MANUAL_VIEWS):
        return []
    try:
        with open(MANUAL_VIEWS, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def save_manual_views(items):
    os.makedirs(os.path.dirname(MANUAL_VIEWS), exist_ok=True)
    tmp = MANUAL_VIEWS + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)
    os.replace(tmp, MANUAL_VIEWS)


ABSTRACT_CACHE = {}


def _clean_abstract(text, title=None, limit=180):
    import re
    t = re.sub(r"\s+", " ", text or "").strip()
    cut = None
    head = t[:400]
    for mk in ("核心观点", "基本内容", "主要观点", "摘要", "要点"):
        i = head.find(mk)
        if i >= 0:
            cut = i + len(mk)
            break
    if cut is None and title:
        core = re.sub(r"\s+", "", title)
        for n in (8, 6, 5):
            if len(core) < n:
                continue
            pat = r"\s*".join(re.escape(c) for c in core[-n:])
            m = re.search(pat, t)
            if m:
                cut = m.end()
                break
    if cut is not None:
        t = t[cut:]
    else:
        last = None
        for m in re.finditer(r"\S+@\S+", head):
            last = m
        if last:
            t = t[last.end():]
    t = re.sub(r"\S+@\S+", " ", t)
    t = re.sub(r"（执业[^）]*）", " ", t)
    for junk in ("敬请参阅最后一页特别声明", "请务必阅读正文之后的信息披露",
                 "敬请阅读末页", "证券研究报告", "分析师：", "联系人：", "宏观经济组"):
        t = t.replace(junk, " ")
    t = re.sub(r"\s+", " ", t).strip(" ：:，,。、-")
    if len(t) > limit:
        cut2 = t[:limit]
        p = max(cut2.rfind("。"), cut2.rfind("；"))
        t = cut2[:p + 1] if p > 60 else cut2 + "…"
    return t


def fetch_report_abstract(code, title=None):
    if code in ABSTRACT_CACHE:
        return ABSTRACT_CACHE[code]
    import io
    import urllib.request
    from pypdf import PdfReader
    url = f"https://pdf.dfcfw.com/pdf/H3_{code}_1.pdf"
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/120 Safari/537.36",
        "Referer": "https://data.eastmoney.com/report/",
    })
    with urllib.request.urlopen(req, timeout=25) as r:
        data = r.read(10 * 1024 * 1024)
    reader = PdfReader(io.BytesIO(data))
    text = reader.pages[0].extract_text() or ""
    out = _clean_abstract(text, title)
    ABSTRACT_CACHE[code] = out
    return out

STATUS = {"running": False, "last_update": None, "last_result": None, "current_step": None}

if os.path.exists(UPDATE_LOG):
    try:
        with open(UPDATE_LOG, "r", encoding="utf-8") as f:
            saved = json.load(f)
            STATUS["last_update"] = saved.get("last_update")
            STATUS["last_result"] = saved.get("last_result")
    except:
        pass


def run_update():
    STATUS["running"] = True
    try:
        steps = [
            ("采集数据", "fetch_data.py"),
            ("分析引擎", "analyze.py"),
            ("数据自检", "smoke_test.py"),
        ]
        results = []
        for i, (name, script) in enumerate(steps):
            STATUS["current_step"] = f"{i+1}/{len(steps)} {name}"
            result = subprocess.run(
                [PYTHON, os.path.join(BASE_DIR, script)],
                capture_output=True, text=True, cwd=BASE_DIR, timeout=300
            )
            ok = result.returncode == 0
            results.append({"step": name, "ok": ok, "output": result.stdout[-500:] if ok else result.stderr[-500:]})
            if not ok:
                break   # stop on failure

        success = all(r["ok"] for r in results)
        STATUS["last_update"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        STATUS["last_result"] = {"success": success, "steps": results}

        # Redirect to build_dashboard.py output as well if it's there
        # Remove the step "生成页面" that just calls build dashboard and it doesn't really inject data now.

        with open(UPDATE_LOG, "w", encoding="utf-8") as f:
            json.dump({"last_update": STATUS["last_update"], "last_result": STATUS["last_result"]}, f, ensure_ascii=False, indent=2)

        return success, results
    except Exception as e:
        STATUS["last_result"] = {"success": False, "error": str(e)}
        return False, [{"step": "异常", "ok": False, "output": str(e)}]
    finally:
        STATUS["running"] = False
        STATUS["current_step"] = None


class APIHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=BASE_DIR, **kwargs)

    def do_POST(self):
        if self.path == "/api/update":
            if STATUS["running"]:
                self.send_json(409, {"ok": False, "message": "更新正在运行中，请稍后再试"})
                return
            t = threading.Thread(target=run_update, daemon=True)
            t.start()
            self.send_json(200, {"ok": True, "message": "更新已启动"})
        elif self.path == "/api/manual-views":
            try:
                length = int(self.headers.get("Content-Length") or 0)
                raw = self.rfile.read(length).decode("utf-8") if length else "{}"
                body = json.loads(raw or "{}")
            except Exception as e:
                self.send_json(400, {"ok": False, "message": f"请求体解析失败：{e}"})
                return
            item = {
                "org": (body.get("org") or "").strip(),
                "date": (body.get("date") or "").strip(),
                "topic": (body.get("topic") or "").strip(),
                "stance": (body.get("stance") or "部分一致").strip(),
                "view": (body.get("view") or "").strip(),
                "note": (body.get("note") or "").strip(),
                "cause": (body.get("cause") or "").strip(),
                "action": (body.get("action") or "").strip(),
                "link": (body.get("link") or "").strip(),
            }
            if not (item["org"] and item["date"] and item["topic"]):
                self.send_json(400, {"ok": False, "message": "机构、日期、标题不能为空"})
                return
            if not item["note"]:
                self.send_json(400, {"ok": False, "message": "请填写对照结论"})
                return
            key = f'{item["org"]}|{item["date"]}|{item["topic"]}'
            items = [x for x in load_manual_views()
                     if f'{x.get("org")}|{x.get("date")}|{x.get("topic")}' != key]
            items.insert(0, item)
            try:
                save_manual_views(items)
            except Exception as e:
                self.send_json(500, {"ok": False, "message": f"保存失败：{e}"})
                return
            self.send_json(200, {"ok": True, "item": item})
        else:
            self.send_json(404, {"ok": False, "message": "Not Found"})

    def do_GET(self):
        if self.path == "/api/status":
            self.send_json(200, {"ok": True, "running": STATUS["running"], "current_step": STATUS["current_step"], "last_update": STATUS["last_update"], "last_result": STATUS["last_result"]})
        elif self.path == "/api/manual-views":
            self.send_json(200, {"ok": True, "items": load_manual_views()})
        elif self.path.startswith("/api/report-abstract"):
            from urllib.parse import urlparse, parse_qs
            import re as _re
            qs = parse_qs(urlparse(self.path).query)
            code = (qs.get("code", [""])[0] or "").strip()
            title = (qs.get("title", [""])[0] or "").strip() or None
            if not _re.fullmatch(r"[A-Za-z]{2}\d{8,20}", code):
                self.send_json(400, {"ok": False, "message": "研报编码不合法"})
                return
            try:
                self.send_json(200, {"ok": True, "text": fetch_report_abstract(code, title)})
            except ImportError:
                self.send_json(500, {"ok": False, "message": "缺少 pypdf，请先安装"})
            except Exception as e:
                self.send_json(500, {"ok": False, "message": f"抓取失败：{e}"})
        elif self.path.startswith("/api/views"):
            from urllib.parse import urlparse, parse_qs
            qs = parse_qs(urlparse(self.path).query)
            try:
                limit = int(qs.get("limit", ["8"])[0])
            except ValueError:
                limit = 8
            force = qs.get("force", ["0"])[0] == "1"
            try:
                import views_feed
                items = views_feed.get_views(limit=limit, force=force)
                self.send_json(200, {"ok": True,
                                     "updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                     "count": len(items), "items": items})
            except Exception as e:
                self.send_json(500, {"ok": False, "message": str(e)})
        elif self.path.startswith("/api/news"):
            from urllib.parse import urlparse, parse_qs
            qs = parse_qs(urlparse(self.path).query)
            try:
                limit = int(qs.get("limit", ["30"])[0])
            except ValueError:
                limit = 30
            force = qs.get("force", ["0"])[0] == "1"
            try:
                import news_feed
                items = news_feed.get_macro_news(limit=limit, force=force)
                self.send_json(200, {"ok": True,
                                     "updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                     "count": len(items), "items": items})
            except Exception as e:
                self.send_json(500, {"ok": False, "message": str(e)})
        elif self.path == "/":
            self.path = "/dashboard.html"
            super().do_GET()
        else:
            super().do_GET()

    def send_json(self, code, data):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", len(body))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def log_message(self, format, *args):
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {args[0]}")

    def end_headers(self):
        # 静态资源短缓存、页面不缓存，避免浏览器拿旧 HTML/JS
        if self.path.startswith("/assets/echarts"):
            self.send_header("Cache-Control", "public, max-age=604800")
        elif not self.path.startswith("/api/"):
            self.send_header("Cache-Control", "no-cache")
        super().end_headers()


class SingleInstanceHTTPServer(http.server.ThreadingHTTPServer):
    allow_reuse_address = False
    daemon_threads = True


def port_in_use(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1)
        return s.connect_ex(("127.0.0.1", port)) == 0


def main():
    port = 4321
    if port_in_use(port):
        print(f"\n[错误] 端口 {port} 已被占用，说明已有一个服务在运行。")
        print(f"       请直接使用 http://localhost:{port} ，")
        print(f"       或先关闭那个窗口再启动本服务。\n")
        sys.exit(1)
    try:
        server = SingleInstanceHTTPServer(("0.0.0.0", port), APIHandler)
    except OSError:
        print(f"\n[错误] 无法绑定端口 {port}，可能已被其他程序占用。\n")
        sys.exit(1)
    print(f"\n{'='*60}")
    print(f"  宏观数据跟踪服务器")
    print(f"  http://localhost:{port}")
    print(f"  POST /api/update → 触发全流程更新")
    print(f"  GET  /api/status  → 查看更新状态")
    print(f"  按 Ctrl+C 停止")
    print(f"{'='*60}\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n服务器已停止")
        server.shutdown()


if __name__ == "__main__":
    main()
