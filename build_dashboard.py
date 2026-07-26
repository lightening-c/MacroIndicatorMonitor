"""
宏观数据跟踪 — 页面数据注入器
将 analysis_result.json 注入到 dashboard.html 和 cycle_report.html 的占位符
"""
import os, json, re

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
ANALYSIS_FILE = os.path.join(DATA_DIR, "analysis_result.json")

def trim_data(data):
    """Trim ts_data arrays for manageable HTML size"""
    for cat in ["leading", "coincident", "lagging"]:
        for ind in data["indicators"][cat]:
            ts = ind.get("ts_data", [])
            if len(ts) > 60:
                ind["ts_data"] = ts[-60:]
    for k in data.get("composite_indices", {}):
        pts = data["composite_indices"][k]
        if len(pts) > 120:
            data["composite_indices"][k] = pts[-120:]
    for ind_id in data.get("decomposition", {}):
        for comp in data["decomposition"][ind_id]:
            pts = data["decomposition"][ind_id][comp]
            if isinstance(pts, list) and len(pts) > 60:
                data["decomposition"][ind_id][comp] = pts[-60:]
    return data

def build():
    with open(ANALYSIS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    data = trim_data(data)
    json_str = json.dumps(data, ensure_ascii=False)

    for fname in ["dashboard.html", "cycle_report.html"]:
        path = os.path.join(BASE_DIR, fname)
        if not os.path.exists(path):
            print(f"[WARN] {fname} not found")
            continue
        with open(path, "r", encoding="utf-8") as f:
            html = f.read()
        if "ANALYSIS_DATA_PLACEHOLDER" in html:
            html = html.replace("ANALYSIS_DATA_PLACEHOLDER", json_str)
            with open(path, "w", encoding="utf-8") as f:
                f.write(html)
            print(f"[OK] {fname} 已注入数据 ({len(html)} chars)")
        else:
            print(f"[WARN] {fname} 未找到占位符")

if __name__ == "__main__":
    build()
