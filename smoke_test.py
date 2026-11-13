"""
宏观数据跟踪 — 数据与分析结果自检
用法:
    python smoke_test.py           # 检查，问题只告警
    python smoke_test.py --strict  # 陈旧数据也视为失败（适合更新后跑）

检查项:
  1. config 中指标 id 唯一，三类指标均非空
  2. 每个指标 CSV 存在、可解析、行数足够
  3. 最新数据日期在按频率设定的时效阈值内
  4. analysis_trimmed.json 字段完整，每个指标有信号
  5. 相关性矩阵为方阵且指标齐全
  6. data_health / 合成指数存在
"""
import os
import sys
import json
import yaml
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)
os.chdir(BASE_DIR)

import analyze as A

STRICT = "--strict" in sys.argv

STALE_LIMIT = {"每日": 10, "月度": 75, "季度": 150}
MIN_ROWS = {"每日": 30, "月度": 12, "季度": 4}

failures = []
warnings = []


def fail(msg):
    failures.append(msg)
    print(f"  [FAIL] {msg}")


def warn(msg):
    warnings.append(msg)
    print(f"  [WARN] {msg}")


def ok(msg):
    print(f"  [ OK ] {msg}")


def main():
    print("=" * 60)
    print("  宏观数据跟踪 — 自检")
    print("=" * 60)

    # ── 1. 配置 ─────────────────────────────────────────────
    cfg = A.load_config()
    seen = set()
    for cat in ["leading", "coincident", "lagging"]:
        inds = cfg.get("indicators", {}).get(cat, [])
        if not inds:
            fail(f"分类 {cat} 为空")
        for ind in inds:
            if ind["id"] in seen:
                fail(f"重复的指标 id: {ind['id']}")
            seen.add(ind["id"])
    ok(f"配置加载: {len(seen)} 个指标")

    # ── 2/3. 每个指标的数据文件与时效 ──────────────────────
    from analyze import load_indicator_data
    stale = []
    for cat in ["leading", "coincident", "lagging"]:
        for ind in cfg["indicators"][cat]:
            iid, name = ind["id"], ind["name"]
            freq = ind.get("frequency", "月度")
            loaded = load_indicator_data(iid)
            if loaded is None:
                fail(f"{name} ({iid}) 无可用数据")
                continue
            df, _, _ = loaded
            if len(df) < MIN_ROWS.get(freq, 12):
                warn(f"{name} 仅 {len(df)} 行（{freq}，期望 >= {MIN_ROWS.get(freq, 12)}）")
            age = (datetime.now() - df["_date"].max().to_pydatetime()).days
            limit = STALE_LIMIT.get(freq, 75)
            if age > limit:
                stale.append((name, age, limit))
                (fail if STRICT else warn)(
                    f"{name} 数据 {age} 天未更新（{freq}阈值 {limit} 天）")

    if not stale and not failures:
        ok("全部指标数据新鲜")

    # ── 4-6. 分析结果 ──────────────────────────────────────
    path = os.path.join(BASE_DIR, "data", "analysis_trimmed.json")
    if not os.path.exists(path):
        fail("analysis_trimmed.json 不存在，先运行 analyze.py")
    else:
        with open(path, "r", encoding="utf-8") as f:
            d = json.load(f)

        total = 0
        for cat in ["leading", "coincident", "lagging"]:
            for ind in d.get("indicators", {}).get(cat, []):
                total += 1
                if ind.get("latest_value") is None:
                    fail(f"{ind.get('name')} 缺少 latest_value")
                if ind.get("signal") not in ("improving", "deteriorating", "stable"):
                    fail(f"{ind.get('name')} 信号异常: {ind.get('signal')}")
                if "data_age_days" not in ind:
                    warn(f"{ind.get('name')} 缺少 data_age_days 字段")
        ok(f"分析结果: {total}/{len(seen)} 个指标进入分析输出")
        if total < len(seen):
            warn(f"有 {len(seen) - total} 个指标未进入分析输出")

        cm = d.get("correlation_matrix") or {}
        m = cm.get("matrix") or []
        ids = cm.get("indicators") or []
        if not m:
            fail("相关性矩阵为空")
        elif len(m) != len(ids) or any(len(row) != len(ids) for row in m):
            fail("相关性矩阵不是方阵")
        else:
            none_cells = sum(1 for row in m for v in row if v is None)
            ratio = none_cells / (len(ids) * len(ids))
            msg = f"相关性矩阵 {len(ids)}x{len(ids)}，空单元 {ratio:.0%}"
            (warn if ratio > 0.25 else ok)(msg)

        for cat in ["leading", "coincident", "lagging"]:
            if not d.get("composite_indices", {}).get(cat):
                fail(f"合成指数缺失: {cat}")

        if "data_health" not in d:
            warn("缺少 data_health 字段")
        else:
            ok(f"数据健康度: 陈旧 {d['data_health'].get('stale_count', 0)} 项")

        for key in ["merrill_lynch", "pring", "cycle_phase", "summary"]:
            if not d.get(key):
                fail(f"分析结果缺少 {key}")

    # ── 总结 ───────────────────────────────────────────────
    print("-" * 60)
    if failures:
        print(f"  失败 {len(failures)} 项，告警 {len(warnings)} 项")
        return 1
    print(f"  通过，告警 {len(warnings)} 项")
    return 0


if __name__ == "__main__":
    sys.exit(main())
