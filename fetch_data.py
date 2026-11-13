"""
宏观数据跟踪 — 数据采集脚本
从 AKShare 拉取各宏观指标数据，存储为 CSV 文件
动态读取 config.yaml 构建指标体系，不硬编码指标列表
"""
import os
import sys
import traceback
import yaml
import numpy as np
import pandas as pd
import akshare as ak
from datetime import datetime, timedelta

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
CONFIG_FILE = os.path.join(BASE_DIR, "config.yaml")

# ──────────────────────────────────────────────────────────────────
#  各 AKShare 函数的精确列名映射
#  键为 akshare_func 名称，值为 {'date_col': ..., 'val_col': ...}
#  部分函数（如 non_man_pmi / fx_reserves_yearly）返回
#  "商品/日期/今值/预测值/前值" 格式的多列数据，需要精确提取。
#  对于 stock_zh_index_daily / shibor / freight_index / rmb，
#  在 create_fetch_function() 中有专门的处理逻辑，不依赖此映射。
# ──────────────────────────────────────────────────────────────────
FUNC_COLUMN_SPEC = {
    "macro_china_non_man_pmi": {
        "date_col": "商品",        # 该函数日期列名为"商品"，需在提取后重命名为"日期"
        "val_col": "今值",
    },
    "macro_china_new_financial_credit": {
        # 返回多列，保留全部
    },
    "macro_china_money_supply_em": {
        # 返回多列（M0/M1/M2），保留全部
    },
    "macro_china_consumer_confidence": {
        # 返回多列，保留全部
    },
    "macro_china_enterprise_boom_index": {
        "date_col": "季度",
        "val_col": "企业景气指数-指数",
    },
    "macro_china_fixed_asset_investment": {
        "date_col": "月份",
        "val_col": "同比增长",
    },
    "macro_china_industrial_value_added": {
        "date_col": "月份",
        "val_col": "同比增长",
    },
    "macro_china_imports_yoy": {
        "date_col": "日期",
        "val_col": "今值",
    },
    "macro_china_new_house_price": {
        "date_col": "月份",
        "val_col": "新建商品住宅价格指数-同比",
    },
    "macro_china_reserve_requirement_ratio": {
        "date_col": "公布时间",
        "val_col": "大型金融机构-调整前",
    },
    "macro_china_real_estate": {
        "date_col": "日期",
        "val_col": "最新值",
    },
    "macro_china_fx_gold_em": {
        "date_col": "月份",
        "val_col": "国家外汇储备-数值",
    },
    "index_pmi_ser_cx": {
        "date_col": "日期",
        "val_col": "服务业PMI",
    },
    "macro_china_fiscal_revenue": {
        "date_col": "月份",
        "val_col": "当月-同比增长",
    },
    "macro_china_commodity_price_index": {
        "date_col": "日期",
        "val_col": "最新值",
    },
    # 以下函数无特殊列映射，直接保留原始返回的全部列：
    #   macro_china_pmi, macro_china_gdp,
    #   macro_china_consumer_goods_retail, macro_china_society_electricity,
    #   macro_china_cpi, macro_china_ppi,
    #   macro_china_urban_unemployment, macro_china_lpr
}


def ensure_data_dir():
    """确保 data 目录存在"""
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)


def load_config():
    """加载配置文件"""
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def save_csv(df, indicator_id, date_col=None):
    """保存 DataFrame 为 CSV（data/{indicator_id}.csv），按日期排序去重"""
    if df is None or df.empty:
        print(f"  [WARN] 数据为空，跳过保存 {indicator_id}")
        return False

    # 尝试自动识别日期列
    if date_col is None:
        for col in df.columns:
            col_str = str(col)
            if any(kw in col_str for kw in [
                "日期", "时间", "date", "Date",
                "月份", "季度", "公布时间", "截止日期",
            ]):
                date_col = col
                break

    # 去重并按日期排序（保护混合类型列）
    if date_col and date_col in df.columns:
        try:
            df_before = len(df)
            df = df.drop_duplicates(subset=[date_col], keep="last")
            df = df.sort_values(date_col)
        except Exception:
            # 如果日期列类型不统一导致排序失败，至少去重
            df = df.drop_duplicates(subset=[date_col], keep="last")

    filename = f"{indicator_id}.csv"
    filepath = os.path.join(DATA_DIR, filename)
    df.to_csv(filepath, index=False, encoding="utf-8-sig")
    print(f"  [OK] 保存 {filename} ({len(df)} 条记录)")
    return True


def _extract_date_val(df, date_col_name, val_col_name, fallback_date="日期", fallback_val=None):
    """
    从 DataFrame 中提取日期列和值列。
    优先使用指定的列名；若不存在则尝试 fallback。
    返回 (result_df, used_date_col) 或 (原始df, None) 表示提取失败。
    """
    actual_date = None
    actual_val = None

    # 定位日期列
    for candidate in [date_col_name, fallback_date]:
        if candidate and candidate in df.columns:
            actual_date = candidate
            break
    if actual_date is None:
        return df, None  # 找不到日期列，返回原始数据

    # 定位值列
    for candidate in [val_col_name, fallback_val] if fallback_val else [val_col_name]:
        if candidate and candidate in df.columns:
            actual_val = candidate
            break
    if actual_val is None:
        return df, actual_date  # 有日期但找不到值列，返回原始数据

    result = df[[actual_date, actual_val]].copy()
    result.columns = ["日期", actual_val]
    return result, "日期"


def create_fetch_function(indicator):
    """
    根据单个指标的配置动态创建采集函数。

    处理模式：
    1. stock_zh_index_daily → 股票指数日线（提取 date + close）
    2. macro_china_shibor_all → Shibor 隔夜利率（提取日期 + O/N-定盘利率）
    3. macro_china_rmb → 人民币中间价（含 fx_gold 回退）
    4. macro_china_freight_index → 货运指数（提取最后一列数值列）
    5. margin_sh (macro_china_market_margin_sh) → 沪市融资余额（提取日期+融资余额）
    6. 有 FUNC_COLUMN_SPEC 的通用函数 → 按映射提取
    7. 无映射的通用函数 → 保留全部列
    """
    func_name = indicator["akshare_func"]
    params = indicator.get("akshare_params", {})
    ind_id = indicator["id"]
    ind_name = indicator["name"]
    spec = FUNC_COLUMN_SPEC.get(func_name, {})
    date_col_spec = spec.get("date_col")
    val_col_spec = spec.get("val_col")

    # ── 模式 1：股票指数 ──────────────────────────────────────
    if func_name == "stock_zh_index_daily":
        symbol = params.get("symbol", "")

        def _fetch():
            try:
                df = ak.stock_zh_index_daily(symbol=symbol)
                if df is None or df.empty:
                    print(f"  [WARN] {ind_name} 返回空数据")
                    return None
                # 查找 date 列
                date_col = "date" if "date" in df.columns else df.columns[0]
                if "close" not in df.columns:
                    print(f"  [WARN] 未找到 close 列，可用列: {list(df.columns)}")
                    return df
                result = df[[date_col, "close"]].copy()
                result.columns = ["日期", "收盘价"]
                print(f"  [INFO] 获取 {ind_name} 共 {len(result)} 条日线数据")
                return result
            except Exception as e:
                print(f"  [ERR] {ind_name} 获取失败: {e}")
                traceback.print_exc()
            return None
        return _fetch

    # ── 模式 2：Shibor ────────────────────────────────────────
    if func_name == "macro_china_shibor":

        def _fetch():
            try:
                df = ak.macro_china_shibor()
                if df is None or df.empty:
                    print(f"  [WARN] Shibor 返回空数据")
                    return None
                date_col_name = "日期"
                val_col_name = "O/N-定价"
                # 尝试精确匹配
                if date_col_name in df.columns and val_col_name in df.columns:
                    result = df[[date_col_name, val_col_name]].copy()
                    result.columns = ["日期", "隔夜Shibor"]
                    print(f"  [INFO] 获取 Shibor 共 {len(result)} 条数据")
                    return result
                # 模糊匹配 O/N 列
                on_col = None
                for col in df.columns:
                    col_s = str(col)
                    if "ON" in col_s.upper() or "O/N" in col_s or "隔夜" in col_s or "定价" in col_s:
                        on_col = col
                        break
                if on_col:
                    # 日期列可能是第一列或叫"日期"
                    d_col = "日期" if "日期" in df.columns else df.columns[0]
                    result = df[[d_col, on_col]].copy()
                    result.columns = ["日期", "隔夜Shibor"]
                    print(f"  [INFO] 获取 Shibor 共 {len(result)} 条数据（模糊匹配 ON 列）")
                    return result
                print(f"  [WARN] Shibor 未找到 ON 列，返回全部列: {list(df.columns)}")
                return df
            except Exception as e:
                print(f"  [ERR] Shibor 获取失败: {e}")
                traceback.print_exc()
            return None
        return _fetch

    # ── 模式 3：RMB 中间价（含 fx_gold 回退）─────────────────
    if func_name == "macro_china_rmb":

        def _fetch():
            try:
                df = ak.macro_china_rmb()
                if df is not None and not df.empty:
                    # 尝试提取 美元/人民币_中间价
                    date_col = "日期"
                    val_col = "美元/人民币_中间价"
                    if date_col in df.columns and val_col in df.columns:
                        result = df[[date_col, val_col]].copy()
                        result.columns = ["日期", "人民币中间价"]
                        print(f"  [INFO] 获取人民币中间价共 {len(result)} 条数据")
                        return result
                    # 模糊查找中间价列
                    for col in df.columns:
                        if "中间价" in str(col) or "人民币" in str(col):
                            d_c = "日期" if "日期" in df.columns else df.columns[0]
                            result = df[[d_c, col]].copy()
                            result.columns = ["日期", "人民币中间价"]
                            print(f"  [INFO] 获取人民币中间价共 {len(result)} 条数据")
                            return result
                    print(f"  [WARN] 未找到中间价列，返回全部列: {list(df.columns)}")
                    return df
            except Exception as e:
                print(f"  [WARN] macro_china_rmb 调用失败 ({e})")
                print(f"  [INFO] 尝试使用 macro_china_fx_gold 作为替代数据源")
            # 回退到 fx_gold
            try:
                df = ak.macro_china_fx_gold()
                if df is not None and not df.empty:
                    date_col = "日期"
                    val_col = "今值"
                    if date_col in df.columns and val_col in df.columns:
                        result = df[[date_col, val_col]].copy()
                        result.columns = ["日期", "人民币中间价"]
                        print(f"  [INFO] (fx_gold 回退) 共 {len(result)} 条数据")
                        return result
                    return df
            except Exception as e2:
                print(f"  [ERR] macro_china_fx_gold 也失败: {e2}")
                traceback.print_exc()
            return None
        return _fetch

    # ── 模式 4：货运指数 ──────────────────────────────────────
    if func_name == "macro_china_freight_index":

        def _fetch():
            try:
                df = ak.macro_china_freight_index()
                if df is None or df.empty:
                    print(f"  [WARN] 货运指数返回空数据")
                    return None
                # 第一列是日期（通常叫"截止日期"）
                date_col = df.columns[0]
                # 取最后一个数值列作为指数值
                numeric_cols = df.select_dtypes(include=["number"]).columns.tolist()
                if numeric_cols:
                    val_col = numeric_cols[-1]
                    result = df[[date_col, val_col]].copy()
                    result.columns = ["日期", "货运指数"]
                    print(f"  [INFO] 获取货运指数共 {len(result)} 条（列: {val_col}）")
                    return result
                print(f"  [WARN] 无数值列，返回全部列: {list(df.columns)}")
                return df
            except Exception as e:
                print(f"  [ERR] 货运指数获取失败: {e}")
                traceback.print_exc()
            return None
        return _fetch

    # ── 模式 5：沪市融资余额（全景数据）───────────────────────
    if func_name == "macro_china_market_margin_sh":

        def _fetch():
            try:
                df = ak.macro_china_market_margin_sh()
                if df is None or df.empty:
                    print(f"  [WARN] 沪市融资余额返回空数据")
                    return None
                date_col_name = spec.get("date_col", "日期") if spec else "日期"
                # 精确匹配AKShare返回的列名: '融资买入额'
                val_col_name = "融资买入额"
                if val_col_name not in df.columns:
                    # 回退：模糊匹配融资+余额
                    for c in df.columns:
                        if '融资' in c and ('余额' in c or '买入额' in c):
                            val_col_name = c
                            break
                if date_col_name in df.columns and val_col_name in df.columns:
                    result = df[[date_col_name, val_col_name]].copy()
                    # 原始数据单位是「元」，转为「亿元」并四舍五入
                    result[val_col_name] = (result[val_col_name] / 1e8).round(2)
                    result.columns = ["日期", "沪市融资余额"]
                    print(f"  [INFO] 获取沪市融资余额共 {len(result)} 条数据（已转换为亿元）")
                    return result
                print(f"  [WARN] 列名不匹配，可用列: {list(df.columns)}，返回全部列")
                return df
            except Exception as e:
                print(f"  [ERR] 沪市融资余额获取失败: {e}")
                traceback.print_exc()
            return None
        return _fetch

    # ── 模式 6：中证商品期货指数 ────────────────────────────
    if func_name == "futures_index_ccidx":

        def _fetch():
            try:
                df = ak.futures_index_ccidx()
                if df is None or df.empty:
                    print(f"  [WARN] 中证商品期货指数返回空数据")
                    return None
                # 列索引: [4]=日期, [14]=收盘点位
                date_col = "日期"
                close_col = "收盘点位"
                if date_col not in df.columns:
                    # fallback to index
                    date_col = df.columns[4]
                if close_col not in df.columns:
                    close_col = df.columns[14]
                result = df[[date_col, close_col]].copy()
                result.columns = ["日期", "中证商品期货指数"]
                print(f"  [INFO] 获取中证商品期货指数共 {len(result)} 条数据（日期范围: {result.iloc[0,0]} ~ {result.iloc[-1,0]}）")
                return result
            except Exception as e:
                print(f"  [ERR] 中证商品期货指数获取失败: {e}")
                traceback.print_exc()
            return None
        return _fetch

    # ── 模式 6.5：海关进出口（出口增速/贸易差额共用）──────────
    if func_name == "macro_china_customs_trade":

        def _fetch():
            try:
                df = ak.macro_china_customs_trade()
                if df is None or df.empty:
                    print(f"  [WARN] {ind_name} 返回空数据")
                    return None
                if ind_id == "exports_yoy":
                    # 出口增速：当月出口额-同比增长
                    result = _extract_date_val(df, "月份", "当月出口额-同比增长")
                    if result[1] is not None:
                        out = result[0].copy()
                        out.columns = ["日期", "出口增速"]
                        print(f"  [INFO] 获取出口增速共 {len(out)} 条数据")
                        return out
                elif ind_id == "trade_balance":
                    # 贸易差额 = 当月出口额 - 当月进口额（千美元→亿美元）
                    if "当月出口额-金额" in df.columns and "当月进口额-金额" in df.columns:
                        out = df[["月份", "当月出口额-金额", "当月进口额-金额"]].copy()
                        out["贸易差额"] = ((out["当月出口额-金额"] - out["当月进口额-金额"]) / 100000).round(2)
                        out = out[["月份", "贸易差额"]].copy()
                        out.columns = ["日期", "贸易差额"]
                        print(f"  [INFO] 获取贸易差额共 {len(out)} 条数据")
                        return out
                print(f"  [WARN] {ind_name} 未匹配处理逻辑，返回全部列: {list(df.columns)}")
                return df
            except Exception as e:
                print(f"  [ERR] {ind_name} 获取失败: {e}")
                traceback.print_exc()
            return None
        return _fetch

    # ── 模式 9：全社会用电量（累计值 → 当月同比）────────────
    if func_name == "macro_china_society_electricity":

        def _fetch():
            try:
                df = ak.macro_china_society_electricity()
                if df is None or df.empty:
                    print(f"  [WARN] 全社会用电量返回空数据")
                    return None
                parts = df["统计时间"].astype(str).str.split(".", expand=True)
                d = pd.DataFrame({
                    "year": pd.to_numeric(parts[0], errors="coerce"),
                    "month": pd.to_numeric(parts[1], errors="coerce"),
                    "cum": pd.to_numeric(df["全社会用电量"], errors="coerce"),
                }).dropna(subset=["year", "month", "cum"]).sort_values(["year", "month"])
                prev_cum = d["cum"].shift(1)
                same_year = d["year"] == d["year"].shift(1)
                # 当年首条记录本身即当期累计（1-2月合并发布）
                d["monthly"] = d["cum"] - np.where(same_year, prev_cum, 0.0)
                d["ym"] = d["year"].astype(int) * 100 + d["month"].astype(int)
                ly = d[["ym", "monthly"]].rename(columns={"monthly": "monthly_ly"}).copy()
                ly["ym"] = ly["ym"] + 100
                m = d.merge(ly, on="ym", how="left")
                m["yoy"] = (m["monthly"] / m["monthly_ly"] - 1) * 100
                m = m.dropna(subset=["yoy"]).reset_index(drop=True)
                out = pd.DataFrame({
                    "日期": m["year"].astype(int).astype(str) + "-"
                            + m["month"].astype(int).astype(str).str.zfill(2) + "-01",
                    "用电量当月同比": m["yoy"].round(2),
                })
                print(f"  [INFO] 用电量当月同比共 {len(out)} 条（{out.iloc[0,0]} ~ {out.iloc[-1,0]}）")
                return out
            except Exception as e:
                print(f"  [ERR] 用电量获取失败: {e}")
                traceback.print_exc()
            return None
        return _fetch

    # ── 模式 10：固定资产投资（当月值 → 当月同比）───────────
    if func_name == "macro_china_fixed_asset_investment":

        def _fetch():
            try:
                df = ak.macro_china_fixed_asset_investment()
                if df is None or df.empty:
                    print(f"  [WARN] 固定资产投资返回空数据")
                    return None
                parts = df["月份"].astype(str).str.extract(r"(\d{4})年(\d{2})月份")
                d = pd.DataFrame({
                    "year": pd.to_numeric(parts[0], errors="coerce"),
                    "month": pd.to_numeric(parts[1], errors="coerce"),
                    "monthly": pd.to_numeric(df["当月"], errors="coerce"),
                }).dropna(subset=["year", "month"]).sort_values(["year", "month"])
                d["ym"] = d["year"].astype(int) * 100 + d["month"].astype(int)
                ly = d[["ym", "monthly"]].rename(columns={"monthly": "monthly_ly"}).copy()
                ly["ym"] = ly["ym"] + 100
                m = d.merge(ly, on="ym", how="left").dropna(subset=["monthly", "monthly_ly"])
                m["yoy"] = (m["monthly"] / m["monthly_ly"] - 1) * 100
                m = m.reset_index(drop=True)
                out = pd.DataFrame({
                    "日期": m["year"].astype(int).astype(str) + "-"
                            + m["month"].astype(int).astype(str).str.zfill(2) + "-01",
                    "固定资产投资当月同比": m["yoy"].round(2),
                })
                print(f"  [INFO] 固投当月同比共 {len(out)} 条（{out.iloc[0,0]} ~ {out.iloc[-1,0]}）")
                return out
            except Exception as e:
                print(f"  [ERR] 固定资产投资获取失败: {e}")
                traceback.print_exc()
            return None
        return _fetch

    # ── 模式 11：10 年期国债收益率 ────────────────────────────
    if func_name == "bond_zh_us_yield_em":

        def _fetch():
            try:
                df = ak.bond_zh_us_yield_em()
                col = "中国国债收益率10年"
                if df is None or df.empty or col not in df.columns:
                    print(f"  [WARN] 国债收益率返回异常，列: {list(df.columns) if df is not None else None}")
                    return None
                out = df[["日期", col]].dropna().copy()
                out.columns = ["日期", "10年国债收益率"]
                print(f"  [INFO] 获取10年国债收益率共 {len(out)} 条数据")
                return out
            except Exception as e:
                print(f"  [ERR] 国债收益率获取失败: {e}")
                traceback.print_exc()
            return None
        return _fetch

    # ── 模式 12：社融滚动12个月增量同比 ──────────────────────
    if func_name == "macro_china_social_financing":

        def _fetch():
            try:
                df = ak.macro_china_social_financing()
                if df is None or df.empty:
                    print(f"  [WARN] 社融数据返回空")
                    return None
                ym = df["月份"].astype(str).str.replace(r"\D", "", regex=True).str.zfill(6)
                d = pd.DataFrame({
                    "year": pd.to_numeric(ym.str[:4], errors="coerce"),
                    "month": pd.to_numeric(ym.str[4:6], errors="coerce"),
                    "inc": pd.to_numeric(df["社会融资规模增量"], errors="coerce"),
                }).dropna(subset=["year", "month", "inc"]).sort_values(["year", "month"])
                d["roll12"] = d["inc"].rolling(12, min_periods=12).sum()
                d["yoy"] = (d["roll12"] / d["roll12"].shift(12) - 1) * 100
                m = d.dropna(subset=["yoy"]).reset_index(drop=True)
                out = pd.DataFrame({
                    "日期": m["year"].astype(int).astype(str) + "-"
                            + m["month"].astype(int).astype(str).str.zfill(2) + "-01",
                    "社融滚动增量同比": m["yoy"].round(2),
                })
                print(f"  [INFO] 社融滚动增量同比共 {len(out)} 条（{out.iloc[0,0]} ~ {out.iloc[-1,0]}）")
                return out
            except Exception as e:
                print(f"  [ERR] 社融数据获取失败: {e}")
                traceback.print_exc()
            return None
        return _fetch

    # ── 模式 13：70城房价（按城市取均值）─────────────────────
    if func_name == "macro_china_new_house_price":

        def _fetch():
            try:
                df = ak.macro_china_new_house_price()
                col = "新建商品住宅价格指数-同比"
                if df is None or df.empty or col not in df.columns:
                    print(f"  [WARN] 房价数据异常，列: {list(df.columns) if df is not None else None}")
                    return None
                d = df[["日期", col]].copy()
                d[col] = pd.to_numeric(d[col], errors="coerce")
                d = d.dropna(subset=[col])
                g = d.groupby("日期", as_index=False)[col].mean().sort_values("日期")
                g.columns = ["日期", "新建住宅价格指数同比"]
                g.iloc[:, 1] = g.iloc[:, 1].round(2)
                print(f"  [INFO] 70城房价均值共 {len(g)} 条（{g.iloc[0,0]} ~ {g.iloc[-1,0]}）")
                return g
            except Exception as e:
                print(f"  [ERR] 房价数据获取失败: {e}")
                traceback.print_exc()
            return None
        return _fetch

    # ── 模式 7：有列名映射的通用函数 ──────────────────────────
    if date_col_spec and val_col_spec:

        def _fetch():
            try:
                fetch_func = getattr(ak, func_name)
                df = fetch_func()
                if df is None or df.empty:
                    print(f"  [WARN] {ind_name} 返回空数据")
                    return None
                result, used_date = _extract_date_val(
                    df, date_col_spec, val_col_spec
                )
                if used_date is not None:
                    # 提取成功，重命名值列
                    cols = list(result.columns)
                    cols[-1] = ind_name
                    result.columns = cols
                    print(f"  [INFO] 获取 {ind_name} 共 {len(result)} 条数据")
                    return result
                else:
                    # 列名不匹配，输出提示并返回全部列
                    print(f"  [WARN] {ind_name} 列名不匹配: 期望 {date_col_spec}/{val_col_spec}")
                    print(f"         实际列: {list(df.columns)}，返回全部列")
                    return df
            except AttributeError:
                print(f"  [ERR] akshare 中未找到函数: {func_name}")
            except Exception as e:
                print(f"  [ERR] {ind_name} 获取失败: {e}")
                traceback.print_exc()
            return None
        return _fetch

    # ── 模式 8：无映射的通用函数（保留全部列）───────────────
    def _fetch():
        try:
            fetch_func = getattr(ak, func_name)
            df = fetch_func()
            if df is not None and not df.empty:
                print(f"  [INFO] 获取 {ind_name} 共 {len(df)} 条数据")
            return df
        except AttributeError:
            print(f"  [ERR] akshare 中未找到函数: {func_name}")
        except Exception as e:
            print(f"  [ERR] {ind_name} 获取失败: {e}")
            traceback.print_exc()
        return None
    return _fetch


def build_fetch_map(config):
    """从配置文件动态构建 FETCH_MAP（indicator_id → callable）"""
    fetch_map = {}
    for category, indicators in config.get("indicators", {}).items():
        for ind in indicators:
            ind_id = ind["id"]
            fetch_map[ind_id] = create_fetch_function(ind)
    return fetch_map


def fetch_all():
    """采集所有指标数据"""
    config = load_config()
    ensure_data_dir()

    fetch_map = build_fetch_map(config)

    results = {"success": [], "failed": []}

    for category, indicators in config.get("indicators", {}).items():
        print(f"\n{'='*50}")
        print(f"  [{category}] 类别")
        print(f"{'='*50}")

        for ind in indicators:
            ind_id = ind["id"]
            name = ind["name"]
            print(f"\n>> 采集: {name} ({ind_id})")

            fetch_func = fetch_map.get(ind_id)
            if fetch_func is None:
                print(f"  [SKIP] 未配置采集函数")
                results["failed"].append(ind_id)
                continue

            try:
                df = fetch_func()
                if df is not None and not df.empty:
                    if save_csv(df, ind_id):
                        results["success"].append(ind_id)
                    else:
                        results["failed"].append(ind_id)
                else:
                    print(f"  [WARN] 返回空数据")
                    results["failed"].append(ind_id)
            except Exception as e:
                print(f"  [ERR] 采集异常: {e}")
                traceback.print_exc()
                results["failed"].append(ind_id)

    # ── 汇总 ──────────────────────────────────────────────────
    n_total = len(results["success"]) + len(results["failed"])
    print(f"\n{'='*50}")
    print(f"  采集完成: {len(results['success'])}/{n_total} 成功, "
          f"{len(results['failed'])} 失败")
    if results["failed"]:
        print(f"  失败项: {', '.join(results['failed'])}")
    print(f"{'='*50}")

    # 写入元数据
    meta = {
        "last_update": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "success_count": len(results["success"]),
        "failed_count": len(results["failed"]),
        "failed_items": results["failed"],
    }
    meta_path = os.path.join(DATA_DIR, "meta.yaml")
    with open(meta_path, "w", encoding="utf-8") as f:
        yaml.dump(meta, f, allow_unicode=True)
    print(f"\n  元数据已保存到 {meta_path}")

    return results


if __name__ == "__main__":
    fetch_all()
