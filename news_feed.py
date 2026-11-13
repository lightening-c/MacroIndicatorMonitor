"""
宏观数据跟踪 — 实时宏观快讯
从东方财富全球快讯中筛选宏观相关条目，带 5 分钟缓存。
"""
import time

KEYWORDS = [
    "宏观", "GDP", "PMI", "社融", "信贷", "CPI", "PPI", "通胀", "通缩",
    "降准", "降息", "央行", "货币政策", "财政", "专项债", "国债", "国债收益率",
    "汇率", "人民币中间价", "出口", "进口", "外贸", "关税",
    "房地产", "楼市", "地产", "基建", "失业", "就业率",
    "美联储", "美债", "国常会", "发改委", "统计局", "财政部", "证监会",
    "国务院", "国新办", "LPR",
]

CN_KEYWORDS = [
    "中国", "国内", "我国", "央行", "国常会", "发改委", "统计局", "财政部",
    "证监会", "国务院", "人民币", "A股", "沪指", "出口", "进口", "外贸",
    "地产", "房地产", "楼市", "社融", "PMI", "CPI", "PPI", "专项债",
    "LPR", "降准", "降息", "基建",
]

GLOBAL_KEYWORDS = ["美联储", "美债", "美国国债", "欧元区", "日本央行", "美元"]

_cache = {"ts": 0.0, "items": []}
_TTL = 300


def get_macro_news(limit=30, force=False):
    """返回 [{title, summary, time, link}]，按时间倒序；失败时返回缓存。"""
    now = time.time()
    if not force and _cache["items"] and now - _cache["ts"] < _TTL:
        return _cache["items"][:limit]

    try:
        import akshare as ak
        df = ak.stock_news_global_em()
    except Exception:
        return _cache["items"][:limit]

    items, seen = [], set()
    for _, row in df.iterrows():
        title = str(row.get("标题") or "").strip()
        summary = str(row.get("摘要") or "").strip()
        text = title + summary
        if not title or not any(k in text for k in KEYWORDS):
            continue
        key = title[:40]
        if key in seen:
            continue
        seen.add(key)
        score = 2 * sum(1 for k in CN_KEYWORDS if k in text) \
            + sum(1 for k in GLOBAL_KEYWORDS if k in text)
        items.append({
            "title": title,
            "summary": summary[:160],
            "time": str(row.get("发布时间") or ""),
            "link": str(row.get("链接") or ""),
            "_score": score,
        })
        if len(items) >= 300:
            break

    items.sort(key=lambda x: (x["_score"], x["time"]), reverse=True)
    for it in items:
        it.pop("_score", None)
    _cache.update(ts=now, items=items)
    return items[:limit]
