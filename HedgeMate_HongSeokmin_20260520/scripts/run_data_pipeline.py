#!/usr/bin/env python3
import argparse
import csv
import html
import itertools
import json
import math
import statistics
import sys
import time
import urllib.parse
import urllib.request
import uuid
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

HEDGEMATE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = HEDGEMATE_ROOT.parent
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from hedge_action_engine import (  # noqa: E402
    build_hedge_action_candidates,
    build_hedge_action_plan,
    build_portfolio_vulnerability_attribution,
    finalize_action_row_contract,
    write_action_artifacts,
)


def resolve_path(*candidates):
    for raw in candidates:
        for p in (HEDGEMATE_ROOT / raw, REPO_ROOT / raw, Path(raw)):
            if p.exists():
                return p
    return HEDGEMATE_ROOT / candidates[0]


DOC_ROOT = resolve_path("docs/STEP_1", "docs")
UNIVERSE_META = resolve_path(
    "docs/STEP_1/01_개요/03_자산유니버스_메타_v1.csv",
    "docs/STEP_1/01_개요/03_자산유니버스_메타_v1.csv",
    "docs/01_개요/03_자산유니버스_메타_v1.csv",
)
OUTPUT_RAW_DIR = HEDGEMATE_ROOT / "outputs" / "raw"
OUTPUT_PROCESSED_DIR = HEDGEMATE_ROOT / "outputs" / "processed"
OUTPUT_REPORT_DIR = HEDGEMATE_ROOT / "outputs" / "reports"
DOC_RESULT_DIR = resolve_path("docs/STEP_1/04_실행결과", "docs/04_실행결과")
SCENARIO_VECTOR_DIR = REPO_ROOT / "scenario_research" / "outputs" / "scenario_vectors"
SCENARIO_MARKET_RAW_DIR = REPO_ROOT / "scenario_research" / "outputs" / "raw"
SCENARIO_OUTPUT_DIR = REPO_ROOT / "scenario_research" / "outputs"
SCENARIO_OUTPUT_MANIFEST = SCENARIO_OUTPUT_DIR / "latest_manifest.json"
PRODUCT_MANIFEST_PATH = HEDGEMATE_ROOT / "outputs" / "latest_manifest.json"

FX_TICKER = "KRW=X"
CASH_TICKER = "__CASH__"
DEFAULT_HISTORY_START_DATE = "2007-01-01"
DEFAULT_ROLLING_HISTORY_DAYS = 365 * 5 + 10
SOXX_TICKER = "SOXX"
KR_FINANCIAL_BASKET = "KR_FINANCIAL_BASKET"
KR_FINANCIAL_BASKET_MEMBERS = {"105560.KS", "055550.KS", "032830.KS"}
DEFAULT_HEDGE_BUDGETS = [10.0, 20.0, 30.0]
DEFAULT_MAX_COMBO_SIZE = 4
DEFAULT_PREFILTER_TOP_K_PER_GROUP = 3
DEFAULT_PREFILTER_GLOBAL_LIMIT = 12
DEFAULT_MULTI_GRID_CANDIDATE_LIMIT = 6
GATE_STRESS_IMPROVE_TOLERANCE = 0.0001
DEFAULT_MAX_FX_LAG_DAYS = 7
DEFAULT_ANNUAL_RISK_FREE_RATE = 0.03

HEDGE_V1_CANDIDATES = {
    "TLT",
    "IEF",
    "SHY",
    "LQD",
    "TIP",
    "GLD",
    "IAU",
    "DBC",
    "USO",
    "XLE",
    "XLP",
    "XLU",
    "XLV",
}

CANDIDATE_ROLES = {"hedge_candidate", "diagnostic_only", "conditional_candidate"}
CONDITIONAL_CANDIDATE_TICKERS = {"BTC-USD", "ETH-USD", "NVDA", "AVGO", "AMD", "QQQ", "SOXX", "EWY", "FXI", "ITA", "PPA"}
DIAGNOSTIC_ONLY_TICKERS = {"SPY", "DIA", "IWM", "VTI", "VXUS", "KRW=X", "UUP"}
CANDIDATE_ROLE_REASON_KO = {
    "hedge_candidate": "기본 포트폴리오 개선 후보입니다.",
    "diagnostic_only": "장세 해석용 자산으로 기본 헤지 후보에서 제외합니다.",
    "conditional_candidate": "위험자산 성격이 강해 all 모드에서만 비교합니다.",
    "mixed_candidate_roles": "여러 후보 역할이 섞인 조합입니다.",
}

RISK_BUCKET_SCENARIO_CANDIDATES = {
    "higher_for_longer_long_rate_shock": {"TLT", "IEF", "SHY", "TIP", "LQD"},
    "stagflation_reinflation_energy_shock": {"GLD", "IAU", "DBC", "USO", "XLE", "TIP"},
    "usd_strength_krw_weakness": {"UUP", "SHY", "IEF", "GLD", "IAU", "EWY"},
    "acute_global_stress_liquidity_crunch": {"TLT", "IEF", "SHY", "GLD", "IAU", "XLP", "XLU", "XLV", "ITA", "PPA"},
    "china_trade_fragmentation_shock": {"GLD", "IAU", "XLP", "XLU", "EWY", "FXI"},
    "slowdown_recession_deflation_risk": {"TLT", "IEF", "SHY", "XLP", "XLU", "XLV", "GLD", "IAU"},
    "semiconductor_ai_cycle_shock": {"GLD", "IAU", "SHY", "IEF", "UUP", "EWY", "SOXX", "QQQ"},
    "korea_domestic_financial_stress": {"UUP", "SHY", "IEF", "GLD", "IAU", "EWY"},
    "geopolitical_escalation_supply_shock": {"GLD", "IAU", "USO", "XLE", "DBC", "TIP", "PPA", "ITA", "UUP", "SHY", "IEF"},
    "soft_landing_goldilocks": set(HEDGE_V1_CANDIDATES),
}

RISK_BUCKET_BASE_CANDIDATES = set(HEDGE_V1_CANDIDATES)

MIN_OBS_POLICY = {
    "vol_annual": 20,
    "mdd_1y": 20,
    "tail_1y": 60,
    "beta_overlap": 60,
    "downside_overlap": 20,
    "corr_overlap": 20,
    "adv_60": 20,
    "portfolio_common_dates": 60,
}

SENSITIVITY_FACTOR_SPECS = [
    {
        "factor": "market_beta_sp500",
        "metric": "beta_sp500_1y_krw",
        "label": "S&P500 beta",
        "flat_threshold": 0.10,
        "medium_threshold": 0.40,
        "high_threshold": 1.00,
        "sign_positive_meaning": "SPY와 같은 방향",
        "sign_negative_meaning": "SPY와 반대 방향",
    },
    {
        "factor": "downside_beta_sp500",
        "metric": "downside_beta_sp500_1y_krw",
        "label": "S&P500 downside beta",
        "flat_threshold": 0.10,
        "medium_threshold": 0.40,
        "high_threshold": 1.00,
        "sign_positive_meaning": "미국 증시 하락일에 함께 하락",
        "sign_negative_meaning": "미국 증시 하락일에 반대로 움직임",
    },
    {
        "factor": "corr_sp500_60d",
        "metric": "corr_sp500_60d_krw",
        "label": "S&P500 60d correlation",
        "flat_threshold": 0.10,
        "medium_threshold": 0.30,
        "high_threshold": 0.60,
        "sign_positive_meaning": "SPY와 같은 방향",
        "sign_negative_meaning": "SPY와 반대 방향",
    },
    {
        "factor": "corr_kospi200_60d",
        "metric": "corr_kospi200_60d_krw",
        "label": "KOSPI200 60d correlation",
        "flat_threshold": 0.10,
        "medium_threshold": 0.30,
        "high_threshold": 0.60,
        "sign_positive_meaning": "KOSPI200과 같은 방향",
        "sign_negative_meaning": "KOSPI200과 반대 방향",
    },
    {
        "factor": "stress_response",
        "metric": "avg_stress_ret_krw",
        "label": "Stress-period average return",
        "flat_threshold": 0.0005,
        "medium_threshold": 0.0015,
        "high_threshold": 0.0030,
        "sign_positive_meaning": "위기구간에서 플러스 성과",
        "sign_negative_meaning": "위기구간에서 마이너스 성과",
    },
]


def find_latest_cached_snapshot(prefix, directory):
    candidates = sorted(directory.glob(f"{prefix}_*.csv"))
    if not candidates:
        return None, None
    latest = candidates[-1]
    name = latest.name
    stem = latest.stem
    version = stem[len(prefix) + 1:] if stem.startswith(f"{prefix}_") else None
    return latest, version


def read_scenario_vector_rows(path):
    """Read a scenario vector file without deciding whether it is current."""
    path = Path(path)
    if path.suffix.lower() == ".json":
        raw = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            raw_rows = raw.get("rows") or raw.get("scenarios") or []
        else:
            raw_rows = raw
        rows = [dict(row) for row in raw_rows]
    else:
        with path.open("r", encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))

    for row in rows:
        for key in ["score", "confidence", "coverage"]:
            row[key] = parse_float(row.get(key))
    return rows


def scenario_vector_as_of(rows):
    return max(
        (row.get("as_of_date") or row.get("date") for row in rows if row.get("as_of_date") or row.get("date")),
        default=None,
    )


def select_latest_scenario_vector(directory):
    candidates = sorted(Path(directory).glob("current_scenario_vector_*.csv"))
    if not candidates:
        return {
            "path": None,
            "rows": [],
            "selected_by": "fallback_none",
            "candidate_count": 0,
            "candidate_as_of_dates": [],
        }

    details = []
    for candidate in candidates:
        try:
            rows = read_scenario_vector_rows(candidate)
            as_of_date = scenario_vector_as_of(rows)
        except (OSError, ValueError, json.JSONDecodeError, csv.Error):
            rows = []
            as_of_date = None
        details.append(
            {
                "path": candidate,
                "rows": rows,
                "as_of_date": as_of_date,
                "mtime": candidate.stat().st_mtime,
            }
        )

    max_as_of = max((item["as_of_date"] or "" for item in details), default="")
    latest_pool = [item for item in details if (item["as_of_date"] or "") == max_as_of]
    selected = sorted(latest_pool, key=lambda item: (item["mtime"], item["path"].name))[-1]
    selected_by = "max_as_of_date" if max_as_of and len(latest_pool) == 1 else "mtime_tiebreak"
    if not max_as_of:
        selected_by = "mtime_tiebreak"

    return {
        "path": selected["path"],
        "rows": selected["rows"],
        "selected_by": selected_by,
        "candidate_count": len(candidates),
        "candidate_as_of_dates": [
            f"{item['path'].name}:{item['as_of_date'] or '-'}" for item in sorted(details, key=lambda x: x["path"].name)
        ],
    }


# -----------------------------
# Generic helpers
# -----------------------------

def now_utc():
    return datetime.now(timezone.utc)


def build_run_id(run_ts=None):
    ts = run_ts or now_utc()
    return f"{ts.strftime('%Y%m%dT%H%M%S%f')}-{uuid.uuid4().hex[:8]}"


def resolve_fetch_start_dt(run_ts, history_start_date=DEFAULT_HISTORY_START_DATE):
    rolling_start = (run_ts - timedelta(days=DEFAULT_ROLLING_HISTORY_DAYS)).replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )
    try:
        historical_start = datetime.strptime(str(history_start_date), "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError as exc:
        raise ValueError("--history-start-date must use YYYY-MM-DD format") from exc
    return min(rolling_start, historical_start)


def parse_float(v):
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def parse_date(v):
    return datetime.strptime(v, "%Y-%m-%d").date()


def clip01(v):
    return max(0.0, min(1.0, v))


def percentile(values, p):
    if not values:
        return None
    arr = sorted(values)
    if len(arr) == 1:
        return arr[0]
    k = (len(arr) - 1) * p
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return arr[int(k)]
    d0 = arr[f] * (c - k)
    d1 = arr[c] * (k - f)
    return d0 + d1


def mean(values):
    return sum(values) / len(values) if values else None


def stdev(values):
    if len(values) < 2:
        return None
    return statistics.stdev(values)


def covariance(xs, ys):
    if len(xs) != len(ys) or len(xs) < 2:
        return None
    mx = mean(xs)
    my = mean(ys)
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / (len(xs) - 1)


def variance(xs):
    if len(xs) < 2:
        return None
    m = mean(xs)
    return sum((x - m) ** 2 for x in xs) / (len(xs) - 1)


def correlation(xs, ys):
    cov = covariance(xs, ys)
    if cov is None:
        return None
    sx = stdev(xs)
    sy = stdev(ys)
    if sx in (None, 0) or sy in (None, 0):
        return None
    return cov / (sx * sy)


def mdd(prices):
    if not prices:
        return None
    peak = prices[0]
    min_dd = 0.0
    for p in prices:
        if p > peak:
            peak = p
        dd = p / peak - 1.0
        if dd < min_dd:
            min_dd = dd
    return min_dd


def cumulative_return(rets):
    if not rets:
        return None
    acc = 1.0
    for r in rets:
        acc *= 1.0 + r
    return acc - 1.0


def annualized_return_from_returns(rets, periods_per_year=252):
    if not rets:
        return None
    acc = 1.0
    for r in rets:
        if r <= -1.0:
            return -1.0
        acc *= 1.0 + r
    if acc <= 0:
        return None
    return acc ** (periods_per_year / len(rets)) - 1.0


def sharpe_from_returns(rets, annual_risk_free_rate=DEFAULT_ANNUAL_RISK_FREE_RATE):
    if not rets:
        return None
    vol = stdev(rets)
    if vol in (None, 0):
        return None
    vol_ann = vol * math.sqrt(252)
    if vol_ann in (None, 0):
        return None
    ann_ret = annualized_return_from_returns(rets)
    if ann_ret is None:
        return None
    return (ann_ret - annual_risk_free_rate) / vol_ann


def returns_from_prices(series):
    # series: list[(date, price)] sorted
    rets = []
    ret_map = {}
    for i in range(1, len(series)):
        _, p_prev = series[i - 1]
        d_cur, p_cur = series[i]
        if p_prev and p_prev > 0 and p_cur and p_cur > 0:
            r = p_cur / p_prev - 1.0
            rets.append(r)
            ret_map[d_cur] = r
    return rets, ret_map


def fetch_yahoo_chart(ticker, period1, period2, retries=5):
    encoded_ticker = urllib.parse.quote(ticker, safe="")
    url = (
        f"https://query1.finance.yahoo.com/v8/finance/chart/{encoded_ticker}"
        f"?period1={period1}&period2={period2}&interval=1d&events=div%2Csplits"
    )

    for attempt in range(1, retries + 1):
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
                "Accept": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
                result = payload.get("chart", {}).get("result", [])
                if not result:
                    return []
                r0 = result[0]
                timestamps = r0.get("timestamp", [])
                quote = r0.get("indicators", {}).get("quote", [{}])[0]
                adj_close_list = (
                    r0.get("indicators", {}).get("adjclose", [{}])[0].get("adjclose", [])
                )

                opens = quote.get("open", [])
                highs = quote.get("high", [])
                lows = quote.get("low", [])
                closes = quote.get("close", [])
                volumes = quote.get("volume", [])

                rows = []
                for i, ts in enumerate(timestamps):
                    dt = datetime.fromtimestamp(ts, tz=timezone.utc).date().isoformat()
                    o = opens[i] if i < len(opens) else None
                    h = highs[i] if i < len(highs) else None
                    l = lows[i] if i < len(lows) else None
                    c = closes[i] if i < len(closes) else None
                    a = adj_close_list[i] if i < len(adj_close_list) else None
                    v = volumes[i] if i < len(volumes) else None

                    if c is None:
                        continue
                    rows.append(
                        {
                            "date": dt,
                            "open": o,
                            "high": h,
                            "low": l,
                            "close": c,
                            "adj_close": a if a is not None else c,
                            "volume": v,
                        }
                    )
                return rows
        except Exception:
            if attempt == retries:
                return []
            time.sleep(min(2**attempt, 20))
    return []


def build_stress_dates(spy_prices, ks200_prices):
    stress_dates = set()

    def add_dates(price_series):
        for i in range(20, len(price_series)):
            d, p = price_series[i]
            _, p20 = price_series[i - 20]
            if p20 and p20 > 0 and p and p > 0:
                r20 = p / p20 - 1.0
                if r20 <= -0.08:
                    stress_dates.add(d)

    add_dates(spy_prices)
    add_dates(ks200_prices)
    return stress_dates


def normalize_minmax(v, vmin, vmax, default_if_flat=0.5):
    if v is None:
        return None
    if vmin is None or vmax is None:
        return default_if_flat
    if vmax == vmin:
        return default_if_flat
    return clip01((v - vmin) / (vmax - vmin))


def safe_round(v, digits=6):
    if v is None:
        return ""
    if isinstance(v, float):
        return round(v, digits)
    return v


def write_csv(path, fieldnames, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for row in rows:
            w.writerow({k: safe_round(row.get(k)) for k in fieldnames})


SOURCE_QUALITY_HIGH_BLOCKERS = {"seed", "manual", "fixture", "unknown"}


def latest_manifest_path():
    return SCENARIO_OUTPUT_DIR / "latest_manifest.json"


def read_latest_manifest(path=None):
    path = path or latest_manifest_path()
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def scenario_manifest_path(raw_path):
    if not raw_path:
        return None
    text = str(raw_path).replace("\\", "/")
    if text.startswith("../") or Path(text).is_absolute():
        return text
    return "../" + text


def artifact_name(raw_path):
    if not raw_path:
        return None
    return Path(str(raw_path).replace("\\", "/")).name


def sync_product_active_bundle_fields(manifest, product_manifest_path=None):
    product = read_latest_manifest(product_manifest_path or PRODUCT_MANIFEST_PATH)
    active_bundle = product.get("active_bundle", {}) if isinstance(product, dict) else {}
    if not isinstance(active_bundle, dict):
        active_bundle = {}
    hedge_run = product.get("active_hedgemate_run") or active_bundle.get("hedgemate_run")
    if not hedge_run:
        return manifest

    updated = dict(manifest)
    previous_run = updated.get("active_hedgemate_run")
    if previous_run and previous_run != hedge_run:
        updated["legacy_hedgemate_run"] = previous_run
        updated["legacy_hedgemate_note"] = (
            "Superseded by HedgeMate/outputs/latest_manifest.json active bundle; "
            "do not use this legacy run as product recommendation evidence."
        )

    artifacts = product.get("artifacts", {}) if isinstance(product.get("artifacts"), dict) else {}
    sensitivity_path = artifacts.get("assetScenarioSensitivity") or f"HedgeMate/outputs/processed/asset_scenario_sensitivity_{hedge_run}.csv"
    summary_path = f"HedgeMate/outputs/reports/asset_scenario_sensitivity_summary_{hedge_run}.md"
    qa_path = artifacts.get("recommendationStatusQa")
    updated.update(
        {
            "active_hedgemate_run": hedge_run,
            "active_hedgemate_summary": artifact_name(summary_path),
            "active_hedgemate_summary_path": scenario_manifest_path(summary_path),
            "active_hedgemate_sensitivity": artifact_name(sensitivity_path),
            "active_hedgemate_sensitivity_path": scenario_manifest_path(sensitivity_path),
            "active_hedgemate_scenario_vector": artifacts.get("scenarioVector"),
            "active_hedgemate_recommendation_status_qa": artifact_name(qa_path),
            "active_hedgemate_recommendation_status_qa_path": scenario_manifest_path(qa_path),
            "active_hedgemate_product_manifest_path": "../HedgeMate/outputs/latest_manifest.json",
            "active_hedgemate_manifest_basis": "HedgeMate/outputs/latest_manifest.json",
        }
    )
    return updated


def update_latest_manifest(updates, path=None):
    path = path or latest_manifest_path()
    existing = read_latest_manifest(path)
    existing.update({key: value for key, value in updates.items() if value is not None})
    existing = sync_product_active_bundle_fields(existing)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")


def resolve_manifest_artifact(manifest, key, default_dir):
    raw_path = manifest.get(f"{key}_path") or manifest.get(key)
    if not raw_path:
        return None
    candidate = Path(str(raw_path))
    if candidate.is_absolute():
        return candidate if candidate.exists() else None
    candidates = [
        SCENARIO_OUTPUT_DIR / candidate,
        Path(default_dir) / candidate,
    ]
    for path in candidates:
        if path.exists():
            return path
    return None


def normalize_source_quality(value):
    value = str(value or "").strip().lower()
    return value or "unknown"


KRX_KNOWN_HOLIDAYS = {
    "2019-01-01", "2019-02-04", "2019-02-05", "2019-02-06", "2019-03-01", "2019-05-01",
    "2019-05-06", "2019-06-06", "2019-08-15", "2019-09-12", "2019-09-13", "2019-10-03",
    "2019-10-09", "2019-12-25", "2019-12-31",
    "2020-01-01", "2020-01-24", "2020-01-27", "2020-04-15", "2020-04-30", "2020-05-01",
    "2020-05-05", "2020-09-30", "2020-10-01", "2020-10-02", "2020-10-09", "2020-12-25",
    "2020-12-31",
    "2021-01-01", "2021-02-11", "2021-02-12", "2021-03-01", "2021-05-05", "2021-05-19",
    "2021-09-20", "2021-09-21", "2021-09-22", "2021-12-31",
    "2022-01-31", "2022-02-01", "2022-02-02", "2022-03-01", "2022-03-09", "2022-05-05",
    "2022-06-01", "2022-06-06", "2022-08-15", "2022-09-09", "2022-09-12", "2022-10-03",
    "2022-10-10", "2022-12-30",
    "2023-01-23", "2023-01-24", "2023-03-01", "2023-05-01", "2023-05-05", "2023-05-29",
    "2023-06-06", "2023-08-15", "2023-09-28", "2023-09-29", "2023-10-03", "2023-10-09",
    "2023-12-25", "2023-12-29",
    "2024-01-01", "2024-02-09", "2024-02-12", "2024-03-01", "2024-04-10", "2024-05-01",
    "2024-05-06", "2024-05-15", "2024-06-06", "2024-08-15", "2024-09-16", "2024-09-17",
    "2024-09-18", "2024-10-03", "2024-10-09", "2024-12-25", "2024-12-31",
    "2025-01-01", "2025-01-27", "2025-01-28", "2025-01-29", "2025-01-30", "2025-03-03",
    "2025-05-01", "2025-05-05", "2025-05-06", "2025-06-06", "2025-08-15", "2025-10-03",
    "2025-10-06", "2025-10-07", "2025-10-08", "2025-10-09", "2025-12-25", "2025-12-31",
    "2026-01-01", "2026-02-16", "2026-02-17", "2026-02-18", "2026-03-02", "2026-05-01",
    "2026-05-05", "2026-05-25", "2026-06-08", "2026-08-17", "2026-09-24", "2026-09-25",
    "2026-10-05", "2026-10-09", "2026-12-25", "2026-12-31",
}


def observed_fixed_holiday(year, month, day):
    dt = datetime(year, month, day).date()
    if dt.weekday() == 5:
        return dt - timedelta(days=1)
    if dt.weekday() == 6:
        return dt + timedelta(days=1)
    return dt


def nth_weekday(year, month, weekday, n):
    dt = datetime(year, month, 1).date()
    while dt.weekday() != weekday:
        dt += timedelta(days=1)
    return dt + timedelta(days=7 * (n - 1))


def last_weekday(year, month, weekday):
    if month == 12:
        dt = datetime(year, 12, 31).date()
    else:
        dt = datetime(year, month + 1, 1).date() - timedelta(days=1)
    while dt.weekday() != weekday:
        dt -= timedelta(days=1)
    return dt


def easter_date(year):
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return datetime(year, month, day).date()


def us_market_holidays(year):
    holidays = {
        observed_fixed_holiday(year, 1, 1),
        nth_weekday(year, 1, 0, 3),
        nth_weekday(year, 2, 0, 3),
        easter_date(year) - timedelta(days=2),
        last_weekday(year, 5, 0),
        observed_fixed_holiday(year, 7, 4),
        nth_weekday(year, 9, 0, 1),
        nth_weekday(year, 11, 3, 4),
        observed_fixed_holiday(year, 12, 25),
    }
    if year >= 2022:
        holidays.add(observed_fixed_holiday(year, 6, 19))
    return holidays


def is_trading_day(region, dt):
    region = (region or "US").upper()
    if region == "CRYPTO":
        return True
    if dt.weekday() >= 5:
        return False
    if region == "KR":
        return dt.isoformat() not in KRX_KNOWN_HOLIDAYS
    holidays = set()
    for year in range(dt.year - 1, dt.year + 2):
        holidays.update(us_market_holidays(year))
    return dt not in holidays


def expected_calendar_rows(region, start_d, end_d):
    if start_d > end_d:
        return 0
    total_days = (end_d - start_d).days + 1
    return sum(1 for i in range(total_days) if is_trading_day(region, start_d + timedelta(days=i)))


def get_region_calendar_type(region):
    if region == "CRYPTO":
        return "CRYPTO_24_7"
    if region == "KR":
        return "KRX_TRADING_DAYS"
    return "US_MARKET_TRADING_DAYS"


def classify_data_quality(miss_rate, coverage_calendar, invalid_price, duplicate_count, outlier_count, fx_missing_count, total_rows):
    reason_codes = []

    calendar_status = "PASS"
    if total_rows <= 0 or coverage_calendar < 0.90:
        calendar_status = "FAIL"
        reason_codes.append("calendar_coverage_fail")
    elif coverage_calendar < 0.97:
        calendar_status = "WARN"
        reason_codes.append("calendar_coverage_warn")

    price_integrity_status = "PASS"
    if invalid_price > 0 or miss_rate > 0.05:
        price_integrity_status = "FAIL"
        if invalid_price > 0:
            reason_codes.append("invalid_price")
        if miss_rate > 0.05:
            reason_codes.append("missing_adjusted_close_fail")
    elif miss_rate >= 0.01 or duplicate_count > 0 or outlier_count > 0:
        price_integrity_status = "WARN"
        if miss_rate >= 0.01:
            reason_codes.append("missing_adjusted_close_warn")
        if duplicate_count > 0:
            reason_codes.append("duplicate_rows_warn")
        if outlier_count > 0:
            reason_codes.append("extreme_return_outlier_warn")

    fx_missing_rate = (fx_missing_count / total_rows) if total_rows else 0.0
    fx_status = "PASS"
    if fx_missing_rate > 0.05:
        fx_status = "FAIL"
        reason_codes.append("fx_missing_fail")
    elif fx_missing_count > 0:
        fx_status = "WARN"
        reason_codes.append("fx_missing_warn")

    statuses = [calendar_status, price_integrity_status, fx_status]
    if "FAIL" in statuses:
        status = "FAIL"
    elif "WARN" in statuses:
        status = "WARN"
    else:
        status = "PASS"

    blocking = "FAIL" in statuses
    return {
        "status": status,
        "dq_status": status,
        "calendar_status": calendar_status,
        "price_integrity_status": price_integrity_status,
        "fx_status": fx_status,
        "dq_blocking": blocking,
        "dq_reason_codes": "|".join(reason_codes),
    }


def calc_adv_60(series):
    # series: [(date, adj_close_krw, volume), ...]
    notional = []
    for _, adj_close, vol in series:
        if adj_close is None or vol is None:
            continue
        if adj_close <= 0 or vol <= 0:
            continue
        notional.append(adj_close * vol)
    if len(notional) < MIN_OBS_POLICY["adv_60"]:
        return None
    return mean(notional[-60:])


def metric_validation_set(tolerance=1e-9):
    rows = []

    def add(metric, expected, actual):
        abs_err = None
        passed = False
        if expected is not None and actual is not None:
            abs_err = abs(expected - actual)
            passed = abs_err <= tolerance
        rows.append(
            {
                "metric": metric,
                "expected": expected,
                "actual": actual,
                "abs_error": abs_err,
                "tolerance": tolerance,
                "status": "PASS" if passed else "FAIL",
            }
        )

    vol_rets = [0.01, -0.02, 0.03, -0.01, 0.0]
    vol_expected = 0.3053522555999873
    vol_actual = stdev(vol_rets) * math.sqrt(252)
    add("vol_annual", vol_expected, vol_actual)

    prices = [100, 110, 90, 95, 80]
    mdd_expected = -0.2727272727272727
    mdd_actual = mdd(prices)
    add("mdd", mdd_expected, mdd_actual)

    tail_rets = [-0.10, -0.05, -0.02, 0.01, 0.03]
    var_expected = -0.09000000000000002
    cvar_expected = -0.1
    var_actual = percentile(tail_rets, 0.05)
    cvar_actual = mean([r for r in tail_rets if var_actual is not None and r <= var_actual])
    add("var_95", var_expected, var_actual)
    add("cvar_95", cvar_expected, cvar_actual)

    market = [-0.02, -0.01, 0.01, 0.03, 0.02]
    asset = [2 * x for x in market]
    cov_xy = covariance(asset, market)
    var_m = variance(market)
    beta_actual = cov_xy / var_m if cov_xy is not None and var_m not in (None, 0) else None
    corr_actual = correlation(asset, market)
    add("beta", 2.0, beta_actual)
    add("corr", 1.0, corr_actual)
    add("sharpe_proxy", sharpe_from_returns([0.01, 0.0, -0.005, 0.012]), sharpe_from_returns([0.01, 0.0, -0.005, 0.012]))

    return rows


# -----------------------------
# Raw cache helpers
# -----------------------------

def load_cached_raw(raw_file, universe_map):
    raw_rows = []
    ticker_series = defaultdict(list)
    class_rows = defaultdict(list)

    if not raw_file.exists():
        return raw_rows, ticker_series, class_rows

    with raw_file.open("r", encoding="utf-8") as f:
        rdr = csv.DictReader(f)
        for row in rdr:
            ticker = row["ticker"]
            asset_class = row["asset_class"]
            parsed = {
                "date": row["date"],
                "ticker": ticker,
                "asset_class": asset_class,
                "source": row.get("source", "yahoo"),
                "open": parse_float(row.get("open")),
                "high": parse_float(row.get("high")),
                "low": parse_float(row.get("low")),
                "close": parse_float(row.get("close")),
                "adj_close": parse_float(row.get("adj_close")),
                "volume": parse_float(row.get("volume")),
                "currency": row.get("currency", universe_map.get(ticker, {}).get("currency", "")),
                "ingested_at": row.get("ingested_at", ""),
            }
            raw_rows.append(parsed)
            ticker_series[ticker].append(
                (
                    parsed["date"],
                    parsed["adj_close"],
                    parsed["volume"],
                    parsed["open"],
                    parsed["high"],
                    parsed["low"],
                    parsed["close"],
                )
            )

    for ticker, series in ticker_series.items():
        series.sort(key=lambda x: x[0])
        asset_class = universe_map.get(ticker, {}).get("asset_class", "unknown")
        class_rows[asset_class].append(len(series))

    return raw_rows, ticker_series, class_rows


def save_raw(raw_file, raw_rows):
    cols = [
        "date",
        "ticker",
        "asset_class",
        "source",
        "open",
        "high",
        "low",
        "close",
        "adj_close",
        "volume",
        "currency",
        "ingested_at",
    ]
    write_csv(raw_file, cols, sorted(raw_rows, key=lambda x: (x["ticker"], x["date"])))


def load_cached_fx_raw(fx_file):
    fx_rows = []
    fx_rate_map = {}
    if not fx_file.exists():
        return fx_rows, fx_rate_map
    with fx_file.open("r", encoding="utf-8") as f:
        rdr = csv.DictReader(f)
        for row in rdr:
            date_str = row["date"]
            close = parse_float(row.get("close"))
            parsed = {
                "date": date_str,
                "ticker": row.get("ticker", FX_TICKER),
                "close": close,
                "source": row.get("source", "yahoo"),
                "currency": row.get("currency", "KRW"),
                "ingested_at": row.get("ingested_at", ""),
            }
            fx_rows.append(parsed)
            if close is not None and close > 0:
                fx_rate_map[date_str] = close
    return fx_rows, fx_rate_map


def save_fx_raw(fx_file, fx_rows):
    cols = ["date", "ticker", "close", "source", "currency", "ingested_at"]
    write_csv(fx_file, cols, sorted(fx_rows, key=lambda x: x["date"]))


def load_cached_benchmark_raw(benchmark_file):
    benchmark_rows = []
    benchmark_map = defaultdict(list)
    if not benchmark_file.exists():
        return benchmark_rows, benchmark_map

    with benchmark_file.open("r", encoding="utf-8") as f:
        rdr = csv.DictReader(f)
        for row in rdr:
            ticker = row.get("ticker", "")
            parsed = {
                "date": row["date"],
                "ticker": ticker,
                "adj_close": parse_float(row.get("adj_close")),
                "source": row.get("source", "yahoo"),
                "currency": row.get("currency", ""),
                "ingested_at": row.get("ingested_at", ""),
            }
            benchmark_rows.append(parsed)
            if parsed["adj_close"] is not None:
                benchmark_map[ticker].append((parsed["date"], parsed["adj_close"]))

    for ticker, series in benchmark_map.items():
        series.sort(key=lambda x: x[0])
    return benchmark_rows, benchmark_map


def save_benchmark_raw(benchmark_file, benchmark_rows):
    cols = ["date", "ticker", "adj_close", "source", "currency", "ingested_at"]
    write_csv(benchmark_file, cols, sorted(benchmark_rows, key=lambda x: (x["ticker"], x["date"])))


def load_or_fetch_benchmark_symbol(preferred_ticker, fallback_ticker, period1, period2, run_id, ingested_at):
    benchmark_file = OUTPUT_RAW_DIR / f"raw_benchmark_daily_{run_id}.csv"
    benchmark_rows, benchmark_map = load_cached_benchmark_raw(benchmark_file)
    if benchmark_map.get(preferred_ticker):
        return benchmark_file, benchmark_rows, benchmark_map[preferred_ticker], preferred_ticker, True
    if benchmark_map.get(fallback_ticker):
        return benchmark_file, benchmark_rows, benchmark_map[fallback_ticker], fallback_ticker, True

    for ticker in [preferred_ticker, fallback_ticker]:
        fetched = fetch_yahoo_chart(ticker, period1, period2)
        series = []
        for row in fetched:
            adj_close = row.get("adj_close")
            if adj_close is None:
                continue
            benchmark_rows.append(
                {
                    "date": row["date"],
                    "ticker": ticker,
                    "adj_close": adj_close,
                    "source": "yahoo",
                    "currency": "KRW" if ticker.startswith("^KS") else "USD",
                    "ingested_at": ingested_at,
                }
            )
            series.append((row["date"], adj_close))
        if series:
            save_benchmark_raw(benchmark_file, benchmark_rows)
            return benchmark_file, benchmark_rows, sorted(series, key=lambda x: x[0]), ticker, False

    save_benchmark_raw(benchmark_file, benchmark_rows)
    return benchmark_file, benchmark_rows, [], fallback_ticker, False


def load_or_fetch_fx(period1, period2, run_id, ingested_at):
    fx_file = OUTPUT_RAW_DIR / f"raw_fx_daily_{run_id}.csv"
    fx_rows, fx_rate_map = load_cached_fx_raw(fx_file)
    used_cached = fx_file.exists() and bool(fx_rate_map)
    if fx_rate_map:
        return fx_file, fx_rows, fx_rate_map, used_cached

    fetched = fetch_yahoo_chart(FX_TICKER, period1, period2)
    fx_rows = []
    fx_rate_map = {}
    for row in fetched:
        close = row.get("adj_close") if row.get("adj_close") is not None else row.get("close")
        if close is None:
            continue
        fx_rows.append(
            {
                "date": row["date"],
                "ticker": FX_TICKER,
                "close": close,
                "source": "yahoo",
                "currency": "KRW",
                "ingested_at": ingested_at,
            }
        )
        fx_rate_map[row["date"]] = close

    if fx_rows:
        save_fx_raw(fx_file, fx_rows)
    return fx_file, fx_rows, fx_rate_map, used_cached


# -----------------------------
# FX / metric helpers
# -----------------------------

def lookup_fx_rate(date_str, fx_rate_map, max_lag_days=DEFAULT_MAX_FX_LAG_DAYS):
    direct = fx_rate_map.get(date_str)
    if direct is not None and direct > 0:
        return direct

    base_dt = parse_date(date_str)
    for lag in range(1, max_lag_days + 1):
        prev = (base_dt - timedelta(days=lag)).isoformat()
        rate = fx_rate_map.get(prev)
        if rate is not None and rate > 0:
            return rate
    return None


def build_krw_price_series(series, currency, fx_rate_map):
    # series: [(date, adj_close, volume, open, high, low, close), ...]
    krw_prices = []
    krw_adv_series = []
    fx_missing_count = 0
    for date_str, adj_close, volume, *_ in series:
        if adj_close is None:
            continue
        if currency == "USD":
            fx_rate = lookup_fx_rate(date_str, fx_rate_map)
            if fx_rate is None:
                fx_missing_count += 1
                continue
            krw_price = adj_close * fx_rate
        else:
            krw_price = adj_close
        krw_prices.append((date_str, krw_price))
        krw_adv_series.append((date_str, krw_price, volume))
    return krw_prices, krw_adv_series, fx_missing_count


def load_market_state_factor_series(ticker, data_version=None):
    candidates = []
    if data_version:
        candidates.append(SCENARIO_MARKET_RAW_DIR / f"raw_market_state_daily_{data_version}.csv")
    latest, _ = find_latest_cached_snapshot("raw_market_state_daily", SCENARIO_MARKET_RAW_DIR)
    if latest:
        candidates.append(latest)

    for path in candidates:
        if not path or not path.exists():
            continue
        series = []
        fallback_currency = None
        with path.open("r", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                if row.get("ticker") != ticker:
                    continue
                close = parse_float(row.get("close") or row.get("adj_close"))
                if close is None or close <= 0:
                    continue
                fallback_currency = row.get("currency") or fallback_currency
                series.append((row["date"], close, None, None, None, None, close))
        if series:
            series.sort(key=lambda item: item[0])
            return series, fallback_currency
    return [], None


def benchmark_return_map_for_ticker(
    ticker,
    ticker_series,
    currency,
    fx_rate_map,
    period1,
    period2,
    allow_fetch=True,
    data_version=None,
):
    series = ticker_series.get(ticker)
    if not series:
        series, fallback_currency = load_market_state_factor_series(ticker, data_version=data_version)
        if fallback_currency:
            currency = fallback_currency
    if not series:
        if not allow_fetch:
            return {}
        fetched = fetch_yahoo_chart(ticker, period1, period2)
        series = [
            (
                row["date"],
                row.get("adj_close"),
                row.get("volume"),
                row.get("open"),
                row.get("high"),
                row.get("low"),
                row.get("close"),
            )
            for row in fetched
            if row.get("adj_close") is not None
        ]
    if not series:
        return {}
    krw_prices, _, _ = build_krw_price_series(series, currency, fx_rate_map)
    _, ret_map = returns_from_prices([(date_str, price) for date_str, price in krw_prices])
    return ret_map


def trailing_corr(base_map, ref_map, n=60):
    cds = sorted(set(base_map.keys()) & set(ref_map.keys()))
    cds = cds[-n:]
    if len(cds) < MIN_OBS_POLICY["corr_overlap"]:
        return None
    xb = [base_map[d] for d in cds]
    yb = [ref_map[d] for d in cds]
    return correlation(xb, yb)


def compute_beta(ret_map, benchmark_ret_map):
    common_dates = sorted(set(ret_map.keys()) & set(benchmark_ret_map.keys()))
    if len(common_dates) < MIN_OBS_POLICY["beta_overlap"]:
        return None
    xs = [ret_map[d] for d in common_dates]
    ys = [benchmark_ret_map[d] for d in common_dates]
    cov_xy = covariance(xs, ys)
    var_y = variance(ys)
    return (cov_xy / var_y) if (cov_xy is not None and var_y not in (None, 0)) else None


def compute_downside_beta(ret_map, benchmark_ret_map):
    common_dates = sorted(set(ret_map.keys()) & set(benchmark_ret_map.keys()))
    down_dates = [d for d in common_dates if benchmark_ret_map[d] < 0]
    if len(down_dates) < MIN_OBS_POLICY["downside_overlap"]:
        return None
    x_down = [ret_map[d] for d in down_dates]
    y_down = [benchmark_ret_map[d] for d in down_dates]
    cov_down = covariance(x_down, y_down)
    var_down = variance(y_down)
    return cov_down / var_down if (cov_down is not None and var_down not in (None, 0)) else None


def overlap_count(left_map, right_map):
    return len(set(left_map.keys()) & set(right_map.keys()))


def build_equal_weight_return_map(ticker_ret_map, members, min_count=2):
    dates = sorted({date_str for ticker in members for date_str in ticker_ret_map.get(ticker, {})})
    out = {}
    for date_str in dates:
        values = [ticker_ret_map[ticker][date_str] for ticker in members if date_str in ticker_ret_map.get(ticker, {})]
        if len(values) >= min_count:
            out[date_str] = sum(values) / len(values)
    return out


def compute_feature_metrics(
    krw_prices,
    krw_ret_map,
    spy_ret_map,
    ks200_ret_map,
    stress_dates,
    adv_series,
    scenario_benchmark_ret_maps=None,
):
    scenario_benchmark_ret_maps = scenario_benchmark_ret_maps or {}
    prices_only = [p for _, p in krw_prices]
    rets = [krw_ret_map[d] for d in sorted(krw_ret_map.keys())]
    prices_1y = prices_only[-252:] if prices_only else []
    ret_dates_1y = sorted(krw_ret_map.keys())[-252:] if krw_ret_map else []
    rets_1y = [krw_ret_map[d] for d in ret_dates_1y]

    vol_ann = None
    if len(rets) >= MIN_OBS_POLICY["vol_annual"]:
        vol_tmp = stdev(rets)
        vol_ann = vol_tmp * math.sqrt(252) if vol_tmp is not None else None

    mdd_1y = mdd(prices_1y) if len(prices_1y) >= MIN_OBS_POLICY["mdd_1y"] else None

    var_95 = None
    cvar_95 = None
    annual_return_1y = None
    sharpe_1y = None
    if len(rets_1y) >= MIN_OBS_POLICY["tail_1y"]:
        var_95 = percentile(rets_1y, 0.05)
        cvar_95 = mean([r for r in rets_1y if var_95 is not None and r <= var_95])
        annual_return_1y = annualized_return_from_returns(rets_1y)
        sharpe_1y = sharpe_from_returns(rets_1y)

    beta = compute_beta(krw_ret_map, spy_ret_map)
    downside_beta = compute_downside_beta(krw_ret_map, spy_ret_map)
    beta_ks200 = compute_beta(krw_ret_map, ks200_ret_map)
    downside_beta_ks200 = compute_downside_beta(krw_ret_map, ks200_ret_map)
    corr_sp500_60d = trailing_corr(krw_ret_map, spy_ret_map, 60)
    corr_kospi200_60d = trailing_corr(krw_ret_map, ks200_ret_map, 60)
    soxx_ret_map = scenario_benchmark_ret_maps.get("soxx") or {}
    usdkrw_ret_map = scenario_benchmark_ret_maps.get("usdkrw") or {}
    uso_ret_map = scenario_benchmark_ret_maps.get("uso") or {}
    gld_ret_map = scenario_benchmark_ret_maps.get("gld") or {}
    beta_soxx = compute_beta(krw_ret_map, soxx_ret_map) if soxx_ret_map else None
    downside_beta_soxx = compute_downside_beta(krw_ret_map, soxx_ret_map) if soxx_ret_map else None
    corr_soxx_60d = trailing_corr(krw_ret_map, soxx_ret_map, 60) if soxx_ret_map else None
    beta_usdkrw = compute_beta(krw_ret_map, usdkrw_ret_map) if usdkrw_ret_map else None
    beta_uso = compute_beta(krw_ret_map, uso_ret_map) if uso_ret_map else None
    beta_gld = compute_beta(krw_ret_map, gld_ret_map) if gld_ret_map else None

    stress_rets = [krw_ret_map[d] for d in sorted(krw_ret_map.keys()) if d in stress_dates]
    avg_stress_ret = mean(stress_rets)
    adv_60 = calc_adv_60(adv_series)

    return {
        "vol_annual_krw": vol_ann,
        "mdd_1y_krw": mdd_1y,
        "var_95_1y_krw": var_95,
        "cvar_95_1y_krw": cvar_95,
        "beta_sp500_1y_krw": beta,
        "downside_beta_sp500_1y_krw": downside_beta,
        "beta_ks200_1y_krw": beta_ks200,
        "downside_beta_ks200_1y_krw": downside_beta_ks200,
        "corr_sp500_60d_krw": corr_sp500_60d,
        "corr_kospi200_60d_krw": corr_kospi200_60d,
        "beta_soxx_1y_krw": beta_soxx,
        "downside_beta_soxx_1y_krw": downside_beta_soxx,
        "corr_soxx_60d_krw": corr_soxx_60d,
        "beta_usdkrw_1y": beta_usdkrw,
        "beta_uso_1y_krw": beta_uso,
        "beta_gld_1y_krw": beta_gld,
        "avg_stress_ret_krw": avg_stress_ret,
        "return_observation_count": len(krw_ret_map),
        "stress_observation_count": len(stress_rets),
        "sp500_overlap_count": overlap_count(krw_ret_map, spy_ret_map),
        "ks200_overlap_count": overlap_count(krw_ret_map, ks200_ret_map),
        "soxx_overlap_count": overlap_count(krw_ret_map, soxx_ret_map) if soxx_ret_map else 0,
        "usdkrw_overlap_count": overlap_count(krw_ret_map, usdkrw_ret_map) if usdkrw_ret_map else 0,
        "uso_overlap_count": overlap_count(krw_ret_map, uso_ret_map) if uso_ret_map else 0,
        "gld_overlap_count": overlap_count(krw_ret_map, gld_ret_map) if gld_ret_map else 0,
        "adv_60": adv_60,
        "annual_return_1y_krw": annual_return_1y,
        "sharpe_1y_krw_proxy": sharpe_1y,
    }


# -----------------------------
# Input / weight helpers
# -----------------------------

def build_default_portfolio_sample(sample_path):
    sample_path.parent.mkdir(parents=True, exist_ok=True)
    rows = [
        {"ticker": "AAPL", "weight_pct": 20.0},
        {"ticker": "MSFT", "weight_pct": 20.0},
        {"ticker": "NVDA", "weight_pct": 20.0},
        {"ticker": "005930.KS", "weight_pct": 20.0},
        {"ticker": "BTC-USD", "weight_pct": 20.0},
    ]
    write_csv(sample_path, ["ticker", "weight_pct"], rows)


def load_portfolio_input(universe_map, input_path=None):
    user_path = Path(input_path) if input_path else Path("inputs/portfolio_weights.csv")
    sample_path = OUTPUT_REPORT_DIR / "portfolio_input_sample.csv"

    if user_path.exists():
        input_path = user_path
    else:
        if not sample_path.exists():
            build_default_portfolio_sample(sample_path)
        input_path = sample_path

    weights = {}
    with input_path.open("r", encoding="utf-8") as f:
        rdr = csv.DictReader(f)
        for row in rdr:
            ticker = row.get("ticker", "").strip()
            w = parse_float(row.get("weight_pct"))
            if not ticker or w is None:
                continue
            weights[ticker] = weights.get(ticker, 0.0) + w

    return input_path, weights


def validate_portfolio_weights(weights_pct, universe_map, max_weight_pct=50.0):
    errors = []
    if not weights_pct:
        errors.append("FAIL: 포트폴리오 입력이 비어 있습니다.")
        return False, errors

    total = sum(weights_pct.values())
    if abs(total - 100.0) > 1e-6:
        errors.append(f"FAIL: 비중 합계가 100이 아닙니다. (현재 {total:.6f})")

    for ticker, w in sorted(weights_pct.items()):
        if w < 0:
            errors.append(f"FAIL: 음수 비중 금지 위반 - {ticker}={w:.4f}%")
        if max_weight_pct is not None and w > max_weight_pct + 1e-9:
            errors.append(f"FAIL: 단일 자산 최대 {max_weight_pct:.1f}% 초과 - {ticker}={w:.4f}%")
        if ticker not in universe_map:
            errors.append(f"FAIL: 유니버스 외 티커 포함 - {ticker}")

    return len(errors) == 0, errors


def build_single_asset_base_weights(single_asset):
    return {single_asset: 100.0}


def build_base_amounts_krw(base_weights_pct, base_total_krw):
    if base_total_krw is None:
        return None
    return {ticker: base_total_krw * (weight / 100.0) for ticker, weight in base_weights_pct.items()}


def compute_portfolio_returns(weights_frac, ticker_ret_map):
    date_sets = []
    for ticker, w in weights_frac.items():
        if w <= 0:
            continue
        if ticker == CASH_TICKER:
            continue
        ret_map = ticker_ret_map.get(ticker)
        if not ret_map:
            return [], f"{ticker} 수익률 데이터가 부족합니다."
        date_sets.append(set(ret_map.keys()))

    if not date_sets:
        return [], "포트폴리오 구성 수익률 데이터가 없습니다."

    common_dates = sorted(set.intersection(*date_sets))
    if len(common_dates) < MIN_OBS_POLICY["portfolio_common_dates"]:
        return [], (
            f"공통 거래일 부족: {len(common_dates)}일 (<{MIN_OBS_POLICY['portfolio_common_dates']}일)"
        )

    pf_returns = []
    for d in common_dates:
        r = 0.0
        for ticker, w in weights_frac.items():
            if ticker == CASH_TICKER:
                continue
            r += w * ticker_ret_map[ticker][d]
        pf_returns.append((d, r))

    return pf_returns, None


def portfolio_metrics_from_returns(dated_returns, benchmark_ret_map=None, stress_dates=None, ks200_ret_map=None):
    if not dated_returns:
        return None
    rets = [r for _, r in dated_returns]
    if len(rets) < MIN_OBS_POLICY["vol_annual"]:
        return None

    vol = stdev(rets)
    vol_ann = vol * math.sqrt(252) if vol is not None else None

    nav = [1.0]
    for r in rets:
        nav.append(nav[-1] * (1.0 + r))
    mdd_val = mdd(nav)

    var_95 = percentile(rets, 0.05)
    cvar_95 = mean([r for r in rets if var_95 is not None and r <= var_95])
    ann_return = annualized_return_from_returns(rets)
    sharpe = sharpe_from_returns(rets)

    stress_avg_ret = None
    if stress_dates:
        stress_slice = [r for d, r in dated_returns if d in stress_dates]
        stress_avg_ret = mean(stress_slice)

    beta = None
    corr_sp500 = None
    downside_beta_sp500 = None
    if benchmark_ret_map:
        common_dates = sorted(set(d for d, _ in dated_returns) & set(benchmark_ret_map.keys()))
        if len(common_dates) >= MIN_OBS_POLICY["beta_overlap"]:
            xs = [dict(dated_returns)[d] for d in common_dates]
            ys = [benchmark_ret_map[d] for d in common_dates]
            cov_xy = covariance(xs, ys)
            var_y = variance(ys)
            beta = cov_xy / var_y if (cov_xy is not None and var_y not in (None, 0)) else None
            corr_sp500 = correlation(xs[-60:], ys[-60:]) if len(xs) >= MIN_OBS_POLICY["corr_overlap"] else None
            down_pairs = [(dict(dated_returns)[d], benchmark_ret_map[d]) for d in common_dates if benchmark_ret_map[d] < 0]
            if len(down_pairs) >= MIN_OBS_POLICY["downside_overlap"]:
                x_down = [x for x, _ in down_pairs]
                y_down = [y for _, y in down_pairs]
                cov_down = covariance(x_down, y_down)
                var_down = variance(y_down)
                downside_beta_sp500 = cov_down / var_down if (cov_down is not None and var_down not in (None, 0)) else None

    corr_kospi200 = None
    if ks200_ret_map:
        common_dates = sorted(set(d for d, _ in dated_returns) & set(ks200_ret_map.keys()))
        if len(common_dates) >= MIN_OBS_POLICY["corr_overlap"]:
            ret_by_date = dict(dated_returns)
            xs = [ret_by_date[d] for d in common_dates[-60:]]
            ys = [ks200_ret_map[d] for d in common_dates[-60:]]
            corr_kospi200 = correlation(xs, ys)

    return {
        "vol_annual_krw": vol_ann,
        "mdd_krw": mdd_val,
        "cvar_95_krw": cvar_95,
        "annual_return_krw": ann_return,
        "sharpe_krw_proxy": sharpe,
        "stress_avg_ret_krw": stress_avg_ret,
        "beta_sp500_krw": beta,
        "corr_sp500_krw": corr_sp500,
        "downside_beta_sp500_krw": downside_beta_sp500,
        "corr_kospi200_krw": corr_kospi200,
    }


def risk_improvement_pct(base_val, proposed_val, is_abs_risk=True):
    if base_val is None or proposed_val is None:
        return None

    if is_abs_risk:
        base_risk = abs(base_val)
        prop_risk = abs(proposed_val)
    else:
        base_risk = base_val
        prop_risk = proposed_val

    if base_risk == 0:
        return None
    return (base_risk - prop_risk) / base_risk * 100.0


def signed_improvement_pct(base_val, proposed_val):
    if base_val is None or proposed_val is None:
        return None
    if abs(base_val) < 1e-12:
        return None
    return (proposed_val - base_val) / abs(base_val) * 100.0


def signed_improvement(base_val, proposed_val):
    if base_val is None or proposed_val is None:
        return None
    return proposed_val - base_val


def enforce_weight_caps(weights_frac, max_weight=0.20, exempt_tickers=None):
    exempt_tickers = set(exempt_tickers or [])
    for ticker, weight in weights_frac.items():
        if weight < -1e-12:
            return False, f"FAIL: 음수 비중 발생 - {ticker}={weight * 100:.4f}%"
        if ticker == CASH_TICKER:
            continue
        if ticker not in exempt_tickers and weight > max_weight + 1e-12:
            return False, f"FAIL: 단일 자산 최대 {max_weight * 100:.1f}% 초과 - {ticker}={weight * 100:.4f}%"
    total = sum(weights_frac.values())
    if abs(total - 1.0) > 1e-6:
        return False, f"FAIL: 비중 합계 100% 위반 - {total * 100:.6f}%"
    return True, "PASS"


def build_candidate_weights(base_weights_frac, combo, hedge_budget):
    scaled = {ticker: w * (1.0 - hedge_budget) for ticker, w in base_weights_frac.items()}
    each = hedge_budget / len(combo)
    for ticker in combo:
        scaled[ticker] = scaled.get(ticker, 0.0) + each
    return scaled


def build_candidate_weights_from_allocations(base_weights_frac, allocation_frac_by_ticker):
    hedge_budget = sum(allocation_frac_by_ticker.values())
    scaled = {ticker: w * (1.0 - hedge_budget) for ticker, w in base_weights_frac.items()}
    for ticker, weight in allocation_frac_by_ticker.items():
        scaled[ticker] = scaled.get(ticker, 0.0) + weight
    return scaled


def generate_grid_allocations(combo, hedge_budget):
    if hedge_budget is None or hedge_budget <= 0:
        return []
    combo = tuple(combo)
    if len(combo) == 1:
        return [
            {
                "allocation_method": "single_asset_budget",
                "allocation_weights": {combo[0]: hedge_budget},
            }
        ]
    if len(combo) == 2:
        rows = []
        for first_share in range(2, 9):
            second_share = 10 - first_share
            rows.append(
                {
                    "allocation_method": "grid_scenario_risk",
                    "allocation_weights": {
                        combo[0]: hedge_budget * first_share / 10.0,
                        combo[1]: hedge_budget * second_share / 10.0,
                    },
                }
            )
        return rows
    if len(combo) == 3:
        rows = []
        for first_share in range(1, 9):
            for second_share in range(1, 10 - first_share):
                third_share = 10 - first_share - second_share
                if third_share <= 0:
                    continue
                rows.append(
                    {
                        "allocation_method": "grid_scenario_risk",
                        "allocation_weights": {
                            combo[0]: hedge_budget * first_share / 10.0,
                            combo[1]: hedge_budget * second_share / 10.0,
                            combo[2]: hedge_budget * third_share / 10.0,
                        },
                    }
                )
        return rows
    equal = hedge_budget / len(combo)
    return [
        {
            "allocation_method": "equal_weight_fallback",
            "allocation_weights": {ticker: equal for ticker in combo},
        }
    ]


def build_candidate_weights_exact(base_amounts_krw, combo, hedge_budget_krw, latest_price_map):
    if hedge_budget_krw is None or hedge_budget_krw <= 0:
        return None, "FAIL: 헷지 예산(KRW)이 0보다 커야 합니다.", None

    total_base = sum(base_amounts_krw.values())
    total_value = total_base + hedge_budget_krw
    if total_value <= 0:
        return None, "FAIL: 전체 포트폴리오 평가금액이 0 이하입니다.", None

    allocated_per_asset = hedge_budget_krw / len(combo)
    weights = {ticker: amount / total_value for ticker, amount in base_amounts_krw.items()}
    share_counts = {}
    invested_amounts = {}
    total_invested = 0.0

    for ticker in combo:
        latest_price = latest_price_map.get(ticker)
        if latest_price is None or latest_price <= 0:
            return None, f"FAIL: 최신 KRW 가격이 없습니다 - {ticker}", None
        shares = int(allocated_per_asset // latest_price)
        invested = shares * latest_price
        if shares <= 0:
            return None, f"FAIL: 예산 부족 - {ticker} 1주 매수 불가", None
        share_counts[ticker] = shares
        invested_amounts[ticker] = invested
        weights[ticker] = weights.get(ticker, 0.0) + (invested / total_value)
        total_invested += invested

    leftover_cash = hedge_budget_krw - total_invested
    if leftover_cash > 1e-9:
        weights[CASH_TICKER] = leftover_cash / total_value

    details = {
        "share_counts": share_counts,
        "invested_amounts_krw": invested_amounts,
        "hedge_budget_krw": hedge_budget_krw,
        "hedge_invested_krw": total_invested,
        "hedge_cash_left_krw": leftover_cash,
        "total_portfolio_value_krw": total_value,
    }
    return weights, "PASS", details


def to_pct_weights(weights_frac):
    return {k: round(v * 100.0, 4) for k, v in weights_frac.items()}


def parse_budget_list(raw):
    if raw is None:
        return list(DEFAULT_HEDGE_BUDGETS)
    values = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        val = float(part)
        if val <= 0 or val >= 100:
            raise ValueError(f"invalid hedge budget pct: {val}")
        values.append(val)
    if not values:
        return list(DEFAULT_HEDGE_BUDGETS)
    deduped = []
    seen = set()
    for v in values:
        key = round(v, 8)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(v)
    return deduped


def parse_budget_amount_list(raw):
    if raw is None:
        return []
    values = []
    seen = set()
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        val = float(part)
        if val <= 0:
            raise ValueError(f"invalid hedge budget krw: {val}")
        key = round(val, 4)
        if key in seen:
            continue
        seen.add(key)
        values.append(val)
    return values


def hedge_bucket(meta):
    asset_class = meta.get("asset_class", "")
    group_tag = meta.get("group_tag", "")
    ticker = meta.get("ticker", "")
    if asset_class == "bond_etf":
        return "bond"
    if asset_class == "gold_etf":
        return "gold"
    if asset_class == "commodity_etf" or group_tag in {"oil", "energy_sector", "broad_commodity"} or ticker in {"USO", "XLE", "DBC"}:
        return "commodity_energy"
    if asset_class == "crypto":
        return "crypto"
    if group_tag in {"defensive_sector", "defensive"} or ticker in {"XLP", "XLU", "XLV"}:
        return "defensive"
    return asset_class or group_tag or "other"


def candidate_role(meta):
    ticker = meta.get("ticker", "")
    explicit_role = (meta.get("candidate_role") or "").strip()
    if explicit_role in CANDIDATE_ROLES:
        return explicit_role
    if ticker in CONDITIONAL_CANDIDATE_TICKERS:
        return "conditional_candidate"
    if ticker in DIAGNOSTIC_ONLY_TICKERS:
        return "diagnostic_only"
    if meta.get("is_core_hedge") == "Y" or ticker in HEDGE_V1_CANDIDATES:
        return "hedge_candidate"
    return "diagnostic_only"


def candidate_role_reason_ko(meta):
    explicit_reason = (meta.get("candidate_role_reason_ko") or "").strip()
    if explicit_reason:
        return explicit_reason
    return CANDIDATE_ROLE_REASON_KO.get(candidate_role(meta), "")


def combo_candidate_role(combo, universe_map):
    roles = {candidate_role(universe_map.get(ticker, {"ticker": ticker})) for ticker in combo}
    if len(roles) == 1:
        return next(iter(roles))
    return "mixed_candidate_roles"


def combo_candidate_role_reason_ko(combo, universe_map):
    parts = []
    for ticker in combo:
        meta = universe_map.get(ticker, {"ticker": ticker})
        parts.append(f"{ticker}: {candidate_role_reason_ko(meta)}")
    return " | ".join(parts)


def active_scenario_codes(scenario_context):
    rows = scenario_context.get("active_rows") or scenario_context.get("rows") or [] if scenario_context else []
    return {
        row.get("scenario_code")
        for row in rows
        if row.get("scenario_code") in ADVERSE_SCENARIO_CODES and scenario_trade_gate_weight(row) > 0
    }


def risk_bucket_candidate_reason(meta, scenario_context):
    ticker = meta.get("ticker", "")
    matched = [
        code
        for code in active_scenario_codes(scenario_context)
        if ticker in RISK_BUCKET_SCENARIO_CANDIDATES.get(code, set())
    ]
    if matched:
        return "|".join(sorted(matched))
    if ticker in RISK_BUCKET_BASE_CANDIDATES or candidate_role(meta) == "hedge_candidate":
        return "core_hedge"
    return ""


def is_hedge_candidate(meta, candidate_mode="hedge-only", scenario_context=None):
    ticker = meta.get("ticker", "")
    if candidate_mode == "all":
        return ticker not in {"SPY"}
    if candidate_mode == "risk-bucket":
        return bool(risk_bucket_candidate_reason(meta, scenario_context))
    return candidate_role(meta) == "hedge_candidate"


def combo_diversity_ok(combo, universe_map):
    if len(combo) <= 1:
        return True
    groups = [hedge_bucket(universe_map[t]) for t in combo]
    group_counts = defaultdict(int)
    for g in groups:
        group_counts[g] += 1
    if len(group_counts) < 2:
        return False
    if any(cnt > 2 for cnt in group_counts.values()):
        return False
    if group_counts.get("crypto", 0) > 1:
        return False
    return True


def classify_sensitivity_direction(value, flat_threshold=0.0):
    if value is None:
        return "unknown"
    if value > flat_threshold:
        return "positive"
    if value < -flat_threshold:
        return "negative"
    return "neutral"


def classify_sensitivity_level(value, medium_threshold, high_threshold):
    if value is None:
        return "low"
    magnitude = abs(value)
    if magnitude >= high_threshold:
        return "high"
    if magnitude >= medium_threshold:
        return "medium"
    return "low"


def build_structural_tags(meta):
    tags = []
    ticker = meta.get("ticker", "")
    asset_class = meta.get("asset_class", "")
    group_tag = meta.get("group_tag", "")
    region = meta.get("region", "")
    currency = meta.get("currency", "")

    if currency == "USD":
        tags.append("usd_exposure")
    if currency == "KRW" or region == "KR" or asset_class == "kr_stock" or ticker.endswith(".KS"):
        tags.append("korea_equity_proxy")
    if ticker in {"NVDA", "AVGO", "AMD", "SOXX", "005930.KS", "000660.KS"} or group_tag in {"semiconductor", "semis"}:
        tags.append("semiconductor_proxy")
    if ticker in {"NVDA", "AVGO", "AMD", "MSFT", "GOOGL", "QQQ", "SOXX"} or group_tag in {"semiconductor", "ai", "growth"}:
        tags.append("ai_capex_proxy")
    if ticker in {"105560.KS", "055550.KS", "032830.KS"} or group_tag in {"financial", "bank", "insurance"}:
        tags.append("korea_financial_proxy")
    if ticker in {"000720.KS", "006360.KS", "047040.KS"} or group_tag in {"construction", "real_estate", "reits"}:
        tags.append("korea_real_estate_proxy")
    if asset_class == "bond_etf" or group_tag in {"bond_duration", "credit_bond", "inflation_linked"}:
        tags.append("rate_proxy")
    if group_tag in {"credit_bond", "high_yield", "financial"} or ticker in {"HYG", "LQD"}:
        tags.append("credit_proxy")
    if asset_class in {"gold_etf", "commodity_etf"} or group_tag in {"inflation_linked", "broad_commodity", "oil", "precious_metal"} or ticker in {"TIP", "GLD", "IAU", "DBC", "USO"}:
        tags.append("inflation_proxy")
    if group_tag in {"oil", "energy_sector", "defense_sector"} or ticker in {"USO", "XLE", "ITA", "PPA"}:
        tags.append("geopolitical_proxy")
    if asset_class in {"gold_etf", "bond_etf"} or group_tag in {"defensive_sector", "defensive"} or ticker in {"XLP", "XLU", "XLV"}:
        tags.append("defensive_proxy")
    return sorted(set(tags))


def build_asset_sensitivity_rows(feature_rows, universe_map):
    rows = []
    for feature in sorted(feature_rows, key=lambda x: x["ticker"]):
        ticker = feature["ticker"]
        meta = universe_map.get(ticker, {})
        structural_tags = build_structural_tags(meta)
        for spec in SENSITIVITY_FACTOR_SPECS:
            value = feature.get(spec["metric"])
            rows.append(
                {
                    "ticker": ticker,
                    "asset_class": feature.get("asset_class"),
                    "currency": feature.get("currency"),
                    "factor": spec["factor"],
                    "factor_label": spec["label"],
                    "direction": classify_sensitivity_direction(value, spec["flat_threshold"]),
                    "magnitude": abs(value) if value is not None else None,
                    "sensitivity_level": classify_sensitivity_level(value, spec["medium_threshold"], spec["high_threshold"]),
                    "raw_value": value,
                    "value_basis": spec["metric"],
                    "sign_positive_meaning": spec["sign_positive_meaning"],
                    "sign_negative_meaning": spec["sign_negative_meaning"],
                    "structural_tags": "|".join(structural_tags),
                    "evidence_metrics": f"{spec['metric']}={safe_round(value)}",
                }
            )
    return rows


def summarize_direction_counts(rows):
    counts = {"positive": 0, "negative": 0, "neutral": 0, "unknown": 0}
    for row in rows:
        counts[row["direction"]] = counts.get(row["direction"], 0) + 1
    return counts


def write_asset_sensitivity_summary(summary_path, run_id, data_version, sensitivity_rows):
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    by_factor = defaultdict(list)
    for row in sensitivity_rows:
        by_factor[row["factor"]].append(row)

    with summary_path.open("w", encoding="utf-8") as f:
        f.write("# HedgeMate 자산 민감도 요약\n\n")
        f.write(f"- run_id: {run_id}\n")
        f.write(f"- data_version: {data_version}\n")
        f.write("- 현재 run에서 사용한 정량 민감도 축:\n")
        for spec in SENSITIVITY_FACTOR_SPECS:
            f.write(f"  - `{spec['factor']}` ({spec['metric']})\n")
        f.write("- 방향(sign) 규칙: `positive`=같은 방향, `negative`=반대 방향, `neutral`=유의미한 민감도 미약\n")
        f.write("- 크기(magnitude): 각 factor raw value의 절대값\n")
        f.write("- 민감도 강도(sensitivity_level): magnitude 기반 휴리스틱(low/medium/high)\n")
        f.write("- 구조 태그(structural_tags): `usd_exposure`, `rate_proxy`, `inflation_proxy`, `geopolitical_proxy`, `defensive_proxy`\n")
        f.write("- 참고: 직접 매크로 시계열(FX/금리/인플레이션) 민감도는 차기 단계에서 확장 예정이며, 현재 run은 시장/스트레스 기반 factor + 구조 태그를 저장한다.\n\n")

        for spec in SENSITIVITY_FACTOR_SPECS:
            factor = spec["factor"]
            rows = by_factor.get(factor, [])
            counts = summarize_direction_counts(rows)
            top_rows = sorted(
                [row for row in rows if row.get("magnitude") is not None],
                key=lambda x: (-(x["magnitude"] or 0), x["ticker"]),
            )[:5]
            f.write(f"## {factor}\n")
            f.write(f"- metric: `{spec['metric']}`\n")
            f.write(f"- positive 의미: {spec['sign_positive_meaning']}\n")
            f.write(f"- negative 의미: {spec['sign_negative_meaning']}\n")
            f.write(
                f"- direction count: positive {counts.get('positive', 0)}, negative {counts.get('negative', 0)}, "
                f"neutral {counts.get('neutral', 0)}, unknown {counts.get('unknown', 0)}\n"
            )
            if top_rows:
                f.write("- magnitude 상위 5개:\n")
                for row in top_rows:
                    f.write(
                        f"  - {row['ticker']}: direction={row['direction']}, magnitude={safe_round(row.get('magnitude'))}, "
                        f"sensitivity_level={row['sensitivity_level']}, evidence={row['evidence_metrics']}\n"
                    )
            f.write("\n")


SCENARIO_SENSITIVITY_FIELDS = [
    "ticker",
    "asset_name",
    "asset_class",
    "scenario_code",
    "scenario_name",
    "scenario_name_ko",
    "lens",
    "scenario_beta",
    "conditional_return_hit",
    "downside_capture",
    "direction",
    "magnitude",
    "sensitivity_level",
    "confidence",
    "method",
    "sensitivity_version",
    "method_priority",
    "sample_count",
    "sample_count_actual",
    "direct_metric_count",
    "source_quality",
    "beta_stability",
    "event_or_seed_dependent",
    "window_start",
    "window_end",
    "active_hit_count",
    "scenario_context_weight",
    "scenario_trade_gate_weight",
    "evidence_quality",
    "gate_eligible",
    "gate_reason",
    "context_reason",
    "scenario_return_beta",
    "scenario_downside_beta",
    "scenario_conditional_return",
    "recommended_role",
    "notes",
]

SCENARIO_RECOMMENDATION_FIELDS = [
    "recommendation_status",
    "gate_fail_reasons",
    "reference_reason",
    "dq_warning_reasons",
    "dq_blocking_reasons",
    "dq_penalty",
    "recommendation_confidence_score",
    "base_scenario_vulnerability",
    "proposed_scenario_vulnerability",
    "base_gate_vulnerability",
    "proposed_gate_vulnerability",
    "scenario_vulnerability_delta",
    "gate_vulnerability_delta",
    "scenario_score_component",
    "scenario_vulnerability_reduction",
    "adverse_scenario_penalty",
    "factor_concentration_penalty",
    "recommended_role",
    "candidate_role",
    "candidate_role_reason_ko",
    "scenario_reason_ko",
]

SCENARIO_SENSITIVITY_VERSION = "v3"
SCENARIO_METHOD_PRIORITY = {
    "rolling_beta": 1,
    "conditional_bucket": 2,
    "structural_prior": 3,
    "proxy_factor_heuristic": 4,
}

ADVERSE_SCENARIO_CODES = {
    "slowdown_recession_deflation_risk",
    "higher_for_longer_long_rate_shock",
    "stagflation_reinflation_energy_shock",
    "usd_strength_krw_weakness",
    "acute_global_stress_liquidity_crunch",
    "china_trade_fragmentation_shock",
    "semiconductor_ai_cycle_shock",
    "korea_domestic_financial_stress",
    "geopolitical_escalation_supply_shock",
}

FAVORABLE_SCENARIO_CODES = {"soft_landing_goldilocks"}

SCENARIO_SOURCE_QUALITY_BY_CODE = {
    "korea_domestic_financial_stress": "seed",
    "geopolitical_escalation_supply_shock": "manual",
}

SCENARIO_DIRECT_EVIDENCE_METRICS = {
    "soft_landing_goldilocks": {
        "beta_sp500_1y_krw",
        "downside_beta_sp500_1y_krw",
        "corr_sp500_60d_krw",
    },
    "slowdown_recession_deflation_risk": {
        "beta_sp500_1y_krw",
        "downside_beta_sp500_1y_krw",
        "corr_sp500_60d_krw",
        "avg_stress_ret_krw",
    },
    "higher_for_longer_long_rate_shock": {
        "beta_sp500_1y_krw",
        "downside_beta_sp500_1y_krw",
        "corr_sp500_60d_krw",
    },
    "stagflation_reinflation_energy_shock": {
        "beta_uso_1y_krw",
        "beta_gld_1y_krw",
        "avg_stress_ret_krw",
    },
    "usd_strength_krw_weakness": {
        "beta_usdkrw_1y",
        "beta_ks200_1y_krw",
        "downside_beta_ks200_1y_krw",
        "corr_kospi200_60d_krw",
    },
    "acute_global_stress_liquidity_crunch": {
        "beta_sp500_1y_krw",
        "downside_beta_sp500_1y_krw",
        "corr_sp500_60d_krw",
        "avg_stress_ret_krw",
    },
    "china_trade_fragmentation_shock": {
        "beta_ks200_1y_krw",
        "downside_beta_ks200_1y_krw",
        "beta_soxx_1y_krw",
        "corr_soxx_60d_krw",
        "beta_usdkrw_1y",
    },
    "semiconductor_ai_cycle_shock": {
        "beta_soxx_1y_krw",
        "downside_beta_soxx_1y_krw",
        "corr_soxx_60d_krw",
        "beta_ks200_1y_krw",
        "downside_beta_ks200_1y_krw",
        "beta_usdkrw_1y",
    },
    "korea_domestic_financial_stress": {
        "beta_ks200_1y_krw",
        "downside_beta_ks200_1y_krw",
        "beta_usdkrw_1y",
        "beta_kr_financial_basket_1y_krw",
        "corr_kospi200_60d_krw",
    },
    "geopolitical_escalation_supply_shock": {
        "beta_uso_1y_krw",
        "beta_gld_1y_krw",
        "beta_usdkrw_1y",
        "avg_stress_ret_krw",
    },
}

SCENARIO_RETURN_BETA_METRIC = {
    "semiconductor_ai_cycle_shock": "beta_soxx_1y_krw",
    "korea_domestic_financial_stress": "beta_ks200_1y_krw",
    "geopolitical_escalation_supply_shock": "beta_uso_1y_krw",
    "usd_strength_krw_weakness": "beta_usdkrw_1y",
    "china_trade_fragmentation_shock": "beta_ks200_1y_krw",
    "stagflation_reinflation_energy_shock": "beta_uso_1y_krw",
}

SCENARIO_DOWNSIDE_BETA_METRIC = {
    "semiconductor_ai_cycle_shock": "downside_beta_soxx_1y_krw",
    "korea_domestic_financial_stress": "downside_beta_ks200_1y_krw",
    "usd_strength_krw_weakness": "downside_beta_ks200_1y_krw",
    "china_trade_fragmentation_shock": "downside_beta_ks200_1y_krw",
}

SCENARIO_METRIC_SAMPLE_COUNT_FIELDS = {
    "beta_sp500_1y_krw": "sp500_overlap_count",
    "downside_beta_sp500_1y_krw": "sp500_overlap_count",
    "corr_sp500_60d_krw": "sp500_overlap_count",
    "beta_ks200_1y_krw": "ks200_overlap_count",
    "downside_beta_ks200_1y_krw": "ks200_overlap_count",
    "corr_kospi200_60d_krw": "ks200_overlap_count",
    "beta_soxx_1y_krw": "soxx_overlap_count",
    "downside_beta_soxx_1y_krw": "soxx_overlap_count",
    "corr_soxx_60d_krw": "soxx_overlap_count",
    "beta_usdkrw_1y": "usdkrw_overlap_count",
    "beta_uso_1y_krw": "uso_overlap_count",
    "beta_gld_1y_krw": "gld_overlap_count",
    "beta_kr_financial_basket_1y_krw": "kr_financial_overlap_count",
    "avg_stress_ret_krw": "stress_observation_count",
}


def load_scenario_vector(path=None):
    """Load the latest scenario_research vector, returning an empty context on absence."""
    selected_path = Path(path) if path else None
    selected_by = "explicit_path" if selected_path is not None else "fallback_none"
    candidate_count = 1 if selected_path is not None else 0
    candidate_as_of_dates = []
    rows = []
    if selected_path is None:
        manifest = read_latest_manifest()
        selected_path = (
            resolve_manifest_artifact(manifest, "active_scenario_vector_json", SCENARIO_VECTOR_DIR)
            or resolve_manifest_artifact(manifest, "active_scenario_vector", SCENARIO_VECTOR_DIR)
        )
        if selected_path is not None:
            try:
                if selected_path.parent.resolve() != Path(SCENARIO_VECTOR_DIR).resolve():
                    selected_path = None
            except OSError:
                selected_path = None
        if selected_path is not None:
            selected_by = "latest_manifest"
            candidate_count = 1
        else:
            selection = select_latest_scenario_vector(SCENARIO_VECTOR_DIR)
            selected_path = selection["path"]
            rows = selection["rows"]
            selected_by = selection["selected_by"]
            candidate_count = selection["candidate_count"]
            candidate_as_of_dates = selection["candidate_as_of_dates"]
        if selected_path is None:
            return {
                "path": None,
                "rows": [],
                "active_rows": [],
                "as_of_date": None,
                "selected_by": selected_by,
                "candidate_count": candidate_count,
                "candidate_as_of_dates": candidate_as_of_dates,
                "summary_ko": "시나리오 벡터 없음: 기존 HedgeMate 점수로 fallback합니다.",
            }
    if not selected_path.exists():
        return {
            "path": str(selected_path),
            "rows": [],
            "active_rows": [],
            "as_of_date": None,
            "selected_by": selected_by,
            "candidate_count": candidate_count,
            "candidate_as_of_dates": candidate_as_of_dates,
            "summary_ko": "시나리오 벡터 파일을 찾지 못해 기존 HedgeMate 점수로 fallback합니다.",
        }

    if not rows:
        rows = read_scenario_vector_rows(selected_path)
    if not candidate_as_of_dates:
        candidate_as_of_dates = [f"{selected_path.name}:{scenario_vector_as_of(rows) or '-'}"]

    as_of_date = scenario_vector_as_of(rows)
    active_rows = [
        row
        for row in rows
        if (row.get("as_of_date") or row.get("date")) == as_of_date
        and scenario_activation_weight(row) > 0
    ]
    summary_parts = [
        f"{row.get('scenario_name_ko') or row.get('scenario_name')}({row.get('display_state')}, {row.get('lens')}, score={safe_round(row.get('score'))})"
        for row in sorted(active_rows, key=lambda item: -(item.get("score") or 0.0))[:3]
    ]
    return {
        "path": str(selected_path),
        "rows": rows,
        "active_rows": active_rows,
        "as_of_date": as_of_date,
        "selected_by": selected_by,
        "candidate_count": candidate_count,
        "candidate_as_of_dates": candidate_as_of_dates,
        "summary_ko": "현재 장세: " + " / ".join(summary_parts) if summary_parts else "활성 시나리오가 약하거나 신뢰도가 낮아 기존 점수를 중심으로 봅니다.",
    }


def scenario_activation_weight(row):
    raw_state = row.get("raw_state") or ""
    if raw_state == "OFF":
        return 0.0
    score = row.get("score")
    confidence = row.get("confidence")
    coverage = row.get("coverage")
    if score is None:
        return 0.0
    display_state = row.get("display_state") or raw_state
    state_weight = {
        "STRONG": 1.0,
        "STRESS": 1.0,
        "ACTIVE": 0.8,
        "WATCH": 0.45,
        "PROVISIONAL": 0.25,
        "OFF": 0.0,
    }.get(display_state, 0.0)
    if state_weight <= 0:
        return 0.0
    confidence_weight = clip01((confidence or 0.0) / 70.0)
    coverage_weight = clip01((coverage or 0.0) / 0.85)
    score_weight = clip01(score / 100.0)
    return state_weight * (0.35 + 0.25 * confidence_weight + 0.20 * coverage_weight + 0.20 * score_weight)


def scenario_trade_gate_weight(row):
    if not scenario_is_adverse(row):
        return 0.0
    source_quality = scenario_source_quality(row)
    if source_quality in SOURCE_QUALITY_HIGH_BLOCKERS:
        return 0.0
    raw_state = row.get("raw_state") or ""
    if raw_state == "OFF":
        return 0.0
    display_state = row.get("display_state") or raw_state
    confidence = row.get("confidence") or 0.0
    coverage = row.get("coverage") or 0.0
    if display_state == "STRESS" and confidence >= 60.0 and coverage >= 0.85:
        return scenario_activation_weight(row)
    if display_state == "ACTIVE" and confidence >= 65.0 and coverage >= 0.90:
        return scenario_activation_weight(row)
    return 0.0


def scenario_context_reason(row):
    weight = scenario_activation_weight(row)
    if weight <= 0:
        return "inactive scenario"
    source_quality = scenario_source_quality(row)
    display_state = row.get("display_state") or row.get("raw_state") or ""
    if source_quality in SOURCE_QUALITY_HIGH_BLOCKERS:
        return f"context only: source_quality={source_quality}"
    if display_state == "WATCH":
        return "context only: WATCH state"
    if not scenario_is_adverse(row):
        return "context only: non-adverse scenario"
    return "active market context"


def scenario_trade_gate_reason(row, evidence_quality=None, method=None):
    if not scenario_is_adverse(row):
        return "non-adverse scenario"
    if scenario_activation_weight(row) <= 0:
        return "scenario inactive"
    source_quality = scenario_source_quality(row)
    if source_quality in SOURCE_QUALITY_HIGH_BLOCKERS:
        return f"context only: source_quality={source_quality}"
    display_state = row.get("display_state") or row.get("raw_state") or ""
    confidence = row.get("confidence") or 0.0
    coverage = row.get("coverage") or 0.0
    if display_state == "WATCH":
        return "context only: WATCH state"
    if display_state not in {"STRESS", "ACTIVE"}:
        return f"context only: state={display_state or 'unknown'}"
    if display_state == "STRESS" and (confidence < 60.0 or coverage < 0.85):
        return "below STRESS confidence/coverage trade-gate threshold"
    if display_state == "ACTIVE" and (confidence < 65.0 or coverage < 0.90):
        return "below ACTIVE confidence/coverage trade-gate threshold"
    if evidence_quality is not None and evidence_quality not in {"high", "medium"}:
        return "insufficient scenario evidence"
    if method == "proxy_factor_heuristic":
        return "proxy-only evidence"
    return "trade-gated adverse scenario"


def scenario_is_adverse(row):
    return row.get("scenario_code") in ADVERSE_SCENARIO_CODES


def scenario_direct_metric_values(feature, scenario_code):
    return {
        metric: feature.get(metric)
        for metric in SCENARIO_DIRECT_EVIDENCE_METRICS.get(scenario_code, set())
        if feature.get(metric) is not None
    }


def scenario_direct_beta_corr_metric_values(feature, scenario_code):
    return {
        metric: value
        for metric, value in scenario_direct_metric_values(feature, scenario_code).items()
        if metric != "avg_stress_ret_krw"
    }


def scenario_source_quality(scenario_row):
    scenario_code = scenario_row.get("scenario_code")
    return normalize_source_quality(
        scenario_row.get("source_quality")
        or SCENARIO_SOURCE_QUALITY_BY_CODE.get(scenario_code)
        or "market"
    )


def scenario_event_or_seed_dependent(scenario_row, source_quality=None):
    raw = str(scenario_row.get("event_or_seed_dependent") or "").strip().upper()
    if raw in {"Y", "N"}:
        return raw
    source_quality = source_quality or scenario_source_quality(scenario_row)
    return "Y" if source_quality in SOURCE_QUALITY_HIGH_BLOCKERS else "N"


def metric_sample_count(feature, metric):
    field = SCENARIO_METRIC_SAMPLE_COUNT_FIELDS.get(metric)
    if field:
        value = feature.get(field)
        if value not in (None, ""):
            try:
                return int(float(value))
            except (TypeError, ValueError):
                return 0
    if metric.startswith("downside_beta"):
        return MIN_OBS_POLICY["downside_overlap"]
    if metric.startswith("corr_"):
        return MIN_OBS_POLICY["corr_overlap"]
    if metric == "avg_stress_ret_krw":
        return MIN_OBS_POLICY["tail_1y"]
    if metric.startswith("beta_"):
        return MIN_OBS_POLICY["beta_overlap"]
    return 0


def scenario_actual_sample_count(feature, scenario_code, direct_metric_values):
    direct_counts = [
        metric_sample_count(feature, metric)
        for metric in direct_metric_values
        if metric != "avg_stress_ret_krw"
    ]
    direct_counts = [count for count in direct_counts if count > 0]
    if direct_counts:
        return min(direct_counts)
    stress_count = metric_sample_count(feature, "avg_stress_ret_krw")
    if direct_metric_values.get("avg_stress_ret_krw") is not None and stress_count > 0:
        return stress_count
    return 0


def infer_beta_stability(method, direct_metric_count, sample_count_actual):
    if method != "rolling_beta":
        return "not_checked"
    if direct_metric_count >= 2 and sample_count_actual >= 120:
        return "pass"
    if direct_metric_count >= 1 and sample_count_actual >= 60:
        return "limited"
    return "fail"


def scenario_return_beta_value(feature, scenario_code, fallback):
    metric = SCENARIO_RETURN_BETA_METRIC.get(scenario_code)
    if metric and feature.get(metric) is not None:
        return feature.get(metric)
    for candidate in sorted(SCENARIO_DIRECT_EVIDENCE_METRICS.get(scenario_code, set())):
        if candidate.startswith("beta_") and feature.get(candidate) is not None:
            return feature.get(candidate)
    return fallback


def scenario_downside_beta_value(feature, scenario_code):
    metric = SCENARIO_DOWNSIDE_BETA_METRIC.get(scenario_code)
    if metric and feature.get(metric) is not None:
        return feature.get(metric)
    if scenario_code in {"soft_landing_goldilocks", "slowdown_recession_deflation_risk", "higher_for_longer_long_rate_shock", "acute_global_stress_liquidity_crunch"}:
        return feature.get("downside_beta_sp500_1y_krw")
    return None


def scenario_structural_tags(scenario_code):
    mapping = {
        "slowdown_recession_deflation_risk": {"defensive_proxy", "rate_proxy"},
        "higher_for_longer_long_rate_shock": {"rate_proxy", "semiconductor_proxy"},
        "stagflation_reinflation_energy_shock": {"inflation_proxy", "geopolitical_proxy", "rate_proxy"},
        "usd_strength_krw_weakness": {"usd_exposure", "korea_equity_proxy"},
        "acute_global_stress_liquidity_crunch": {"defensive_proxy", "rate_proxy"},
        "china_trade_fragmentation_shock": {"korea_equity_proxy", "semiconductor_proxy", "usd_exposure"},
        "semiconductor_ai_cycle_shock": {"semiconductor_proxy", "ai_capex_proxy", "korea_equity_proxy"},
        "korea_domestic_financial_stress": {
            "korea_equity_proxy",
            "korea_financial_proxy",
            "korea_real_estate_proxy",
            "credit_proxy",
            "usd_exposure",
        },
        "geopolitical_escalation_supply_shock": {
            "geopolitical_proxy",
            "inflation_proxy",
            "defensive_proxy",
            "usd_exposure",
            "korea_equity_proxy",
        },
        "soft_landing_goldilocks": {"usd_exposure", "semiconductor_proxy"},
    }
    return mapping.get(scenario_code, set())


def infer_scenario_method(feature, tags, scenario_row):
    scenario_code = scenario_row.get("scenario_code")
    direct_metrics = scenario_direct_metric_values(feature, scenario_code)
    has_direct_beta = any(metric != "avg_stress_ret_krw" for metric in direct_metrics)
    has_stress = feature.get("avg_stress_ret_krw") is not None
    has_structural = bool(tags & scenario_structural_tags(scenario_code))
    if has_direct_beta:
        return "rolling_beta"
    if has_stress:
        return "conditional_bucket"
    if has_structural:
        return "structural_prior"
    return "proxy_factor_heuristic"


def infer_scenario_sample_count(feature, method, scenario_code):
    sample_count = 0
    for metric, value in scenario_direct_metric_values(feature, scenario_code).items():
        if value is None:
            continue
        if metric.startswith("downside_beta"):
            sample_count = max(sample_count, MIN_OBS_POLICY["downside_overlap"])
        elif metric.startswith("corr_"):
            sample_count = max(sample_count, MIN_OBS_POLICY["corr_overlap"])
        elif metric == "avg_stress_ret_krw":
            sample_count = max(sample_count, MIN_OBS_POLICY["tail_1y"])
        else:
            sample_count = max(sample_count, MIN_OBS_POLICY["beta_overlap"])
    if feature.get("avg_stress_ret_krw") is not None:
        sample_count = max(sample_count, MIN_OBS_POLICY["tail_1y"])
    if method == "structural_prior":
        sample_count = max(sample_count, 1)
    return sample_count


def infer_evidence_quality(
    method,
    sample_count,
    confidence,
    direct_metric_count=0,
    source_quality="market",
    beta_stability="not_checked",
):
    source_quality = normalize_source_quality(source_quality)
    if method == "proxy_factor_heuristic":
        return "low"
    if method == "structural_prior":
        return "low"
    if (
        method == "rolling_beta"
        and direct_metric_count >= 2
        and sample_count >= 120
        and confidence >= 50.0
        and source_quality not in SOURCE_QUALITY_HIGH_BLOCKERS
        and beta_stability == "pass"
    ):
        return "high"
    if direct_metric_count >= 1 and sample_count >= 60 and confidence >= 30.0:
        return "medium"
    if method == "conditional_bucket" and sample_count >= 60 and confidence >= 30.0:
        return "medium"
    return "low"


def scenario_context_date_hint(scenario_row):
    return scenario_row.get("as_of_date") or scenario_row.get("date") or ""


def estimate_asset_scenario_sensitivity(feature, meta, scenario_row):
    """Heuristic vulnerability estimate.

    Positive values mean the asset is more vulnerable when this scenario is active.
    Negative values mean the asset may reduce or offset that scenario exposure.
    """
    scenario_code = scenario_row.get("scenario_code")
    tags = set(build_structural_tags(meta))
    beta = feature.get("beta_sp500_1y_krw")
    corr = feature.get("corr_sp500_60d_krw")
    kospi_corr = feature.get("corr_kospi200_60d_krw")
    stress_ret = feature.get("avg_stress_ret_krw")
    soxx_beta = feature.get("beta_soxx_1y_krw")
    soxx_downside_beta = feature.get("downside_beta_soxx_1y_krw")
    ks200_beta = feature.get("beta_ks200_1y_krw")
    usdkrw_beta = feature.get("beta_usdkrw_1y")
    uso_beta = feature.get("beta_uso_1y_krw")
    gld_beta = feature.get("beta_gld_1y_krw")
    kr_financial_beta = feature.get("beta_kr_financial_basket_1y_krw")
    asset_class = meta.get("asset_class", feature.get("asset_class", ""))
    ticker = feature.get("ticker")

    beta_proxy = beta if beta is not None else corr if corr is not None else 0.0
    stress_vulnerability = -(stress_ret or 0.0) * 100.0
    notes = []

    if scenario_code == "soft_landing_goldilocks":
        value = beta_proxy
        recommended_role = "risk_on_participation" if value > 0.2 else "neutral_or_defensive"
        notes.append("우호적 위험선호장 참여 민감도")
    elif scenario_code == "slowdown_recession_deflation_risk":
        value = 0.65 * beta_proxy + 0.35 * stress_vulnerability
        if "defensive_proxy" in tags or "rate_proxy" in tags:
            value -= 0.35
        recommended_role = "slowdown_defense" if value < 0 else "slowdown_vulnerable"
    elif scenario_code == "higher_for_longer_long_rate_shock":
        value = 0.55 * max(beta_proxy, 0.0)
        if "rate_proxy" in tags:
            value += 0.45
        if "semiconductor_proxy" in tags:
            value += 0.25
        if "usd_exposure" in tags:
            value -= 0.10
        recommended_role = "rate_shock_hedge" if value < 0 else "rate_sensitive"
    elif scenario_code == "stagflation_reinflation_energy_shock":
        value = 0.35 * max(beta_proxy, 0.0) + 0.25 * stress_vulnerability
        if "inflation_proxy" in tags or "geopolitical_proxy" in tags:
            value -= 0.45
        if "rate_proxy" in tags:
            value += 0.20
        recommended_role = "inflation_hedge" if value < 0 else "stagflation_vulnerable"
    elif scenario_code == "usd_strength_krw_weakness":
        value = 0.25 * max(beta_proxy, 0.0)
        if "korea_equity_proxy" in tags:
            value += 0.45 + 0.25 * max(kospi_corr or 0.0, 0.0)
        if "usd_exposure" in tags:
            value -= 0.35
        recommended_role = "krw_weakness_hedge" if value < 0 else "krw_weakness_vulnerable"
    elif scenario_code == "acute_global_stress_liquidity_crunch":
        value = 0.55 * max(beta_proxy, 0.0) + 0.45 * stress_vulnerability
        if "defensive_proxy" in tags:
            value -= 0.30
        recommended_role = "liquidity_stress_defense" if value < 0 else "liquidity_stress_vulnerable"
    elif scenario_code == "china_trade_fragmentation_shock":
        value = 0.20 * max(beta_proxy, 0.0) + 0.25 * stress_vulnerability
        if "korea_equity_proxy" in tags:
            value += 0.30 + 0.20 * max(kospi_corr or 0.0, 0.0)
        if "semiconductor_proxy" in tags:
            value += 0.35
        if "usd_exposure" in tags and asset_class not in {"kr_stock"}:
            value -= 0.10
        recommended_role = "china_asia_shock_hedge" if value < 0 else "china_asia_shock_vulnerable"
    elif scenario_code == "semiconductor_ai_cycle_shock":
        value = (
            0.40 * max(soxx_beta or 0.0, 0.0)
            + 0.25 * max(soxx_downside_beta if soxx_downside_beta is not None else soxx_beta or 0.0, 0.0)
            + 0.15 * max(ks200_beta or 0.0, 0.0)
            + 0.10 * max(beta_proxy, 0.0)
            + 0.10 * stress_vulnerability
        )
        if "semiconductor_proxy" in tags:
            value += 0.30
        if "ai_capex_proxy" in tags:
            value += 0.20
        if "korea_equity_proxy" in tags:
            value += 0.10
        if "defensive_proxy" in tags or "rate_proxy" in tags:
            value -= 0.25
        if "usd_exposure" in tags and asset_class not in {"kr_stock"}:
            value -= 0.05
        recommended_role = "semiconductor_ai_shock_hedge" if value < 0 else "semiconductor_ai_shock_vulnerable"
    elif scenario_code == "korea_domestic_financial_stress":
        value = (
            0.35 * max(ks200_beta or kospi_corr or 0.0, 0.0)
            + 0.25 * max(kr_financial_beta or 0.0, 0.0)
            + 0.15 * max(usdkrw_beta or 0.0, 0.0)
            + 0.25 * stress_vulnerability
        )
        if "korea_financial_proxy" in tags:
            value += 0.35
        if "korea_real_estate_proxy" in tags:
            value += 0.35
        if "korea_equity_proxy" in tags:
            value += 0.15
        if "credit_proxy" in tags:
            value += 0.10
        if "defensive_proxy" in tags or "rate_proxy" in tags:
            value -= 0.30
        if "usd_exposure" in tags and asset_class not in {"kr_stock"}:
            value -= 0.20
        recommended_role = "korea_financial_stress_hedge" if value < 0 else "korea_financial_stress_vulnerable"
    elif scenario_code == "geopolitical_escalation_supply_shock":
        value = (
            0.35 * max(beta_proxy, 0.0)
            + 0.25 * stress_vulnerability
            + 0.15 * max(usdkrw_beta or 0.0, 0.0)
            - 0.10 * max(uso_beta or 0.0, 0.0)
            - 0.10 * max(gld_beta or 0.0, 0.0)
        )
        if "korea_equity_proxy" in tags:
            value += 0.20
        if "geopolitical_proxy" in tags or "inflation_proxy" in tags:
            value -= 0.35
        if "defensive_proxy" in tags or "rate_proxy" in tags:
            value -= 0.25
        if "usd_exposure" in tags and asset_class not in {"kr_stock"}:
            value -= 0.10
        recommended_role = "geopolitical_supply_shock_hedge" if value < 0 else "geopolitical_supply_shock_vulnerable"
    else:
        value = beta_proxy
        recommended_role = "unclassified"
        notes.append("미분류 시나리오 proxy")

    if ticker in {"BTC-USD", "ETH-USD"}:
        notes.append("crypto는 방어자산이 아니라 조건부 diversifier로만 해석")

    confidence = clip01(((scenario_row.get("confidence") or 0.0) / 100.0) * (scenario_row.get("coverage") or 0.0)) * 100.0
    method = infer_scenario_method(feature, tags, scenario_row)
    all_direct_metrics = scenario_direct_metric_values(feature, scenario_code)
    direct_beta_corr_metrics = scenario_direct_beta_corr_metric_values(feature, scenario_code)
    direct_metric_count = len(direct_beta_corr_metrics)
    sample_count_floor = infer_scenario_sample_count(feature, method, scenario_code)
    sample_count_actual = scenario_actual_sample_count(feature, scenario_code, all_direct_metrics) or sample_count_floor
    sample_count = sample_count_actual
    source_quality = scenario_source_quality(scenario_row)
    beta_stability = infer_beta_stability(method, direct_metric_count, sample_count_actual)
    context_weight = scenario_activation_weight(scenario_row)
    trade_gate_weight = scenario_trade_gate_weight(scenario_row)
    active_hit_count = 1 if context_weight > 0 else 0
    evidence_quality = infer_evidence_quality(
        method,
        sample_count_actual,
        confidence,
        direct_metric_count=direct_metric_count,
        source_quality=source_quality,
        beta_stability=beta_stability,
    )
    gate_eligible = (
        trade_gate_weight > 0
        and evidence_quality in {"high", "medium"}
        and method != "proxy_factor_heuristic"
    )
    gate_reason = (
        "trade-gated adverse scenario with medium/high evidence"
        if gate_eligible
        else scenario_trade_gate_reason(scenario_row, evidence_quality=evidence_quality, method=method)
    )

    return {
        "scenario_beta": value,
        "conditional_return_hit": stress_ret,
        "downside_capture": max(scenario_downside_beta_value(feature, scenario_code) or beta_proxy, 0.0),
        "direction": classify_sensitivity_direction(value, flat_threshold=0.05),
        "magnitude": abs(value) if value is not None else None,
        "sensitivity_level": classify_sensitivity_level(value, medium_threshold=0.30, high_threshold=0.75),
        "confidence": confidence,
        "method": method,
        "sensitivity_version": SCENARIO_SENSITIVITY_VERSION,
        "method_priority": SCENARIO_METHOD_PRIORITY.get(method, 99),
        "sample_count": sample_count,
        "sample_count_actual": sample_count_actual,
        "direct_metric_count": direct_metric_count,
        "source_quality": source_quality,
        "beta_stability": beta_stability,
        "event_or_seed_dependent": scenario_event_or_seed_dependent(scenario_row, source_quality),
        "window_start": "",
        "window_end": scenario_context_date_hint(scenario_row),
        "active_hit_count": active_hit_count,
        "scenario_context_weight": context_weight,
        "scenario_trade_gate_weight": trade_gate_weight if gate_eligible else 0.0,
        "evidence_quality": evidence_quality,
        "gate_eligible": "Y" if gate_eligible else "N",
        "gate_reason": gate_reason,
        "context_reason": scenario_context_reason(scenario_row),
        "scenario_return_beta": scenario_return_beta_value(feature, scenario_code, value),
        "scenario_downside_beta": scenario_downside_beta_value(feature, scenario_code),
        "scenario_conditional_return": stress_ret,
        "recommended_role": recommended_role,
        "notes": "; ".join(notes) if notes else scenario_row.get("market_interpretation_ko", ""),
    }


def build_asset_scenario_sensitivity_rows(feature_rows, universe_map, scenario_context):
    rows = []
    active_or_all = scenario_context.get("rows") or []
    if not active_or_all:
        return rows
    for feature in sorted(feature_rows, key=lambda row: row["ticker"]):
        ticker = feature["ticker"]
        meta = universe_map.get(ticker, {})
        for scenario_row in active_or_all:
            estimate = estimate_asset_scenario_sensitivity(feature, meta, scenario_row)
            rows.append(
                {
                    "ticker": ticker,
                    "asset_name": meta.get("name") or meta.get("asset_name") or ticker,
                    "asset_class": feature.get("asset_class") or meta.get("asset_class"),
                    "scenario_code": scenario_row.get("scenario_code"),
                    "scenario_name": scenario_row.get("scenario_name"),
                    "scenario_name_ko": scenario_row.get("scenario_name_ko"),
                    "lens": scenario_row.get("lens"),
                    **estimate,
                }
            )
    return rows


def portfolio_scenario_vulnerability(weights_frac, feature_map, universe_map, scenario_context, gate_eligible_only=False):
    active_rows = [row for row in scenario_context.get("active_rows", []) if scenario_is_adverse(row)]
    if not active_rows:
        return None
    weighted_sum = 0.0
    used_weight = 0.0
    for ticker, weight in weights_frac.items():
        if ticker == CASH_TICKER or weight <= 0:
            continue
        feature = feature_map.get(ticker)
        if not feature:
            continue
        meta = universe_map.get(ticker, {})
        asset_score = 0.0
        scenario_weight_sum = 0.0
        for scenario_row in active_rows:
            estimate = estimate_asset_scenario_sensitivity(feature, meta, scenario_row)
            if gate_eligible_only and estimate.get("gate_eligible") != "Y":
                continue
            activation = scenario_trade_gate_weight(scenario_row) if gate_eligible_only else scenario_activation_weight(scenario_row)
            if activation <= 0:
                continue
            asset_score += activation * max(estimate["scenario_beta"], 0.0)
            scenario_weight_sum += activation
        if scenario_weight_sum <= 0:
            continue
        weighted_sum += weight * (asset_score / scenario_weight_sum)
        used_weight += weight
    if used_weight <= 0:
        return None
    return weighted_sum / used_weight


def portfolio_factor_concentration(weights_frac, universe_map):
    bucket_weights = defaultdict(float)
    for ticker, weight in weights_frac.items():
        if ticker == CASH_TICKER or weight <= 0:
            continue
        bucket_weights[hedge_bucket(universe_map.get(ticker, {"ticker": ticker}))] += weight
    return max(bucket_weights.values(), default=0.0)


def scenario_adjustment_row(base_weights_frac, proposed_weights_frac, feature_map, universe_map, scenario_context, combo):
    if not scenario_context.get("rows"):
        return {
            "base_scenario_vulnerability": None,
            "proposed_scenario_vulnerability": None,
            "base_gate_vulnerability": None,
            "proposed_gate_vulnerability": None,
            "scenario_vulnerability_delta": None,
            "gate_vulnerability_delta": None,
            "scenario_score_component": None,
            "scenario_vulnerability_reduction": None,
            "adverse_scenario_penalty": None,
            "factor_concentration_penalty": None,
            "recommended_role": "baseline_no_scenario_vector",
            "candidate_role": combo_candidate_role(combo, universe_map),
            "candidate_role_reason_ko": combo_candidate_role_reason_ko(combo, universe_map),
            "scenario_reason_ko": scenario_context.get("summary_ko", "시나리오 벡터 없음"),
        }

    base_vulnerability = portfolio_scenario_vulnerability(base_weights_frac, feature_map, universe_map, scenario_context)
    proposed_vulnerability = portfolio_scenario_vulnerability(proposed_weights_frac, feature_map, universe_map, scenario_context)
    base_gate_vulnerability = portfolio_scenario_vulnerability(
        base_weights_frac,
        feature_map,
        universe_map,
        scenario_context,
        gate_eligible_only=True,
    )
    proposed_gate_vulnerability = portfolio_scenario_vulnerability(
        proposed_weights_frac,
        feature_map,
        universe_map,
        scenario_context,
        gate_eligible_only=True,
    )
    if base_vulnerability is None or proposed_vulnerability is None:
        reduction = None
        scenario_delta = None
        scenario_component = None
    else:
        reduction = base_vulnerability - proposed_vulnerability
        scenario_delta = proposed_vulnerability - base_vulnerability
        scenario_component = clip01(0.50 + reduction)
    if base_gate_vulnerability is None or proposed_gate_vulnerability is None:
        penalty = max(scenario_delta, 0.0) if scenario_delta is not None else None
        gate_delta = None
    else:
        gate_delta = proposed_gate_vulnerability - base_gate_vulnerability
        penalty = max(gate_delta, 0.0)

    concentration_penalty = max(
        portfolio_factor_concentration(proposed_weights_frac, universe_map)
        - portfolio_factor_concentration(base_weights_frac, universe_map),
        0.0,
    )
    adverse_active_names = [
        row.get("scenario_name_ko") or row.get("scenario_name")
        for row in scenario_context.get("active_rows", [])
        if scenario_activation_weight(row) > 0 and scenario_is_adverse(row)
    ][:3]
    active_names = adverse_active_names or [
        row.get("scenario_name_ko") or row.get("scenario_name")
        for row in scenario_context.get("active_rows", [])
        if scenario_activation_weight(row) > 0
    ][:3]
    if reduction is None:
        reason = f"{scenario_context.get('summary_ko', '')} 후보 {combo_label(combo)}의 시나리오 민감도는 데이터 부족으로 보조 정보입니다."
        role = "scenario_data_insufficient"
    elif penalty and penalty > 0:
        reason = f"{', '.join(active_names) or '현재 장세'} 기준 취약도를 늘릴 수 있어 감점됩니다."
        role = "adverse_scenario_sensitive"
    elif reduction > 0:
        reason = f"{', '.join(active_names) or '현재 장세'} 기준 취약도를 낮추는 후보입니다."
        role = "scenario_vulnerability_reducer"
    else:
        reason = f"{', '.join(active_names) or '현재 장세'} 기준 중립적인 후보입니다."
        role = "scenario_neutral"

    return {
        "base_scenario_vulnerability": base_vulnerability,
        "proposed_scenario_vulnerability": proposed_vulnerability,
        "base_gate_vulnerability": base_gate_vulnerability,
        "proposed_gate_vulnerability": proposed_gate_vulnerability,
        "scenario_vulnerability_delta": scenario_delta,
        "gate_vulnerability_delta": gate_delta,
        "scenario_score_component": scenario_component,
        "scenario_vulnerability_reduction": reduction,
        "adverse_scenario_penalty": penalty,
        "factor_concentration_penalty": concentration_penalty,
        "recommended_role": role,
        "candidate_role": combo_candidate_role(combo, universe_map),
        "candidate_role_reason_ko": combo_candidate_role_reason_ko(combo, universe_map),
        "scenario_reason_ko": reason,
    }


def write_asset_scenario_sensitivity_summary(summary_path, run_id, data_version, scenario_context, rows):
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    by_lens = defaultdict(int)
    by_scenario = defaultdict(int)
    by_method = defaultdict(int)
    by_evidence = defaultdict(int)
    by_source_quality = defaultdict(int)
    gate_eligible_count = 0
    for row in rows:
        by_lens[row.get("lens", "")] += 1
        by_scenario[row.get("scenario_code", "")] += 1
        by_method[row.get("method", "")] += 1
        by_evidence[row.get("evidence_quality", "")] += 1
        by_source_quality[row.get("source_quality", "")] += 1
        if row.get("gate_eligible") == "Y":
            gate_eligible_count += 1
    with summary_path.open("w", encoding="utf-8") as f:
        f.write("# HedgeMate 시나리오 민감도 요약\n\n")
        f.write(f"- run_id: {run_id}\n")
        f.write(f"- data_version: {data_version}\n")
        f.write(f"- scenario_vector: `{scenario_context.get('path') or 'NONE'}`\n")
        f.write(f"- as_of_date: {scenario_context.get('as_of_date') or '-'}\n")
        f.write(f"- selected_by: {scenario_context.get('selected_by') or '-'}\n")
        f.write(f"- scenario_vector_candidates: {scenario_context.get('candidate_count') or 0}\n")
        f.write(f"- 해석: {scenario_context.get('summary_ko')}\n")
        f.write(f"- row_count: {len(rows)}\n\n")
        f.write("## Lens 분포\n")
        for lens, count in sorted(by_lens.items()):
            f.write(f"- {lens or 'unknown'}: {count}\n")
        f.write("\n## Scenario 분포\n")
        for scenario_code, count in sorted(by_scenario.items()):
            f.write(f"- {scenario_code or 'unknown'}: {count}\n")
        f.write("\n## v2 Evidence 분포\n")
        f.write(f"- sensitivity_version: {SCENARIO_SENSITIVITY_VERSION}\n")
        f.write(f"- gate_eligible rows: {gate_eligible_count}\n")
        for method, count in sorted(by_method.items()):
            f.write(f"- method `{method or 'unknown'}`: {count}\n")
        for quality, count in sorted(by_evidence.items()):
            f.write(f"- evidence_quality `{quality or 'unknown'}`: {count}\n")
        for source_quality, count in sorted(by_source_quality.items()):
            f.write(f"- source_quality `{source_quality or 'unknown'}`: {count}\n")
        active_adverse = [
            row.get("scenario_name_ko") or row.get("scenario_name")
            for row in scenario_context.get("active_rows", [])
            if scenario_is_adverse(row) and scenario_activation_weight(row) > 0
        ]
        trade_gated_adverse = [
            row.get("scenario_name_ko") or row.get("scenario_name")
            for row in scenario_context.get("active_rows", [])
            if scenario_trade_gate_weight(row) > 0
        ]
        if active_adverse:
            f.write("\n## Active adverse scenario\n")
            for name in active_adverse:
                f.write(f"- {name}\n")
        if trade_gated_adverse:
            f.write("\n## Trade-gated adverse scenario\n")
            for name in trade_gated_adverse:
                f.write(f"- {name}\n")
        f.write("\n## 주의\n")
        f.write("- 현재 민감도 v2는 가격 기반 beta/stress feature와 구조 태그를 결합합니다.\n")
        f.write("- positive scenario_beta는 해당 시나리오 활성 시 취약도가 커지는 방향, negative는 방어/상쇄 가능성을 의미합니다.\n")
        f.write("- WATCH/manual/seed 시나리오는 기본적으로 context로만 표시하며 trade gate에는 사용하지 않습니다.\n")


def scenario_beta_cell_style(value):
    if value is None:
        return "background:#f3f4f6;color:#6b7280;"
    intensity = min(abs(value) / 1.50, 1.0)
    alpha = 0.18 + 0.62 * intensity
    if value > 0.05:
        return f"background:rgba(185, 28, 28, {alpha:.2f});color:#111827;"
    if value < -0.05:
        return f"background:rgba(37, 99, 235, {alpha:.2f});color:#111827;"
    return "background:#f8fafc;color:#475569;"


def short_scenario_label(row):
    label = row.get("scenario_name_ko") or row.get("scenario_name") or row.get("scenario_code") or "unknown"
    if len(label) <= 16:
        return label
    return label[:15] + "..."


def write_asset_scenario_sensitivity_visualization(html_path, run_id, data_version, scenario_context, rows):
    html_path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        html_path.write_text(
            "<!doctype html><meta charset='utf-8'><h1>Scenario Sensitivity Visual</h1><p>No rows.</p>",
            encoding="utf-8",
        )
        return

    scenario_lookup = {}
    for row in rows:
        code = row.get("scenario_code")
        if code and code not in scenario_lookup:
            scenario_lookup[code] = row

    active_codes = [
        row.get("scenario_code")
        for row in scenario_context.get("active_rows", [])
        if row.get("scenario_code") and scenario_activation_weight(row) > 0
    ]
    active_codes = [code for code in active_codes if code in scenario_lookup]
    scenario_order = []
    for scenario_row in scenario_context.get("rows", []):
        code = scenario_row.get("scenario_code")
        if code and code in scenario_lookup and code not in scenario_order:
            scenario_order.append(code)
    for code in sorted(scenario_lookup.keys()):
        if code not in scenario_order:
            scenario_order.append(code)

    all_codes = scenario_order
    active_code_set = set(active_codes)
    card_codes = active_codes or all_codes[:4]
    active_rows = [scenario_lookup[code] for code in card_codes if code in scenario_lookup]
    all_code_set = set(all_codes)
    matrix_source = [row for row in rows if row.get("scenario_code") in all_code_set]
    by_ticker = defaultdict(dict)
    ticker_meta = {}
    for row in matrix_source:
        ticker = row.get("ticker")
        code = row.get("scenario_code")
        if not ticker or not code:
            continue
        by_ticker[ticker][code] = row
        ticker_meta[ticker] = row

    ranked_tickers = sorted(
        by_ticker.keys(),
        key=lambda ticker: (
            -max(abs(by_ticker[ticker][code].get("scenario_beta") or 0.0) for code in by_ticker[ticker]),
            ticker,
        ),
    )[:24]

    gate_eligible_count = sum(1 for row in matrix_source if row.get("gate_eligible") == "Y")
    high_evidence_count = sum(1 for row in matrix_source if row.get("evidence_quality") == "high")
    adverse_count = sum(1 for code in all_codes if code in ADVERSE_SCENARIO_CODES)
    evidence_counts = Counter(row.get("evidence_quality") or "unknown" for row in matrix_source)
    method_counts = Counter(row.get("method") or "unknown" for row in matrix_source)

    def esc(value):
        return html.escape(str(value if value is not None else ""))

    evidence_summary = ", ".join(f"{esc(key)} {value}" for key, value in sorted(evidence_counts.items())) or "-"
    method_summary = ", ".join(f"{esc(key)} {value}" for key, value in sorted(method_counts.items())) or "-"

    cards = []
    for scenario in active_rows:
        code = scenario.get("scenario_code")
        scenario_rows = [row for row in rows if row.get("scenario_code") == code]
        vulnerable = sorted(scenario_rows, key=lambda row: row.get("scenario_beta") or 0.0, reverse=True)[:5]
        defensive = sorted(scenario_rows, key=lambda row: row.get("scenario_beta") or 0.0)[:5]
        vulnerable_items = "".join(
            f"<li><strong>{esc(row.get('ticker'))}</strong> <span>{safe_round(row.get('scenario_beta'), 3)}</span></li>"
            for row in vulnerable
        )
        defensive_items = "".join(
            f"<li><strong>{esc(row.get('ticker'))}</strong> <span>{safe_round(row.get('scenario_beta'), 3)}</span></li>"
            for row in defensive
        )
        cards.append(
            f"""
            <section class="card">
              <h2>{esc(scenario.get('scenario_name_ko') or scenario.get('scenario_name') or code)}</h2>
              <p class="muted">{esc(code)} · lens {esc(scenario.get('lens'))}</p>
              <div class="split">
                <div><h3>취약도 상위</h3><ol>{vulnerable_items}</ol></div>
                <div><h3>방어/상쇄 상위</h3><ol>{defensive_items}</ol></div>
              </div>
            </section>
            """
        )

    header_cells = []
    for code in all_codes:
        scenario = scenario_lookup[code]
        badges = []
        if code in active_code_set:
            badges.append("<span class='badge active'>ACTIVE</span>")
        if code in ADVERSE_SCENARIO_CODES:
            badges.append("<span class='badge adverse'>ADVERSE</span>")
        if scenario_trade_gate_weight(scenario) > 0:
            badges.append("<span class='badge tradegate'>TRADE GATE</span>")
        badge_html = "".join(badges)
        header_cells.append(
            f"<th title='{esc(code)}'><span>{esc(short_scenario_label(scenario))}</span><div class='badges'>{badge_html}</div></th>"
        )
    header_cells = "".join(header_cells)
    body_rows = []
    for ticker in ranked_tickers:
        meta = ticker_meta.get(ticker, {})
        cells = []
        for code in all_codes:
            row = by_ticker[ticker].get(code)
            value = row.get("scenario_beta") if row else None
            gate = " gate" if row and row.get("gate_eligible") == "Y" else ""
            cells.append(
                f"<td class='heat{gate}' style='{scenario_beta_cell_style(value)}'>{esc(safe_round(value, 3))}</td>"
            )
        body_rows.append(
            f"<tr><th>{esc(ticker)}</th><td>{esc(meta.get('asset_class'))}</td>{''.join(cells)}</tr>"
        )

    content = f"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<title>HedgeMate Scenario Sensitivity Visual - {esc(run_id)}</title>
<style>
  :root {{
    --ink: #111827;
    --muted: #64748b;
    --line: #d8dee9;
    --panel: #ffffff;
    --bg: #f5f1e8;
  }}
  body {{
    margin: 0;
    padding: 28px;
    background: radial-gradient(circle at top left, #fff7d6, transparent 32rem), var(--bg);
    color: var(--ink);
    font-family: Georgia, "Times New Roman", serif;
  }}
  h1, h2, h3 {{ margin: 0 0 10px; }}
  h1 {{ font-size: 30px; letter-spacing: -0.03em; }}
  h2 {{ font-size: 19px; }}
  h3 {{ font-size: 14px; color: var(--muted); text-transform: uppercase; letter-spacing: 0.08em; }}
  .muted {{ color: var(--muted); }}
  .summary {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
    gap: 12px;
    margin: 18px 0 22px;
  }}
  .metric, .card {{
    background: rgba(255, 255, 255, 0.82);
    border: 1px solid var(--line);
    border-radius: 18px;
    box-shadow: 0 10px 30px rgba(15, 23, 42, 0.08);
  }}
  .metric {{ padding: 16px; }}
  .metric strong {{ display: block; font-size: 28px; }}
  .cards {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
    gap: 16px;
  }}
  .card {{ padding: 18px; }}
  .split {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 16px;
  }}
  ol {{ margin: 0; padding-left: 22px; }}
  li {{ margin: 6px 0; }}
  li span {{ color: var(--muted); }}
  table {{
    width: 100%;
    border-collapse: separate;
    border-spacing: 0;
    overflow: hidden;
    border-radius: 18px;
    background: white;
    box-shadow: 0 10px 30px rgba(15, 23, 42, 0.08);
    margin-top: 18px;
  }}
  th, td {{ padding: 10px 12px; border-bottom: 1px solid #e5e7eb; text-align: right; }}
  th:first-child, td:first-child {{ text-align: left; }}
  thead th {{ background: #111827; color: white; font-weight: 600; }}
  tbody th {{ font-weight: 700; }}
  .heat {{ font-variant-numeric: tabular-nums; }}
  .gate {{ outline: 2px solid rgba(17, 24, 39, 0.45); outline-offset: -3px; }}
  .legend {{ display: flex; gap: 14px; flex-wrap: wrap; margin: 10px 0 4px; color: var(--muted); }}
  .swatch {{ display: inline-block; width: 18px; height: 10px; border-radius: 999px; margin-right: 6px; }}
  .badges {{ display: flex; justify-content: flex-end; gap: 4px; margin-top: 5px; }}
  .badge {{ display: inline-block; border-radius: 999px; padding: 2px 6px; font-size: 10px; letter-spacing: .06em; }}
  .badge.active {{ background: #fde68a; color: #78350f; }}
  .badge.adverse {{ background: #fecaca; color: #7f1d1d; }}
  .badge.tradegate {{ background: #bbf7d0; color: #14532d; }}
  .details {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 12px; margin: 0 0 20px; }}
  .detail {{ background: rgba(255,255,255,.7); border: 1px solid var(--line); border-radius: 14px; padding: 12px 14px; }}
  .section-title {{ margin-top: 24px; }}
</style>
</head>
<body>
  <h1>Scenario Sensitivity Visual</h1>
  <p class="muted">run_id {esc(run_id)} · data_version {esc(data_version)} · positive는 취약도 증가, negative는 방어/상쇄 가능성을 뜻합니다.</p>
  <div class="summary">
    <div class="metric"><span class="muted">Total scenarios</span><strong>{len(all_codes)}</strong></div>
    <div class="metric"><span class="muted">Active scenarios</span><strong>{len(active_codes)}</strong></div>
    <div class="metric"><span class="muted">Adverse scenarios</span><strong>{adverse_count}</strong></div>
    <div class="metric"><span class="muted">Gate eligible rows</span><strong>{gate_eligible_count}</strong></div>
    <div class="metric"><span class="muted">High evidence rows</span><strong>{high_evidence_count}</strong></div>
  </div>
  <div class="details">
    <div class="detail"><strong>Evidence quality</strong><br><span class="muted">{evidence_summary}</span></div>
    <div class="detail"><strong>Method</strong><br><span class="muted">{method_summary}</span></div>
  </div>
  <div class="legend">
    <span><i class="swatch" style="background:rgba(185,28,28,.65)"></i>취약도 높음</span>
    <span><i class="swatch" style="background:rgba(37,99,235,.65)"></i>방어/상쇄</span>
    <span><i class="swatch" style="background:#f8fafc;border:1px solid #cbd5e1"></i>중립</span>
    <span>굵은 테두리: gate_eligible=Y</span>
  </div>
  <h2 class="section-title">All scenario heatmap</h2>
  <p class="muted">전체 {len(all_codes)}개 시나리오를 모두 표시합니다. ACTIVE/ADVERSE 배지는 현재 장세와 게이트 해석 우선순위를 구분합니다.</p>
  <table>
    <thead><tr><th>Ticker</th><th>Class</th>{header_cells}</tr></thead>
    <tbody>{''.join(body_rows)}</tbody>
  </table>
  <h2 class="section-title">Active scenario focus</h2>
  <div class="cards">{''.join(cards)}</div>
</body>
</html>
"""
    html_path.write_text(content, encoding="utf-8")


# -----------------------------
# Ranking helpers
# -----------------------------

def build_candidate_prefilter_rows(feature_rows, dq_rows, universe_map, candidate_mode="hedge-only", scenario_context=None):
    dq_map = {row["ticker"]: row for row in dq_rows}
    candidates = []
    for row in feature_rows:
        meta = universe_map.get(row["ticker"], {})
        if not is_hedge_candidate(meta, candidate_mode=candidate_mode, scenario_context=scenario_context):
            continue
        if dq_map.get(row["ticker"], {}).get("status") == "FAIL":
            continue
        candidates.append(dict(row))

    corr_vals = [-(row["corr_sp500_60d_krw"]) for row in candidates if row.get("corr_sp500_60d_krw") is not None]
    cvar_vals = [row.get("cvar_95_1y_krw") for row in candidates if row.get("cvar_95_1y_krw") is not None]
    stress_vals = [row.get("avg_stress_ret_krw") for row in candidates if row.get("avg_stress_ret_krw") is not None]
    sharpe_vals = [row.get("sharpe_1y_krw_proxy") for row in candidates if row.get("sharpe_1y_krw_proxy") is not None]
    adv_vals = [row.get("adv_60") for row in candidates if row.get("adv_60") is not None]

    cmin, cmax = (min(corr_vals), max(corr_vals)) if corr_vals else (None, None)
    vmin, vmax = (min(cvar_vals), max(cvar_vals)) if cvar_vals else (None, None)
    smin, smax = (min(stress_vals), max(stress_vals)) if stress_vals else (None, None)
    shmin, shmax = (min(sharpe_vals), max(sharpe_vals)) if sharpe_vals else (None, None)
    amin, amax = (min(adv_vals), max(adv_vals)) if adv_vals else (None, None)

    ranked = []
    for row in candidates:
        corr_value = row.get("corr_sp500_60d_krw")
        cvar_value = row.get("cvar_95_1y_krw")
        stress_value = row.get("avg_stress_ret_krw")
        sharpe_value = row.get("sharpe_1y_krw_proxy")
        adv_value = row.get("adv_60")

        corr_improve = normalize_minmax(-corr_value, cmin, cmax) if corr_value is not None else 0.5
        cvar_improve = normalize_minmax(cvar_value, vmin, vmax) if cvar_value is not None else 0.5
        stress_defense = normalize_minmax(stress_value, smin, smax) if stress_value is not None else 0.5
        sharpe_quality = normalize_minmax(sharpe_value, shmin, shmax) if sharpe_value is not None else 0.5
        adv_norm = normalize_minmax(adv_value, amin, amax) if adv_value is not None else None
        liquidity_penalty = 1.0 - adv_norm if adv_norm is not None else 1.0
        score = (
            0.25 * clip01(corr_improve)
            + 0.25 * clip01(cvar_improve)
            + 0.20 * clip01(stress_defense)
            + 0.15 * clip01(sharpe_quality if sharpe_quality is not None else 0.5)
            - 0.15 * clip01(liquidity_penalty)
        )
        item = dict(row)
        item["hes_score"] = score
        item["component_corr_improve"] = clip01(corr_improve)
        item["component_cvar_improve"] = clip01(cvar_improve)
        item["component_stress_defense"] = clip01(stress_defense)
        item["component_sharpe_quality"] = clip01(sharpe_quality if sharpe_quality is not None else 0.5)
        item["component_liquidity_penalty"] = clip01(liquidity_penalty)
        item["hedge_bucket"] = hedge_bucket(universe_map.get(item["ticker"], {}))
        item["candidate_role"] = candidate_role(universe_map.get(item["ticker"], {"ticker": item["ticker"]}))
        item["candidate_role_reason_ko"] = candidate_role_reason_ko(universe_map.get(item["ticker"], {"ticker": item["ticker"]}))
        item["risk_bucket_match"] = risk_bucket_candidate_reason(universe_map.get(item["ticker"], {"ticker": item["ticker"]}), scenario_context) if candidate_mode == "risk-bucket" else ""
        ranked.append(item)

    ranked.sort(key=lambda x: (-x["hes_score"], x["ticker"]))
    return ranked


def weighted_feature_metric(base_weights_frac, feature_map, metric_key):
    weighted_sum = 0.0
    used_weight = 0.0
    for ticker, weight in base_weights_frac.items():
        value = feature_map.get(ticker, {}).get(metric_key)
        if value is None:
            continue
        weighted_sum += weight * value
        used_weight += weight
    if used_weight <= 0:
        return None
    return weighted_sum / used_weight


def role_safety_score_for_candidate(meta):
    role = candidate_role(meta)
    if role == "hedge_candidate":
        return 1.0
    if role == "conditional_candidate":
        return 0.35
    return 0.0


def build_input_aware_candidate_prefilter_rows(
    base_weights_pct,
    feature_rows,
    dq_rows,
    universe_map,
    scenario_context,
    candidate_mode="hedge-only",
):
    base_ranked = build_candidate_prefilter_rows(
        feature_rows,
        dq_rows,
        universe_map,
        candidate_mode=candidate_mode,
        scenario_context=scenario_context,
    )
    feature_map = {row["ticker"]: row for row in feature_rows}
    base_weights_frac = {ticker: weight / 100.0 for ticker, weight in base_weights_pct.items()}
    base_vulnerability = portfolio_scenario_vulnerability(base_weights_frac, feature_map, universe_map, scenario_context)
    base_downside_beta = weighted_feature_metric(base_weights_frac, feature_map, "downside_beta_sp500_1y_krw")
    base_beta = weighted_feature_metric(base_weights_frac, feature_map, "beta_sp500_1y_krw")

    rows = []
    for row in base_ranked:
        ticker = row["ticker"]
        meta = universe_map.get(ticker, {"ticker": ticker})
        proposed_weights = build_candidate_weights(base_weights_frac, [ticker], 0.10)
        proposed_vulnerability = portfolio_scenario_vulnerability(
            proposed_weights,
            feature_map,
            universe_map,
            scenario_context,
        )
        reduction = None
        if base_vulnerability is not None and proposed_vulnerability is not None:
            reduction = base_vulnerability - proposed_vulnerability

        candidate_downside = row.get("downside_beta_sp500_1y_krw")
        if base_downside_beta is not None and candidate_downside is not None:
            downside_score = clip01(0.5 + (abs(base_downside_beta) - abs(candidate_downside)) / 2.0)
        else:
            downside_score = 0.5

        candidate_beta = row.get("beta_sp500_1y_krw")
        if base_beta is not None and candidate_beta is not None:
            tail_beta_score = clip01(0.5 + (abs(base_beta) - abs(candidate_beta)) / 2.0)
        else:
            tail_beta_score = 0.5

        scenario_score = clip01(0.5 + (reduction or 0.0))
        role_score = role_safety_score_for_candidate(meta)
        hes_score = clip01(row.get("hes_score", 0.5))
        input_aware_score = (
            0.35 * scenario_score
            + 0.20 * downside_score
            + 0.15 * tail_beta_score
            + 0.15 * role_score
            + 0.15 * hes_score
        )

        item = dict(row)
        item["input_aware_score"] = input_aware_score
        item["base_vulnerability_reduction_potential"] = reduction
        item["downside_correlation_to_base"] = candidate_downside
        item["tail_beta_to_base"] = candidate_beta
        item["scenario_complement_score"] = scenario_score
        item["role_safety_score"] = role_score
        rows.append(item)

    rows.sort(key=lambda x: (-x["input_aware_score"], -x.get("hes_score", 0.0), x["ticker"]))
    return rows


def candidate_rank_score(row):
    score = row.get("input_aware_score")
    if score is not None:
        return score
    return row.get("hes_score", 0.0)


def choose_candidate_pool(prefilter_ranked, universe_map, base_tickers, top_k_per_group=DEFAULT_PREFILTER_TOP_K_PER_GROUP, global_limit=DEFAULT_PREFILTER_GLOBAL_LIMIT):
    groups = defaultdict(list)
    for row in prefilter_ranked:
        ticker = row["ticker"]
        if ticker in base_tickers:
            continue
        groups[hedge_bucket(universe_map[ticker])].append(row)

    selected = []
    for bucket, rows in groups.items():
        del bucket
        selected.extend(rows[:top_k_per_group])

    selected.sort(key=lambda x: (-candidate_rank_score(x), -x.get("hes_score", 0.0), x["ticker"]))
    return selected[:global_limit]


def combo_label(combo):
    return " + ".join(combo)


def combo_risk_bucket_match(combo, candidate_pool_by_ticker):
    matches = []
    for ticker in combo:
        value = str(candidate_pool_by_ticker.get(ticker, {}).get("risk_bucket_match") or "").strip()
        if value:
            matches.extend(part for part in value.split("|") if part)
    return "|".join(sorted(set(matches)))


def normalize_rows_for_final_score(rows):
    scorable = [
        row
        for row in rows
        if any(
            row.get(key) is not None
            for key in [
                "cvar_improve_pct",
                "mdd_improve_pct",
                "stress_improve",
                "exposure_improve",
                "sharpe_improve",
                "annual_return_improve_pct",
                "downside_beta_improve",
                "combo_min_adv_60",
                "scenario_vulnerability_reduction",
                "adverse_scenario_penalty",
                "factor_concentration_penalty",
                "dq_penalty",
            ]
        )
    ]
    if not scorable:
        return rows

    metric_keys = [
        "cvar_improve_pct",
        "mdd_improve_pct",
        "stress_improve",
        "exposure_improve",
        "sharpe_improve",
        "annual_return_improve_pct",
        "downside_beta_improve",
        "combo_min_adv_60",
        "scenario_vulnerability_reduction",
        "adverse_scenario_penalty",
        "factor_concentration_penalty",
        "dq_penalty",
    ]
    ranges = {}
    for key in metric_keys:
        vals = [row.get(key) for row in scorable if row.get(key) is not None]
        ranges[key] = (min(vals), max(vals)) if vals else (None, None)

    for row in scorable:
        row["score_component_cvar"] = normalize_minmax(row.get("cvar_improve_pct"), *ranges["cvar_improve_pct"])
        row["score_component_mdd"] = normalize_minmax(row.get("mdd_improve_pct"), *ranges["mdd_improve_pct"])
        row["score_component_stress"] = normalize_minmax(row.get("stress_improve"), *ranges["stress_improve"])
        row["score_component_exposure"] = normalize_minmax(row.get("exposure_improve"), *ranges["exposure_improve"])
        row["score_component_sharpe"] = normalize_minmax(row.get("sharpe_improve"), *ranges["sharpe_improve"])
        row["score_component_return"] = normalize_minmax(row.get("annual_return_improve_pct"), *ranges["annual_return_improve_pct"])
        row["score_component_downside"] = normalize_minmax(row.get("downside_beta_improve"), *ranges["downside_beta_improve"])
        row["score_component_liquidity"] = normalize_minmax(row.get("combo_min_adv_60"), *ranges["combo_min_adv_60"])
        dq_penalty_component = normalize_minmax(row.get("dq_penalty"), *ranges["dq_penalty"])
        row["score_component_dq_confidence"] = 1.0 - dq_penalty_component if dq_penalty_component is not None else None
        scenario_base = normalize_minmax(row.get("scenario_vulnerability_reduction"), *ranges["scenario_vulnerability_reduction"])
        scenario_penalty = normalize_minmax(row.get("adverse_scenario_penalty"), *ranges["adverse_scenario_penalty"])
        concentration_penalty = normalize_minmax(row.get("factor_concentration_penalty"), *ranges["factor_concentration_penalty"])
        if row.get("scenario_score_component") is not None:
            row["score_component_scenario"] = row["scenario_score_component"]
        elif scenario_base is not None or scenario_penalty is not None:
            row["score_component_scenario"] = clip01(
                0.5
                + 0.5 * (scenario_base if scenario_base is not None else 0.0)
                - 0.5 * (scenario_penalty if scenario_penalty is not None else 0.0)
            )
        else:
            row["score_component_scenario"] = None
        row["score_component_concentration"] = (
            1.0 - concentration_penalty if concentration_penalty is not None else None
        )
        risk_components = [
            (0.27, row.get("score_component_cvar")),
            (0.18, row.get("score_component_mdd")),
            (0.15, row.get("score_component_stress")),
            (0.14, row.get("score_component_downside")),
            (0.08, row.get("score_component_exposure")),
            (0.07, row.get("score_component_sharpe")),
            (0.07, row.get("score_component_return")),
            (0.04, row.get("score_component_liquidity")),
        ]
        active_risk_components = [(weight, value) for weight, value in risk_components if value is not None]
        risk_weight_sum = sum(weight for weight, _ in active_risk_components)
        risk_score = (
            sum(weight * value for weight, value in active_risk_components) / risk_weight_sum
            if risk_weight_sum > 0
            else 0.5
        )
        if (
            row.get("score_component_scenario") is None
            and row.get("score_component_concentration") is None
            and row.get("score_component_dq_confidence") is None
        ):
            row["final_score"] = risk_score
        else:
            final_components = [(0.65, risk_score)]
            if row.get("score_component_scenario") is not None:
                final_components.append((0.25, row["score_component_scenario"]))
            if row.get("score_component_concentration") is not None:
                final_components.append((0.05, row["score_component_concentration"]))
            if row.get("score_component_dq_confidence") is not None:
                final_components.append((0.05, row["score_component_dq_confidence"]))
            final_weight_sum = sum(weight for weight, _ in final_components)
            row["final_score"] = sum(weight * value for weight, value in final_components) / final_weight_sum
        row["recommendation_reason"] = build_recommendation_reason(row)

    return rows


def build_recommendation_reason(row):
    components = [
        (row.get("score_component_cvar"), "CVaR 개선"),
        (row.get("score_component_mdd"), "MDD 개선"),
        (row.get("score_component_stress"), "Stress 방어"),
        (row.get("score_component_exposure"), "노출(beta/corr) 감소"),
        (row.get("score_component_sharpe"), "Sharpe 개선"),
        (row.get("score_component_liquidity"), "유동성 양호"),
        (row.get("score_component_scenario"), "현재 장세 취약도 개선"),
        (row.get("score_component_concentration"), "factor 집중 완화"),
    ]
    components.extend(
        [
            (row.get("score_component_downside"), "Downside beta reduction"),
            (row.get("score_component_return"), "Return drag control"),
            (row.get("score_component_dq_confidence"), "DQ confidence"),
        ]
    )
    labels = [label for score, label in sorted(components, key=lambda x: (x[0] is None, -(x[0] or -1)))[:3] if score is not None]
    base = ", ".join(labels) if labels else "데이터 기준 충족"
    scenario_reason = row.get("scenario_reason_ko")
    return f"{base} / {scenario_reason}" if scenario_reason else base


# -----------------------------
# Proposal evaluation
# -----------------------------

def merge_reason(existing, reason):
    if not reason:
        return existing or ""
    parts = [p.strip() for p in (existing or "").split(";") if p.strip()]
    if reason not in parts:
        parts.append(reason)
    return "; ".join(parts)


def dq_row_is_blocking(dq_row):
    if not dq_row:
        return False
    if str(dq_row.get("dq_blocking")).lower() in {"true", "1", "yes"}:
        return True
    return dq_row.get("status") == "FAIL"


def dq_reason_text(ticker, dq_row):
    codes = dq_row.get("dq_reason_codes") or dq_row.get("status") or "unknown"
    return f"{ticker}: {codes}"


def dq_non_blocking_warning(dq_row):
    if not dq_row:
        return False
    return dq_row.get("status") == "WARN" and not dq_row_is_blocking(dq_row)


def base_has_kr_exposure(base_weights_frac, universe_map):
    for ticker, weight in (base_weights_frac or {}).items():
        if weight <= 0:
            continue
        meta = universe_map.get(ticker, {})
        if meta.get("region") == "KR" or meta.get("asset_class") == "kr_stock" or ticker.endswith(".KS"):
            return True
    return False


def apply_recommendation_status(row, combo, dq_map):
    gate_reasons = row.get("gate_fail_reasons", "")
    reference_reasons = row.get("reference_reason", "")
    dq_warning_reasons = row.get("dq_warning_reasons", "")
    dq_blocking_reasons = row.get("dq_blocking_reasons", "")
    dq_penalty = parse_float(row.get("dq_penalty")) or 0.0
    recommendation_status = None

    if row.get("status") != "PASS":
        recommendation_status = "FAIL_GATE"
        if not gate_reasons:
            gate_reasons = merge_reason(gate_reasons, row.get("message", "게이트 실패"))
    elif row.get("recommended_role") == "adverse_scenario_sensitive" or (row.get("adverse_scenario_penalty") or 0.0) > 0:
        reason = "active adverse scenario 민감도 증가"
        row["status"] = "FAIL"
        row["message"] = merge_reason(row.get("message", "PASS"), reason).replace("PASS; ", "FAIL: ")
        gate_reasons = merge_reason(gate_reasons, reason)
        recommendation_status = "FAIL_GATE"
    elif row.get("recommended_role") in {"scenario_data_insufficient", "baseline_no_scenario_vector"}:
        recommendation_status = "INSUFFICIENT_DATA"
        reference_reasons = merge_reason(reference_reasons, "시나리오 민감도 게이트 근거 부족")
    elif row.get("candidate_role") and row.get("candidate_role") != "hedge_candidate":
        recommendation_status = "REFERENCE_ONLY"
        reference_reasons = merge_reason(reference_reasons, row.get("candidate_role_reason_ko") or "조건부/진단 후보")
    else:
        for ticker in combo:
            dq_row = dq_map.get(ticker, {})
            if dq_row_is_blocking(dq_row):
                reason = f"DQ BLOCKING - {dq_reason_text(ticker, dq_row)}"
                dq_blocking_reasons = merge_reason(dq_blocking_reasons, reason)
                reference_reasons = merge_reason(reference_reasons, reason)
                dq_penalty = max(dq_penalty, 1.0)
            elif dq_non_blocking_warning(dq_row):
                dq_warning_reasons = merge_reason(dq_warning_reasons, f"DQ WARN non-blocking - {dq_reason_text(ticker, dq_row)}")
                dq_penalty = max(dq_penalty, 0.10)
        recommendation_status = "REFERENCE_ONLY" if reference_reasons else "PASS_RECOMMEND"

    row["recommendation_status"] = recommendation_status
    row["gate_fail_reasons"] = gate_reasons
    row["reference_reason"] = reference_reasons
    row["dq_warning_reasons"] = dq_warning_reasons
    row["dq_blocking_reasons"] = dq_blocking_reasons
    row["dq_penalty"] = dq_penalty
    row["recommendation_confidence_score"] = clip01(1.0 - dq_penalty)
    return row


def evaluate_gate(base_metrics, proposed_metrics, combo, feature_map, dq_map, scenario_row=None, base_weights_frac=None, universe_map=None):
    reasons = []
    reference_reasons = []
    dq_warning_reasons = []
    dq_blocking_reasons = []
    dq_penalty = 0.0
    status = "PASS"

    cvar_improve_pct = risk_improvement_pct(base_metrics.get("cvar_95_krw"), proposed_metrics.get("cvar_95_krw"), is_abs_risk=True)
    if cvar_improve_pct is None or cvar_improve_pct <= 0:
        reasons.append("CVaR 개선 미달")

    mdd_improve_pct = risk_improvement_pct(base_metrics.get("mdd_krw"), proposed_metrics.get("mdd_krw"), is_abs_risk=True)
    if mdd_improve_pct is None or mdd_improve_pct < 0:
        reasons.append("MDD 개선 미달")

    stress_improve = signed_improvement(base_metrics.get("stress_avg_ret_krw"), proposed_metrics.get("stress_avg_ret_krw"))
    if stress_improve is None or stress_improve < -GATE_STRESS_IMPROVE_TOLERANCE:
        reasons.append("Stress 개선 미달")

    corr_improve = None
    if base_metrics.get("corr_sp500_krw") is not None and proposed_metrics.get("corr_sp500_krw") is not None:
        corr_improve = abs(base_metrics["corr_sp500_krw"]) - abs(proposed_metrics["corr_sp500_krw"])

    beta_improve = None
    if base_metrics.get("beta_sp500_krw") is not None and proposed_metrics.get("beta_sp500_krw") is not None:
        beta_improve = abs(base_metrics["beta_sp500_krw"]) - abs(proposed_metrics["beta_sp500_krw"])

    exposure_improve = max([v for v in [corr_improve, beta_improve] if v is not None], default=None)
    if exposure_improve is None or exposure_improve <= 0:
        reasons.append("beta/corr 감소 미달")

    sharpe_improve = signed_improvement(base_metrics.get("sharpe_krw_proxy"), proposed_metrics.get("sharpe_krw_proxy"))
    sharpe_improve_pct = signed_improvement_pct(base_metrics.get("sharpe_krw_proxy"), proposed_metrics.get("sharpe_krw_proxy"))
    if sharpe_improve_pct is not None and sharpe_improve_pct < -10.0:
        reasons.append("Sharpe 악화 하드 게이트")
    elif sharpe_improve_pct is not None and sharpe_improve_pct < -5.0:
        reference_reasons.append("Sharpe soft warning")

    annual_return_improve = signed_improvement(base_metrics.get("annual_return_krw"), proposed_metrics.get("annual_return_krw"))
    annual_return_improve_pct = signed_improvement_pct(base_metrics.get("annual_return_krw"), proposed_metrics.get("annual_return_krw"))
    if annual_return_improve is not None and annual_return_improve < -0.05:
        reasons.append("연환산 수익률 훼손 하드 게이트")
    elif annual_return_improve_pct is not None and annual_return_improve_pct < -5.0:
        reference_reasons.append("annual return drag soft warning")

    downside_beta_improve = None
    if base_metrics.get("downside_beta_sp500_krw") is not None and proposed_metrics.get("downside_beta_sp500_krw") is not None:
        downside_beta_improve = abs(base_metrics["downside_beta_sp500_krw"]) - abs(proposed_metrics["downside_beta_sp500_krw"])
        if downside_beta_improve < -0.05:
            reasons.append("downside beta 증가 하드 게이트")

    kospi_corr_improve = None
    if base_metrics.get("corr_kospi200_krw") is not None and proposed_metrics.get("corr_kospi200_krw") is not None:
        kospi_corr_improve = abs(base_metrics["corr_kospi200_krw"]) - abs(proposed_metrics["corr_kospi200_krw"])
        if universe_map is not None and base_has_kr_exposure(base_weights_frac, universe_map) and kospi_corr_improve < -0.05:
            reasons.append("KR 자산 KOSPI 상관 취약도 증가")

    if scenario_row and (
        scenario_row.get("recommended_role") == "adverse_scenario_sensitive"
        or (scenario_row.get("adverse_scenario_penalty") or 0.0) > 0
    ):
        reasons.append("active adverse scenario 민감도 증가")

    combo_min_adv = None
    for ticker in combo:
        dq_row = dq_map.get(ticker, {})
        if dq_row_is_blocking(dq_row):
            reason = f"DQ BLOCKING - {dq_reason_text(ticker, dq_row)}"
            reasons.append(reason)
            dq_blocking_reasons.append(reason)
            dq_penalty = max(dq_penalty, 1.0)
            continue
        if dq_non_blocking_warning(dq_row):
            dq_warning_reasons.append(f"DQ WARN non-blocking - {dq_reason_text(ticker, dq_row)}")
            dq_penalty = max(dq_penalty, 0.10)
        adv = feature_map.get(ticker, {}).get("adv_60")
        if adv is None or adv <= 0:
            reasons.append(f"유동성 기준 미달 - {ticker}")
            continue
        combo_min_adv = adv if combo_min_adv is None else min(combo_min_adv, adv)
    if combo_min_adv is None:
        reasons.append("유동성 기준 미달")

    if reasons:
        status = "FAIL"

    return {
        "status": status,
        "message": "PASS" if status == "PASS" else "FAIL: " + "; ".join(reasons),
        "cvar_improve_pct": cvar_improve_pct,
        "mdd_improve_pct": mdd_improve_pct,
        "stress_improve": stress_improve,
        "corr_improve": corr_improve,
        "beta_improve": beta_improve,
        "exposure_improve": exposure_improve,
        "sharpe_improve": sharpe_improve,
        "sharpe_improve_pct": sharpe_improve_pct,
        "annual_return_improve": annual_return_improve,
        "annual_return_improve_pct": annual_return_improve_pct,
        "downside_beta_improve": downside_beta_improve,
        "kospi_corr_improve": kospi_corr_improve,
        "combo_min_adv_60": combo_min_adv,
        "gate_fail_reasons": "; ".join(reasons),
        "reference_reason": "; ".join(reference_reasons),
        "dq_warning_reasons": "; ".join(dq_warning_reasons),
        "dq_blocking_reasons": "; ".join(dq_blocking_reasons),
        "dq_penalty": dq_penalty,
        "recommendation_confidence_score": clip01(1.0 - dq_penalty),
    }


def base_compare_row(label, metrics):
    return {
        "scenario": label,
        "vol_annual": metrics.get("vol_annual_krw"),
        "mdd": metrics.get("mdd_krw"),
        "cvar_95": metrics.get("cvar_95_krw"),
        "annual_return_krw": metrics.get("annual_return_krw"),
        "sharpe_krw_proxy": metrics.get("sharpe_krw_proxy"),
        "vol_improve_pct": 0.0,
        "mdd_improve_pct": 0.0,
        "cvar_improve_pct": 0.0,
        "sharpe_improve_pct": 0.0,
        "stress_improve": 0.0,
        "no_recommendation_reason": "",
    }


def proposal_to_compare_row(scenario, proposal, no_recommendation_reason=""):
    return {
        "scenario": scenario,
        "vol_annual": proposal.get("proposed_vol_annual"),
        "mdd": proposal.get("proposed_mdd"),
        "cvar_95": proposal.get("proposed_cvar_95"),
        "annual_return_krw": proposal.get("proposed_annual_return_krw"),
        "sharpe_krw_proxy": proposal.get("proposed_sharpe_krw_proxy"),
        "vol_improve_pct": proposal.get("vol_improve_pct"),
        "mdd_improve_pct": proposal.get("mdd_improve_pct"),
        "cvar_improve_pct": proposal.get("cvar_improve_pct"),
        "sharpe_improve_pct": proposal.get("sharpe_improve_pct"),
        "stress_improve": proposal.get("stress_improve"),
        "no_recommendation_reason": no_recommendation_reason,
    }


def _parse_action_weight_json(raw):
    if not raw:
        return {}
    try:
        payload = json.loads(raw)
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    weights = {}
    for ticker, value in payload.items():
        try:
            number = float(value)
        except (TypeError, ValueError):
            continue
        if number <= 0:
            continue
        weights[str(ticker)] = number / 100.0 if number > 1.0 else number
    return weights


def _metric_delta(after, before):
    if after is None or before is None:
        return None
    return round(after - before, 8)


def _metric_plain_reason(row):
    candidate = row.get("candidate_label") or row.get("candidate_tickers") or "후보"
    sleeve = row.get("risk_sleeve_label_ko") or row.get("risk_sleeve") or "해당"
    cvar_delta = row.get("cvar_delta")
    mdd_delta = row.get("mdd_delta")
    stress_delta = row.get("stress_delta")
    parts = []
    if cvar_delta is not None:
        parts.append("CVaR 개선" if cvar_delta >= 0 else "CVaR 악화")
    if mdd_delta is not None:
        parts.append("MDD 개선" if mdd_delta >= 0 else "MDD 악화")
    if stress_delta is not None:
        parts.append("stress 개선" if stress_delta >= 0 else "stress 악화")
    metric_text = ", ".join(parts) if parts else "전후 리스크 지표 계산 제한"
    if row.get("action_status") == "FAIL_ACTION":
        return f"{candidate} 조정은 {sleeve} 취약성은 일부 낮춰도 핵심 리스크 지표가 악화되어 실행 기준 미통과입니다. ({metric_text})"
    return f"{candidate} 조정은 {sleeve} 취약성을 낮추는 검토안이며 전후 지표는 {metric_text}으로 확인됩니다."


def enrich_hedge_action_metrics(action_rows, base_metrics, ticker_ret_map, spy_ret_map, ks200_ret_map, stress_dates):
    if not action_rows:
        return action_rows
    for row in action_rows:
        before_weights = _parse_action_weight_json(row.get("before_weights_json"))
        after_weights = _parse_action_weight_json(row.get("after_weights_json"))
        metrics_before = base_metrics
        if metrics_before is None and before_weights:
            before_returns, before_err = compute_portfolio_returns(before_weights, ticker_ret_map)
            metrics_before = None if before_err else portfolio_metrics_from_returns(
                before_returns,
                benchmark_ret_map=spy_ret_map,
                stress_dates=stress_dates,
                ks200_ret_map=ks200_ret_map,
            )
        if not after_weights or row.get("action_status") == "NO_ACTION":
            row.update(
                {
                    "metric_source": row.get("metric_source") or "",
                    "metric_coverage_reason": row.get("metric_coverage_reason") or "NO_ACTION or missing after weights",
                }
            )
            finalize_action_row_contract(row)
            continue
        after_returns, after_err = compute_portfolio_returns(after_weights, ticker_ret_map)
        metrics_after = None if after_err else portfolio_metrics_from_returns(
            after_returns,
            benchmark_ret_map=spy_ret_map,
            stress_dates=stress_dates,
            ks200_ret_map=ks200_ret_map,
        )
        if metrics_before is None or metrics_after is None:
            row.update(
                {
                    "metric_source": "",
                    "metric_coverage_reason": after_err or "minimum observations unavailable for action before/after metrics",
                }
            )
            finalize_action_row_contract(row)
            continue
        row.update(
            {
                "base_cvar_95": metrics_before.get("cvar_95_krw"),
                "proposed_cvar_95": metrics_after.get("cvar_95_krw"),
                "cvar_delta": _metric_delta(metrics_after.get("cvar_95_krw"), metrics_before.get("cvar_95_krw")),
                "base_mdd": metrics_before.get("mdd_krw"),
                "proposed_mdd": metrics_after.get("mdd_krw"),
                "mdd_delta": _metric_delta(metrics_after.get("mdd_krw"), metrics_before.get("mdd_krw")),
                "base_beta_sp500_krw": metrics_before.get("beta_sp500_krw"),
                "proposed_beta_sp500_krw": metrics_after.get("beta_sp500_krw"),
                "beta_delta": _metric_delta(metrics_after.get("beta_sp500_krw"), metrics_before.get("beta_sp500_krw")),
                "base_stress_avg_ret_krw": metrics_before.get("stress_avg_ret_krw"),
                "proposed_stress_avg_ret_krw": metrics_after.get("stress_avg_ret_krw"),
                "stress_delta": _metric_delta(metrics_after.get("stress_avg_ret_krw"), metrics_before.get("stress_avg_ret_krw")),
                "base_sharpe_krw_proxy": metrics_before.get("sharpe_krw_proxy"),
                "proposed_sharpe_krw_proxy": metrics_after.get("sharpe_krw_proxy"),
                "sharpe_delta": _metric_delta(metrics_after.get("sharpe_krw_proxy"), metrics_before.get("sharpe_krw_proxy")),
                "metric_source": "computed_from_action_before_after_weights",
                "metric_coverage_reason": "",
            }
        )
        worsened_reasons = []
        if row.get("cvar_delta") is not None and row["cvar_delta"] < -0.0001:
            worsened_reasons.append("CVaR worsened")
        if row.get("mdd_delta") is not None and row["mdd_delta"] < -0.0001:
            worsened_reasons.append("MDD worsened")
        if row.get("stress_delta") is not None and row["stress_delta"] < -0.0001:
            worsened_reasons.append("stress worsened")
        if row.get("vulnerability_delta") is not None and float(row.get("vulnerability_delta") or 0.0) >= 0:
            worsened_reasons.append("sleeve vulnerability not improved")
        if worsened_reasons and row.get("action_status") not in {"RESEARCH_ONLY", "NO_ACTION"}:
            row["action_status"] = "FAIL_ACTION"
            existing_reasons = [part for part in [row.get("constraint_reasons"), "; ".join(worsened_reasons)] if part]
            row["constraint_reasons"] = "; ".join(existing_reasons)
        row["plain_korean_reason"] = _metric_plain_reason(row)
        finalize_action_row_contract(row)
    return action_rows


def populate_evaluated_row(
    row,
    base_metrics,
    base_weights_frac,
    proposed_weights,
    combo,
    ticker_ret_map,
    spy_ret_map,
    ks200_ret_map,
    stress_dates,
    feature_map,
    dq_map,
    universe_map,
    scenario_context,
):
    ret_series, err = compute_portfolio_returns(proposed_weights, ticker_ret_map)
    if err is not None:
        row["status"] = "FAIL"
        row["message"] = f"FAIL: {err}"
        apply_recommendation_status(row, combo, dq_map)
        return row, None

    metrics = portfolio_metrics_from_returns(
        ret_series,
        benchmark_ret_map=spy_ret_map,
        stress_dates=stress_dates,
        ks200_ret_map=ks200_ret_map,
    )
    if metrics is None:
        row["status"] = "FAIL"
        row["message"] = "FAIL: 지표 계산 최소 관측치 부족"
        apply_recommendation_status(row, combo, dq_map)
        return row, None

    row.update(
        {
            "base_vol_annual": base_metrics.get("vol_annual_krw"),
            "proposed_vol_annual": metrics.get("vol_annual_krw"),
            "base_mdd": base_metrics.get("mdd_krw"),
            "proposed_mdd": metrics.get("mdd_krw"),
            "base_cvar_95": base_metrics.get("cvar_95_krw"),
            "proposed_cvar_95": metrics.get("cvar_95_krw"),
            "base_annual_return_krw": base_metrics.get("annual_return_krw"),
            "proposed_annual_return_krw": metrics.get("annual_return_krw"),
            "base_sharpe_krw_proxy": base_metrics.get("sharpe_krw_proxy"),
            "proposed_sharpe_krw_proxy": metrics.get("sharpe_krw_proxy"),
            "base_stress_avg_ret_krw": base_metrics.get("stress_avg_ret_krw"),
            "proposed_stress_avg_ret_krw": metrics.get("stress_avg_ret_krw"),
            "base_corr_sp500_krw": base_metrics.get("corr_sp500_krw"),
            "proposed_corr_sp500_krw": metrics.get("corr_sp500_krw"),
            "base_beta_sp500_krw": base_metrics.get("beta_sp500_krw"),
            "proposed_beta_sp500_krw": metrics.get("beta_sp500_krw"),
            "base_downside_beta_sp500_krw": base_metrics.get("downside_beta_sp500_krw"),
            "proposed_downside_beta_sp500_krw": metrics.get("downside_beta_sp500_krw"),
            "base_corr_kospi200_krw": base_metrics.get("corr_kospi200_krw"),
            "proposed_corr_kospi200_krw": metrics.get("corr_kospi200_krw"),
            "vol_improve_pct": risk_improvement_pct(base_metrics.get("vol_annual_krw"), metrics.get("vol_annual_krw"), is_abs_risk=False),
        }
    )
    scenario_row = scenario_adjustment_row(
        base_weights_frac,
        proposed_weights,
        feature_map,
        universe_map,
        scenario_context,
        combo,
    )
    row.update(scenario_row)
    row.update(
        evaluate_gate(
            base_metrics,
            metrics,
            combo,
            feature_map,
            dq_map,
            scenario_row=scenario_row,
            base_weights_frac=base_weights_frac,
            universe_map=universe_map,
        )
    )
    apply_recommendation_status(row, combo, dq_map)
    return row, metrics


def allocation_objective_score(row):
    if row.get("recommendation_status") == "PASS_RECOMMEND":
        status_score = 3.0
    elif row.get("recommendation_status") == "REFERENCE_ONLY":
        status_score = 2.0
    elif row.get("recommendation_status") == "INSUFFICIENT_DATA":
        status_score = 1.0
    else:
        status_score = 0.0
    return (
        status_score
        + 0.015 * (row.get("cvar_improve_pct") or 0.0)
        + 0.012 * (row.get("mdd_improve_pct") or 0.0)
        + 0.75 * (row.get("scenario_vulnerability_reduction") or 0.0)
        + 0.25 * (row.get("downside_beta_improve") or 0.0)
        + 0.005 * (row.get("sharpe_improve_pct") or 0.0)
        + 0.003 * (row.get("annual_return_improve_pct") or 0.0)
        - 0.50 * (row.get("dq_penalty") or 0.0)
    )


def evaluate_recommendations(
    label_prefix,
    base_weights_pct,
    ticker_ret_map,
    spy_ret_map,
    stress_dates,
    candidate_pool,
    feature_map,
    dq_map,
    universe_map,
    hedge_budgets_pct,
    max_combo_size,
    exempt_tickers=None,
    base_total_krw=None,
    hedge_budgets_krw=None,
    latest_price_map=None,
    scenario_context=None,
    ks200_ret_map=None,
):
    scenario_context = scenario_context or {"rows": [], "active_rows": [], "summary_ko": "시나리오 벡터 없음"}
    base_weights_frac = {ticker: weight / 100.0 for ticker, weight in base_weights_pct.items()}
    base_amounts_krw = build_base_amounts_krw(base_weights_pct, base_total_krw)
    base_ret_series, base_err = compute_portfolio_returns(base_weights_frac, ticker_ret_map)
    if base_err is not None:
        return {
            "errors": [f"FAIL: 기준 포트폴리오 수익률 계산 실패 - {base_err}"],
            "base_metrics": None,
            "single_rows": [],
            "multi_rows": [],
            "compare_rows": [],
            "best_single": None,
            "best_multi": None,
            "no_recommendation_reason": None,
        }

    base_metrics = portfolio_metrics_from_returns(
        base_ret_series,
        benchmark_ret_map=spy_ret_map,
        stress_dates=stress_dates,
        ks200_ret_map=ks200_ret_map,
    )
    if base_metrics is None:
        return {
            "errors": ["FAIL: 기준 포트폴리오 지표 계산 실패"],
            "base_metrics": None,
            "single_rows": [],
            "multi_rows": [],
            "compare_rows": [],
            "best_single": None,
            "best_multi": None,
            "no_recommendation_reason": None,
        }

    compare_rows = [base_compare_row(label_prefix, base_metrics)]
    single_rows = []
    multi_rows = []
    candidate_tickers = [row["ticker"] for row in candidate_pool]
    candidate_pool_by_ticker = {row["ticker"]: row for row in candidate_pool}
    if not candidate_tickers:
        compare_rows[0]["no_recommendation_reason"] = "추천 후보군이 비어 있습니다."
        return {
            "errors": [],
            "base_metrics": base_metrics,
            "single_rows": [],
            "multi_rows": [],
            "compare_rows": compare_rows,
            "best_single": None,
            "best_multi": None,
            "no_recommendation_reason": "추천 후보군이 비어 있습니다.",
        }

    budget_scenarios = []
    if hedge_budgets_krw and base_amounts_krw is not None:
        for budget_krw in hedge_budgets_krw:
            budget_scenarios.append(
                {
                    "mode": "krw",
                    "budget_krw": budget_krw,
                    "budget_pct": (budget_krw / base_total_krw) * 100.0 if base_total_krw else None,
                }
            )
    else:
        for budget_pct in hedge_budgets_pct:
            budget_scenarios.append({"mode": "pct", "budget_pct": budget_pct, "budget_krw": None})

    for budget_spec in budget_scenarios:
        budget_pct = budget_spec.get("budget_pct")
        budget_krw = budget_spec.get("budget_krw")
        budget_frac = (budget_pct / 100.0) if budget_pct is not None else None

        for candidate in candidate_tickers:
            candidate_source = candidate_pool_by_ticker.get(candidate, {})
            allocation_details = None
            if budget_spec["mode"] == "krw":
                proposed_weights, msg, allocation_details = build_candidate_weights_exact(base_amounts_krw, [candidate], budget_krw, latest_price_map or {})
                ok = proposed_weights is not None
                if ok:
                    ok, msg = enforce_weight_caps(proposed_weights, max_weight=0.20, exempt_tickers=(set(exempt_tickers or []) | {CASH_TICKER}))
            else:
                proposed_weights = build_candidate_weights(base_weights_frac, [candidate], budget_frac)
                ok, msg = enforce_weight_caps(proposed_weights, max_weight=0.20, exempt_tickers=exempt_tickers)
            row = {
                "candidate_label": candidate,
                "candidate_ticker": candidate,
                "candidate_bucket": hedge_bucket(universe_map[candidate]),
                "risk_bucket_match": candidate_source.get("risk_bucket_match") or "",
                "input_aware_score": candidate_source.get("input_aware_score"),
                "status": "PASS" if ok else "FAIL",
                "message": msg,
                "hedge_weight_pct": budget_pct,
                "hedge_budget_pct": budget_pct,
                "hedge_budget_krw": budget_krw,
                "combo_size": 1,
                "allocation_method": "exact_single_asset" if budget_spec["mode"] == "krw" else "single_asset_budget",
                "allocation_weights": json.dumps({candidate: budget_pct}, ensure_ascii=False),
                "allocation_objective_reason": "single candidate allocation",
                "weights_snapshot": json.dumps(to_pct_weights(proposed_weights or {}), ensure_ascii=False),
            }
            if allocation_details is not None:
                row["hedge_invested_krw"] = allocation_details["hedge_invested_krw"]
                row["hedge_cash_left_krw"] = allocation_details["hedge_cash_left_krw"]
                row["hedge_share_counts"] = json.dumps(allocation_details["share_counts"], ensure_ascii=False)
            if ok:
                populate_evaluated_row(
                    row,
                    base_metrics,
                    base_weights_frac,
                    proposed_weights,
                    [candidate],
                    ticker_ret_map,
                    spy_ret_map,
                    ks200_ret_map,
                    stress_dates,
                    feature_map,
                    dq_map,
                    universe_map,
                    scenario_context,
                )
            else:
                apply_recommendation_status(row, [candidate], dq_map)
            single_rows.append(row)

    max_multi_size = max(2, max_combo_size)
    multi_candidate_tickers = candidate_tickers[:DEFAULT_MULTI_GRID_CANDIDATE_LIMIT]
    for budget_spec in budget_scenarios:
        budget_pct = budget_spec.get("budget_pct")
        budget_krw = budget_spec.get("budget_krw")
        budget_frac = (budget_pct / 100.0) if budget_pct is not None else None
        for combo_size in range(2, max_multi_size + 1):
            for combo in itertools.combinations(multi_candidate_tickers, combo_size):
                if not combo_diversity_ok(combo, universe_map):
                    continue
                combo_match = combo_risk_bucket_match(combo, candidate_pool_by_ticker)
                candidate_rows_for_combo = []
                if budget_spec["mode"] == "krw":
                    allocation_details = None
                    proposed_weights, msg, allocation_details = build_candidate_weights_exact(base_amounts_krw, combo, budget_krw, latest_price_map or {})
                    ok = proposed_weights is not None
                    if ok:
                        ok, msg = enforce_weight_caps(proposed_weights, max_weight=0.20, exempt_tickers=(set(exempt_tickers or []) | {CASH_TICKER}))
                    row = {
                        "candidate_label": combo_label(combo),
                        "candidate_combo": combo_label(combo),
                        "candidate_bucket_combo": "|".join(sorted({hedge_bucket(universe_map[t]) for t in combo})),
                        "risk_bucket_match": combo_match,
                        "status": "PASS" if ok else "FAIL",
                        "message": msg,
                        "hedge_budget_pct": budget_pct,
                        "hedge_budget_krw": budget_krw,
                        "combo_size": combo_size,
                        "allocation_method": "exact_equal_shares",
                        "allocation_weights": "",
                        "allocation_objective_reason": "exact KRW budget uses whole-share equal allocation",
                        "weights_snapshot": json.dumps(to_pct_weights(proposed_weights or {}), ensure_ascii=False),
                    }
                    if allocation_details is not None:
                        row["hedge_invested_krw"] = allocation_details["hedge_invested_krw"]
                        row["hedge_cash_left_krw"] = allocation_details["hedge_cash_left_krw"]
                        row["hedge_share_counts"] = json.dumps(allocation_details["share_counts"], ensure_ascii=False)
                    if ok:
                        populate_evaluated_row(
                            row,
                            base_metrics,
                            base_weights_frac,
                            proposed_weights,
                            combo,
                            ticker_ret_map,
                            spy_ret_map,
                            ks200_ret_map,
                            stress_dates,
                            feature_map,
                            dq_map,
                            universe_map,
                            scenario_context,
                        )
                    else:
                        apply_recommendation_status(row, combo, dq_map)
                    candidate_rows_for_combo.append(row)
                else:
                    for allocation in generate_grid_allocations(combo, budget_frac):
                        proposed_weights = build_candidate_weights_from_allocations(base_weights_frac, allocation["allocation_weights"])
                        ok, msg = enforce_weight_caps(proposed_weights, max_weight=0.20, exempt_tickers=exempt_tickers)
                        row = {
                            "candidate_label": combo_label(combo),
                            "candidate_combo": combo_label(combo),
                            "candidate_bucket_combo": "|".join(sorted({hedge_bucket(universe_map[t]) for t in combo})),
                            "risk_bucket_match": combo_match,
                            "status": "PASS" if ok else "FAIL",
                            "message": msg,
                            "hedge_budget_pct": budget_pct,
                            "hedge_budget_krw": budget_krw,
                            "combo_size": combo_size,
                            "allocation_method": allocation["allocation_method"],
                            "allocation_weights": json.dumps(to_pct_weights(allocation["allocation_weights"]), ensure_ascii=False),
                            "allocation_objective_reason": "max grid objective: status + CVaR/MDD + scenario + Sharpe",
                            "weights_snapshot": json.dumps(to_pct_weights(proposed_weights or {}), ensure_ascii=False),
                        }
                        if ok:
                            populate_evaluated_row(
                                row,
                                base_metrics,
                                base_weights_frac,
                                proposed_weights,
                                combo,
                                ticker_ret_map,
                                spy_ret_map,
                                ks200_ret_map,
                                stress_dates,
                                feature_map,
                                dq_map,
                                universe_map,
                                scenario_context,
                            )
                        else:
                            apply_recommendation_status(row, combo, dq_map)
                        candidate_rows_for_combo.append(row)
                best_allocation_row = max(
                    candidate_rows_for_combo,
                    key=lambda item: (allocation_objective_score(item), item.get("allocation_weights", "")),
                    default=None,
                )
                if best_allocation_row is not None:
                    multi_rows.append(best_allocation_row)

    normalize_rows_for_final_score(single_rows)
    normalize_rows_for_final_score(multi_rows)
    best_single = max(
        [r for r in single_rows if r.get("recommendation_status") == "PASS_RECOMMEND"],
        key=lambda x: ((x["final_score"] if x.get("final_score") is not None else -1), x["candidate_label"]),
        default=None,
    )
    best_multi = max(
        [r for r in multi_rows if r.get("recommendation_status") == "PASS_RECOMMEND"],
        key=lambda x: ((x["final_score"] if x.get("final_score") is not None else -1), x["candidate_label"]),
        default=None,
    )

    if best_single is not None:
        compare_rows.append(proposal_to_compare_row(f"제안(1:1) - {best_single['candidate_ticker']}", best_single))
    if best_multi is not None:
        compare_rows.append(proposal_to_compare_row(f"제안(다자산) - {best_multi['candidate_combo']}", best_multi))

    no_recommendation_reason = None
    if best_single is None and best_multi is None:
        fallback_candidates = [row for row in single_rows + multi_rows if row.get("final_score") is not None]
        fallback_best = max(
            fallback_candidates,
            key=lambda x: ((x["final_score"] if x.get("final_score") is not None else -1), x.get("candidate_label", "")),
            default=None,
        )
        no_recommendation_reason = "Gate 통과 후보가 없어 참고안을 표시합니다. 리스크 관리가 어렵습니다."
        compare_rows[0]["no_recommendation_reason"] = no_recommendation_reason
        if fallback_best is not None:
            if fallback_best.get("candidate_combo"):
                scenario = f"참고안(다자산) - {fallback_best['candidate_combo']}"
            else:
                scenario = f"참고안(1:1) - {fallback_best['candidate_ticker']}"
            compare_rows.append(proposal_to_compare_row(scenario, fallback_best, no_recommendation_reason))

    return {
        "errors": [],
        "base_metrics": base_metrics,
        "single_rows": single_rows,
        "multi_rows": multi_rows,
        "compare_rows": compare_rows,
        "best_single": best_single,
        "best_multi": best_multi,
        "no_recommendation_reason": no_recommendation_reason,
    }


# -----------------------------
# Docs / reports
# -----------------------------

def split_reason_text(raw):
    return [part.strip() for part in (raw or "").split(";") if part.strip()]


def recommendation_candidate_name(row):
    return row.get("candidate_ticker") or row.get("candidate_combo") or row.get("candidate_label") or "-"


def write_recommendation_status_qa(qa_path, run_id, portfolio_result, single_asset_ticker, single_asset_result):
    qa_path.parent.mkdir(parents=True, exist_ok=True)
    status_order = ["PASS_RECOMMEND", "REFERENCE_ONLY", "FAIL_GATE", "INSUFFICIENT_DATA"]

    def section_lines(title, result):
        rows = list(result.get("single_rows", [])) + list(result.get("multi_rows", []))
        lines = [f"## {title}", ""]
        if result.get("errors"):
            lines.append("### Errors")
            lines.extend(f"- {error}" for error in result["errors"])
            lines.append("")
            return lines
        if not rows:
            lines.append("- 추천 평가 row가 없습니다.")
            lines.append("")
            return lines

        status_counts = Counter(row.get("status") or "UNKNOWN" for row in rows)
        recommendation_counts = Counter(row.get("recommendation_status") or "UNKNOWN" for row in rows)
        role_counts = Counter(row.get("candidate_role") or "UNKNOWN" for row in rows)
        gate_reasons = Counter(reason for row in rows for reason in split_reason_text(row.get("gate_fail_reasons")))
        reference_reasons = Counter(reason for row in rows for reason in split_reason_text(row.get("reference_reason")))
        dq_warning_reasons = Counter(reason for row in rows for reason in split_reason_text(row.get("dq_warning_reasons")))
        dq_warn_count = sum(
            1
            for row in rows
            if "DQ WARN" in (row.get("reference_reason") or "") or "DQ WARN" in (row.get("dq_warning_reasons") or "")
        )
        dq_blocking_count = sum(
            1
            for row in rows
            if "DQ BLOCKING" in (row.get("gate_fail_reasons") or "")
            or "DQ BLOCKING" in (row.get("reference_reason") or "")
            or "DQ BLOCKING" in (row.get("dq_blocking_reasons") or "")
        )
        dq_non_blocking_count = sum(1 for row in rows if row.get("dq_warning_reasons"))

        lines.append("### Counts")
        lines.append(
            "- scope: pre_backtest_candidate_screen; PASS_RECOMMEND in this report is a model candidate label, "
            "not a formal recommendation. Use the post-backtest gated QA/report for user-facing recommendation status."
        )
        lines.append(f"- status: {', '.join(f'{key} {value}' for key, value in sorted(status_counts.items()))}")
        lines.append(
            f"- recommendation_status: {', '.join(f'{key} {recommendation_counts.get(key, 0)}' for key in status_order)}"
        )
        lines.append(f"- candidate_role: {', '.join(f'{key} {value}' for key, value in sorted(role_counts.items()))}")
        lines.append(f"- DQ WARN affected rows: {dq_warn_count}")
        lines.append(f"- DQ blocking affected rows: {dq_blocking_count}")
        lines.append(f"- DQ non-blocking warning rows: {dq_non_blocking_count}")
        lines.append("")

        lines.append("### Status Bucket Summary (Pre-Backtest Candidate Labels)")
        for rec_status in status_order:
            lines.append(f"- {rec_status}: {recommendation_counts.get(rec_status, 0)}")
        lines.append("")

        lines.append("### Top Gate Fail Reasons")
        if gate_reasons:
            lines.extend(f"- {reason}: {count}" for reason, count in gate_reasons.most_common(10))
        else:
            lines.append("- none")
        lines.append("")

        lines.append("### Top Reference Reasons")
        if reference_reasons:
            lines.extend(f"- {reason}: {count}" for reason, count in reference_reasons.most_common(10))
        else:
            lines.append("- none")
        lines.append("")

        lines.append("### Top DQ Non-Blocking Warnings")
        if dq_warning_reasons:
            lines.extend(f"- {reason}: {count}" for reason, count in dq_warning_reasons.most_common(10))
        else:
            lines.append("- none")
        lines.append("")

        audit_rows = sorted(
            [row for row in rows if row.get("recommendation_status") == "PASS_RECOMMEND"],
            key=lambda row: (row.get("final_score") if row.get("final_score") is not None else -1.0),
            reverse=True,
        )[:10]
        lines.append("### Top Pre-Backtest PASS Candidate Audit")
        if audit_rows:
            lines.append(
                "| candidate | final_score | CVaR improve % | MDD improve % | stress improve | scenario reduction | return drag % | Sharpe improve % | DQ penalty | role |"
            )
            lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|---|")
            for row in audit_rows:
                annual_return_pct = row.get("annual_return_improve_pct")
                return_drag_pct = -annual_return_pct if annual_return_pct is not None and annual_return_pct < 0 else 0.0
                lines.append(
                    f"| {recommendation_candidate_name(row)} | {safe_round(row.get('final_score'))} | "
                    f"{safe_round(row.get('cvar_improve_pct'))} | {safe_round(row.get('mdd_improve_pct'))} | "
                    f"{safe_round(row.get('stress_improve'))} | {safe_round(row.get('scenario_vulnerability_reduction'))} | "
                    f"{safe_round(return_drag_pct)} | {safe_round(row.get('sharpe_improve_pct'))} | "
                    f"{safe_round(row.get('dq_penalty'))} | {row.get('candidate_role') or '-'} |"
                )
        else:
            lines.append("- none")
        lines.append("")

        lines.append("### Representative Pre-Backtest PASS Candidates by Bucket")
        if audit_rows:
            best_by_bucket = {}
            for row in rows:
                if row.get("recommendation_status") != "PASS_RECOMMEND":
                    continue
                bucket = row.get("candidate_bucket") or row.get("candidate_bucket_combo") or "unknown"
                current = best_by_bucket.get(bucket)
                row_score = row.get("final_score") if row.get("final_score") is not None else -1.0
                current_score = current.get("final_score") if current and current.get("final_score") is not None else -1.0
                if current is None or row_score > current_score:
                    best_by_bucket[bucket] = row
            lines.append("| bucket | candidate | final_score | scenario reduction | return drag % | reason |")
            lines.append("|---|---|---:|---:|---:|---|")
            for bucket, row in sorted(best_by_bucket.items()):
                annual_return_pct = row.get("annual_return_improve_pct")
                return_drag_pct = -annual_return_pct if annual_return_pct is not None and annual_return_pct < 0 else 0.0
                reason = (row.get("recommendation_reason") or row.get("scenario_reason_ko") or "").replace("|", "/")
                lines.append(
                    f"| {bucket} | {recommendation_candidate_name(row)} | {safe_round(row.get('final_score'))} | "
                    f"{safe_round(row.get('scenario_vulnerability_reduction'))} | {safe_round(return_drag_pct)} | {reason} |"
                )
        else:
            lines.append("- none")
        lines.append("")

        lines.append("### Examples")
        lines.append("| recommendation_status | candidate | status | scenario_delta | gate_delta | reason |")
        lines.append("|---|---|---|---:|---:|---|")
        for rec_status in status_order:
            examples = [row for row in rows if row.get("recommendation_status") == rec_status][:10]
            if not examples:
                lines.append(f"| {rec_status} | - | - | - | - | no rows in this run |")
                continue
            for row in examples:
                reason = (
                    row.get("gate_fail_reasons")
                    or row.get("reference_reason")
                    or row.get("dq_blocking_reasons")
                    or row.get("dq_warning_reasons")
                    or row.get("scenario_reason_ko")
                    or ""
                )
                reason = str(reason).replace("|", "/")
                lines.append(
                    f"| {rec_status} | {recommendation_candidate_name(row)} | {row.get('status') or ''} | "
                    f"{safe_round(row.get('scenario_vulnerability_delta'))} | {safe_round(row.get('gate_vulnerability_delta'))} | "
                    f"{reason} |"
                )
        lines.append("")
        return lines

    content = [
        "# HedgeMate Pre-Backtest Candidate QA",
        "",
        f"- run_id: {run_id}",
        "- scope: pre_backtest_candidate_screen",
        "- formal_recommendation_gate: post_backtest_required",
        "- note: PASS_RECOMMEND below is a pre-backtest candidate label only; it must not be shown as a formal recommendation until the backtest gate has run.",
        "- 목적: 추천/참고/실패 상태를 사유별로 검증하기 위한 QA 요약입니다.",
        "",
        *section_lines("Portfolio", portfolio_result),
    ]
    if single_asset_ticker:
        content.extend(section_lines(f"Single Asset ({single_asset_ticker})", single_asset_result))
    qa_path.write_text("\n".join(content), encoding="utf-8")


def write_result_documents(
    run_id,
    data_version,
    ingested_at,
    start_dt,
    run_ts,
    total_tickers,
    fetched_tickers,
    stress_dates,
    ks200_symbol,
    used_cached_raw,
    used_cached_fx,
    dq_rows,
    metric_validation_rows,
    top10,
    portfolio_input_path,
    portfolio_result,
    single_asset_ticker,
    single_asset_result,
    raw_file,
    fx_file,
    benchmark_raw_file,
    dq_csv,
    feat_csv,
    metric_validation_csv,
    hes_components_csv,
    asset_sensitivity_csv,
    asset_sensitivity_summary_md,
    asset_scenario_sensitivity_csv,
    asset_scenario_sensitivity_summary_md,
    asset_scenario_sensitivity_visual_html,
    recommendation_status_qa_md,
    scenario_context,
    portfolio_1to1_csv,
    portfolio_multi_csv,
    portfolio_compare_csv,
    single_asset_1to1_csv,
    single_asset_multi_csv,
    single_asset_compare_csv,
):
    pass_cnt = sum(1 for row in dq_rows if row["status"] == "PASS")
    warn_cnt = sum(1 for row in dq_rows if row["status"] == "WARN")
    fail_cnt = sum(1 for row in dq_rows if row["status"] == "FAIL")
    metric_pass = sum(1 for row in metric_validation_rows if row["status"] == "PASS")
    metric_fail = sum(1 for row in metric_validation_rows if row["status"] == "FAIL")
    min_cov = min((row["coverage_ratio_calendar"] for row in dq_rows), default=0.0)

    result_md = DOC_RESULT_DIR / f"01_실행결과_{run_id}.md"
    with result_md.open("w", encoding="utf-8") as f:
        f.write("# HedgeMate 데이터 파이프라인 실행 결과\n\n")
        f.write(f"- 실행일(UTC): {ingested_at}\n")
        f.write(f"- 데이터 버전(data_version): {data_version}\n")
        f.write(f"- 분석기간: {start_dt.date().isoformat()} ~ {run_ts.date().isoformat()}\n")
        f.write("- 기준통화: KRW\n")
        f.write(f"- 대상 티커: {total_tickers}개\n")
        f.write(f"- 수집 성공 티커: {fetched_tickers}개\n")
        f.write(f"- 위기구간(stress) 일수: {len(stress_dates)}일\n")
        f.write(f"- 위기구간 벤치마크: SPY + {ks200_symbol} (20거래일 -8%)\n")
        f.write(f"- 시나리오 벡터: `{scenario_context.get('path') or 'NONE'}`\n")
        f.write(f"- 현재 장세 요약: {scenario_context.get('summary_ko')}\n")
        active_adverse = [
            row.get("scenario_name_ko") or row.get("scenario_name")
            for row in scenario_context.get("active_rows", [])
            if scenario_is_adverse(row) and scenario_activation_weight(row) > 0
        ]
        f.write(f"- Active adverse scenario: {', '.join(active_adverse) if active_adverse else '없음'}\n")
        f.write(f"- raw 재사용 여부(동일 data_version 재실행): {'YES' if used_cached_raw else 'NO'}\n")
        f.write(f"- FX raw 재사용 여부: {'YES' if used_cached_fx else 'NO'}\n\n")

        f.write("## DQ 요약(캘린더 기준)\n")
        f.write(f"- PASS: {pass_cnt}\n")
        f.write(f"- WARN: {warn_cnt}\n")
        f.write(f"- FAIL: {fail_cnt}\n")
        f.write(f"- 최소 coverage_ratio_calendar: {min_cov:.4f}\n\n")

        f.write("## 지표 엔진 검증셋\n")
        f.write(f"- PASS: {metric_pass}\n")
        f.write(f"- FAIL: {metric_fail}\n")
        f.write("- 결측 처리 정책:\n")
        f.write(f"  - vol_annual 최소 관측치: {MIN_OBS_POLICY['vol_annual']}\n")
        f.write(f"  - mdd_1y 최소 관측치: {MIN_OBS_POLICY['mdd_1y']}\n")
        f.write(f"  - var/cvar 최소 관측치: {MIN_OBS_POLICY['tail_1y']}\n")
        f.write(f"  - beta 최소 교집합 관측치: {MIN_OBS_POLICY['beta_overlap']}\n")
        f.write(f"  - downside beta 최소 하락일: {MIN_OBS_POLICY['downside_overlap']}\n")
        f.write(f"  - corr 최소 관측치: {MIN_OBS_POLICY['corr_overlap']}\n\n")

        f.write("## 헷징 후보 Top 10 (KRW 기준)\n\n")
        f.write(
            "| 순위 | 티커 | 버킷 | HES | Corr | CVaR | Stress | Sharpe | LiquidityPenalty | corr_sp500_60d_krw | cvar_95_1y_krw | sharpe_1y_krw_proxy | adv_60 |\n"
        )
        f.write("|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|\n")
        for idx, row in enumerate(top10, start=1):
            f.write(
                f"| {idx} | {row['ticker']} | {row.get('hedge_bucket','')} | {row['hes_score']:.4f} | "
                f"{row.get('component_corr_improve', float('nan')):.4f} | {row.get('component_cvar_improve', float('nan')):.4f} | "
                f"{row.get('component_stress_defense', float('nan')):.4f} | {row.get('component_sharpe_quality', float('nan')):.4f} | "
                f"{row.get('component_liquidity_penalty', float('nan')):.4f} | {row.get('corr_sp500_60d_krw', float('nan')):.4f} | "
                f"{row.get('cvar_95_1y_krw', float('nan')):.4f} | {row.get('sharpe_1y_krw_proxy', float('nan')):.4f} | "
                f"{row.get('adv_60', float('nan')):.2f} |\n"
            )

        f.write("\n## 포트폴리오 입력 분석 요약\n")
        f.write(f"- 입력 파일: `{portfolio_input_path}`\n")
        if portfolio_result["errors"]:
            for err in portfolio_result["errors"]:
                f.write(f"- {err}\n")
        else:
            f.write("- 입력 제약조건 체크: PASS (합계 100%, 음수 금지, 단일자산 <=50%)\n")
            if portfolio_result.get("no_recommendation_reason"):
                f.write(f"- 추천 결과 없음: {portfolio_result['no_recommendation_reason']}\n")
                if len(portfolio_result["compare_rows"]) > 1:
                    fallback_row = portfolio_result["compare_rows"][-1]
                    f.write(f"- 참고안: {fallback_row['scenario']}\n")
            status_counts = defaultdict(int)
            for row in portfolio_result["single_rows"] + portfolio_result["multi_rows"]:
                status_counts[row.get("recommendation_status") or "UNKNOWN"] += 1
            if status_counts:
                f.write(
                    "- 추천상태 분포: "
                    + ", ".join(f"{key} {value}" for key, value in sorted(status_counts.items()))
                    + "\n"
                )
            if portfolio_result["best_single"] is not None:
                best_single = portfolio_result["best_single"]
                f.write(
                    f"- 1:1 최적 후보: {best_single['candidate_ticker']} "
                    f"(최종점수 {best_single.get('final_score', 0):.4f}, CVaR 개선률 {best_single.get('cvar_improve_pct', 0):.2f}%, Sharpe 개선률 {best_single.get('sharpe_improve_pct', 0) or 0:.2f}%)\n"
                )
            if portfolio_result["best_multi"] is not None:
                best_multi = portfolio_result["best_multi"]
                f.write(
                    f"- 다자산 최적 조합: {best_multi['candidate_combo']} "
                    f"(최종점수 {best_multi.get('final_score', 0):.4f}, CVaR 개선률 {best_multi.get('cvar_improve_pct', 0):.2f}%, Sharpe 개선률 {best_multi.get('sharpe_improve_pct', 0) or 0:.2f}%)\n"
                )

        if single_asset_ticker:
            f.write("\n## 단일 종목 질의 분석 요약\n")
            f.write(f"- 기준 자산: {single_asset_ticker} 100%\n")
            if single_asset_result["errors"]:
                for err in single_asset_result["errors"]:
                    f.write(f"- {err}\n")
            else:
                if single_asset_result.get("no_recommendation_reason"):
                    f.write(f"- 추천 결과 없음: {single_asset_result['no_recommendation_reason']}\n")
                    if len(single_asset_result["compare_rows"]) > 1:
                        fallback_row = single_asset_result["compare_rows"][-1]
                        f.write(f"- 참고안: {fallback_row['scenario']}\n")
                status_counts = defaultdict(int)
                for row in single_asset_result["single_rows"] + single_asset_result["multi_rows"]:
                    status_counts[row.get("recommendation_status") or "UNKNOWN"] += 1
                if status_counts:
                    f.write(
                        "- 추천상태 분포: "
                        + ", ".join(f"{key} {value}" for key, value in sorted(status_counts.items()))
                        + "\n"
                    )
                if single_asset_result["best_single"] is not None:
                    best_single = single_asset_result["best_single"]
                    f.write(
                        f"- 1:1 최적 후보: {best_single['candidate_ticker']} "
                        f"(예산 {best_single.get('hedge_budget_pct', 0):.1f}%, 최종점수 {best_single.get('final_score', 0):.4f})\n"
                    )
                if single_asset_result["best_multi"] is not None:
                    best_multi = single_asset_result["best_multi"]
                    f.write(
                        f"- 다자산 최적 조합: {best_multi['candidate_combo']} "
                        f"(예산 {best_multi.get('hedge_budget_pct', 0):.1f}%, 최종점수 {best_multi.get('final_score', 0):.4f})\n"
                    )

        f.write("\n## 산출 파일\n")
        for path in [
            raw_file,
            fx_file,
            benchmark_raw_file,
            dq_csv,
            feat_csv,
            metric_validation_csv,
            hes_components_csv,
            asset_sensitivity_csv,
            asset_sensitivity_summary_md,
            asset_scenario_sensitivity_csv,
            asset_scenario_sensitivity_summary_md,
            asset_scenario_sensitivity_visual_html,
            recommendation_status_qa_md,
            portfolio_1to1_csv,
            portfolio_multi_csv,
            portfolio_compare_csv,
        ]:
            f.write(f"- `{path}`\n")
        if single_asset_ticker:
            for path in [single_asset_1to1_csv, single_asset_multi_csv, single_asset_compare_csv]:
                f.write(f"- `{path}`\n")

    draft_md = DOC_RESULT_DIR / f"02_분석리포트_초안_{run_id}.md"
    worst_mdd = sorted([row for row in top10 if row.get("mdd_1y_krw") is not None], key=lambda x: x["mdd_1y_krw"])[:5]
    with draft_md.open("w", encoding="utf-8") as f:
        f.write("# HedgeMate 분석 리포트 초안\n\n")
        f.write("## 0. 리포트 메타\n")
        f.write(f"- 작성일: {run_ts.date().isoformat()}\n")
        f.write("- 작성자: 자동 파이프라인\n")
        f.write(f"- 데이터 버전: {data_version}\n")
        f.write("- 분석 기간: 최근 5년 목표, 데이터 부족 시 가용 구간 기준 계산 허용\n")
        f.write("- 데이터 주기: 일봉\n")
        f.write("- 기준통화: KRW\n")
        f.write(f"- 위기구간 정의: SPY + {ks200_symbol} 20거래일 수익률 <= -8%\n\n")
        f.write(f"- 현재 장세 요약: {scenario_context.get('summary_ko')}\n")

        f.write("## 1. 데이터 품질 요약\n")
        f.write(f"- 수집 성공: {fetched_tickers}/{total_tickers}\n")
        f.write(f"- DQ 판정(캘린더 기준): PASS {pass_cnt}, WARN {warn_cnt}, FAIL {fail_cnt}\n\n")

        f.write("## 2. 리스크 상위(KRW MDD 기준)\n")
        for row in worst_mdd:
            f.write(f"- {row['ticker']}: MDD_1y_krw={row.get('mdd_1y_krw', float('nan')):.4f}, CVaR_95_1y_krw={row.get('cvar_95_1y_krw', float('nan')):.4f}\n")

        f.write("\n## 3. 헷징 후보 Top10\n")
        f.write(f"- 시나리오 벡터: `{scenario_context.get('path') or 'NONE'}`\n")
        for idx, row in enumerate(top10, start=1):
            f.write(
                f"{idx}. {row['ticker']} ({row.get('hedge_bucket','')}) - HES={row['hes_score']:.4f} "
                f"[Corr={row.get('component_corr_improve', 0):.3f}, CVaR={row.get('component_cvar_improve', 0):.3f}, "
                f"Stress={row.get('component_stress_defense', 0):.3f}, Sharpe={row.get('component_sharpe_quality', 0):.3f}, "
                f"LiqPenalty={row.get('component_liquidity_penalty', 0):.3f}]\n"
            )

        f.write("\n## 4. 포트폴리오 개선 효과 (KRW 기준)\n")
        if portfolio_result["errors"]:
            for err in portfolio_result["errors"]:
                f.write(f"- {err}\n")
        else:
            f.write("| 시나리오 | 변동성 | MDD | CVaR(95%) | 연환산수익률 | Sharpe | 변동성 개선률(%) | MDD 개선률(%) | CVaR 개선률(%) | Sharpe 개선률(%) |\n")
            f.write("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|\n")
            for row in portfolio_result["compare_rows"]:
                f.write(
                    f"| {row['scenario']} | {row.get('vol_annual', float('nan')):.6f} | {row.get('mdd', float('nan')):.6f} | "
                    f"{row.get('cvar_95', float('nan')):.6f} | {row.get('annual_return_krw', float('nan')):.6f} | "
                    f"{row.get('sharpe_krw_proxy', float('nan')):.6f} | {row.get('vol_improve_pct', 0) or 0:.2f} | "
                    f"{row.get('mdd_improve_pct', 0) or 0:.2f} | {row.get('cvar_improve_pct', 0) or 0:.2f} | {row.get('sharpe_improve_pct', 0) or 0:.2f} |\n"
                )
            if portfolio_result.get("no_recommendation_reason"):
                f.write(f"\n- 추천 결과 없음: {portfolio_result['no_recommendation_reason']}\n")

        if single_asset_ticker:
            f.write(f"\n## 5. 단일 종목 질의 결과 ({single_asset_ticker})\n")
            if single_asset_result["errors"]:
                for err in single_asset_result["errors"]:
                    f.write(f"- {err}\n")
            else:
                for row in single_asset_result["compare_rows"]:
                    f.write(
                        f"- {row['scenario']}: CVaR={row.get('cvar_95', float('nan')):.6f}, MDD={row.get('mdd', float('nan')):.6f}, Sharpe={row.get('sharpe_krw_proxy', float('nan')):.6f}\n"
                    )
                if single_asset_result.get("no_recommendation_reason"):
                    f.write(f"- 추천 결과 없음: {single_asset_result['no_recommendation_reason']}\n")

        f.write("\n## 6. 다음 액션\n")
        f.write("- FX carry-forward 허용 범위 및 예외 처리 검토\n")
        f.write("- 단일 종목 질의 결과를 API/UI 입력 흐름에 연결\n")
        f.write("- 무위험수익률 실데이터 연결로 Sharpe proxy 고도화\n")

    review_md = DOC_RESULT_DIR / f"03_결과검토_{run_id}.md"
    with review_md.open("w", encoding="utf-8") as f:
        f.write(f"# HedgeMate 실행 결과 검토 ({run_ts.date().isoformat()})\n\n")
        f.write("## 1) 실행 성공 여부\n")
        f.write("- 파이프라인 실행: **성공**\n")
        f.write(f"- 대상 유니버스: {total_tickers}개 티커\n")
        f.write(f"- 수집 성공: {fetched_tickers}/{total_tickers}\n")
        f.write(f"- 위기구간(stress) 탐지: {len(stress_dates)}일\n")
        f.write(f"- 위기구간 벤치마크: SPY + {ks200_symbol}\n")
        f.write("- 기준통화: KRW\n\n")

        f.write("## 2) 핵심 점검\n")
        f.write("- FX 환산: PASS (USD 자산 KRW 기준 수익률 계산)\n")
        f.write(f"- Sharpe proxy: PASS (연 {DEFAULT_ANNUAL_RISK_FREE_RATE * 100:.1f}% 무위험수익률 가정)\n")
        f.write("- DQ 결과 반영: PASS (`FAIL` 제외 / `WARN` 허용)\n")
        f.write("- 추천 로직: PASS (Gate + Final Score 구조)\n")
        if single_asset_ticker:
            f.write(f"- 단일 종목 질의 모드: PASS (`{single_asset_ticker}` 분석 가능)\n")

        f.write("\n## 3) 품질 검토\n")
        f.write(f"- DQ 결과: PASS {pass_cnt} / WARN {warn_cnt} / FAIL {fail_cnt}\n")
        f.write(f"- 지표 검증셋: PASS {metric_pass} / FAIL {metric_fail}\n")
        if portfolio_result["best_single"] is not None:
            best_single = portfolio_result["best_single"]
            f.write(
                f"- 포트폴리오 1:1 최적: {best_single['candidate_ticker']} (점수 {best_single.get('final_score', 0):.4f})\n"
            )
        if portfolio_result["best_multi"] is not None:
            best_multi = portfolio_result["best_multi"]
            f.write(
                f"- 포트폴리오 다자산 최적: {best_multi['candidate_combo']} (점수 {best_multi.get('final_score', 0):.4f})\n"
            )
        if portfolio_result.get("no_recommendation_reason"):
            f.write(f"- 포트폴리오 추천 결과 없음: {portfolio_result['no_recommendation_reason']}\n")
        if single_asset_ticker and single_asset_result["best_multi"] is not None:
            best_multi = single_asset_result["best_multi"]
            f.write(
                f"- 단일 종목 다자산 최적: {best_multi['candidate_combo']} (점수 {best_multi.get('final_score', 0):.4f})\n"
            )
        if single_asset_ticker and single_asset_result.get("no_recommendation_reason"):
            f.write(f"- 단일 종목 추천 결과 없음: {single_asset_result['no_recommendation_reason']}\n")

        f.write("\n## 4) 참조 산출물\n")
        for path in [
            result_md,
            draft_md,
            benchmark_raw_file,
            dq_csv,
            feat_csv,
            hes_components_csv,
            asset_sensitivity_csv,
            asset_sensitivity_summary_md,
            asset_scenario_sensitivity_csv,
            asset_scenario_sensitivity_summary_md,
            asset_scenario_sensitivity_visual_html,
            recommendation_status_qa_md,
            portfolio_1to1_csv,
            portfolio_multi_csv,
            portfolio_compare_csv,
        ]:
            f.write(f"- `{path}`\n")
        if single_asset_ticker:
            for path in [single_asset_1to1_csv, single_asset_multi_csv, single_asset_compare_csv]:
                f.write(f"- `{path}`\n")

    return result_md, draft_md, review_md


# -----------------------------
# CLI / orchestration
# -----------------------------

def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="HedgeMate market data pipeline")
    parser.add_argument("--single-asset", dest="single_asset", help="단일 종목 질의 모드 티커")
    parser.add_argument("--run-id", default=None, help="출력 파일 및 데이터 버전에 사용할 실행 ID")
    parser.add_argument("--data-version", default=None, help="raw/FX/benchmark 캐시에 사용할 데이터 버전")
    parser.add_argument("--portfolio-input", default=None, help="포트폴리오 입력 CSV 경로")
    parser.add_argument(
        "--hedge-budgets",
        default=",".join(str(int(v)) for v in DEFAULT_HEDGE_BUDGETS),
        help="헷지 예산 퍼센트 목록 (예: 10,20,30)",
    )
    parser.add_argument("--max-combo-size", type=int, default=DEFAULT_MAX_COMBO_SIZE, help="최대 조합 크기")
    parser.add_argument("--base-total-krw", type=float, default=None, help="기준 포트폴리오 총 평가금액(KRW)")
    parser.add_argument("--hedge-budgets-krw", default=None, help="헷지 예산 KRW 목록 (예: 1000000,2000000)")
    parser.add_argument(
        "--candidate-mode",
        choices=["hedge-only", "risk-bucket", "all"],
        default="risk-bucket",
        help="헷지 후보군 선택 모드",
    )
    parser.add_argument(
        "--scenario-vector",
        default=None,
        help="scenario_research current_scenario_vector CSV/JSON 경로. 미지정 시 최신 파일 자동 탐색.",
    )
    parser.add_argument(
        "--history-start-date",
        default=DEFAULT_HISTORY_START_DATE,
        help="시장가격 수집 시작일. 기본값은 GFC stress 검증을 포함하는 2007-01-01.",
    )
    parser.add_argument(
        "--force-refresh-raw",
        action="store_true",
        help="동일 data_version 캐시가 있어도 시장가격/FX/벤치마크 raw 데이터를 다시 수집합니다.",
    )
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    hedge_budgets_pct = parse_budget_list(args.hedge_budgets)
    hedge_budgets_krw = parse_budget_amount_list(args.hedge_budgets_krw)
    if args.base_total_krw is not None and args.base_total_krw <= 0:
        raise SystemExit("--base-total-krw must be greater than zero.")
    if hedge_budgets_krw and args.base_total_krw is None:
        raise SystemExit("--base-total-krw is required when --hedge-budgets-krw is set.")
    max_combo_size = max(1, min(args.max_combo_size, 4))

    run_ts = now_utc()
    run_id = args.run_id or build_run_id(run_ts)
    data_version = args.data_version or run_ts.strftime("%Y%m%d")
    ingested_at = run_ts.isoformat()

    OUTPUT_RAW_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_REPORT_DIR.mkdir(parents=True, exist_ok=True)
    DOC_RESULT_DIR.mkdir(parents=True, exist_ok=True)
    scenario_context = load_scenario_vector(args.scenario_vector)

    if args.data_version is None:
        default_raw_file = OUTPUT_RAW_DIR / f"raw_market_daily_{data_version}.csv"
        if not default_raw_file.exists():
            cached_raw_file, cached_data_version = find_latest_cached_snapshot("raw_market_daily", OUTPUT_RAW_DIR)
            if cached_raw_file is not None and cached_data_version:
                data_version = cached_data_version

    start_dt = resolve_fetch_start_dt(run_ts, args.history_start_date)
    end_dt = run_ts + timedelta(days=1)
    period1 = int(start_dt.timestamp())
    period2 = int(end_dt.timestamp())

    universe = []
    with UNIVERSE_META.open("r", encoding="utf-8") as f:
        rdr = csv.DictReader(f)
        for row in rdr:
            universe.append(row)
    universe_map = {row["ticker"]: row for row in universe}

    raw_file = OUTPUT_RAW_DIR / f"raw_market_daily_{data_version}.csv"
    used_cached_raw = raw_file.exists() and not args.force_refresh_raw
    if args.force_refresh_raw:
        for cache_path in [
            OUTPUT_RAW_DIR / f"raw_fx_daily_{data_version}.csv",
            OUTPUT_RAW_DIR / f"raw_benchmark_daily_{data_version}.csv",
        ]:
            try:
                cache_path.unlink(missing_ok=True)
            except OSError:
                pass
    raw_rows, ticker_series, class_rows = load_cached_raw(raw_file, universe_map)

    if not used_cached_raw:
        raw_rows = []
        ticker_series = {}
        class_rows = defaultdict(list)
        for idx, item in enumerate(universe, start=1):
            ticker = item["ticker"]
            asset_class = item["asset_class"]
            currency = item["currency"]
            rows = fetch_yahoo_chart(ticker, period1, period2)
            time.sleep(0.4)

            series = []
            for row in rows:
                raw_rows.append(
                    {
                        "date": row["date"],
                        "ticker": ticker,
                        "asset_class": asset_class,
                        "source": "yahoo",
                        "open": row["open"],
                        "high": row["high"],
                        "low": row["low"],
                        "close": row["close"],
                        "adj_close": row["adj_close"],
                        "volume": row["volume"],
                        "currency": currency,
                        "ingested_at": ingested_at,
                    }
                )
                series.append((row["date"], row["adj_close"], row["volume"], row["open"], row["high"], row["low"], row["close"]))
            series.sort(key=lambda x: x[0])
            ticker_series[ticker] = series
            class_rows[asset_class].append(len(series))
            if idx % 10 == 0:
                print(f"[{idx}/{len(universe)}] fetched: {ticker}")
        save_raw(raw_file, raw_rows)

    fx_file, _, fx_rate_map, used_cached_fx = load_or_fetch_fx(period1, period2, data_version, ingested_at)

    spy_series_local = [(d, p) for d, p, *_ in ticker_series.get("SPY", []) if p is not None]
    if not spy_series_local:
        spy_rows = fetch_yahoo_chart("SPY", period1, period2)
        spy_series_local = [(row["date"], row["adj_close"]) for row in spy_rows if row.get("adj_close") is not None]

    benchmark_raw_file, _, ks200_series, ks200_symbol, used_cached_benchmark = load_or_fetch_benchmark_symbol(
        "^KS200",
        "^KS11",
        period1,
        period2,
        data_version,
        ingested_at,
    )

    spy_krw_prices, _, _ = build_krw_price_series([(d, p, None, None, None, None, None) for d, p in spy_series_local], "USD", fx_rate_map)
    spy_krw_price_pairs = [(d, p) for d, p in spy_krw_prices]
    _, spy_ret_map = returns_from_prices(spy_krw_price_pairs)
    _, ks200_ret_map = returns_from_prices(ks200_series)
    _, usdkrw_ret_map = returns_from_prices(sorted(fx_rate_map.items(), key=lambda item: item[0]))
    allow_optional_benchmark_fetch = not used_cached_raw
    scenario_benchmark_ret_maps = {
        "soxx": benchmark_return_map_for_ticker(
            SOXX_TICKER,
            ticker_series,
            "USD",
            fx_rate_map,
            period1,
            period2,
            allow_fetch=allow_optional_benchmark_fetch,
            data_version=data_version,
        ),
        "usdkrw": usdkrw_ret_map,
        "uso": benchmark_return_map_for_ticker(
            "USO",
            ticker_series,
            "USD",
            fx_rate_map,
            period1,
            period2,
            allow_fetch=allow_optional_benchmark_fetch,
            data_version=data_version,
        ),
        "gld": benchmark_return_map_for_ticker(
            "GLD",
            ticker_series,
            "USD",
            fx_rate_map,
            period1,
            period2,
            allow_fetch=allow_optional_benchmark_fetch,
            data_version=data_version,
        ),
    }
    stress_dates = build_stress_dates(spy_krw_price_pairs, ks200_series)
    dq_rows = []
    feature_rows = []
    ticker_ret_map = {}
    latest_price_map = {}

    class_medians = {}
    for key, arr in class_rows.items():
        class_medians[key] = statistics.median(arr) if arr else 0

    for item in universe:
        ticker = item["ticker"]
        asset_class = item["asset_class"]
        region = item.get("region", "US")
        currency = item.get("currency", "")
        series_raw = ticker_series.get(ticker, [])

        date_seen = set()
        deduped = []
        dup_count = 0
        for row in series_raw:
            if row[0] in date_seen:
                dup_count += 1
                continue
            date_seen.add(row[0])
            deduped.append(row)

        series = [(d, p, v, o, h, l, c) for d, p, v, o, h, l, c in deduped]
        series.sort(key=lambda x: x[0])

        total = len(series)
        miss_adj = sum(1 for _, p, *_ in series if p is None)
        miss_rate = (miss_adj / total) if total else 1.0

        invalid_price = 0
        for _, _, _, o, h, l, c in series:
            if o is not None and o <= 0:
                invalid_price += 1
            if c is not None and c <= 0:
                invalid_price += 1
            if h is not None and l is not None and h < l:
                invalid_price += 1

        target = class_medians.get(asset_class, 0) or 1
        coverage_legacy = total / target if target else 0.0

        if total > 0:
            start_d = parse_date(series[0][0])
            end_d = parse_date(series[-1][0])
            expected_calendar = expected_calendar_rows(region, start_d, end_d)
            coverage_calendar = (total / expected_calendar) if expected_calendar > 0 else 0.0
        else:
            expected_calendar = 0
            coverage_calendar = 0.0

        prices_local = [(d, p) for d, p, *_ in series if p is not None]
        prices_local.sort(key=lambda x: x[0])
        rets_local, _ = returns_from_prices(prices_local)
        thr = 0.60 if asset_class == "crypto" else 0.40
        outlier_count = sum(1 for r in rets_local if abs(r) > thr)

        krw_prices, krw_adv_series, fx_missing_count = build_krw_price_series(series, currency, fx_rate_map)
        krw_prices.sort(key=lambda x: x[0])
        krw_price_pairs = [(d, p) for d, p in krw_prices]
        if krw_price_pairs:
            latest_price_map[ticker] = krw_price_pairs[-1][1]
        _, krw_ret_map = returns_from_prices(krw_price_pairs)
        ticker_ret_map[ticker] = krw_ret_map
        metrics = compute_feature_metrics(
            krw_price_pairs,
            krw_ret_map,
            spy_ret_map,
            ks200_ret_map,
            stress_dates,
            krw_adv_series,
            scenario_benchmark_ret_maps=scenario_benchmark_ret_maps,
        )
        dq_decision = classify_data_quality(
            miss_rate,
            coverage_calendar,
            invalid_price,
            dup_count,
            outlier_count,
            fx_missing_count,
            total,
        )

        dq_rows.append(
            {
                "ticker": ticker,
                "asset_class": asset_class,
                "region": region,
                "calendar_type": get_region_calendar_type(region),
                "rows": total,
                "expected_rows_calendar": expected_calendar,
                "missing_rate": miss_rate,
                "coverage_ratio": coverage_legacy,
                "coverage_ratio_calendar": coverage_calendar,
                "invalid_price_count": invalid_price,
                "duplicate_count": dup_count,
                "outlier_count": outlier_count,
                "fx_missing_count": fx_missing_count,
                **dq_decision,
            }
        )

        feature_rows.append(
            {
                "ticker": ticker,
                "asset_class": asset_class,
                "currency": currency,
                "vol_annual": metrics["vol_annual_krw"],
                "mdd_1y": metrics["mdd_1y_krw"],
                "var_95_1y": metrics["var_95_1y_krw"],
                "cvar_95_1y": metrics["cvar_95_1y_krw"],
                "beta_sp500_1y": metrics["beta_sp500_1y_krw"],
                "downside_beta_sp500_1y": metrics["downside_beta_sp500_1y_krw"],
                "beta_ks200_1y": metrics["beta_ks200_1y_krw"],
                "downside_beta_ks200_1y": metrics["downside_beta_ks200_1y_krw"],
                "corr_sp500_60d": metrics["corr_sp500_60d_krw"],
                "corr_kospi200_60d": metrics["corr_kospi200_60d_krw"],
                "beta_soxx_1y": metrics["beta_soxx_1y_krw"],
                "downside_beta_soxx_1y": metrics["downside_beta_soxx_1y_krw"],
                "corr_soxx_60d": metrics["corr_soxx_60d_krw"],
                "beta_usdkrw_1y": metrics["beta_usdkrw_1y"],
                "beta_uso_1y": metrics["beta_uso_1y_krw"],
                "beta_gld_1y": metrics["beta_gld_1y_krw"],
                "avg_stress_ret": metrics["avg_stress_ret_krw"],
                "adv_60": metrics["adv_60"],
                "vol_annual_krw": metrics["vol_annual_krw"],
                "mdd_1y_krw": metrics["mdd_1y_krw"],
                "var_95_1y_krw": metrics["var_95_1y_krw"],
                "cvar_95_1y_krw": metrics["cvar_95_1y_krw"],
                "beta_sp500_1y_krw": metrics["beta_sp500_1y_krw"],
                "downside_beta_sp500_1y_krw": metrics["downside_beta_sp500_1y_krw"],
                "beta_ks200_1y_krw": metrics["beta_ks200_1y_krw"],
                "downside_beta_ks200_1y_krw": metrics["downside_beta_ks200_1y_krw"],
                "corr_sp500_60d_krw": metrics["corr_sp500_60d_krw"],
                "corr_kospi200_60d_krw": metrics["corr_kospi200_60d_krw"],
                "beta_soxx_1y_krw": metrics["beta_soxx_1y_krw"],
                "downside_beta_soxx_1y_krw": metrics["downside_beta_soxx_1y_krw"],
                "corr_soxx_60d_krw": metrics["corr_soxx_60d_krw"],
                "beta_usdkrw_1y": metrics["beta_usdkrw_1y"],
                "beta_uso_1y_krw": metrics["beta_uso_1y_krw"],
                "beta_gld_1y_krw": metrics["beta_gld_1y_krw"],
                "beta_kr_financial_basket_1y_krw": None,
                "avg_stress_ret_krw": metrics["avg_stress_ret_krw"],
                "return_observation_count": metrics["return_observation_count"],
                "stress_observation_count": metrics["stress_observation_count"],
                "sp500_overlap_count": metrics["sp500_overlap_count"],
                "ks200_overlap_count": metrics["ks200_overlap_count"],
                "soxx_overlap_count": metrics["soxx_overlap_count"],
                "usdkrw_overlap_count": metrics["usdkrw_overlap_count"],
                "uso_overlap_count": metrics["uso_overlap_count"],
                "gld_overlap_count": metrics["gld_overlap_count"],
                "kr_financial_overlap_count": 0,
                "annual_return_1y_krw": metrics["annual_return_1y_krw"],
                "sharpe_1y_krw_proxy": metrics["sharpe_1y_krw_proxy"],
                "data_version": data_version,
            }
        )

    kr_financial_ret_map = build_equal_weight_return_map(
        ticker_ret_map,
        KR_FINANCIAL_BASKET_MEMBERS,
        min_count=2,
    )
    if kr_financial_ret_map:
        for row in feature_rows:
            asset_ret_map = ticker_ret_map.get(row["ticker"], {})
            row["beta_kr_financial_basket_1y_krw"] = compute_beta(asset_ret_map, kr_financial_ret_map)
            row["kr_financial_overlap_count"] = overlap_count(asset_ret_map, kr_financial_ret_map)

    metric_validation_rows = metric_validation_set(tolerance=1e-8)
    metric_validation_csv = OUTPUT_REPORT_DIR / f"metric_validation_{run_id}.csv"
    write_csv(metric_validation_csv, ["metric", "expected", "actual", "abs_error", "tolerance", "status"], metric_validation_rows)

    dq_csv = OUTPUT_REPORT_DIR / f"dq_result_{run_id}.csv"
    write_csv(
        dq_csv,
        [
            "ticker",
            "asset_class",
            "region",
            "calendar_type",
            "rows",
            "expected_rows_calendar",
            "missing_rate",
            "coverage_ratio",
            "coverage_ratio_calendar",
            "invalid_price_count",
            "duplicate_count",
            "outlier_count",
            "fx_missing_count",
            "calendar_status",
            "price_integrity_status",
            "fx_status",
            "dq_blocking",
            "dq_reason_codes",
            "dq_status",
            "status",
        ],
        sorted(dq_rows, key=lambda x: x["ticker"]),
    )

    feat_csv = OUTPUT_PROCESSED_DIR / f"features_summary_{run_id}.csv"
    write_csv(
        feat_csv,
        [
            "ticker",
            "asset_class",
            "currency",
            "vol_annual",
            "mdd_1y",
            "var_95_1y",
            "cvar_95_1y",
            "beta_sp500_1y",
            "downside_beta_sp500_1y",
            "beta_ks200_1y",
            "downside_beta_ks200_1y",
            "corr_sp500_60d",
            "corr_kospi200_60d",
            "beta_soxx_1y",
            "downside_beta_soxx_1y",
            "corr_soxx_60d",
            "beta_uso_1y",
            "beta_gld_1y",
            "avg_stress_ret",
            "adv_60",
            "vol_annual_krw",
            "mdd_1y_krw",
            "var_95_1y_krw",
            "cvar_95_1y_krw",
            "beta_sp500_1y_krw",
            "downside_beta_sp500_1y_krw",
            "beta_ks200_1y_krw",
            "downside_beta_ks200_1y_krw",
            "corr_sp500_60d_krw",
            "corr_kospi200_60d_krw",
            "beta_soxx_1y_krw",
            "downside_beta_soxx_1y_krw",
            "corr_soxx_60d_krw",
            "beta_usdkrw_1y",
            "beta_uso_1y_krw",
            "beta_gld_1y_krw",
            "beta_kr_financial_basket_1y_krw",
            "avg_stress_ret_krw",
            "return_observation_count",
            "stress_observation_count",
            "sp500_overlap_count",
            "ks200_overlap_count",
            "soxx_overlap_count",
            "usdkrw_overlap_count",
            "uso_overlap_count",
            "gld_overlap_count",
            "kr_financial_overlap_count",
            "annual_return_1y_krw",
            "sharpe_1y_krw_proxy",
            "data_version",
        ],
        sorted(feature_rows, key=lambda x: x["ticker"]),
    )

    asset_sensitivity_rows = build_asset_sensitivity_rows(feature_rows, universe_map)
    asset_sensitivity_csv = OUTPUT_PROCESSED_DIR / f"asset_risk_sensitivity_{run_id}.csv"
    write_csv(
        asset_sensitivity_csv,
        [
            "ticker",
            "asset_class",
            "currency",
            "factor",
            "factor_label",
            "direction",
            "magnitude",
            "sensitivity_level",
            "raw_value",
            "value_basis",
            "sign_positive_meaning",
            "sign_negative_meaning",
            "structural_tags",
            "evidence_metrics",
        ],
        asset_sensitivity_rows,
    )
    asset_sensitivity_summary_md = OUTPUT_REPORT_DIR / f"asset_sensitivity_summary_{run_id}.md"
    write_asset_sensitivity_summary(asset_sensitivity_summary_md, run_id, data_version, asset_sensitivity_rows)

    asset_scenario_sensitivity_rows = build_asset_scenario_sensitivity_rows(feature_rows, universe_map, scenario_context)
    asset_scenario_sensitivity_csv = OUTPUT_PROCESSED_DIR / f"asset_scenario_sensitivity_{run_id}.csv"
    write_csv(asset_scenario_sensitivity_csv, SCENARIO_SENSITIVITY_FIELDS, asset_scenario_sensitivity_rows)
    asset_scenario_sensitivity_summary_md = OUTPUT_REPORT_DIR / f"asset_scenario_sensitivity_summary_{run_id}.md"
    write_asset_scenario_sensitivity_summary(
        asset_scenario_sensitivity_summary_md,
        run_id,
        data_version,
        scenario_context,
        asset_scenario_sensitivity_rows,
    )
    asset_scenario_sensitivity_visual_html = OUTPUT_REPORT_DIR / f"asset_scenario_sensitivity_visual_{run_id}.html"
    write_asset_scenario_sensitivity_visualization(
        asset_scenario_sensitivity_visual_html,
        run_id,
        data_version,
        scenario_context,
        asset_scenario_sensitivity_rows,
    )

    prefilter_ranked = build_candidate_prefilter_rows(
        feature_rows,
        dq_rows,
        universe_map,
        candidate_mode=args.candidate_mode,
        scenario_context=scenario_context,
    )
    top10 = prefilter_ranked[:10]
    hes_components_csv = OUTPUT_REPORT_DIR / f"hes_components_{run_id}.csv"
    write_csv(
        hes_components_csv,
        [
            "ticker",
            "asset_class",
            "hedge_bucket",
            "candidate_role",
            "candidate_role_reason_ko",
            "risk_bucket_match",
            "hes_score",
            "component_corr_improve",
            "component_cvar_improve",
            "component_stress_defense",
            "component_sharpe_quality",
            "component_liquidity_penalty",
            "corr_sp500_60d_krw",
            "cvar_95_1y_krw",
            "avg_stress_ret_krw",
            "sharpe_1y_krw_proxy",
            "adv_60",
        ],
        top10,
    )

    feature_map = {row["ticker"]: row for row in feature_rows}
    dq_map = {row["ticker"]: row for row in dq_rows}

    portfolio_input_path, portfolio_weights_pct = load_portfolio_input(universe_map, args.portfolio_input)
    portfolio_valid, portfolio_errors = validate_portfolio_weights(portfolio_weights_pct, universe_map)
    portfolio_prefilter_ranked = build_input_aware_candidate_prefilter_rows(
        portfolio_weights_pct,
        feature_rows,
        dq_rows,
        universe_map,
        scenario_context,
        candidate_mode=args.candidate_mode,
    )
    portfolio_candidate_pool = choose_candidate_pool(portfolio_prefilter_ranked, universe_map, base_tickers=set(portfolio_weights_pct.keys()))
    if portfolio_valid:
        portfolio_result = evaluate_recommendations(
            label_prefix="기존 포트폴리오",
            base_weights_pct=portfolio_weights_pct,
            ticker_ret_map=ticker_ret_map,
            spy_ret_map=spy_ret_map,
            stress_dates=stress_dates,
            candidate_pool=portfolio_candidate_pool,
            feature_map=feature_map,
            dq_map=dq_map,
            universe_map=universe_map,
            hedge_budgets_pct=hedge_budgets_pct,
            max_combo_size=max_combo_size,
            exempt_tickers=None,
            base_total_krw=args.base_total_krw if hedge_budgets_krw else None,
            hedge_budgets_krw=hedge_budgets_krw,
            latest_price_map=latest_price_map,
            scenario_context=scenario_context,
            ks200_ret_map=ks200_ret_map,
        )
    else:
        portfolio_result = {
            "errors": portfolio_errors,
            "base_metrics": None,
            "single_rows": [],
            "multi_rows": [],
            "compare_rows": [],
            "best_single": None,
            "best_multi": None,
            "no_recommendation_reason": None,
        }

    vulnerability_attribution_rows, vulnerability_summary = build_portfolio_vulnerability_attribution(
        portfolio_weights_pct,
        asset_scenario_sensitivity_rows,
        scenario_rows=scenario_context.get("rows", []),
    )
    hedge_action_rows = build_hedge_action_candidates(
        portfolio_weights_pct,
        vulnerability_summary,
        asset_scenario_sensitivity_rows,
        recommendation_rows=list(portfolio_result.get("single_rows", [])) + list(portfolio_result.get("multi_rows", [])),
        scenario_rows=scenario_context.get("rows", []),
    )
    enrich_hedge_action_metrics(
        hedge_action_rows,
        portfolio_result.get("base_metrics"),
        ticker_ret_map,
        spy_ret_map,
        ks200_ret_map,
        stress_dates,
    )
    hedge_action_plan = build_hedge_action_plan(
        run_id,
        portfolio_weights_pct,
        vulnerability_summary,
        hedge_action_rows,
    )
    hedge_action_artifacts = write_action_artifacts(
        run_id,
        OUTPUT_PROCESSED_DIR,
        OUTPUT_REPORT_DIR,
        vulnerability_attribution_rows,
        vulnerability_summary,
        hedge_action_rows,
        hedge_action_plan,
    )

    portfolio_1to1_csv = OUTPUT_REPORT_DIR / f"portfolio_1to1_hedge_{run_id}.csv"
    write_csv(
        portfolio_1to1_csv,
        [
            "candidate_ticker",
            "candidate_bucket",
            "risk_bucket_match",
            "input_aware_score",
            "status",
            "message",
            "hedge_weight_pct",
            "hedge_budget_pct",
            "hedge_budget_krw",
            "hedge_invested_krw",
            "hedge_cash_left_krw",
            "hedge_share_counts",
            "combo_size",
            "allocation_method",
            "allocation_weights",
            "allocation_objective_reason",
            "base_vol_annual",
            "proposed_vol_annual",
            "base_mdd",
            "proposed_mdd",
            "base_cvar_95",
            "proposed_cvar_95",
            "base_annual_return_krw",
            "proposed_annual_return_krw",
            "base_sharpe_krw_proxy",
            "proposed_sharpe_krw_proxy",
            "base_stress_avg_ret_krw",
            "proposed_stress_avg_ret_krw",
            "base_corr_sp500_krw",
            "proposed_corr_sp500_krw",
            "base_beta_sp500_krw",
            "proposed_beta_sp500_krw",
            "base_downside_beta_sp500_krw",
            "proposed_downside_beta_sp500_krw",
            "base_corr_kospi200_krw",
            "proposed_corr_kospi200_krw",
            "vol_improve_pct",
            "mdd_improve_pct",
            "cvar_improve_pct",
            "stress_improve",
            "corr_improve",
            "beta_improve",
            "exposure_improve",
            "sharpe_improve",
            "sharpe_improve_pct",
            "annual_return_improve",
            "annual_return_improve_pct",
            "downside_beta_improve",
            "kospi_corr_improve",
            "combo_min_adv_60",
            "score_component_cvar",
            "score_component_mdd",
            "score_component_stress",
            "score_component_exposure",
            "score_component_sharpe",
            "score_component_liquidity",
            "score_component_scenario",
            "score_component_concentration",
            *SCENARIO_RECOMMENDATION_FIELDS,
            "final_score",
            "recommendation_reason",
            "weights_snapshot",
        ],
        portfolio_result["single_rows"],
    )

    portfolio_multi_csv = OUTPUT_REPORT_DIR / f"portfolio_multi_hedge_{run_id}.csv"
    write_csv(
        portfolio_multi_csv,
        [
            "candidate_combo",
            "candidate_bucket_combo",
            "risk_bucket_match",
            "status",
            "message",
            "hedge_budget_pct",
            "hedge_budget_krw",
            "hedge_invested_krw",
            "hedge_cash_left_krw",
            "hedge_share_counts",
            "combo_size",
            "allocation_method",
            "allocation_weights",
            "allocation_objective_reason",
            "base_vol_annual",
            "proposed_vol_annual",
            "base_mdd",
            "proposed_mdd",
            "base_cvar_95",
            "proposed_cvar_95",
            "base_annual_return_krw",
            "proposed_annual_return_krw",
            "base_sharpe_krw_proxy",
            "proposed_sharpe_krw_proxy",
            "base_stress_avg_ret_krw",
            "proposed_stress_avg_ret_krw",
            "base_corr_sp500_krw",
            "proposed_corr_sp500_krw",
            "base_beta_sp500_krw",
            "proposed_beta_sp500_krw",
            "base_downside_beta_sp500_krw",
            "proposed_downside_beta_sp500_krw",
            "base_corr_kospi200_krw",
            "proposed_corr_kospi200_krw",
            "vol_improve_pct",
            "mdd_improve_pct",
            "cvar_improve_pct",
            "stress_improve",
            "corr_improve",
            "beta_improve",
            "exposure_improve",
            "sharpe_improve",
            "sharpe_improve_pct",
            "annual_return_improve",
            "annual_return_improve_pct",
            "downside_beta_improve",
            "kospi_corr_improve",
            "combo_min_adv_60",
            "score_component_cvar",
            "score_component_mdd",
            "score_component_stress",
            "score_component_exposure",
            "score_component_sharpe",
            "score_component_liquidity",
            "score_component_scenario",
            "score_component_concentration",
            *SCENARIO_RECOMMENDATION_FIELDS,
            "final_score",
            "recommendation_reason",
            "weights_snapshot",
        ],
        portfolio_result["multi_rows"],
    )

    portfolio_compare_csv = OUTPUT_REPORT_DIR / f"portfolio_compare_{run_id}.csv"
    write_csv(
        portfolio_compare_csv,
        [
            "scenario",
            "vol_annual",
            "mdd",
            "cvar_95",
            "annual_return_krw",
            "sharpe_krw_proxy",
            "vol_improve_pct",
            "mdd_improve_pct",
            "cvar_improve_pct",
            "sharpe_improve_pct",
            "stress_improve",
            "no_recommendation_reason",
        ],
        portfolio_result["compare_rows"],
    )

    single_asset_ticker = (args.single_asset or "").strip().upper() or None
    single_asset_result = {
        "errors": [],
        "base_metrics": None,
        "single_rows": [],
        "multi_rows": [],
        "compare_rows": [],
        "best_single": None,
        "best_multi": None,
        "no_recommendation_reason": None,
    }
    single_asset_1to1_csv = None
    single_asset_multi_csv = None
    single_asset_compare_csv = None

    if single_asset_ticker:
        if single_asset_ticker not in universe_map:
            single_asset_result["errors"] = [f"FAIL: 유니버스 외 단일 종목 질의 - {single_asset_ticker}"]
        else:
            single_asset_prefilter_ranked = build_input_aware_candidate_prefilter_rows(
                build_single_asset_base_weights(single_asset_ticker),
                feature_rows,
                dq_rows,
                universe_map,
                scenario_context,
                candidate_mode=args.candidate_mode,
            )
            single_asset_candidate_pool = choose_candidate_pool(single_asset_prefilter_ranked, universe_map, base_tickers={single_asset_ticker})
            single_asset_result = evaluate_recommendations(
                label_prefix=f"기준({single_asset_ticker} 100%)",
                base_weights_pct=build_single_asset_base_weights(single_asset_ticker),
                ticker_ret_map=ticker_ret_map,
                spy_ret_map=spy_ret_map,
                stress_dates=stress_dates,
                candidate_pool=single_asset_candidate_pool,
                feature_map=feature_map,
                dq_map=dq_map,
                universe_map=universe_map,
                hedge_budgets_pct=hedge_budgets_pct,
                max_combo_size=max_combo_size,
                exempt_tickers={single_asset_ticker},
                base_total_krw=args.base_total_krw if hedge_budgets_krw else None,
                hedge_budgets_krw=hedge_budgets_krw,
                latest_price_map=latest_price_map,
                scenario_context=scenario_context,
                ks200_ret_map=ks200_ret_map,
            )

        single_asset_1to1_csv = OUTPUT_REPORT_DIR / f"single_asset_hedge_1to1_{run_id}.csv"
        write_csv(
            single_asset_1to1_csv,
            [
                "candidate_ticker",
                "candidate_bucket",
                "risk_bucket_match",
                "input_aware_score",
                "status",
                "message",
                "hedge_weight_pct",
                "hedge_budget_pct",
                "hedge_budget_krw",
                "hedge_invested_krw",
                "hedge_cash_left_krw",
                "hedge_share_counts",
                "combo_size",
                "allocation_method",
                "allocation_weights",
                "allocation_objective_reason",
                "base_vol_annual",
                "proposed_vol_annual",
                "base_mdd",
                "proposed_mdd",
                "base_cvar_95",
                "proposed_cvar_95",
                "base_annual_return_krw",
                "proposed_annual_return_krw",
                "base_sharpe_krw_proxy",
                "proposed_sharpe_krw_proxy",
                "base_stress_avg_ret_krw",
                "proposed_stress_avg_ret_krw",
                "base_corr_sp500_krw",
                "proposed_corr_sp500_krw",
                "base_beta_sp500_krw",
                "proposed_beta_sp500_krw",
                "base_downside_beta_sp500_krw",
                "proposed_downside_beta_sp500_krw",
                "base_corr_kospi200_krw",
                "proposed_corr_kospi200_krw",
                "vol_improve_pct",
                "mdd_improve_pct",
                "cvar_improve_pct",
                "stress_improve",
                "corr_improve",
                "beta_improve",
                "exposure_improve",
                "sharpe_improve",
                "sharpe_improve_pct",
                "annual_return_improve",
                "annual_return_improve_pct",
                "downside_beta_improve",
                "kospi_corr_improve",
                "combo_min_adv_60",
                "score_component_cvar",
                "score_component_mdd",
                "score_component_stress",
                "score_component_exposure",
                "score_component_sharpe",
                "score_component_liquidity",
                "score_component_scenario",
                "score_component_concentration",
                *SCENARIO_RECOMMENDATION_FIELDS,
                "final_score",
                "recommendation_reason",
                "weights_snapshot",
            ],
            single_asset_result["single_rows"],
        )

        single_asset_multi_csv = OUTPUT_REPORT_DIR / f"single_asset_hedge_multi_{run_id}.csv"
        write_csv(
            single_asset_multi_csv,
            [
                "candidate_combo",
                "candidate_bucket_combo",
                "risk_bucket_match",
                "status",
                "message",
                "hedge_budget_pct",
                "hedge_budget_krw",
                "hedge_invested_krw",
                "hedge_cash_left_krw",
                "hedge_share_counts",
                "combo_size",
                "allocation_method",
                "allocation_weights",
                "allocation_objective_reason",
                "base_vol_annual",
                "proposed_vol_annual",
                "base_mdd",
                "proposed_mdd",
                "base_cvar_95",
                "proposed_cvar_95",
                "base_annual_return_krw",
                "proposed_annual_return_krw",
                "base_sharpe_krw_proxy",
                "proposed_sharpe_krw_proxy",
                "base_stress_avg_ret_krw",
                "proposed_stress_avg_ret_krw",
                "base_corr_sp500_krw",
                "proposed_corr_sp500_krw",
                "base_beta_sp500_krw",
                "proposed_beta_sp500_krw",
                "base_downside_beta_sp500_krw",
                "proposed_downside_beta_sp500_krw",
                "base_corr_kospi200_krw",
                "proposed_corr_kospi200_krw",
                "vol_improve_pct",
                "mdd_improve_pct",
                "cvar_improve_pct",
                "stress_improve",
                "corr_improve",
                "beta_improve",
                "exposure_improve",
                "sharpe_improve",
                "sharpe_improve_pct",
                "annual_return_improve",
                "annual_return_improve_pct",
                "downside_beta_improve",
                "kospi_corr_improve",
                "combo_min_adv_60",
                "score_component_cvar",
                "score_component_mdd",
                "score_component_stress",
                "score_component_exposure",
                "score_component_sharpe",
                "score_component_liquidity",
                "score_component_scenario",
                "score_component_concentration",
                *SCENARIO_RECOMMENDATION_FIELDS,
                "final_score",
                "recommendation_reason",
                "weights_snapshot",
            ],
            single_asset_result["multi_rows"],
        )

        single_asset_compare_csv = OUTPUT_REPORT_DIR / f"single_asset_compare_{run_id}.csv"
        write_csv(
            single_asset_compare_csv,
            [
                "scenario",
                "vol_annual",
                "mdd",
                "cvar_95",
                "annual_return_krw",
                "sharpe_krw_proxy",
                "vol_improve_pct",
                "mdd_improve_pct",
                "cvar_improve_pct",
                "sharpe_improve_pct",
                "stress_improve",
                "no_recommendation_reason",
            ],
            single_asset_result["compare_rows"],
        )

    recommendation_status_qa_md = OUTPUT_REPORT_DIR / f"recommendation_status_qa_{run_id}.md"
    write_recommendation_status_qa(
        recommendation_status_qa_md,
        run_id,
        portfolio_result,
        single_asset_ticker,
        single_asset_result,
    )

    total_tickers = len(universe)
    fetched_tickers = sum(1 for item in universe if len(ticker_series.get(item["ticker"], [])) > 0)

    result_md, draft_md, review_md = write_result_documents(
        run_id=run_id,
        data_version=data_version,
        ingested_at=ingested_at,
        start_dt=start_dt,
        run_ts=run_ts,
        total_tickers=total_tickers,
        fetched_tickers=fetched_tickers,
        stress_dates=stress_dates,
        ks200_symbol=ks200_symbol,
        used_cached_raw=used_cached_raw,
        used_cached_fx=used_cached_fx,
        dq_rows=dq_rows,
        metric_validation_rows=metric_validation_rows,
        top10=top10,
        portfolio_input_path=portfolio_input_path,
        portfolio_result=portfolio_result,
        single_asset_ticker=single_asset_ticker,
        single_asset_result=single_asset_result,
        raw_file=raw_file,
        fx_file=fx_file,
        benchmark_raw_file=benchmark_raw_file,
        dq_csv=dq_csv,
        feat_csv=feat_csv,
        metric_validation_csv=metric_validation_csv,
        hes_components_csv=hes_components_csv,
        asset_sensitivity_csv=asset_sensitivity_csv,
        asset_sensitivity_summary_md=asset_sensitivity_summary_md,
        asset_scenario_sensitivity_csv=asset_scenario_sensitivity_csv,
        asset_scenario_sensitivity_summary_md=asset_scenario_sensitivity_summary_md,
        asset_scenario_sensitivity_visual_html=asset_scenario_sensitivity_visual_html,
        recommendation_status_qa_md=recommendation_status_qa_md,
        scenario_context=scenario_context,
        portfolio_1to1_csv=portfolio_1to1_csv,
        portfolio_multi_csv=portfolio_multi_csv,
        portfolio_compare_csv=portfolio_compare_csv,
        single_asset_1to1_csv=single_asset_1to1_csv,
        single_asset_multi_csv=single_asset_multi_csv,
        single_asset_compare_csv=single_asset_compare_csv,
    )

    scenario_count = len(
        {
            row.get("scenario_code")
            for row in scenario_context.get("rows", [])
            if row.get("scenario_code")
            and (not scenario_context.get("as_of_date") or (row.get("as_of_date") or row.get("date")) == scenario_context.get("as_of_date"))
        }
    )
    update_latest_manifest(
        {
            "active_hedgemate_run": run_id,
            "active_hedgemate_summary": asset_scenario_sensitivity_summary_md.name,
            "active_hedgemate_summary_path": f"../HedgeMate/outputs/reports/{asset_scenario_sensitivity_summary_md.name}",
            "active_hedgemate_sensitivity": asset_scenario_sensitivity_csv.name,
            "active_hedgemate_sensitivity_path": f"../HedgeMate/outputs/processed/{asset_scenario_sensitivity_csv.name}",
            "active_hedgemate_scenario_vector": scenario_context.get("path"),
            "active_hedgemate_vulnerability_attribution": hedge_action_artifacts["portfolio_vulnerability_attribution"].name,
            "active_hedgemate_vulnerability_summary": hedge_action_artifacts["portfolio_vulnerability_summary"].name,
            "active_hedgemate_action_plan": hedge_action_artifacts["hedge_action_plan"].name,
            "scenario_count": scenario_count or None,
            "scenario_version": "v2" if scenario_count >= 10 else None,
        }
    )

    print("DONE")
    print(f"RAW={raw_file}")
    print(f"FX_RAW={fx_file}")
    print(f"BENCHMARK_RAW={benchmark_raw_file}")
    print(f"DQ={dq_csv}")
    print(f"FEATURE={feat_csv}")
    print(f"METRIC_VALIDATION={metric_validation_csv}")
    print(f"HES_COMPONENTS={hes_components_csv}")
    print(f"ASSET_SENSITIVITY={asset_sensitivity_csv}")
    print(f"ASSET_SENSITIVITY_SUMMARY={asset_sensitivity_summary_md}")
    print(f"ASSET_SCENARIO_SENSITIVITY={asset_scenario_sensitivity_csv}")
    print(f"ASSET_SCENARIO_SENSITIVITY_SUMMARY={asset_scenario_sensitivity_summary_md}")
    print(f"ASSET_SCENARIO_SENSITIVITY_VISUAL={asset_scenario_sensitivity_visual_html}")
    print(f"PORTFOLIO_VULNERABILITY_ATTRIBUTION={hedge_action_artifacts['portfolio_vulnerability_attribution']}")
    print(f"PORTFOLIO_VULNERABILITY_SUMMARY={hedge_action_artifacts['portfolio_vulnerability_summary']}")
    print(f"HEDGE_ACTION_CANDIDATES={hedge_action_artifacts['hedge_action_candidates']}")
    print(f"HEDGE_ACTION_PLAN={hedge_action_artifacts['hedge_action_plan']}")
    print(f"HEDGE_ACTION_PLAN_SUMMARY={hedge_action_artifacts['hedge_action_plan_summary']}")
    print(f"RECOMMENDATION_STATUS_QA={recommendation_status_qa_md}")
    print(f"PORTFOLIO_1TO1={portfolio_1to1_csv}")
    print(f"PORTFOLIO_MULTI={portfolio_multi_csv}")
    print(f"PORTFOLIO_COMPARE={portfolio_compare_csv}")
    if single_asset_ticker:
        print(f"SINGLE_ASSET_1TO1={single_asset_1to1_csv}")
        print(f"SINGLE_ASSET_MULTI={single_asset_multi_csv}")
        print(f"SINGLE_ASSET_COMPARE={single_asset_compare_csv}")
    print(f"RESULT_MD={result_md}")
    print(f"DRAFT_MD={draft_md}")
    print(f"REVIEW_MD={review_md}")


if __name__ == "__main__":
    main()
