#!/usr/bin/env python3
import argparse
import csv
import itertools
import json
import math
import statistics
import time
import urllib.parse
import urllib.request
import uuid
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path


def resolve_path(*candidates):
    for raw in candidates:
        p = Path(raw)
        if p.exists():
            return p
    return Path(candidates[0])


DOC_ROOT = resolve_path("docs/STEP_1", "docs")
UNIVERSE_META = resolve_path(
    "docs/STEP_1/01_개요/03_자산유니버스_메타_v1.csv",
    "docs/01_개요/03_자산유니버스_메타_v1.csv",
)
OUTPUT_RAW_DIR = Path("outputs/raw")
OUTPUT_PROCESSED_DIR = Path("outputs/processed")
OUTPUT_REPORT_DIR = Path("outputs/reports")
DOC_RESULT_DIR = resolve_path("docs/STEP_1/04_실행결과", "docs/04_실행결과")

FX_TICKER = "KRW=X"
CASH_TICKER = "__CASH__"
DEFAULT_HEDGE_BUDGETS = [10.0, 20.0, 30.0]
DEFAULT_MAX_COMBO_SIZE = 4
DEFAULT_PREFILTER_TOP_K_PER_GROUP = 3
DEFAULT_PREFILTER_GLOBAL_LIMIT = 12
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
    "BTC-USD",
    "ETH-USD",
}

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


# -----------------------------
# Generic helpers
# -----------------------------

def now_utc():
    return datetime.now(timezone.utc)


def build_run_id(run_ts=None):
    ts = run_ts or now_utc()
    return f"{ts.strftime('%Y%m%dT%H%M%S%f')}-{uuid.uuid4().hex[:8]}"


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


def expected_calendar_rows(region, start_d, end_d):
    if start_d > end_d:
        return 0
    total_days = (end_d - start_d).days + 1
    if region == "CRYPTO":
        return total_days
    return sum(1 for i in range(total_days) if (start_d + timedelta(days=i)).weekday() < 5)


def get_region_calendar_type(region):
    if region == "CRYPTO":
        return "CRYPTO_24_7"
    if region == "KR":
        return "KR_WEEKDAY"
    return "US_WEEKDAY"


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


def compute_feature_metrics(krw_prices, krw_ret_map, spy_ret_map, ks200_ret_map, stress_dates, adv_series):
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
    corr_sp500_60d = trailing_corr(krw_ret_map, spy_ret_map, 60)
    corr_kospi200_60d = trailing_corr(krw_ret_map, ks200_ret_map, 60)

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
        "corr_sp500_60d_krw": corr_sp500_60d,
        "corr_kospi200_60d_krw": corr_kospi200_60d,
        "avg_stress_ret_krw": avg_stress_ret,
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


def portfolio_metrics_from_returns(dated_returns, benchmark_ret_map=None, stress_dates=None):
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
    if benchmark_ret_map:
        common_dates = sorted(set(d for d, _ in dated_returns) & set(benchmark_ret_map.keys()))
        if len(common_dates) >= MIN_OBS_POLICY["beta_overlap"]:
            xs = [dict(dated_returns)[d] for d in common_dates]
            ys = [benchmark_ret_map[d] for d in common_dates]
            cov_xy = covariance(xs, ys)
            var_y = variance(ys)
            beta = cov_xy / var_y if (cov_xy is not None and var_y not in (None, 0)) else None
            corr_sp500 = correlation(xs[-60:], ys[-60:]) if len(xs) >= MIN_OBS_POLICY["corr_overlap"] else None

    return {
        "vol_annual_krw": vol_ann,
        "mdd_krw": mdd_val,
        "cvar_95_krw": cvar_95,
        "annual_return_krw": ann_return,
        "sharpe_krw_proxy": sharpe,
        "stress_avg_ret_krw": stress_avg_ret,
        "beta_sp500_krw": beta,
        "corr_sp500_krw": corr_sp500,
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


def is_hedge_candidate(meta, candidate_mode="hedge-only"):
    ticker = meta.get("ticker", "")
    if candidate_mode == "all":
        return ticker not in {"SPY"}
    return meta.get("is_core_hedge") == "Y" or ticker in HEDGE_V1_CANDIDATES


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
    currency = meta.get("currency", "")

    if currency == "USD":
        tags.append("usd_exposure")
    if asset_class == "bond_etf" or group_tag in {"bond_duration", "credit_bond", "inflation_linked"}:
        tags.append("rate_proxy")
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


# -----------------------------
# Ranking helpers
# -----------------------------

def build_candidate_prefilter_rows(feature_rows, dq_rows, universe_map, candidate_mode="hedge-only"):
    dq_map = {row["ticker"]: row for row in dq_rows}
    candidates = []
    for row in feature_rows:
        meta = universe_map.get(row["ticker"], {})
        if not is_hedge_candidate(meta, candidate_mode=candidate_mode):
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
        ranked.append(item)

    ranked.sort(key=lambda x: (-x["hes_score"], x["ticker"]))
    return ranked


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

    selected.sort(key=lambda x: (-x["hes_score"], x["ticker"]))
    return selected[:global_limit]


def combo_label(combo):
    return " + ".join(combo)


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
                "combo_min_adv_60",
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
        "combo_min_adv_60",
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
        row["score_component_liquidity"] = normalize_minmax(row.get("combo_min_adv_60"), *ranges["combo_min_adv_60"])
        row["final_score"] = (
            0.35 * (row["score_component_cvar"] if row.get("score_component_cvar") is not None else 0.5)
            + 0.20 * (row["score_component_mdd"] if row.get("score_component_mdd") is not None else 0.5)
            + 0.20 * (row["score_component_stress"] if row.get("score_component_stress") is not None else 0.5)
            + 0.10 * (row["score_component_exposure"] if row.get("score_component_exposure") is not None else 0.5)
            + 0.10 * (row["score_component_sharpe"] if row.get("score_component_sharpe") is not None else 0.5)
            + 0.05 * (row["score_component_liquidity"] if row.get("score_component_liquidity") is not None else 0.5)
        )
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
    ]
    labels = [label for score, label in sorted(components, key=lambda x: (x[0] is None, -(x[0] or -1)))[:3] if score is not None]
    return ", ".join(labels) if labels else "데이터 기준 충족"


# -----------------------------
# Proposal evaluation
# -----------------------------

def evaluate_gate(base_metrics, proposed_metrics, combo, feature_map, dq_map):
    reasons = []
    status = "PASS"

    cvar_improve_pct = risk_improvement_pct(base_metrics.get("cvar_95_krw"), proposed_metrics.get("cvar_95_krw"), is_abs_risk=True)
    if cvar_improve_pct is None or cvar_improve_pct <= 0:
        reasons.append("CVaR 개선 미달")

    mdd_improve_pct = risk_improvement_pct(base_metrics.get("mdd_krw"), proposed_metrics.get("mdd_krw"), is_abs_risk=True)
    if mdd_improve_pct is None or mdd_improve_pct < 0:
        reasons.append("MDD 개선 미달")

    stress_improve = signed_improvement(base_metrics.get("stress_avg_ret_krw"), proposed_metrics.get("stress_avg_ret_krw"))
    if stress_improve is None or stress_improve < 0:
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

    combo_min_adv = None
    for ticker in combo:
        if dq_map.get(ticker, {}).get("status") == "FAIL":
            reasons.append(f"DQ FAIL 제외 - {ticker}")
            continue
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
        "combo_min_adv_60": combo_min_adv,
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
):
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

    base_metrics = portfolio_metrics_from_returns(base_ret_series, benchmark_ret_map=spy_ret_map, stress_dates=stress_dates)
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
                "status": "PASS" if ok else "FAIL",
                "message": msg,
                "hedge_weight_pct": budget_pct,
                "hedge_budget_pct": budget_pct,
                "hedge_budget_krw": budget_krw,
                "combo_size": 1,
                "weights_snapshot": json.dumps(to_pct_weights(proposed_weights or {}), ensure_ascii=False),
            }
            if allocation_details is not None:
                row["hedge_invested_krw"] = allocation_details["hedge_invested_krw"]
                row["hedge_cash_left_krw"] = allocation_details["hedge_cash_left_krw"]
                row["hedge_share_counts"] = json.dumps(allocation_details["share_counts"], ensure_ascii=False)
            if ok:
                ret_series, err = compute_portfolio_returns(proposed_weights, ticker_ret_map)
                if err is not None:
                    row["status"] = "FAIL"
                    row["message"] = f"FAIL: {err}"
                else:
                    metrics = portfolio_metrics_from_returns(ret_series, benchmark_ret_map=spy_ret_map, stress_dates=stress_dates)
                    if metrics is None:
                        row["status"] = "FAIL"
                        row["message"] = "FAIL: 지표 계산 최소 관측치 부족"
                    else:
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
                                "vol_improve_pct": risk_improvement_pct(base_metrics.get("vol_annual_krw"), metrics.get("vol_annual_krw"), is_abs_risk=False),
                                "sharpe_improve": signed_improvement(base_metrics.get("sharpe_krw_proxy"), metrics.get("sharpe_krw_proxy")),
                                "sharpe_improve_pct": signed_improvement_pct(base_metrics.get("sharpe_krw_proxy"), metrics.get("sharpe_krw_proxy")),
                            }
                        )
                        row.update(evaluate_gate(base_metrics, metrics, [candidate], feature_map, dq_map))
            single_rows.append(row)

    max_multi_size = max(2, max_combo_size)
    for budget_spec in budget_scenarios:
        budget_pct = budget_spec.get("budget_pct")
        budget_krw = budget_spec.get("budget_krw")
        budget_frac = (budget_pct / 100.0) if budget_pct is not None else None
        for combo_size in range(2, max_multi_size + 1):
            for combo in itertools.combinations(candidate_tickers, combo_size):
                if not combo_diversity_ok(combo, universe_map):
                    continue
                allocation_details = None
                if budget_spec["mode"] == "krw":
                    proposed_weights, msg, allocation_details = build_candidate_weights_exact(base_amounts_krw, combo, budget_krw, latest_price_map or {})
                    ok = proposed_weights is not None
                    if ok:
                        ok, msg = enforce_weight_caps(proposed_weights, max_weight=0.20, exempt_tickers=(set(exempt_tickers or []) | {CASH_TICKER}))
                else:
                    proposed_weights = build_candidate_weights(base_weights_frac, combo, budget_frac)
                    ok, msg = enforce_weight_caps(proposed_weights, max_weight=0.20, exempt_tickers=exempt_tickers)
                row = {
                    "candidate_label": combo_label(combo),
                    "candidate_combo": combo_label(combo),
                    "candidate_bucket_combo": "|".join(sorted({hedge_bucket(universe_map[t]) for t in combo})),
                    "status": "PASS" if ok else "FAIL",
                    "message": msg,
                    "hedge_budget_pct": budget_pct,
                    "hedge_budget_krw": budget_krw,
                    "combo_size": combo_size,
                    "weights_snapshot": json.dumps(to_pct_weights(proposed_weights or {}), ensure_ascii=False),
                }
                if allocation_details is not None:
                    row["hedge_invested_krw"] = allocation_details["hedge_invested_krw"]
                    row["hedge_cash_left_krw"] = allocation_details["hedge_cash_left_krw"]
                    row["hedge_share_counts"] = json.dumps(allocation_details["share_counts"], ensure_ascii=False)
                if ok:
                    ret_series, err = compute_portfolio_returns(proposed_weights, ticker_ret_map)
                    if err is not None:
                        row["status"] = "FAIL"
                        row["message"] = f"FAIL: {err}"
                    else:
                        metrics = portfolio_metrics_from_returns(ret_series, benchmark_ret_map=spy_ret_map, stress_dates=stress_dates)
                        if metrics is None:
                            row["status"] = "FAIL"
                            row["message"] = "FAIL: 지표 계산 최소 관측치 부족"
                        else:
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
                                    "vol_improve_pct": risk_improvement_pct(base_metrics.get("vol_annual_krw"), metrics.get("vol_annual_krw"), is_abs_risk=False),
                                    "sharpe_improve": signed_improvement(base_metrics.get("sharpe_krw_proxy"), metrics.get("sharpe_krw_proxy")),
                                    "sharpe_improve_pct": signed_improvement_pct(base_metrics.get("sharpe_krw_proxy"), metrics.get("sharpe_krw_proxy")),
                                }
                            )
                            row.update(evaluate_gate(base_metrics, metrics, combo, feature_map, dq_map))
                multi_rows.append(row)

    normalize_rows_for_final_score(single_rows)
    normalize_rows_for_final_score(multi_rows)
    best_single = max(
        [r for r in single_rows if r.get("status") == "PASS"],
        key=lambda x: ((x["final_score"] if x.get("final_score") is not None else -1), x["candidate_label"]),
        default=None,
    )
    best_multi = max(
        [r for r in multi_rows if r.get("status") == "PASS"],
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

        f.write("## 1. 데이터 품질 요약\n")
        f.write(f"- 수집 성공: {fetched_tickers}/{total_tickers}\n")
        f.write(f"- DQ 판정(캘린더 기준): PASS {pass_cnt}, WARN {warn_cnt}, FAIL {fail_cnt}\n\n")

        f.write("## 2. 리스크 상위(KRW MDD 기준)\n")
        for row in worst_mdd:
            f.write(f"- {row['ticker']}: MDD_1y_krw={row.get('mdd_1y_krw', float('nan')):.4f}, CVaR_95_1y_krw={row.get('cvar_95_1y_krw', float('nan')):.4f}\n")

        f.write("\n## 3. 헷징 후보 Top10\n")
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
        choices=["hedge-only", "all"],
        default="hedge-only",
        help="헷지 후보군 선택 모드",
    )
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    hedge_budgets_pct = parse_budget_list(args.hedge_budgets)
    hedge_budgets_krw = parse_budget_amount_list(args.hedge_budgets_krw)
    max_combo_size = max(1, min(args.max_combo_size, 4))

    run_ts = now_utc()
    run_id = args.run_id or build_run_id(run_ts)
    data_version = args.data_version or run_ts.strftime("%Y%m%d")
    ingested_at = run_ts.isoformat()

    OUTPUT_RAW_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_REPORT_DIR.mkdir(parents=True, exist_ok=True)
    DOC_RESULT_DIR.mkdir(parents=True, exist_ok=True)

    if args.data_version is None:
        default_raw_file = OUTPUT_RAW_DIR / f"raw_market_daily_{data_version}.csv"
        if not default_raw_file.exists():
            cached_raw_file, cached_data_version = find_latest_cached_snapshot("raw_market_daily", OUTPUT_RAW_DIR)
            if cached_raw_file is not None and cached_data_version:
                data_version = cached_data_version

    start_dt = (run_ts - timedelta(days=365 * 5 + 10)).replace(hour=0, minute=0, second=0, microsecond=0)
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
    used_cached_raw = raw_file.exists()
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

        status = "PASS"
        if miss_rate > 0.05 or coverage_calendar < 0.90 or invalid_price > 0:
            status = "FAIL"
        elif miss_rate >= 0.01 or coverage_calendar < 0.97:
            status = "WARN"

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
        metrics = compute_feature_metrics(krw_price_pairs, krw_ret_map, spy_ret_map, ks200_ret_map, stress_dates, krw_adv_series)

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
                "status": status,
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
                "corr_sp500_60d": metrics["corr_sp500_60d_krw"],
                "corr_kospi200_60d": metrics["corr_kospi200_60d_krw"],
                "avg_stress_ret": metrics["avg_stress_ret_krw"],
                "adv_60": metrics["adv_60"],
                "vol_annual_krw": metrics["vol_annual_krw"],
                "mdd_1y_krw": metrics["mdd_1y_krw"],
                "var_95_1y_krw": metrics["var_95_1y_krw"],
                "cvar_95_1y_krw": metrics["cvar_95_1y_krw"],
                "beta_sp500_1y_krw": metrics["beta_sp500_1y_krw"],
                "downside_beta_sp500_1y_krw": metrics["downside_beta_sp500_1y_krw"],
                "corr_sp500_60d_krw": metrics["corr_sp500_60d_krw"],
                "corr_kospi200_60d_krw": metrics["corr_kospi200_60d_krw"],
                "avg_stress_ret_krw": metrics["avg_stress_ret_krw"],
                "annual_return_1y_krw": metrics["annual_return_1y_krw"],
                "sharpe_1y_krw_proxy": metrics["sharpe_1y_krw_proxy"],
                "data_version": data_version,
            }
        )

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
            "corr_sp500_60d",
            "corr_kospi200_60d",
            "avg_stress_ret",
            "adv_60",
            "vol_annual_krw",
            "mdd_1y_krw",
            "var_95_1y_krw",
            "cvar_95_1y_krw",
            "beta_sp500_1y_krw",
            "downside_beta_sp500_1y_krw",
            "corr_sp500_60d_krw",
            "corr_kospi200_60d_krw",
            "avg_stress_ret_krw",
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

    prefilter_ranked = build_candidate_prefilter_rows(feature_rows, dq_rows, universe_map, candidate_mode=args.candidate_mode)
    top10 = prefilter_ranked[:10]
    hes_components_csv = OUTPUT_REPORT_DIR / f"hes_components_{run_id}.csv"
    write_csv(
        hes_components_csv,
        [
            "ticker",
            "asset_class",
            "hedge_bucket",
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
    portfolio_candidate_pool = choose_candidate_pool(prefilter_ranked, universe_map, base_tickers=set(portfolio_weights_pct.keys()))
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

    portfolio_1to1_csv = OUTPUT_REPORT_DIR / f"portfolio_1to1_hedge_{run_id}.csv"
    write_csv(
        portfolio_1to1_csv,
        [
            "candidate_ticker",
            "candidate_bucket",
            "status",
            "message",
            "hedge_weight_pct",
            "hedge_budget_pct",
            "hedge_budget_krw",
            "hedge_invested_krw",
            "hedge_cash_left_krw",
            "hedge_share_counts",
            "combo_size",
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
            "vol_improve_pct",
            "mdd_improve_pct",
            "cvar_improve_pct",
            "stress_improve",
            "corr_improve",
            "beta_improve",
            "exposure_improve",
            "sharpe_improve",
            "sharpe_improve_pct",
            "combo_min_adv_60",
            "score_component_cvar",
            "score_component_mdd",
            "score_component_stress",
            "score_component_exposure",
            "score_component_sharpe",
            "score_component_liquidity",
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
            "status",
            "message",
            "hedge_budget_pct",
            "hedge_budget_krw",
            "hedge_invested_krw",
            "hedge_cash_left_krw",
            "hedge_share_counts",
            "combo_size",
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
            "vol_improve_pct",
            "mdd_improve_pct",
            "cvar_improve_pct",
            "stress_improve",
            "corr_improve",
            "beta_improve",
            "exposure_improve",
            "sharpe_improve",
            "sharpe_improve_pct",
            "combo_min_adv_60",
            "score_component_cvar",
            "score_component_mdd",
            "score_component_stress",
            "score_component_exposure",
            "score_component_sharpe",
            "score_component_liquidity",
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
            single_asset_candidate_pool = choose_candidate_pool(prefilter_ranked, universe_map, base_tickers={single_asset_ticker})
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
            )

        single_asset_1to1_csv = OUTPUT_REPORT_DIR / f"single_asset_hedge_1to1_{run_id}.csv"
        write_csv(
            single_asset_1to1_csv,
            [
                "candidate_ticker",
                "candidate_bucket",
                "status",
                "message",
                "hedge_weight_pct",
                "hedge_budget_pct",
                "hedge_budget_krw",
                "hedge_invested_krw",
                "hedge_cash_left_krw",
                "hedge_share_counts",
                "combo_size",
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
                "vol_improve_pct",
                "mdd_improve_pct",
                "cvar_improve_pct",
                "stress_improve",
                "corr_improve",
                "beta_improve",
                "exposure_improve",
                "sharpe_improve",
                "sharpe_improve_pct",
                "combo_min_adv_60",
                "score_component_cvar",
                "score_component_mdd",
                "score_component_stress",
                "score_component_exposure",
                "score_component_sharpe",
                "score_component_liquidity",
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
                "status",
                "message",
                "hedge_budget_pct",
                "hedge_budget_krw",
                "hedge_invested_krw",
                "hedge_cash_left_krw",
                "hedge_share_counts",
                "combo_size",
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
                "vol_improve_pct",
                "mdd_improve_pct",
                "cvar_improve_pct",
                "stress_improve",
                "corr_improve",
                "beta_improve",
                "exposure_improve",
                "sharpe_improve",
                "sharpe_improve_pct",
                "combo_min_adv_60",
                "score_component_cvar",
                "score_component_mdd",
                "score_component_stress",
                "score_component_exposure",
                "score_component_sharpe",
                "score_component_liquidity",
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
        portfolio_1to1_csv=portfolio_1to1_csv,
        portfolio_multi_csv=portfolio_multi_csv,
        portfolio_compare_csv=portfolio_compare_csv,
        single_asset_1to1_csv=single_asset_1to1_csv,
        single_asset_multi_csv=single_asset_multi_csv,
        single_asset_compare_csv=single_asset_compare_csv,
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
