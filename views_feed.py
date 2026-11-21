"""
宏观数据跟踪 — 机构观点实时抓取
来源：东方财富研报中心（宏观/策略研报），按宏观关键词过滤，带 15 分钟缓存。
"""
import json
import re
import time
import urllib.request
from datetime import datetime, timedelta

UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36",
    "Referer": "https://data.eastmoney.com/report/",
}

API = ("https://reportapi.eastmoney.com/report/list"
       "?pageSize=60&pageNo={page}&qType=2&beginTime={begin}&endTime={end}")

# 强关键词：命中任一个即视为宏观研报
MACRO_KEYWORDS = [
    "宏观", "PMI", "CPI", "PPI", "社融", "信贷", "货币", "财政", "专项债",
    "汇率", "国债", "利率", "LPR", "库存", "GDP", "通胀", "通缩", "失业",
    "就业", "降准", "降息", "内需", "外需",
]

# 弱关键词：单个不足以判定，需命中两个
WEAK_KEYWORDS = [
    "出口", "进口", "外贸", "关税", "消费", "投资", "地产", "房地产",
    "政策", "经济", "制造业", "服务业",
]

EXCLUDE_ORGS = ["资信评估", "信用评级", "评级"]

_cache = {"ts": 0.0, "items": []}
_TTL = 900


def _get(url, timeout=15):
    req = urllib.request.Request(url, headers=UA)
    return urllib.request.urlopen(req, timeout=timeout).read().decode("utf-8", "ignore")


def _is_macro(title, org):
    if any(x in org for x in EXCLUDE_ORGS):
        return False
    if any(k in title for k in MACRO_KEYWORDS):
        return True
    return sum(1 for k in WEAK_KEYWORDS if k in title) >= 2


def fetch_reports(days=45):
    end = datetime.now()
    begin = end - timedelta(days=days)
    out, seen = [], set()
    for page in (1, 2):
        url = API.format(page=page, begin=begin.strftime("%Y-%m-%d"),
                         end=end.strftime("%Y-%m-%d"))
        try:
            data = json.loads(_get(url))
        except Exception:
            break
        rows = data.get("data") or []
        if not rows:
            break
        for it in rows:
            title = " ".join((it.get("title") or "").split())
            org = (it.get("orgSName") or "").strip()
            code = it.get("infoCode") or ""
            if not title or not org or not code or not _is_macro(title, org):
                continue
            key = re.sub(r"[^\w]", "", title)[:24]
            if key in seen:
                continue
            seen.add(key)
            out.append({
                "org": org,
                "date": (it.get("publishDate") or "")[:10],
                "topic": title,
                "link": f"https://data.eastmoney.com/report/info/{code}.html",
                "source": "东方财富研报",
            })
    out.sort(key=lambda x: x["date"], reverse=True)
    return out


def get_views(limit=10, force=False):
    now = time.time()
    if not force and _cache["items"] and now - _cache["ts"] < _TTL:
        return _cache["items"][:limit]
    try:
        items = fetch_reports()
    except Exception:
        return _cache["items"][:limit]
    if items:
        _cache.update(ts=now, items=items)
    return items[:limit]


if __name__ == "__main__":
    for v in get_views(limit=12, force=True):
        print(v["date"], v["org"], "|", v["topic"][:50])
