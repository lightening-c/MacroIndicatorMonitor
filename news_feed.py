"""
宏观数据跟踪 — 实时宏观快讯
聚合：东方财富全球快讯、新华网、人民日报(人民网)、求是网、证监会、国家统计局、
发改委、国务院、新浪财经、人民银行、金融监管总局、华尔街日报、纽约时报
带 5 分钟缓存。所有来源失败时返回上一次缓存。
"""
import re
import json
import time
from datetime import datetime
import urllib.request
from urllib.parse import urljoin

UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"
}

# 宽松关键词已弃用（个股/公司类噪声太多），统一改用下方 MACRO_KEYWORDS 严格名单
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
    "中国人民银行", "人民银行", "金融监管总局", "银保监会", "银行", "保险",
]

# 严格宏观关键词：新浪财经滚动里个股/公司新闻太多，用更聚焦宏观的名单过滤
MACRO_KEYWORDS = [
    "宏观", "GDP", "PMI", "社融", "信贷", "CPI", "PPI", "通胀", "通缩",
    "降准", "降息", "央行", "货币政策", "财政", "专项债", "国债", "汇率",
    "人民币", "出口", "进口", "外贸", "关税", "房地产", "楼市", "地产",
    "基建", "失业", "美联储", "美债", "国常会", "发改委", "统计局", "财政部",
    "证监会", "国务院", "国新办", "LPR", "金融监管总局", "人民银行", "利率",
    "资本市场", "债券", "期货", "融资保证金", "降费", "交易所", "退市", "IPO",
    # 具体宏观统计术语（不会引入个股噪声）
    "国民经济", "工业增加值", "规模以上工业", "社会消费品零售", "消费品零售",
    "进出口", "贸易差额", "用电量", "发电量", "固定资产投资", "房地产开发投资",
    "可支配收入", "居民收入", "消费支出", "财政收入", "财政支出", "税收", "海关",
    "成品油", "能源", "新质生产力", "十五五", "十四五", "高质量发展", "就业",
]


EN_KEYWORDS = [
    "china", "chinese", "economy", "economic", "growth", "recession",
    "inflation", "deflation", "tariff", "tariffs", "trade", "yuan", "renminbi",
    "pboc", "central bank", "fed", "federal reserve", "interest rate", "rates",
    "jobs", "unemployment", "gdp", "exports", "imports", "manufacturing", "pmi",
    "stocks", "bonds", "real estate", "property", "housing", "stimulus",
    "fiscal", "monetary", "consumer", "retail", "investment", "banking",
    "oil", "commodities", "prices", "debt", "deficit", "budget", "market",
    "markets", "slowdown",
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
    return any(k in text for k in MACRO_KEYWORDS)


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


def fetch_sina():
    url = "https://feed.mix.sina.com.cn/api/roll/get?pageid=153&lid=2516&num=30&page=1"
    data = _get_json(url)
    out, seen = [], set()
    for it in (data.get("result") or {}).get("data") or []:
        title = " ".join((it.get("title") or "").split())
        intro = " ".join((it.get("intro") or it.get("summary") or "").split())
        if not title or title in seen or not _match(title + " " + intro):
            continue
        seen.add(title)
        try:
            t = datetime.fromtimestamp(int(it.get("ctime") or 0)).strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            t = ""
        out.append({"title": title, "summary": intro[:160], "time": t,
                    "link": it.get("url") or "", "source": "新浪财经"})
    return out


def fetch_cls():
    import akshare as ak
    df = ak.stock_news_global_cls()
    out, seen = [], set()
    for _, row in df.iterrows():
        title = " ".join(str(row.get("标题") or "").split())
        content = " ".join(str(row.get("内容") or "").split())
        if not title:
            # 财联社电报标题常为空，从正文去电头提取
            title = re.sub(r"^财联社(?:20\d{2}年)?\d{1,2}月\d{1,2}日电[，,]?\s*", "", content)
            title = title.split("。")[0][:60]
        title = title.strip()
        if not title or title in seen or not _match(title + " " + content):
            continue
        seen.add(title)
        d = str(row.get("发布日期") or "").strip()
        t = str(row.get("发布时间") or "").strip()
        ts = (d + " " + t).strip() if d else t
        out.append({"title": title, "summary": content[:160],
                    "time": _norm_time(ts), "link": "", "source": "财联社"})
    return out


def fetch_ce():
    return _scrape_links("http://finance.ce.cn/", r"t20\d{6}", "经济日报")


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


def _get_json(url, referer=None):
    import json
    headers = dict(UA)
    if referer:
        headers["Referer"] = referer
    req = urllib.request.Request(url, headers=headers)
    return json.loads(urllib.request.urlopen(req, timeout=15).read().decode("utf-8", "ignore"))


def _match_en(text):
    t = (text or "").lower()
    return any(k in t for k in EN_KEYWORDS)


_TRANS_CACHE = {}


def _translate_zh(text):
    t = " ".join((text or "").split())
    if not t or not re.search(r"[A-Za-z]", t):
        return t
    key = t[:300]
    if key in _TRANS_CACHE:
        return _TRANS_CACHE[key]
    import urllib.parse
    try:
        u = ("https://translate.googleapis.com/translate_a/single?client=gtx&sl=en&tl=zh-CN&dt=t&q="
             + urllib.parse.quote(t[:500]))
        req = urllib.request.Request(u, headers={"User-Agent": UA["User-Agent"]})
        raw = json.loads(urllib.request.urlopen(req, timeout=10).read().decode("utf-8", "ignore"))
        zh = "".join(p[0] for p in (raw[0] or []) if p and p[0]).strip()
    except Exception:
        zh = ""
    if zh:
        _TRANS_CACHE[key] = zh
        return zh
    return t


def _fetch_rss(urls, source, max_age_days=30):
    import xml.etree.ElementTree as ET
    from email.utils import parsedate_to_datetime
    from datetime import timezone
    raw, seen = [], set()
    now = datetime.now(timezone.utc)
    for u in urls:
        try:
            root = ET.fromstring(_get(u))
        except Exception:
            continue
        for it in root.findall(".//item"):
            title = " ".join((it.findtext("title") or "").split())
            link = (it.findtext("link") or "").strip()
            desc = re.sub(r"<[^>]+>", " ", it.findtext("description") or "")
            desc = " ".join(desc.split())[:160]
            if not title or not link or title in seen:
                continue
            if not _match_en(title + " " + desc):
                continue
            try:
                dt = parsedate_to_datetime(it.findtext("pubDate") or "")
            except Exception:
                continue
            if dt is None:
                continue
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            if (now - dt).days > max_age_days:
                continue
            seen.add(title)
            raw.append({"title": title, "summary": desc, "dt": dt,
                        "link": link, "source": source})
    raw.sort(key=lambda x: x["dt"], reverse=True)
    from concurrent.futures import ThreadPoolExecutor
    def enrich(x):
        zh_title = _translate_zh(x["title"])
        zh_desc = _translate_zh(x["summary"]) if x["summary"] else ""
        return {"title": zh_title or x["title"],
                "summary": zh_desc or x["summary"],
                "time": x["dt"].astimezone().strftime("%Y-%m-%d %H:%M:%S"),
                "link": x["link"], "source": source}
    with ThreadPoolExecutor(max_workers=8) as ex:
        return list(ex.map(enrich, raw[:8]))


def fetch_pbc():
    html = _get("http://www.pbc.gov.cn/goutongjiaoliu/113456/113469/index.html")
    out, seen = [], set()
    for m in re.finditer(
            r'<a[^>]+href="(/goutongjiaoliu/113456/113469/(20\d{6})(\d{2})(\d{2})(\d{2})\d+/index\.html)"[^>]*>(.*?)</a>',
            html, re.S):
        href, ymd, hh, mm, ss, raw = m.group(1), m.group(2), m.group(3), m.group(4), m.group(5), m.group(6)
        title = re.sub(r"<[^>]+>", "", raw)
        title = " ".join(title.split())
        if not title or title in seen or not _match(title):
            continue
        seen.add(title)
        t = f"{ymd[:4]}-{ymd[4:6]}-{ymd[6:8]} {hh}:{mm}:{ss}"
        out.append({"title": title, "summary": "", "time": t,
                    "link": "http://www.pbc.gov.cn" + href, "source": "人民银行"})
    return out


def fetch_nfra():
    base = "https://www.nfra.gov.cn/cbircweb/DocInfo/SelectDocByItemUUIdsAndChild?itemUUIds="
    out, seen = [], set()
    for uuid in ("910201", "910202"):
        try:
            data = _get_json(base + uuid, referer="https://www.nfra.gov.cn/")
        except Exception:
            continue
        for it in (data.get("data") or []):
            title = " ".join((it.get("docTitle") or it.get("docSubtitle") or "").split())
            if not title or title in seen or not _match(title):
                continue
            seen.add(title)
            doc_id = it.get("docId")
            link = (f"https://www.nfra.gov.cn/cn/view/pages/ItemDetail.html?docId={doc_id}"
                    f"&itemId={it.get('itemId') or ''}&generaltype=0")
            out.append({"title": title, "summary": "",
                        "time": _norm_time(it.get("publishDate")),
                        "link": link, "source": "金融监管总局"})
    return out


def fetch_wsj():
    return _fetch_rss(["https://feeds.a.dj.com/rss/RSSWorldNews.xml",
                       "https://feeds.a.dj.com/rss/RSSMarketsMain.xml",
                       "https://feeds.a.dj.com/rss/WSJcomUSBusiness.xml"], "华尔街日报")


def fetch_nyt():
    return _fetch_rss(["https://rss.nytimes.com/services/xml/rss/nyt/World.xml",
                       "https://rss.nytimes.com/services/xml/rss/nyt/Business.xml",
                       "https://rss.nytimes.com/services/xml/rss/nyt/Economy.xml"], "纽约时报")


def get_macro_news(limit=30, force=False):
    now = time.time()
    if not force and _cache["items"] and now - _cache["ts"] < _TTL:
        return _cache["items"][:limit]

    items = []
    # 每个来源设上限，保证官方媒体不会被快讯流淹没
    sources = [(fetch_eastmoney, 12), (fetch_xinhua, 8), (fetch_people, 8),
               (fetch_qstheory, 8), (fetch_csrc, 10),
               (fetch_stats, 10), (fetch_ndrc, 10), (fetch_gov, 10),
               (fetch_sina, 8), (fetch_cls, 8), (fetch_ce, 8), (fetch_pbc, 8), (fetch_nfra, 8),
               (fetch_wsj, 6), (fetch_nyt, 6)]
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
