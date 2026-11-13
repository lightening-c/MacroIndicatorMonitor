"""
宏观数据跟踪 — 分析引擎 v3
Dynamic indicator loading from config.yaml, auto-detect date/value columns,
compute trend / momentum / volatility / correlation / composite indices / decomposition.
"""
import os
import re
import json
import yaml
import numpy as np
import pandas as pd
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
CONFIG_FILE = os.path.join(BASE_DIR, "config.yaml")
ANALYSIS_OUTPUT = os.path.join(DATA_DIR, "analysis_result.json")

# Indicators where rising is "bad" (signal flipped)
NEGATIVE_INDICATORS = {"cpi", "ppi", "unemployment", "lpr", "reserve_ratio",
                       "rmb_rate", "shibor_overnight", "bond_yield_10y"}

# ---------------------------------------------------------------------------
# Legacy column hints: used as fallback / override for auto-detection
# Format: {ind_id: {"date_col": "...", "val_col": "..."}}
# When {ind_id}.csv exists but column auto-detection may be ambiguous.
# ---------------------------------------------------------------------------
COLUMN_HINTS = {
    "pmi_manufacturing":     {"date_col": "日期",     "val_col": "制造业-指数"},
    "pmi_non_manufacturing": {"date_col": "日期",     "val_col": "非制造业PMI"},
    "social_financing":      {"date_col": "月份",     "val_col": "当月-同比增长"},
    "m2_growth":             {"date_col": "月份",     "val_col": "货币和准货币(M2)-同比增长"},
    "consumer_confidence":   {"date_col": "月份",     "val_col": "消费者信心指数-指数值"},
    "enterprise_boom":       {"date_col": "日期",     "val_col": "企业景气指数"},
    "shibor_overnight":      {"date_col": "日期",     "val_col": "隔夜Shibor"},
    "margin_sh":             {"date_col": "日期",     "val_col": "沪市融资余额"},
    "commodity_price_index": {"date_col": "日期", "val_col": "中证商品期货指数"},
    "new_house_price":       {"date_col": "日期",     "val_col": "新建住宅价格指数同比"},
    "sh_index":              {"date_col": "日期",     "val_col": "收盘价"},
    "sz_index":              {"date_col": "日期",     "val_col": "收盘价"},
    "industrial_production": {"date_col": "日期",     "val_col": "工业增加值增速"},
    "fixed_asset_investment":{"date_col": "日期",     "val_col": "固定资产投资当月同比"},
    "retail_sales":          {"date_col": "月份",     "val_col": "同比增长"},
    "electricity":           {"date_col": "日期",     "val_col": "用电量当月同比"},
    "services_pmi":          {"date_col": "日期",     "val_col": "财新服务业PMI"},
    "bond_yield_10y":        {"date_col": "日期",     "val_col": "10年国债收益率"},
    "tsf_rolling_yoy":       {"date_col": "日期",     "val_col": "社融滚动增量同比"},
    "exports_yoy":           {"date_col": "日期",     "val_col": "出口增速"},
    "imports_yoy":           {"date_col": "日期",     "val_col": "进口增速"},
    "freight_index":         {"date_col": "日期",     "val_col": "货运指数"},
    "fiscal_revenue":        {"date_col": "日期",     "val_col": "财政收入增速"},
    "gdp_growth":            {"date_col": "季度",     "val_col": "国内生产总值-同比增长"},
    "cpi":                   {"date_col": "月份",     "val_col": "全国-同比增长"},
    "ppi":                   {"date_col": "月份",     "val_col": "当月同比增长"},
    "unemployment":          {"date_col": "date",     "val_col": "value"},
    "trade_balance":         {"date_col": "日期",     "val_col": "贸易差额"},
    "lpr":                   {"date_col": "TRADE_DATE", "val_col": "RATE_1"},
    "reserve_ratio":         {"date_col": "日期",     "val_col": "存款准备金率"},
    "real_estate_dev":       {"date_col": "日期",     "val_col": "国房景气指数"},
    "fx_reserves":           {"date_col": "日期",     "val_col": "外汇储备"},
    "rmb_rate":              {"date_col": "月份",     "val_col": "国家外汇储备-同比"},
}


# ---------------------------------------------------------------------------
# Date parsing
# ---------------------------------------------------------------------------
def parse_date(val):
    """Try to parse a string or numeric value into a datetime object."""
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return pd.NaT
    s = str(val).strip()
    if not s:
        return pd.NaT

    # Numeric date: 201801, 20180112, 2018.01
    if re.match(r'^\d{4,8}(\.\d+)?$', s):
        clean = s.replace(".", "")
        if len(clean) == 4:
            try:
                return pd.to_datetime(clean, format="%Y")
            except Exception:
                pass
        elif len(clean) == 6:
            try:
                return pd.to_datetime(clean, format="%Y%m")
            except Exception:
                pass
        elif len(clean) == 8:
            try:
                return pd.to_datetime(clean, format="%Y%m%d")
            except Exception:
                pass

    # Chinese patterns
    m = re.match(r'^(\d{4})年(\d{1,2})月份?$', s)
    if m:
        try:
            return pd.to_datetime(f"{m.group(1)}-{int(m.group(2)):02d}")
        except Exception:
            pass

    m = re.match(r'^(\d{4})年第(\d)季度$', s)
    if m:
        try:
            return pd.to_datetime(f"{m.group(1)}-Q{m.group(2)}")
        except Exception:
            pass

    m = re.match(r'^(\d{4})年第(\d)-(\d)季度$', s)
    if m:
        try:
            # 累计口径如"2026年第1-3季度"应落在第3季度(Q3)
            return pd.to_datetime(f"{m.group(1)}-Q{m.group(3)}")
        except Exception:
            pass

    m = re.match(r'^(\d{4})[.\s]Q(\d)$', s)
    if m:
        try:
            return pd.to_datetime(f"{m.group(1)}-Q{m.group(2)}")
        except Exception:
            pass

    # e.g. "2007年01月05日" (reserve_ratio)
    m = re.match(r'^(\d{4})年(\d{1,2})月(\d{1,2})日$', s)
    if m:
        try:
            return pd.to_datetime(f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}")
        except Exception:
            pass

    # Standard formats
    for fmt in ["%Y-%m-%d", "%Y/%m/%d", "%Y%m%d", "%Y-%m", "%Y/%m", "%Y", "%Y年"]:
        try:
            return pd.to_datetime(s, format=fmt)
        except Exception:
            continue

    # Pandas auto-parse as last resort
    try:
        r = pd.to_datetime(s, errors="coerce")
        if pd.notna(r):
            return r
    except Exception:
        pass

    return pd.NaT


# ---------------------------------------------------------------------------
# Auto column detection (used when hints are absent or column not found)
# ---------------------------------------------------------------------------
DATE_KW = ["日期", "时间", "date", "月份", "季度", "统计时间",
           "trade_date", "统计", "公布", "month", "quarter"]

VAL_HIGH = ["同比增长", "同比", "增速", "收盘价", "收盘", "今值", "lpr1y",
            "rate_1", "amount", "余额", "value", "利率", "非制造业PMI",
            "企业景气指数", "隔夜Shibor", "沪市融资余额", "新建住宅价格指数",
            "出口增速", "进口增速", "货运指数", "财政收入增速", "固定资产投资增速",
            "房地产投资增速", "外汇储备", "存款准备金率"]
VAL_GOOD = ["指数", "指数值", "当月", "当月同比增长", "全社会用电量同比",
            "增长率", "增长", "值", "价", "制造业-指数", "消费者信心指数-指数值",
            "人民币中间价"]
VAL_AVOID = ["环比", "预测", "前值", "累计", "绝对值", "数量", "环比增长",
             "lpr5y", "rate_2", "上年同月", "上年同期", "绝对值",
             "黄金储备", "国家外汇储备-环比"]


def _kw_score(col, keywords):
    """Return number of keywords that are a substring of col (case-insensitive)."""
    c = str(col).lower().strip()
    return sum(1 for k in keywords if k.lower().strip() in c)


def detect_date_column(df):
    """Find best date column. If first column looks like a label/title, skip it."""
    best, best_score = None, -1
    for col in df.columns:
        s = _kw_score(col, DATE_KW)
        if s > best_score:
            best_score, best = s, col
    if best is None:
        best = df.columns[0]
    return best


def detect_value_column(df, date_col):
    """Find best numeric value column, excluding the date column."""
    candidates = []
    for col in df.columns:
        if col == date_col:
            continue
        s = pd.to_numeric(df[col], errors="coerce")
        n = s.notna().sum()
        if n == 0:
            continue
        high = _kw_score(col, VAL_HIGH)
        good = _kw_score(col, VAL_GOOD)
        avoid = _kw_score(col, VAL_AVOID)
        coverage = n / len(df)
        score = high * 12 + good * 4 - avoid * 6 + coverage * 3
        candidates.append((col, score, n))
    if not candidates:
        return None
    candidates.sort(key=lambda x: x[1], reverse=True)
    return candidates[0][0]


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------
def load_indicator_data(ind_id):
    """Load CSV for an indicator. Returns (df, date_col, val_col) or None."""

    # Find file: {ind_id}.csv (new naming) or skip if missing
    filepath = os.path.join(DATA_DIR, f"{ind_id}.csv")
    if not os.path.isfile(filepath):
        print(f"    [ERR] 文件不存在: {ind_id}.csv")
        return None

    try:
        df = pd.read_csv(filepath, encoding="utf-8-sig")
        if df.empty:
            print(f"    [ERR] 文件为空")
            return None
    except Exception as e:
        print(f"    [ERR] 读取失败: {e}")
        return None

    # Special handling: unemployment has item column, filter to 全国城镇调查失业率
    if ind_id == "unemployment" and "item" in df.columns:
        df = df[df["item"].str.contains("全国城镇调查失业率", na=False)].copy()
        if df.empty:
            print(f"    [ERR] 失业率筛选后无数据")
            return None

    # Special handling: industrial_production has "商品" label column
    if ind_id == "industrial_production" and "商品" in df.columns:
        # Move date detection past the label column
        pass  # handled by date detection heuristics

    # Special handling: trade_balance has "商品" label column
    if ind_id == "trade_balance" and "商品" in df.columns:
        pass  # handled by date detection heuristics

    # Determine columns: use explicit hints if present and column exists
    hints = COLUMN_HINTS.get(ind_id, {})
    date_col = hints.get("date_col") if hints.get("date_col") in df.columns else None
    val_col = hints.get("val_col") if hints.get("val_col") in df.columns else None

    if date_col is None:
        date_col = detect_date_column(df)
    if val_col is None:
        val_col = detect_value_column(df, date_col)

    if val_col is None:
        print(f"    [ERR] 无法检测数值列, 可用列: {list(df.columns)}")
        return None

    # Parse dates
    df["_date"] = df[date_col].apply(parse_date)
    df = df[df["_date"].notna()].copy()
    if df.empty:
        print(f"    [ERR] 日期解析后无有效数据")
        return None
    df = df.sort_values("_date")

    # Parse values
    df["_val"] = pd.to_numeric(df[val_col], errors="coerce")
    df = df[df["_val"].notna()].copy()
    if df.empty:
        print(f"    [ERR] 数值解析后无有效数据 (列: {val_col})")
        return None

    print(f"    [OK] {date_col} | {val_col} | {len(df)}行")
    return df, date_col, val_col


# ---------------------------------------------------------------------------
# Trend analysis
# ---------------------------------------------------------------------------
def compute_trend(values, ma_short=3, ma_long=6):
    v = values.dropna().reset_index(drop=True)
    if len(v) < 1:
        return {"latest": None, "prev": None, "mom_change": None,
                "yoy_change": None, "ma_short": None, "ma_long": None,
                "direction": "stable", "signal": "stable", "trend_strength": 0}

    latest = float(v.iloc[-1]) if pd.notna(v.iloc[-1]) else None
    prev = float(v.iloc[-2]) if len(v) >= 2 and pd.notna(v.iloc[-2]) else None
    mom = latest - prev if latest is not None and prev is not None else None

    yoy = None
    if len(v) >= 13:
        yv = v.iloc[-13]
        if latest is not None and pd.notna(yv):
            yoy = latest - float(yv)

    ms, ml = min(ma_short, len(v)), min(ma_long, len(v))
    ma_s = float(v.rolling(ms, min_periods=1).mean().iloc[-1])
    ma_l = float(v.rolling(ml, min_periods=1).mean().iloc[-1]) if ml >= 1 else ma_s

    direction = "stable"
    if ma_s is not None and ma_l is not None and ma_l != 0:
        ratio = ma_s / ma_l
        if ratio > 1.005:
            direction = "up"
        elif ratio < 0.995:
            direction = "down"

    strength = 0.0
    if ma_l is not None and ma_l != 0 and ma_s is not None:
        strength = (ma_s - ma_l) / abs(ma_l) * 5
        strength = max(-1.0, min(1.0, strength))

    smap = {"up": "improving", "down": "deteriorating", "stable": "stable"}
    return {
        "latest":      round(latest, 4)     if latest is not None else None,
        "prev":        round(prev, 4)       if prev is not None   else None,
        "mom_change":  round(mom, 4)        if mom is not None    else None,
        "yoy_change":  round(yoy, 4)        if yoy is not None    else None,
        "ma_short":    round(ma_s, 4)       if ma_s is not None and pd.notna(ma_s) else None,
        "ma_long":     round(ma_l, 4)       if ma_l is not None and pd.notna(ma_l) else None,
        "direction":   direction,
        "signal":      smap[direction],
        "trend_strength": round(float(strength), 4),
    }


# ---------------------------------------------------------------------------
# Momentum (multi-period rate of change)
# ---------------------------------------------------------------------------
def compute_momentum(values, periods=(1, 3, 6, 12)):
    v = values.dropna().reset_index(drop=True)
    result = {}
    for p in periods:
        key = f"{p}m"
        if len(v) > p:
            pv, cv = v.iloc[-(p + 1)], v.iloc[-1]
            if pv and cv and pv != 0:
                result[key] = round(float((cv - pv) / abs(pv) * 100), 4)
            else:
                result[key] = None
        else:
            result[key] = None
    return result


# ---------------------------------------------------------------------------
# Rolling volatility (annualized)
# ---------------------------------------------------------------------------
def compute_volatility(values, window=12):
    v = values.dropna()
    if len(v) < window + 1:
        return None
    pct = v.pct_change().dropna()
    if len(pct) < window:
        window = max(len(pct), 2)
    if window < 2:
        return None
    latest = pct.rolling(window, min_periods=2).std().iloc[-1]
    return round(float(latest), 6) if pd.notna(latest) else None


# ---------------------------------------------------------------------------
# Z-score vs history
# ---------------------------------------------------------------------------
def compute_zscore(values, window=24):
    v = values.dropna()
    if len(v) < max(window, 4):
        window = max(len(v) // 2, 2)
    if len(v) < 2:
        return None
    rm = v.rolling(window, min_periods=2).mean().iloc[-1]
    rs = v.rolling(window, min_periods=2).std().iloc[-1]
    if rs == 0:
        return 0.0
    z = (v.iloc[-1] - rm) / rs
    return round(float(z), 4) if pd.notna(z) else None


# ---------------------------------------------------------------------------
# Time-series decomposition (MA-based)
# ---------------------------------------------------------------------------
def compute_decomposition(values, dates=None, freq="monthly"):
    v = values.dropna().reset_index(drop=True)
    period = 12 if freq == "monthly" else 4 if freq == "quarterly" else None
    if period is None or len(v) < period * 2:
        return None

    s = pd.Series(v.values)

    trend = s.rolling(period, center=True, min_periods=period).mean()
    trend = trend.bfill().ffill()

    detrended = s - trend

    si_arr = np.zeros(period)
    cnt = np.zeros(period)
    for i in range(len(detrended)):
        idx = i % period
        if pd.notna(detrended.iloc[i]):
            si_arr[idx] += detrended.iloc[i]
            cnt[idx] += 1
    for j in range(period):
        if cnt[j] > 0:
            si_arr[j] /= cnt[j]

    seasonal = pd.Series([si_arr[i % period] for i in range(len(s))], index=s.index)
    residual = s - trend - seasonal

    date_strs = None
    if dates is not None and len(dates) == len(s):
        date_strs = [d.strftime("%Y-%m-%d") if hasattr(d, "strftime") else str(d)
                     for d in dates]

    def _ts(arr):
        if date_strs:
            return [{"date": date_strs[i], "value": round(float(arr.iloc[i]), 4)}
                    for i in range(len(arr))]
        return [round(float(arr.iloc[i]), 4) for i in range(len(arr))]

    return {"trend": _ts(trend), "seasonal": _ts(seasonal), "residual": _ts(residual)}


# ---------------------------------------------------------------------------
# Correlation matrix (pairwise Pearson)
# ---------------------------------------------------------------------------
def compute_correlation_matrix(ind_values, ind_dates, window_months=120):
    """先把每个序列重采样到月末，再两两求相关。
    日频/月频/季频直接按日期取交集几乎取不上，会造成大量空单元。"""
    series = {}
    for ind_id, vals in ind_values.items():
        dates = ind_dates.get(ind_id)
        if dates is None or len(vals) == 0:
            continue
        s = pd.Series(pd.to_numeric(vals, errors="coerce").values,
                      index=pd.to_datetime(pd.Series(dates).values))
        s = s.dropna()
        if s.empty:
            continue
        monthly = s.resample("ME").last().dropna()
        if len(monthly) >= 12:
            series[ind_id] = monthly

    ids = list(series.keys())
    if len(ids) < 2:
        return {"indicators": ids, "matrix": [], "method": "month-end resample",
                "window_months": window_months}

    df = pd.DataFrame(series).sort_index()
    if window_months and len(df) > window_months:
        df = df.tail(window_months)

    corr = df.corr(min_periods=12)
    matrix = []
    for i, row_id in enumerate(corr.index):
        row = []
        for j, col_id in enumerate(corr.columns):
            v = corr.iloc[i, j]
            row.append(None if pd.isna(v) else round(float(v), 4))
        matrix.append(row)

    return {"indicators": list(corr.index), "matrix": matrix,
            "method": "month-end resample", "window_months": window_months,
            "observations": int(df.shape[0])}


# ---------------------------------------------------------------------------
# Composite indices (z-score weighted average)
# ---------------------------------------------------------------------------
def compute_composite_index(ind_entries):
    if not ind_entries:
        return []
    all_dates = set()
    ind_series = {}
    for entry in ind_entries:
        ts = entry.get("ts_data", [])
        if not ts:
            continue
        vals = [pt["value"] for pt in ts if pt["value"] is not None]
        if len(vals) < 4:
            continue
        dates = [pt["date"] for pt in ts if pt["value"] is not None]
        mean, std = np.mean(vals), np.std(vals)
        if std == 0:
            std = 1.0
        z_vals = [(v - mean) / std for v in vals]
        for d, zv in zip(dates, z_vals):
            all_dates.add(d)
            ind_series.setdefault(d, []).append(zv)
    if not all_dates:
        return []
    return [{"date": d, "value": round(float(np.mean(ind_series[d])), 4)}
            for d in sorted(all_dates) if d in ind_series]


# ---------------------------------------------------------------------------
# Merrill Lynch Clock
# ---------------------------------------------------------------------------
def compute_merrill_lynch(growth_ts_list, infl_ts_list):
    """
    Merrill Lynch Investment Clock — absolute-threshold scoring.

    Instead of Z-score (which can flag "overheat" when CPI ticks from
    0 % to 1 % – still very low in absolute terms), each indicator is
    scored against fixed economic thresholds:

    Growth (X-axis):
      PMI:         50 = 0,  above/below scaled linearly (52 → +1, 48 → -1)
      IP (yoy %):  6 % = 0,  above/below scaled linearly (8 → +1, 4 → -1)
      GDP (yoy %): 5.5 % = 0,   8 → +1,  3 → -1

    Inflation (Y-axis):
      CPI (yoy %):  2 % = 0,  3 → +1,  0 → -1
      PPI (yoy %):  0 % = 0,  4 → +1, -4 → -1

    An indicator that falls between thresholds is linearly interpolated.
    The final X / Y are the simple average of each group, clamped to [-2, 2].
    """
    THRESH = {
        "pmi_manufacturing":      (50.0, 2.0),   # neutral 50, ±1 per 2 pts
        "industrial_production":  (6.0,  2.0),   # neutral  6 %, ±1 per 2 %
        "gdp_growth":             (5.5,  2.5),   # neutral 5.5 %, ±1 per 2.5 %
        "cpi":                    (2.0,  1.0),   # neutral  2 %, ±1 per 1 %
        "ppi":                    (0.0,  4.0),   # neutral  0 %, ±1 per 4 %
    }

    def _score(val, neutral, width):
        return max(-2.0, min(2.0, (val - neutral) / width))

    # ------------------------------------------------------------------
    # Per-indicator monthly series – each ts_list element is
    # [{date: "YYYY-MM-DD", value: ...}, ...] for one indicator.
    # They may have different date ranges; build {date: value} lookups.
    # ------------------------------------------------------------------
    G_IDS = ["pmi_manufacturing", "industrial_production", "gdp_growth"]
    I_IDS = ["cpi", "ppi"]
    # CPI is the core consumer inflation gauge; PPI is upstream and
    # often diverges (e.g. PPI +4 % while CPI +1 %).  Weighted 70/30
    # so that CPI dominates the Y-axis signal.
    G_WEIGHTS = {"pmi_manufacturing": 0.3, "industrial_production": 0.4, "gdp_growth": 0.3}
    I_WEIGHTS = {"cpi": 0.7, "ppi": 0.3}

    # Build monthly lookups: indicator_id → {YYYY-MM: value}
    def _monthly_lookup(ts):
        """ts is a list of {date, value} dicts."""
        out = {}
        for pt in ts:
            v = pt["value"]
            if v is not None:
                out.setdefault(pt["date"][:7], []).append(v)
        return {k: float(np.mean(vals)) for k, vals in out.items()}

    g_lookups = {}
    for idx, gid in enumerate(G_IDS):
        if idx < len(growth_ts_list):
            g_lookups[gid] = _monthly_lookup(growth_ts_list[idx])

    i_lookups = {}
    for idx, iid in enumerate(I_IDS):
        if idx < len(infl_ts_list):
            i_lookups[iid] = _monthly_lookup(infl_ts_list[idx])

    # Collect all months to build a common time axis
    all_months = set()
    for lu in list(g_lookups.values()) + list(i_lookups.values()):
        all_months |= set(lu.keys())
    months = sorted(all_months)

    if len(months) < 24:
        return {"x": 0, "y": 0, "quadrant": "数据不足",
                "asset_allocation": "-", "advice": "历史数据不足（需≥24个月），无法计算美林时钟。",
                "trajectory": []}

    # --- Current position ---
    def _latest_score(ind_id, lookups):
        if ind_id not in lookups or ind_id not in THRESH:
            return None
        lu = lookups[ind_id]
        if not lu:
            return None
        latest_m = max(lu.keys())
        neutral, width = THRESH[ind_id]
        return _score(lu[latest_m], neutral, width)

    g_parts = {}
    for gid in G_IDS:
        s = _latest_score(gid, g_lookups)
        if s is not None:
            g_parts[gid] = s
    i_parts = {}
    for iid in I_IDS:
        s = _latest_score(iid, i_lookups)
        if s is not None:
            i_parts[iid] = s

    if not g_parts or not i_parts:
        return {"x": 0, "y": 0, "quadrant": "数据不足",
                "asset_allocation": "-", "advice": "增长或通胀指标数据不足。",
                "trajectory": []}

    # Weighted: IP → 0.4, PMI → 0.3, GDP → 0.3  |  CPI → 0.7, PPI → 0.3
    x = max(-2.0, min(2.0, sum(G_WEIGHTS[k] * v for k, v in g_parts.items())))
    y = max(-2.0, min(2.0, sum(I_WEIGHTS[k] * v for k, v in i_parts.items())))

    if x >= 0 and y >= 0:
        quad, alloc, adv = ("过热期", "商品 > 股票 > 现金 > 债券",
                            "通胀上行+增长强劲，大宗商品表现最佳，央行可能收紧货币政策")
    elif x >= 0 and y < 0:
        quad, alloc, adv = ("复苏期", "股票 > 债券 > 现金 > 商品",
                            "增长回暖+通胀温和，股票最优配置窗口，周期性行业领先")
    elif x < 0 and y >= 0:
        quad, alloc, adv = ("滞胀期", "现金 > 商品 > 债券 > 股票",
                            "增长放缓+通胀高企，现金为王，防御性资产优先")
    else:
        quad, alloc, adv = ("衰退期", "债券 > 现金 > 股票 > 商品",
                            "增长疲弱+通缩压力，债券表现最佳，央行可能降息刺激经济")

    # --- Trajectory ---
    trajectory = []
    for off in range(24, len(months)):
        m_slice = months[:off + 1]
        tg = {}
        for gid in G_IDS:
            if gid in g_lookups and gid in THRESH:
                lu = g_lookups[gid]
                avail = {m: lu[m] for m in m_slice if m in lu}
                if avail:
                    latest_m = max(avail.keys())
                    n, w = THRESH[gid]
                    tg[gid] = _score(avail[latest_m], n, w)
        ti = {}
        for iid in I_IDS:
            if iid in i_lookups and iid in THRESH:
                lu = i_lookups[iid]
                avail = {m: lu[m] for m in m_slice if m in lu}
                if avail:
                    latest_m = max(avail.keys())
                    n, w = THRESH[iid]
                    ti[iid] = _score(avail[latest_m], n, w)

        tx = sum(G_WEIGHTS[k] * v for k, v in tg.items()) if tg else 0.0
        ty = sum(I_WEIGHTS[k] * v for k, v in ti.items()) if ti else 0.0
        trajectory.append({"date": months[off],
                           "x": round(max(-2.0, min(2.0, tx)), 4),
                           "y": round(max(-2.0, min(2.0, ty)), 4)})

    return {"x": round(x, 4), "y": round(y, 4), "quadrant": quad,
            "asset_allocation": alloc, "advice": adv, "trajectory": trajectory}


# ---------------------------------------------------------------------------
# Pring Six-Stage
# ---------------------------------------------------------------------------
def compute_pring_stage(bond_dir, stock_dir, commodity_dir):
    mapping = {
        ("up",  "down", "down"): ("阶段1", "衰退初期 - 仅债券牛市，央行开始降息"),
        ("up",  "up",   "down"): ("阶段2", "复苏初期 - 债券+股票走强，经济见底回升"),
        ("up",  "up",   "up"):   ("阶段3", "全面牛市 - 三类资产齐涨，经济扩张"),
        ("down","up",   "up"):   ("阶段4", "过热初期 - 股票+商品走强，通胀压力上升"),
        ("down","down", "up"):   ("阶段5", "滞胀 - 仅商品走强，经济放缓+通胀高企"),
        ("down","down", "down"): ("阶段6", "全面衰退 - 三市场齐跌，避险模式"),
    }
    key = (bond_dir, stock_dir, commodity_dir)
    stage, desc = mapping.get(key, ("过渡期",
                                    f"三市场信号混合: 债{bond_dir}/股{stock_dir}/商{commodity_dir}"))
    weights = {
        "阶段1": {"债券": "50%", "股票": "15%", "商品": "5%",  "现金": "30%"},
        "阶段2": {"债券": "30%", "股票": "40%", "商品": "10%", "现金": "20%"},
        "阶段3": {"债券": "20%", "股票": "35%", "商品": "25%", "现金": "20%"},
        "阶段4": {"债券": "10%", "股票": "35%", "商品": "30%", "现金": "25%"},
        "阶段5": {"债券": "10%", "股票": "15%", "商品": "35%", "现金": "40%"},
        "阶段6": {"债券": "40%", "股票": "10%", "商品": "5%",  "现金": "45%"},
    }
    return {"stage": stage, "description": desc,
            "bond_signal": bond_dir, "stock_signal": stock_dir,
            "commodity_signal": commodity_dir,
            "asset_weights": weights.get(stage, {})}


# ---------------------------------------------------------------------------
# Cycle phase detection (6-phase framework)
# ---------------------------------------------------------------------------
def detect_cycle_phase(leading_dirs, coincident_dirs, lagging_dirs):
    def majority(seq):
        if not seq:
            return "stable"
        up = sum(1 for x in seq if x == "up")
        down = sum(1 for x in seq if x == "down")
        if up > down and up > len(seq) / 3:
            return "up"
        if down > up and down > len(seq) / 3:
            return "down"
        return "stable"

    l, c, lg = majority(leading_dirs), majority(coincident_dirs), majority(lagging_dirs)

    if l == "up" and c in ("stable", "down") and lg == "down":
        phase, desc = ("阶段1 — 复苏初期",
                       "先行指标回升，同步指标尚未跟进，滞后指标仍在下降。经济触底。")
    elif l == "up" and c == "up" and lg in ("stable", "down"):
        phase, desc = ("阶段2 — 扩张中期",
                       "先行和同步指标均上行，经济进入扩张中期。")
    elif l in ("stable", "down") and c == "up" and lg == "up":
        phase, desc = ("阶段3 — 扩张后期",
                       "同步和滞后指标上行，先行指标走平或回落。接近周期顶部。")
    elif l == "down" and c in ("stable", "up") and lg == "up":
        phase, desc = ("阶段4 — 放缓期",
                       "先行指标下行，同步指标走平，滞后指标仍在上升。减速信号。")
    elif l == "down" and c == "down" and lg in ("stable", "down"):
        phase, desc = ("阶段5 — 衰退期",
                       "三类指标同步下行，经济陷入衰退。政策宽松预期强烈。")
    elif l in ("stable", "up") and c == "down" and lg == "down":
        phase, desc = ("阶段6 — 谷底",
                       "先行指标企稳，同步和滞后指标仍在下降。经济处于谷底。")
    else:
        phase, desc = ("过渡期",
                       f"信号混合: 领先{l}/同步{c}/滞后{lg}，经济方向不明确。")

    return {"phase": phase, "description": desc,
            "leading_majority": l, "coincident_majority": c, "lagging_majority": lg}


# ---------------------------------------------------------------------------
# Main orchestration
# ---------------------------------------------------------------------------
def load_config():
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def run_analysis():
    config = load_config()
    chart_cfg = config.get("chart", {})

    results = {
        "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "indicators":        {"leading": [], "coincident": [], "lagging": []},
        "merrill_lynch":     {},
        "pring":             {},
        "summary":           {},
        "correlation_matrix": {},
        "composite_indices":  {},
        "momentum":           {},
        "decomposition":      {},
        "cycle_phase":        {},
    }

    ind_data = {}
    ind_values = {}
    ind_dates = {}

    for category in ["leading", "coincident", "lagging"]:
        for ind_cfg in config["indicators"][category]:
            ind_id = ind_cfg["id"]
            name = ind_cfg["name"]
            freq = ind_cfg.get("frequency", "")
            print(f"  分析: {name} ({ind_id}) [{category}]")

            loaded = load_indicator_data(ind_id)
            if loaded is None:
                print(f"    [WARN] 跳过 {ind_id}")
                continue

            df, date_col, val_col = loaded
            values = df["_val"]
            dates = df["_date"]

            # --- Trend（均线窗口按频率适配：日频看 20/60 根，避免 3/6 天的噪声）---
            ma_windows = chart_cfg.get("ma_windows", {})
            if "每日" in freq:
                ma_s, ma_l = ma_windows.get("daily", [20, 60])
                stale_limit = 10
            elif "季度" in freq:
                ma_s, ma_l = ma_windows.get("quarterly", [2, 4])
                stale_limit = 150
            else:
                ma_s, ma_l = ma_windows.get("monthly", [chart_cfg.get("ma_short", 3),
                                                        chart_cfg.get("ma_long", 6)])
                stale_limit = 75
            trend = compute_trend(values, ma_s, ma_l)

            # --- 数据时效 ---
            last_date = dates.max()
            data_age_days = int((datetime.now() - last_date.to_pydatetime()).days) \
                if pd.notna(last_date) else None
            is_stale = data_age_days is not None and data_age_days > stale_limit

            # --- Time series ---
            if "每日" in freq:
                n_disp = chart_cfg.get("daily_display_points", 120)
            elif "季度" in freq:
                n_disp = chart_cfg.get("quarterly_display_points", 40)
            else:
                n_disp = chart_cfg.get("monthly_display_points", 60)

            df_tail = df.tail(n_disp)
            ts_data = []
            for _, row in df_tail.iterrows():
                d, v = row["_date"], row["_val"]
                if pd.notna(d) and pd.notna(v):
                    ts_data.append({"date": d.strftime("%Y-%m-%d"),
                                    "value": round(float(v), 4)})

            # --- Momentum, Volatility, Z-score ---
            momentum = compute_momentum(values, periods=[1, 3, 6, 12])
            vol = compute_volatility(values, window=12)
            zs = compute_zscore(values, window=24)

            # --- Decomposition ---
            decomp = None
            if "月度" in freq and len(values) >= 24:
                decomp = compute_decomposition(values, dates, freq="monthly")
            elif "季度" in freq and len(values) >= 8:
                decomp = compute_decomposition(values, dates, freq="quarterly")

            # --- Signal ---
            raw_signal = trend["signal"]
            raw_direction = trend["direction"]
            if ind_id in NEGATIVE_INDICATORS:
                flip = {"improving": "deteriorating", "deteriorating": "improving",
                        "stable": "stable"}
                signal = flip.get(raw_signal, raw_signal)
            else:
                signal = raw_signal

            entry = {
                "id": ind_id, "name": name,
                "unit": ind_cfg.get("unit", ""),
                "source": ind_cfg.get("source", ""),
                "frequency": freq,
                "description": ind_cfg.get("description", ""),
                "category": category,
                "latest_value": trend["latest"],
                "latest_date": ts_data[-1]["date"] if ts_data else None,
                "data_age_days": data_age_days,
                "stale": is_stale,
                "mom_change": trend["mom_change"],
                "yoy_change": trend["yoy_change"],
                "direction": trend["direction"],
                "raw_direction": raw_direction,
                "signal": signal,
                "trend_strength": trend["trend_strength"],
                "ma_short": trend["ma_short"],
                "ma_long": trend["ma_long"],
                "volatility": vol,
                "zscore": zs,
                "momentum": momentum,
                "ts_data": ts_data,
            }
            results["indicators"][category].append(entry)
            ind_data[ind_id] = entry
            ind_values[ind_id] = values.reset_index(drop=True)
            ind_dates[ind_id] = dates.reset_index(drop=True)
            results["momentum"][ind_id] = momentum
            if decomp:
                results["decomposition"][ind_id] = decomp

    # === Correlation Matrix ===
    print("\n  计算相关系数矩阵...")
    results["correlation_matrix"] = compute_correlation_matrix(ind_values, ind_dates)

    # === Composite Indices（陈旧指标不参与，避免旧数据扭曲合成指数）===
    print("  计算合成指数...")
    for cat in ["leading", "coincident", "lagging"]:
        fresh = [e for e in results["indicators"].get(cat, []) if not e.get("stale")]
        results["composite_indices"][cat] = compute_composite_index(fresh)

    # === Merrill Lynch Clock ===
    ml_cfg = config.get("merrill_lynch", {})
    growth_ids = ml_cfg.get("growth_indicators", [])
    inflation_ids = ml_cfg.get("inflation_indicators", [])

    g_ts = [ind_data.get(gid, {}).get("ts_data", []) for gid in growth_ids]
    i_ts = [ind_data.get(iid, {}).get("ts_data", []) for iid in inflation_ids]

    ml = compute_merrill_lynch(g_ts, i_ts)
    results["merrill_lynch"] = {
        **ml,
        "growth_indicators": growth_ids,
        "inflation_indicators": inflation_ids,
        "growth_latest": [ind_data.get(gid, {}).get("latest_value") for gid in growth_ids],
        "inflation_latest": [ind_data.get(iid, {}).get("latest_value") for iid in inflation_ids],
    }

    # === Pring Six-Stage ===
    pring_cfg = config.get("pring", {})
    bond_id = pring_cfg.get("bond_proxy", "lpr")
    stock_id = pring_cfg.get("stock_proxy", "sh_index")
    com_id = pring_cfg.get("commodity_proxy", "ppi")

    br = ind_data.get(bond_id, {})
    sr = ind_data.get(stock_id, {})
    cr = ind_data.get(com_id, {})

    if br and sr and cr:
        bond_raw = br.get("direction", "stable")
        # 收益率上行 = 债券走弱，收益率类代理需要反向
        bond_sig = {"up": "down", "down": "up", "stable": "stable"}.get(bond_raw, "stable") \
            if bond_id in NEGATIVE_INDICATORS else bond_raw

        pring = compute_pring_stage(bond_sig, sr.get("direction", "stable"),
                                    cr.get("direction", "stable"))
        results["pring"] = {
            **pring,
            "bond_indicator": br.get("name", bond_id),
            "stock_indicator": sr.get("name", stock_id),
            "commodity_indicator": cr.get("name", com_id),
            "bond_proxy_id": bond_id,
            "stock_proxy_id": stock_id,
            "commodity_proxy_id": com_id,
            "bond_proxy_value": br.get("latest_value"),
            "stock_proxy_value": sr.get("latest_value"),
            "commodity_proxy_value": cr.get("latest_value"),
        }

    # === Cycle Phase Detection（仅用新鲜数据）===
    results["cycle_phase"] = detect_cycle_phase(
        [r["raw_direction"] for r in results["indicators"].get("leading", []) if not r.get("stale")],
        [r["raw_direction"] for r in results["indicators"].get("coincident", []) if not r.get("stale")],
        [r["raw_direction"] for r in results["indicators"].get("lagging", []) if not r.get("stale")],
    )

    # === Summary（陈旧指标不计数）===
    for cat in ["leading", "coincident", "lagging"]:
        sigs = [r["signal"] for r in results["indicators"].get(cat, []) if not r.get("stale")]
        imp = sum(1 for s in sigs if s == "improving")
        det = sum(1 for s in sigs if s == "deteriorating")
        results["summary"][f"{cat}_score"] = imp - det
        results["summary"][f"{cat}_count"] = len(sigs)
        results["summary"][f"{cat}_improving"] = imp
        results["summary"][f"{cat}_deteriorating"] = det

    ls = results["summary"].get("leading_score", 0)
    cs = results["summary"].get("coincident_score", 0)
    lgs = results["summary"].get("lagging_score", 0)

    if ls > 0 and cs >= 0:
        cycle, outlook = ("扩张期",
                          "提前和同步指标均向好，经济处于扩张阶段。关注通胀压力是否上升。")
    elif ls > 0 and cs < 0:
        cycle, outlook = ("复苏初期",
                          "提前指标转好但同步指标尚未跟进，经济可能正在筑底。")
    elif ls < 0 and cs >= 0:
        cycle, outlook = ("放缓期",
                          "同步指标仍好但提前指标走弱，经济可能接近拐点。警惕下行风险。")
    elif ls < 0 and cs < 0 and lgs < 0:
        cycle, outlook = ("衰退期",
                          "三类指标全面走弱，经济面临较大下行压力。政策宽松预期增强。")
    else:
        cycle, outlook = ("震荡期",
                          "各指标信号不一，经济方向不明朗。建议关注后续数据确认。")

    results["summary"]["cycle_phase"] = cycle
    results["summary"]["outlook"] = outlook
    results["summary"]["cycle_phase_detail"] = results["cycle_phase"]

    # === Data Health（陈旧与采集失败）===
    stale_items = []
    for cat in ["leading", "coincident", "lagging"]:
        for e in results["indicators"].get(cat, []):
            if e.get("stale"):
                stale_items.append({"id": e["id"], "name": e["name"], "category": cat,
                                    "latest_date": e["latest_date"],
                                    "age_days": e["data_age_days"]})
    failed_items = []
    meta_path = os.path.join(DATA_DIR, "meta.yaml")
    if os.path.exists(meta_path):
        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                failed_items = (yaml.safe_load(f) or {}).get("failed_items", []) or []
        except Exception:
            pass
    total_ind = sum(len(results["indicators"].get(c, []))
                    for c in ["leading", "coincident", "lagging"])
    results["data_health"] = {
        "total": total_ind,
        "stale_count": len(stale_items),
        "stale": stale_items,
        "failed_items": failed_items,
    }

    # === Save ===
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(ANALYSIS_OUTPUT, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    # Also generate trimmed JSON (dashboard uses fetch) and JS file (cycle report uses <script src>)
    trimmed = json.loads(json.dumps(results, ensure_ascii=False))
    for cat in ["leading", "coincident", "lagging"]:
        for ind in trimmed["indicators"][cat]:
            ts = ind.get("ts_data", [])
            freq = ind.get("frequency", "")
            limit = 240 if "每日" in freq else (48 if "季度" in freq else 120)
            if len(ts) > limit:
                ind["ts_data"] = ts[-limit:]
    for k in trimmed.get("composite_indices", {}):
        pts = trimmed["composite_indices"][k]
        if isinstance(pts, list) and len(pts) > 120:
            trimmed["composite_indices"][k] = pts[-120:]
    for ind_id in trimmed.get("decomposition", {}):
        for comp in trimmed["decomposition"][ind_id]:
            pts = trimmed["decomposition"][ind_id][comp]
            if isinstance(pts, list) and len(pts) > 60:
                trimmed["decomposition"][ind_id][comp] = pts[-60:]

    trimmed_path = os.path.join(DATA_DIR, "analysis_trimmed.json")
    with open(trimmed_path, "w", encoding="utf-8") as f:
        json.dump(trimmed, f, ensure_ascii=False)
    print(f"  精简版已保存至: {trimmed_path}")

    js_path = os.path.join(DATA_DIR, "analysis_data.js")
    js_str = json.dumps(trimmed, ensure_ascii=False)
    with open(js_path, "w", encoding="utf-8") as f:
        f.write("window.__ANALYSIS_DATA__ = ")
        f.write(js_str)
        f.write(";\n")
    print(f"  JS数据已保存至: {js_path}")

    print(f"\n  分析结果已保存至: {ANALYSIS_OUTPUT}")
    print(f"  加载指标: 领先{results['summary'].get('leading_count',0)} "
          f"同步{results['summary'].get('coincident_count',0)} "
          f"滞后{results['summary'].get('lagging_count',0)}")
    print(f"  美林时钟: {ml.get('quadrant', 'N/A')}")
    print(f"  普林格阶段: {results.get('pring', {}).get('stage', 'N/A')}")
    print(f"  经济周期: {cycle}")
    cphase = results.get("cycle_phase", {}).get("phase", "")
    if cphase:
        print(f"  周期阶段: {cphase}")

    return results


if __name__ == "__main__":
    run_analysis()
