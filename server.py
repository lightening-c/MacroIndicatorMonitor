"""
宏观数据跟踪 — 本地服务器
端口 4321, 提供静态文件 + API: POST /api/update 触发全流程更新
"""
import http.server
import subprocess
import sys
import os
import json
import re
import socket
import threading
import urllib.request
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PYTHON = sys.executable
UPDATE_LOG = os.path.join(BASE_DIR, "data", "update_log.json")
MANUAL_VIEWS = os.path.join(BASE_DIR, "assets", "manual_views.json")
DISMISSED_VIEWS = os.path.join(BASE_DIR, "assets", "dismissed_views.json")
READING_NOTES = os.path.join(BASE_DIR, "assets", "reading_notes.json")
METHODOLOGY = os.path.join(BASE_DIR, "assets", "methodology.json")
SAVE_LOCK = threading.Lock()
READING_NOTES_LOCK = threading.Lock()


def _load_list(path):
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _save_list(path, items):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with SAVE_LOCK:
        tmp = path + f".{os.getpid()}.{threading.get_ident()}.tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(items, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)


def load_manual_views():
    return _load_list(MANUAL_VIEWS)


def save_manual_views(items):
    _save_list(MANUAL_VIEWS, items)


def load_dismissed_views():
    return _load_list(DISMISSED_VIEWS)


def save_dismissed_views(items):
    _save_list(DISMISSED_VIEWS, items)


def load_reading_notes():
    return _load_list(READING_NOTES)


def save_reading_notes(items):
    _save_list(READING_NOTES, items)


def load_methodology():
    try:
        with open(METHODOLOGY, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_methodology(data):
    os.makedirs(os.path.dirname(METHODOLOGY), exist_ok=True)
    with SAVE_LOCK:
        tmp = METHODOLOGY + f".{os.getpid()}.{threading.get_ident()}.tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, METHODOLOGY)


ABSTRACT_CACHE = {}


def _clean_abstract(text, title=None, limit=180):
    import re
    t = re.sub(r"\s+", " ", text or "").strip()
    cut = None
    head = t[:400]
    for mk in ("核心观点", "基本内容", "主要观点", "摘要", "正文", "要点", "前言"):
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
    t = re.sub(r"（[^）]{0,24}证号[^）]*）", " ", t)
    t = re.sub(r"投资咨询业务资格[^，。：]{0,30}", " ", t)
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

# ---------------------------------------------------------------------------
# 外部文章抓取（内容摘要）
# ---------------------------------------------------------------------------
ARTICLE_HOSTS = (
    "eastmoney.com", "dfcfw.com", "stockstar.com", "stcn.com", "gelonghui.com",
    "163.com", "sina.com.cn", "hexun.com", "news.cn", "xinhuanet.com",
    "people.com.cn", "qstheory.cn", "stats.gov.cn", "ndrc.gov.cn", "gov.cn",
    "csrc.gov.cn", "yicai.com", "caixin.com", "ce.cn",
    "pbc.gov.cn", "nfra.gov.cn", "wsj.com", "nytimes.com",
)
ARTICLE_CACHE = {}
ARTICLE_TTL = 600
ARTICLE_JUNK = re.compile(
    r"^(责任编辑|编辑|来源[:：]|免责声明|风险提示|特别提示|版权|版权所有|"
    r"扫描|扫码|点击|关注|原标题|相关阅读|延伸阅读|上一篇|下一篇|"
    r"返回首页|分享到|字体[:：]|声明[:：])")


def _host_of(url):
    from urllib.parse import urlparse
    return (urlparse(url).hostname or "").lower()


def _validate_article_url(url):
    import ipaddress
    import socket
    from urllib.parse import urlparse
    p = urlparse(url or "")
    if p.scheme not in ("http", "https"):
        raise ValueError("仅支持 http/https 链接")
    if p.username or p.password:
        raise ValueError("链接不合法")
    host = (p.hostname or "").lower().rstrip(".")
    if not host:
        raise ValueError("链接缺少域名")
    port = p.port or (443 if p.scheme == "https" else 80)
    if port not in (80, 443):
        raise ValueError("仅支持 80/443 端口")
    if not any(host == d or host.endswith("." + d) for d in ARTICLE_HOSTS):
        raise ValueError("该来源暂不支持抓取，请打开原文查看")
    try:
        infos = socket.getaddrinfo(host, None)
    except Exception:
        raise ValueError("域名解析失败")
    for info in infos:
        try:
            ip = ipaddress.ip_address(info[4][0])
        except Exception:
            continue
        if not ip.is_global:
            raise ValueError("目标地址不允许访问")
    return url


def _decode_html(data, ctype):
    m = re.search(r"charset=([\w-]+)", ctype or "", re.I)
    encs = [m.group(1)] if m else []
    head = data[:4000].decode("ascii", "ignore")
    m2 = re.search(r"""charset=["']?([\w-]+)""", head, re.I)
    if m2:
        encs.append(m2.group(1))
    encs += ["utf-8", "gb18030"]
    for enc in encs:
        try:
            return data.decode(enc)
        except Exception:
            continue
    return data.decode("utf-8", "ignore")


def _meta_content(soup, names):
    for n in names:
        tag = soup.find("meta", attrs={"property": n}) or soup.find("meta", attrs={"name": n})
        if tag and tag.get("content"):
            return " ".join(tag["content"].split())
    return ""


def _block_texts(el):
    ps = [" ".join(p.get_text(" ", strip=True).split()) for p in el.find_all("p")]
    ps = [x for x in ps if len(x) >= 12]
    if len(ps) >= 3 and sum(len(x) for x in ps) >= 180:
        return ps
    lines = [" ".join(x.split()) for x in el.get_text("\n", strip=True).split("\n")]
    lines = [x for x in lines if len(x) >= 12]
    if sum(len(x) for x in lines) > sum(len(x) for x in ps) + 60:
        return lines
    if len(ps) >= 3:
        return ps
    leaf = []
    for d in el.find_all("div"):
        if d.find(["div", "p", "table", "ul", "ol"]):
            continue
        s = " ".join(d.get_text(" ", strip=True).split())
        if len(s) >= 12:
            leaf.append(s)
    return ps + leaf


def _clean_article_lines(lines):
    out, seen = [], set()
    for s in lines:
        s = (s or "").replace("u200b", "").replace("​", "")
        s = " ".join(s.split())
        if len(s) < 10 or ARTICLE_JUNK.search(s):
            continue
        key = re.sub(r"[^一-龥A-Za-z0-9]", "", s)[:60]
        if s in seen or (key and key in seen):
            continue
        seen.add(s)
        seen.add(key)
        out.append(s)
    return out


def _extract_article(html):
    from bs4 import BeautifulSoup
    try:
        soup = BeautifulSoup(html, "html5lib")
    except Exception:
        soup = BeautifulSoup(html, "html.parser")
    title = _meta_content(soup, ("og:title", "twitter:title"))
    if not title and soup.title:
        title = " ".join(soup.title.get_text(" ", strip=True).split())
    date = _meta_content(soup, ("article:published_time", "og:release_date",
                                "pubdate", "publishdate", "date", "weibo:article:create_at",
                                "firstpublishedtime", "lastmodifiedtime"))
    if not date:
        import json as _json
        for sc in soup.find_all("script", attrs={"type": "application/ld+json"}):
            try:
                obj = _json.loads(sc.string or sc.get_text() or "")
            except Exception:
                continue
            items = obj if isinstance(obj, list) else [obj]
            for o in items:
                if isinstance(o, dict) and o.get("datePublished"):
                    date = str(o["datePublished"])
                    break
            if date:
                break
    for tag in soup(["script", "style", "noscript", "svg", "form", "iframe",
                     "header", "footer", "nav", "aside"]):
        tag.decompose()
    selectors = [
        "article", "[itemprop=articleBody]", "#js_content", "#Content", "#content",
        "#articleContent", "#artibody", "#article_content", "#news_content",
        "#detail-content", ".article-content", ".article_content", ".articleCont",
        ".post_content", ".content_area", ".detail-content", ".main-content",
        ".news-content", ".TRS_Editor", ".rich_media_content", ".article",
        ".article-body", ".artical_content", ".txt_con", ".detail_text", ".content",
    ]
    best, best_score, seen = [], 0, set()
    for sel in selectors:
        try:
            els = soup.select(sel)
        except Exception:
            els = []
        for el in els:
            if id(el) in seen:
                continue
            seen.add(id(el))
            ps = _block_texts(el)
            if not ps:
                continue
            plen = sum(len(x) for x in ps)
            if plen < 80:
                continue
            link_len = sum(len(a.get_text(strip=True)) for a in el.find_all("a"))
            score = plen - link_len * 2
            if plen / max(1, len(ps)) < 16:
                score -= 200
            if score > best_score:
                best_score, best = score, ps
    if best_score < 300:
        for el in soup.find_all(["article", "section", "div"]):
            cls = " ".join(el.get("class") or []) + " " + (el.get("id") or "")
            if re.search(r"nav|menu|foot|head|side|comment|share|related|list", cls, re.I):
                continue
            txt = el.get_text(" ", strip=True)
            if not (150 <= len(txt) <= 30000):
                continue
            ps = _block_texts(el)
            if not ps:
                continue
            plen = sum(len(x) for x in ps)
            link_len = sum(len(a.get_text(strip=True)) for a in el.find_all("a"))
            score = plen - link_len * 2
            if plen / max(1, len(ps)) < 16:
                score -= 200
            if score > best_score:
                best_score, best = score, ps
    if best_score < 120:
        alt = _block_texts(soup.body or soup)
        if sum(len(x) for x in alt) > best_score:
            best = alt
    if not best:
        text = (soup.body or soup).get_text("\n", strip=True)
        best = [x for x in text.split("\n") if len(x) >= 12]
    lines = _clean_article_lines(best)
    if not date:
        probe = " ".join(lines[:3])
        m = re.search(r"(20\d{2})[-/年.](\d{1,2})[-/月.](\d{1,2})", probe)
        if m:
            date = f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    if date:
        m = re.search(r"(20\d{2})[-/年.](\d{1,2})[-/月.](\d{1,2})", str(date))
        if m:
            date = f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    text = "\n".join(lines)[:12000]
    return {"title": title[:160], "text": text,
            "date": (date or "")[:10], "paragraphs": len(lines)}


def _date_from_url(url):
    m = re.search(r"(20\d{2})(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])", url or "")
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    return ""


class _SafeArticleRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        _validate_article_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _fetch_nfra_doc(doc_id):
    import json as _json
    api = f"https://www.nfra.gov.cn/cbircweb/DocInfo/SelectByDocId?docId={doc_id}"
    req = urllib.request.Request(api, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/120 Safari/537.36",
        "Referer": "https://www.nfra.gov.cn/",
    })
    with urllib.request.urlopen(req, timeout=20) as r:
        data = _json.loads(r.read().decode("utf-8", "ignore"))
    item = data.get("data") or {}
    html = item.get("docClob") or ""
    if not html:
        raise ValueError("未能获取该文正文")
    out = _extract_article(html)
    out["title"] = (item.get("docTitle") or item.get("docSubtitle") or out.get("title") or "")[:160]
    m = re.search(r"(20\d{2})-(\d{1,2})-(\d{1,2})", item.get("publishDate") or "")
    out["date"] = f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}" if m else ""
    out["site"] = "www.nfra.gov.cn"
    if not out.get("text"):
        raise ValueError("未能从页面提取到正文")
    return out


def fetch_article(url, force=False):
    import time
    url = _validate_article_url(url)
    now = time.time()
    hit = ARTICLE_CACHE.get(url)
    if hit and not force and now - hit[0] < ARTICLE_TTL:
        return hit[1]
    from urllib.parse import urlparse, parse_qs
    if _host_of(url).endswith("nfra.gov.cn") and "/ItemDetail.html" in url:
        doc_id = (parse_qs(urlparse(url).query).get("docId", [""])[0] or "").strip()
        if doc_id.isdigit():
            out = _fetch_nfra_doc(doc_id)
            ARTICLE_CACHE[url] = (now, out)
            return out
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/120 Safari/537.36",
        "Accept-Language": "zh-CN,zh;q=0.9",
    })
    with urllib.request.build_opener(_SafeArticleRedirect()).open(req, timeout=20) as r:
        final = r.geturl()
        _validate_article_url(final)
        ctype = (r.headers.get("Content-Type") or "").lower()
        data = r.read(3 * 1024 * 1024)
    if "pdf" in ctype or final.lower().split("?")[0].endswith(".pdf"):
        import io
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(data))
        raw = "\n".join((p.extract_text() or "") for p in reader.pages[:3])
        lines = _clean_article_lines(raw.split("\n"))
        out = {"title": "", "text": "\n".join(lines)[:12000],
               "date": "", "paragraphs": len(lines)}
    else:
        out = _extract_article(_decode_html(data, ctype))
    out["site"] = _host_of(final)
    if not out.get("date"):
        out["date"] = _date_from_url(final)
    if not out.get("text"):
        raise ValueError("未能从页面提取到正文，请打开原文查看")
    ARTICLE_CACHE[url] = (now, out)
    return out

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
        elif self.path == "/api/reading-notes":
            try:
                length = int(self.headers.get("Content-Length") or 0)
                raw = self.rfile.read(length).decode("utf-8") if length else "{}"
                body = json.loads(raw or "{}")
            except Exception as e:
                self.send_json(400, {"ok": False, "message": f"请求体解析失败：{e}"})
                return
            text = (body.get("raw") or "").strip()
            if len(text) < 10:
                self.send_json(400, {"ok": False, "message": "请先粘贴原文内容"})
                return
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            note = {
                "id": str(body.get("id") or datetime.now().strftime("%Y%m%d%H%M%S%f")),
                "kind": str(body.get("kind") or "note")[:20],
                "category": str(body.get("category") or "")[:20],
                "created_at": str(body.get("created_at") or now),
                "updated_at": str(body.get("updated_at") or "")[:20],
                "source": str(body.get("source") or "手动粘贴")[:200],
                "article_date": str(body.get("article_date") or "")[:20],
                "title": str(body.get("title") or "")[:300],
                "link": str(body.get("link") or "")[:1000],
                "memo": str(body.get("memo") or "")[:1000],
                "raw": text[:50000],
                "summary": [str(x)[:500] for x in (body.get("summary") or []) if str(x).strip()][:10],
                "stance": str(body.get("stance") or "")[:20],
                "cause": str(body.get("cause") or "")[:20],
                "action": str(body.get("action") or "")[:1000],
                "note": str(body.get("note") or "")[:2000],
            }
            try:
                with READING_NOTES_LOCK:
                    items = load_reading_notes()
                    items = [note] + [x for x in items if x.get("id") != note["id"]]
                    items = items[:500]
                    save_reading_notes(items)
                self.send_json(200, {"ok": True, "item": note, "count": len(items)})
            except Exception as e:
                self.send_json(500, {"ok": False, "message": f"保存失败：{e}"})
        elif self.path == "/api/methodology":
            try:
                length = int(self.headers.get("Content-Length") or 0)
                raw = self.rfile.read(length).decode("utf-8") if length else "{}"
                body = json.loads(raw or "{}")
            except Exception as e:
                self.send_json(400, {"ok": False, "message": f"请求体解析失败：{e}"})
                return
            doc = {
                "raw": str(body.get("raw") or "")[:200000],
                "article": str(body.get("article") or "")[:200000],
                "updated_at": str(body.get("updated_at") or datetime.now().strftime("%Y-%m-%d %H:%M:%S"))[:20],
            }
            try:
                save_methodology(doc)
                self.send_json(200, {"ok": True, "data": doc})
            except Exception as e:
                self.send_json(500, {"ok": False, "message": f"保存失败：{e}"})
        elif self.path == "/api/views/dismiss":
            try:
                length = int(self.headers.get("Content-Length") or 0)
                raw = self.rfile.read(length).decode("utf-8") if length else "{}"
                body = json.loads(raw or "{}")
            except Exception as e:
                self.send_json(400, {"ok": False, "message": f"请求体解析失败：{e}"})
                return
            key = (body.get("key") or "").strip()
            if not key:
                self.send_json(400, {"ok": False, "message": "缺少 key"})
                return
            items = load_dismissed_views()
            if key not in items:
                items.append(key)
                try:
                    save_dismissed_views(items)
                except Exception as e:
                    self.send_json(500, {"ok": False, "message": f"保存失败：{e}"})
                    return
            self.send_json(200, {"ok": True, "count": len(items)})
        else:
            self.send_json(404, {"ok": False, "message": "Not Found"})

    def do_DELETE(self):
        if self.path.startswith("/api/reading-notes"):
            from urllib.parse import urlparse, parse_qs
            qs = parse_qs(urlparse(self.path).query)
            nid = (qs.get("id", [""])[0] or "").strip()
            if not nid:
                self.send_json(400, {"ok": False, "message": "缺少 id"})
                return
            with READING_NOTES_LOCK:
                items = load_reading_notes()
                kept = [x for x in items if str(x.get("id")) != nid]
                if len(kept) == len(items):
                    self.send_json(404, {"ok": False, "message": "未找到该笔记"})
                    return
                try:
                    save_reading_notes(kept)
                except Exception as e:
                    self.send_json(500, {"ok": False, "message": f"保存失败：{e}"})
                    return
            self.send_json(200, {"ok": True, "count": len(kept)})
        elif self.path.startswith("/api/views/dismiss"):
            from urllib.parse import urlparse, parse_qs
            qs = parse_qs(urlparse(self.path).query)
            key = (qs.get("key", [""])[0] or "").strip()
            if not key:
                self.send_json(400, {"ok": False, "message": "缺少 key"})
                return
            items = [str(k) for k in load_dismissed_views() if str(k) != key]
            try:
                save_dismissed_views(items)
            except Exception as e:
                self.send_json(500, {"ok": False, "message": f"保存失败：{e}"})
                return
            self.send_json(200, {"ok": True, "count": len(items)})
        elif self.path.startswith("/api/manual-views"):
            from urllib.parse import urlparse, parse_qs
            qs = parse_qs(urlparse(self.path).query)
            key = (qs.get("key", [""])[0] or "").strip()
            if not key:
                self.send_json(400, {"ok": False, "message": "缺少 key"})
                return
            items = load_manual_views()
            kept = [x for x in items
                    if f'{x.get("org")}|{x.get("date")}|{x.get("topic")}' != key]
            if len(kept) == len(items):
                self.send_json(404, {"ok": False, "message": "未找到该条目"})
                return
            try:
                save_manual_views(kept)
            except Exception as e:
                self.send_json(500, {"ok": False, "message": f"保存失败：{e}"})
                return
            self.send_json(200, {"ok": True, "count": len(kept)})
        else:
            self.send_json(404, {"ok": False, "message": "Not Found"})

    def do_GET(self):
        if self.path == "/api/status":
            self.send_json(200, {"ok": True, "running": STATUS["running"], "current_step": STATUS["current_step"], "last_update": STATUS["last_update"], "last_result": STATUS["last_result"]})
        elif self.path == "/api/manual-views":
            self.send_json(200, {"ok": True, "items": load_manual_views(),
                                 "dismissed": load_dismissed_views()})
        elif self.path == "/api/reading-notes":
            self.send_json(200, {"ok": True, "items": load_reading_notes()})
        elif self.path == "/api/methodology":
            self.send_json(200, {"ok": True, "data": load_methodology()})
        elif self.path == "/api/corrections":
            items = _load_list(os.path.join(BASE_DIR, "data", "corrections_auto.json"))
            self.send_json(200, {"ok": True, "items": items})
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
                self.send_json(200, {"ok": False, "message": f"抓取失败：{e}"})
        elif self.path.startswith("/api/article"):
            from urllib.parse import urlparse, parse_qs
            qs = parse_qs(urlparse(self.path).query)
            url = (qs.get("url", [""])[0] or "").strip()
            force = qs.get("force", ["0"])[0] == "1"
            try:
                data = fetch_article(url, force=force)
                self.send_json(200, dict(ok=True, **data))
            except ValueError as e:
                self.send_json(400, {"ok": False, "message": str(e)})
            except Exception as e:
                self.send_json(500, {"ok": False, "message": f"抓取失败：{e}"})
        elif self.path.startswith("/api/views"):
            from urllib.parse import urlparse, parse_qs
            qs = parse_qs(urlparse(self.path).query)
            try:
                limit = int(qs.get("limit", ["10"])[0])
            except ValueError:
                limit = 10
            force = qs.get("force", ["0"])[0] == "1"
            try:
                import views_feed
                raw = views_feed.get_views(limit=max(limit * 4, 40), force=force)
                skip = {f'{x.get("org")}|{x.get("date")}|{x.get("topic")}' for x in load_manual_views()}
                skip |= {str(k) for k in load_dismissed_views()}
                items = [x for x in raw if f'{x.get("org")}|{x.get("date")}|{x.get("topic")}' not in skip][:limit]
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
