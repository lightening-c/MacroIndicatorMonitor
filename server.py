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

STATUS = {"running": False, "last_update": None, "last_result": None}

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
        ]
        results = []
        for name, script in steps:
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
        else:
            self.send_json(404, {"ok": False, "message": "Not Found"})

    def do_GET(self):
        if self.path == "/api/status":
            self.send_json(200, {"ok": True, "running": STATUS["running"], "last_update": STATUS["last_update"], "last_result": STATUS["last_result"]})
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
