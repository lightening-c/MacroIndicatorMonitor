"""
宏观数据跟踪 — 模型修正记录（自动检测）
每次分析后与上一次快照对比，把指标增删、口径变化、数据端点回退/补采、
陈旧项与样本数变化、相关系数缺失、采集失败等记入 data/corrections_auto.json。
"""
import json
import os
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
CUR = os.path.join(DATA_DIR, "analysis_trimmed.json")
PREV = os.path.join(DATA_DIR, "analysis_prev.json")
LOG = os.path.join(DATA_DIR, "corrections_auto.json")
WARN = os.path.join(DATA_DIR, "fetch_warnings.json")
MAX_ENTRIES = 60


def _load(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def snapshot(d):
    inds = {}
    for cat in ("leading", "coincident", "lagging"):
        for e in (d.get("indicators") or {}).get(cat, []):
            inds[e["id"]] = {
                "name": e.get("name", e["id"]),
                "freq": e.get("frequency", ""),
                "caliber": e.get("caliber", ""),
                "date": (e.get("latest_date") or "")[:10] or None,
                "stale": bool(e.get("stale")),
                "signal": e.get("signal"),
            }
    cm = d.get("correlation_matrix") or {}
    mat = cm.get("matrix") or []
    cells = sum(len(r) for r in mat)
    empty = sum(1 for r in mat for v in r if v is None)
    s = d.get("summary") or {}
    health = d.get("data_health") or {}
    return {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "indicators": inds,
        "counts": {k: s.get(f"{k}_count") for k in ("leading", "coincident", "lagging")},
        "stale_ids": sorted(x.get("id", x.get("name", "")) for x in health.get("stale", [])),
        "stale_names": [x.get("name", "") for x in health.get("stale", [])],
        "corr_empty_ratio": round(empty / cells, 4) if cells else None,
        "failed": health.get("failed_items") or [],
        "phase": (d.get("cycle_phase") or {}).get("phase") or s.get("cycle_phase"),
    }


def _entry(today, item, issue, fix):
    return {"date": today, "item": item, "issue": issue, "fix": fix, "auto": True}


def diff(prev, cur):
    out = []
    today = cur["date"]
    p, c = prev.get("indicators", {}), cur["indicators"]

    added = [c[i]["name"] for i in c if i not in p]
    if added:
        out.append(_entry(today, "新增指标", "、".join(added),
                          "已纳入分析；请确认口径与分类是否合适"))

    removed = [p[i]["name"] for i in p if i not in c]
    if removed:
        out.append(_entry(today, "指标消失", "、".join(removed),
                          "已从面板移除；若为误删请检查 config.yaml"))

    cal = [f'{c[i]["name"]}（{p[i].get("caliber") or "—"} → {c[i].get("caliber") or "—"}）'
           for i in c if i in p and (p[i].get("caliber") or "") != (c[i].get("caliber") or "")]
    if cal:
        out.append(_entry(today, "口径变化", "、".join(cal),
                          "已按新口径重算；历史值未回溯"))

    back = [f'{c[i]["name"]}（{p[i].get("date")} → {c[i].get("date")}）'
            for i in c
            if i in p and p[i].get("date") and c[i].get("date") and c[i]["date"] < p[i]["date"]]
    if back:
        out.append(_entry(today, "数据端点回退", "、".join(back),
                          "源端历史被改写或抓取异常，已按最新值计算，请核对数据源"))

    jump = []
    for i, e in c.items():
        if i not in p or e.get("freq") != "月度":
            continue
        try:
            d0 = datetime.strptime(p[i]["date"], "%Y-%m-%d")
            d1 = datetime.strptime(e["date"], "%Y-%m-%d")
        except Exception:
            continue
        if (d1 - d0).days >= 62:
            jump.append(f'{e["name"]}（{p[i]["date"]} → {e["date"]}）')
    if jump:
        out.append(_entry(today, "数据补采", "、".join(jump),
                          "一次性补齐多期，已按最新值计算"))

    ps, cs = prev.get("stale_ids", []), cur.get("stale_ids", [])
    if abs(len(cs) - len(ps)) >= 3:
        out.append(_entry(today, "陈旧指标数量变化",
                          f"{len(ps)} 项 → {len(cs)} 项" +
                          (f"；当前：{'、'.join(cur.get('stale_names', []))}" if cs else "；当前无"),
                          "陈旧指标已排除出合成指数，请确认是否为源端未发布"))

    pc, cc = prev.get("counts") or {}, cur.get("counts") or {}
    chg = [f"{k} {pc.get(k)}→{cc.get(k)}" for k in ("leading", "coincident", "lagging")
           if pc.get(k) != cc.get(k)]
    if chg:
        out.append(_entry(today, "合成指数样本数变化", "、".join(chg),
                          "已按新样本重算合成指数与信号汇总"))

    pe, ce = prev.get("corr_empty_ratio"), cur.get("corr_empty_ratio")
    if pe is not None and ce is not None and abs(ce - pe) >= 0.1:
        out.append(_entry(today, "相关系数矩阵缺失变化",
                          f"空单元占比 {pe:.0%} → {ce:.0%}",
                          "多因新增指标历史过短，随数据积累自动改善"))

    if cur.get("failed"):
        out.append(_entry(today, "采集失败", "、".join(str(x) for x in cur["failed"]),
                          "本次未更新，沿用上一期数据"))

    return out


def _consume_warnings():
    """读取采集端记录的端点回退告警，读完即清空"""
    items = _load(WARN, [])
    if not isinstance(items, list) or not items:
        return []
    try:
        os.remove(WARN)
    except Exception:
        pass
    return items


def update():
    data = _load(CUR, None)
    if not data:
        return []
    cur = snapshot(data)
    prev = _load(PREV, None)
    found = diff(prev, cur) if prev else []

    for w in _consume_warnings():
        found.append(_entry(cur["date"], "数据端点回退（已自动保留旧数据）",
                            f'{w.get("name") or w.get("id")}：新数据末日 {w.get("new")} '
                            f'早于已有 {w.get("old")}',
                            "已自动跳过本次覆盖，沿用较长历史；请核对数据源是否改写历史"))

    log = _load(LOG, [])
    seen = {(x.get("date"), x.get("item"), x.get("issue")) for x in log}
    for e in found:
        k = (e["date"], e["item"], e["issue"])
        if k not in seen:
            log.append(e)
            seen.add(k)
    log = log[-MAX_ENTRIES:]

    os.makedirs(DATA_DIR, exist_ok=True)
    with open(LOG, "w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=2)
    with open(PREV, "w", encoding="utf-8") as f:
        json.dump(cur, f, ensure_ascii=False, indent=2)
    return found


if __name__ == "__main__":
    for e in update():
        print(e["date"], e["item"], "|", e["issue"][:80])
