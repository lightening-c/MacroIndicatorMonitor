"""
宏观数据跟踪 — 实时宏观快讯
聚合：东方财富全球快讯、新华网、人民日报(人民网)、求是网、证监会
带 5 分钟缓存。所有来源失败时返回上一次缓存。
"""
import re
import time
from datetime import datetime
import urllib.request
from urllib.parse import urljoin

UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"
}

KEYWORDS = [
    "宏观", "GDP", "PMI", "社融", "信贷", "CPI", "PPI", "通胀", "通缩",
    "降准", "降息", "央行", "货币政策", "财政", "专项债", "国债", "国债收益率",
    "汇率", "人民币", "出口", "进口", "外贸", "关税",
    "房地产", "楼市", "地产", "基建", "失业", "就业率",
    "美联储", "美债", "国常会", "发改委", "统计局", "财政部", "证监会",
    "国务院", "国新办", "LPR", "监管", "上市公司", "退市", "IPO", "基金",
    "期货", "债券", "利率", "资本市场", "金融", "经济", "消费", "投资",
    "发展", "改革", "政策", "市场", "产业", "企业", "开放", "增长", "稳",
    "价格", "收入", "就业", "贸易", "制造业", "服务业", "进出口",
]

_cache = {"ts": 0.0, "items": []}
_TTL = 300


def _get(url, timeout=15):
    req = urllib.request.Request(url, headers=UA)
    return urllib.request.urlopen(req, timeout=timeout).read().decode("utf-8", "ignore")


def _norm_time(s):
    s = (s or "").strip()
    if not s:
        return ""
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d",
                "%Y/%m/%d %H:%M", "%Y/%m/%d"):
        try:
            return datetime.strptime(s, fmt).strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            continue
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)} 00:00:00"
    return ""


def _match(text):
    return any(k in text for k in KEYWORDS)


def fetch_eastmoney():
    import akshare as ak
    df = ak.stock_news_global_em()
    out = []
    for _, row in df.iterrows():
        title = str(row.get("标题") or "").strip()
        summary = str(row.get("摘要") or "").strip()
        if not title or not _match(title + summary):
            continue
        out.append({"title": title, "summary": summary[:160],
                    "time": _norm_time(str(row.get("发布时间") or "")),
                    "link": str(row.get("链接") or ""), "source": "东方财富"})
    return out


def _scrape_links(url, pattern, source, time_from_url=True):
    """通用：抓取页面内符合 pattern 的 (链接, 标题)，时间从 URL 里的 YYYYMMDD 解析。"""
    html = _get(url)
    out, seen = [], set()
    for href, title in re.findall(r'<a[^>]+href="([^"]+)"[^>]*>([^<]{5,80})</a>', html):
        m = re.search(pattern, href)
        if not m:
            continue
        title = " ".join(title.split())
        if not title or title in seen or not _match(title):
            continue
        seen.add(title)
        t = ""
        if time_from_url:
            g = re.search(r"20(\d{2})[/-]?(\d{2})[/-]?(\d{2})", href)
            if g:
                y, mo, d = "20" + g.group(1), g.group(2), g.group(3)
                t = f"{y}-{mo}-{d} 00:00:00"
        if href.startswith("//"):
            href = "https:" + href
        else:
            href = urljoin(url, href)
        out.append({"title": title, "summary": "", "time": t,
                    "link": href, "source": source})
    return out


def fetch_xinhua():
    return _scrape_links("https://www.news.cn/", r"/20\d{6}/", "新华网")


def fetch_people():
    return _scrape_links("http://www.people.com.cn/", r"/n1/20\d{2}/\d{4}/", "人民日报")


def fetch_qstheory():
    return _scrape_links("https://www.qstheory.cn/economy/index.htm",
                         r"/20\d{6}/", "求是")


def fetch_stats():
    return _scrape_links("https://www.stats.gov.cn/sj/zxfb/", r"t20\d{6}", "国家统计局")


def fetch_ndrc():
    return _scrape_links("https://www.ndrc.gov.cn/xwdt/xwfb/", r"t20\d{6}", "发改委")


def fetch_gov():
    import json
    url = ("https://sousuo.www.gov.cn/search-gov/data?t=zhengcelibrary_gw&q=&timetype=timeqb"
           "&mintime=&maxtime=&sort=pubtime&sortType=1&searchfield=title&p=1&n=15")
    data = json.loads(_get(url))
    lst = (data.get("searchVO") or {}).get("listVO") or []
    out = []
    for it in lst:
        title = " ".join((it.get("title") or "").split())
        if not title or not _match(title):
            continue
        out.append({"title": title, "summary": (it.get("summary") or "")[:160],
                    "time": _norm_time((it.get("pubtimeStr") or "").replace(".", "-")),
                    "link": it.get("url") or "", "source": "国务院"})
    return out


def fetch_csrc():
    html = _get("https://www.csrc.gov.cn/csrc/index.shtml")
    out, seen = [], set()
    year = datetime.now().year
    for href, title, md in re.findall(
            r'<a[^>]+href="(/csrc/[^"]+)"[^>]*>([^<]{5,80})</a>\s*<span class="time">\s*(\d{2}-\d{2})',
            html, re.S):
        title = title.strip()
        if not title or title in seen:
            continue
        seen.add(title)
        if "行政复议" in title:
            continue
        mon, day = md.split("-")
        y = year if int(mon) <= datetime.now().month else year - 1
        out.append({"title": title, "summary": "",
                    "time": f"{y}-{mon}-{day} 00:00:00",
                    "link": "https://www.csrc.gov.cn" + href, "source": "证监会"})
    return out


def get_macro_news(limit=30, force=False):
    now = time.time()
    if not force and _cache["items"] and now - _cache["ts"] < _TTL:
        return _cache["items"][:limit]

    items = []
    # 每个来源设上限，保证官方媒体不会被快讯流淹没
    sources = [(fetch_eastmoney, 12), (fetch_xinhua, 8), (fetch_people, 8),
               (fetch_qstheory, 8), (fetch_csrc, 10),
               (fetch_stats, 10), (fetch_ndrc, 10), (fetch_gov, 10)]
    for fn, cap in sources:
        try:
            items.extend(fn()[:cap])
        except Exception:
            continue

    seen, uniq = set(), []
    for it in items:
        key = it["title"][:40]
        if key in seen:
            continue
        seen.add(key)
        uniq.append(it)
    uniq.sort(key=lambda x: x.get("time") or "", reverse=True)

    # 每个来源先保底 2 条，保证官方来源不被快讯流淹没；再按时间补足
    per, picked = {}, []
    for it in uniq:
        src = it.get("source", "")
        if per.get(src, 0) < 2:
            picked.append(it)
            per[src] = per.get(src, 0) + 1
    chosen = {id(x) for x in picked}
    for it in uniq:
        if len(picked) >= limit:
            break
        if id(it) not in chosen:
            picked.append(it)
    picked.sort(key=lambda x: x.get("time") or "", reverse=True)

    if picked:
        _cache.update(ts=now, items=picked)
    return picked[:limit]
