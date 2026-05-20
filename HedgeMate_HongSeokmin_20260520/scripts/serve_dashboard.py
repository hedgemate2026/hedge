#!/usr/bin/env python3
import argparse
import csv
import hashlib
import json
import mimetypes
import re
import subprocess
import sys
import threading
import uuid
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

ROOT = Path(__file__).resolve().parents[1]
WEB_DIR = ROOT / "web"
INPUT_DIR = ROOT / "inputs"
OUTPUT_RAW_DIR = ROOT / "outputs" / "raw"
OUTPUT_PROCESSED_DIR = ROOT / "outputs" / "processed"
OUTPUT_REPORT_DIR = ROOT / "outputs" / "reports"
DOC_RESULT_DIR = ROOT / "docs" / "STEP_1" / "04_실행결과"
SCENARIO_RESEARCH_ROOT = ROOT.parent / "scenario_research"
SCENARIO_OUTPUT_DIR = SCENARIO_RESEARCH_ROOT / "outputs"
SCENARIO_FINAL_DIR = SCENARIO_OUTPUT_DIR / "final"
SCENARIO_PROCESSED_DIR = SCENARIO_OUTPUT_DIR / "processed"
SCENARIO_REPORT_DIR = SCENARIO_OUTPUT_DIR / "reports"
SCENARIO_VECTOR_DIR = SCENARIO_OUTPUT_DIR / "scenario_vectors"
SCENARIO_NOWCAST_DIR = SCENARIO_OUTPUT_DIR / "nowcast_vectors"
SCENARIO_EVENT_DIR = SCENARIO_OUTPUT_DIR / "events"
SCENARIO_VALIDATION_DIR = SCENARIO_OUTPUT_DIR / "validation"
SCENARIO_MANIFEST_PATH = SCENARIO_OUTPUT_DIR / "latest_manifest.json"
HEDGEMATE_MANIFEST_PATH = ROOT / "outputs" / "latest_manifest.json"
OUTPUT_VALIDATION_DIR = ROOT / "outputs" / "validation"
PRICE_CACHE_DIR = ROOT / "outputs" / "price_cache"
LOCALHOST_CLIENTS = {"127.0.0.1", "::1", "::ffff:127.0.0.1"}
DEFAULT_EVENT_OVERLAY_STATUS = {
    "mode": "reviewed_fixture",
    "live_gemini_extraction": "implemented_api_key_required",
    "recommendation_usage": "fixture_context_only",
    "trade_gate_usage": "disabled_for_fixture",
}
PORTFOLIO_FINGERPRINT_DIGITS = 4
CONTENT_SECURITY_POLICY = (
    "default-src 'self'; "
    "script-src 'self'; "
    "style-src 'self'; "
    "img-src 'self' data:; "
    "object-src 'none'; "
    "base-uri 'self'; "
    "frame-ancestors 'none'"
)

TICKER_LABELS = {
    "__CASH__": "현금",
    "005930.KS": "삼성전자",
    "000660.KS": "SK하이닉스",
    "005380.KS": "현대차",
    "000270.KS": "기아",
    "035420.KS": "NAVER",
    "035720.KS": "카카오",
    "207940.KS": "삼성바이오로직스",
    "068270.KS": "셀트리온",
    "051910.KS": "LG화학",
    "006400.KS": "삼성SDI",
    "066570.KS": "LG전자",
    "105560.KS": "KB금융",
    "055550.KS": "신한지주",
    "005490.KS": "POSCO홀딩스",
    "032830.KS": "삼성생명",
    "034020.KS": "두산에너빌리티",
    "003670.KS": "포스코퓨처엠",
    "011200.KS": "HMM",
    "017670.KS": "SK텔레콤",
    "000810.KS": "삼성화재",
    "AAPL": "Apple",
    "MSFT": "Microsoft",
    "NVDA": "NVIDIA",
    "AMZN": "Amazon",
    "GOOGL": "Alphabet",
    "META": "Meta",
    "TSLA": "Tesla",
    "BRK-B": "Berkshire Hathaway B",
    "JPM": "JPMorgan Chase",
    "V": "Visa",
    "MA": "Mastercard",
    "XOM": "Exxon Mobil",
    "JNJ": "Johnson & Johnson",
    "UNH": "UnitedHealth",
    "PG": "Procter & Gamble",
    "KO": "Coca-Cola",
    "HD": "Home Depot",
    "AVGO": "Broadcom",
    "COST": "Costco",
    "PFE": "Pfizer",
    "SPY": "S&P500 ETF",
    "QQQ": "Nasdaq 100 ETF",
    "DIA": "Dow ETF",
    "IWM": "Russell 2000 ETF",
    "VTI": "미국 전체주식 ETF",
    "VXUS": "미국 제외 글로벌 ETF",
    "EWY": "코리아 ETF",
    "EFA": "선진국 ETF",
    "TLT": "장기 미국국채 ETF",
    "IEF": "중기 미국국채 ETF",
    "SHY": "단기 미국국채 ETF",
    "LQD": "우량회사채 ETF",
    "HYG": "하이일드채권 ETF",
    "TIP": "물가연동채 ETF",
    "GLD": "금 ETF",
    "IAU": "금 ETF",
    "DBC": "원자재 ETF",
    "USO": "원유 ETF",
    "XLE": "에너지 섹터 ETF",
    "XLP": "필수소비재 ETF",
    "XLU": "유틸리티 ETF",
    "XLV": "헬스케어 ETF",
    "ITA": "방산 ETF",
    "PPA": "방산 ETF",
    "VNQ": "리츠 ETF",
    "BTC-USD": "비트코인",
    "ETH-USD": "이더리움",
    "BNB-USD": "BNB",
    "SOL-USD": "솔라나",
    "XRP-USD": "리플",
    "^KS200": "KOSPI200",
    "^KS11": "코스피",
}

RUN_JOBS = {}
RUN_JOBS_LOCK = threading.Lock()
_MARKET_PRICE_CACHE = {}
_FX_PRICE_CACHE = {}

ASSET_ALIASES = {
    "삼성전자": "005930.KS",
    "삼성": "005930.KS",
    "sk하이닉스": "000660.KS",
    "하이닉스": "000660.KS",
    "현대차": "005380.KS",
    "현대자동차": "005380.KS",
    "기아": "000270.KS",
    "네이버": "035420.KS",
    "naver": "035420.KS",
    "카카오": "035720.KS",
    "셀트리온": "068270.KS",
    "애플": "AAPL",
    "apple": "AAPL",
    "마이크로소프트": "MSFT",
    "microsoft": "MSFT",
    "엔비디아": "NVDA",
    "nvidia": "NVDA",
    "테슬라": "TSLA",
    "tesla": "TSLA",
    "금 etf": "GLD",
    "금etf": "GLD",
    "금": "GLD",
    "gold": "GLD",
    "gld": "GLD",
    "장기국채 etf": "TLT",
    "장기국채etf": "TLT",
    "장기국채": "TLT",
    "장기 미국국채": "TLT",
    "중기국채 etf": "IEF",
    "중기국채etf": "IEF",
    "중기국채": "IEF",
    "중기 미국국채": "IEF",
    "단기국채 etf": "SHY",
    "단기국채etf": "SHY",
    "단기국채": "SHY",
    "단기 미국국채": "SHY",
    "s&p500 etf": "SPY",
    "s&p 500 etf": "SPY",
    "sp500 etf": "SPY",
    "sp500": "SPY",
    "s&p500": "SPY",
    "나스닥 etf": "QQQ",
    "나스닥": "QQQ",
    "현금": "__CASH__",
    "cash": "__CASH__",
}


def normalize_asset_query(value):
    return re.sub(r"[^0-9A-Za-z가-힣&+.^-]+", "", str(value or "").strip()).lower()


def aliases_by_ticker():
    rows = {}
    for alias, ticker in ASSET_ALIASES.items():
        rows.setdefault(ticker, set()).add(alias)
    return {ticker: sorted(values) for ticker, values in rows.items()}


def asset_class_label(ticker):
    ticker = str(ticker or "")
    if ticker == "__CASH__":
        return "현금"
    if ticker.endswith(".KS"):
        return "국내주식"
    if ticker.endswith("-USD"):
        return "암호자산"
    if ticker.startswith("^"):
        return "시장지수"
    label = display_name(ticker)
    if "ETF" in label or ticker in {"SPY", "QQQ", "DIA", "IWM", "VTI", "VXUS", "EWY", "EFA", "TLT", "IEF", "SHY", "LQD", "HYG", "TIP", "GLD", "IAU", "DBC", "USO", "XLE", "XLP", "XLU", "XLV", "ITA", "PPA", "VNQ"}:
        return "ETF"
    return "미국주식"


def display_label(ticker):
    ticker = str(ticker or "")
    label = display_name(ticker)
    if not ticker or ticker == "__CASH__":
        return label
    return f"{label} ({ticker})"


def asset_options():
    aliases = aliases_by_ticker()
    rows = []
    for ticker, label in sorted(TICKER_LABELS.items(), key=lambda item: (item[1], item[0])):
        if ticker == "__CASH__":
            continue
        ticker_aliases = aliases.get(ticker, [])
        search_parts = [label, ticker, display_label(ticker), *ticker_aliases]
        rows.append(
            {
                "ticker": ticker,
                "label": label,
                "displayLabel": display_label(ticker),
                "popularName": label,
                "assetClass": asset_class_label(ticker),
                "aliases": ticker_aliases,
                "searchText": " ".join(search_parts),
            }
        )
    return rows


def resolve_asset_query(query):
    raw = str(query or "").strip()
    if not raw:
        raise ValueError("자산명이 비어 있습니다.")

    upper = raw.upper()
    if upper in TICKER_LABELS:
        return upper

    normalized = normalize_asset_query(raw)
    alias_key = re.sub(r"\s+", " ", raw.lower()).strip()
    if alias_key in ASSET_ALIASES:
        return ASSET_ALIASES[alias_key]
    if normalized in ASSET_ALIASES:
        return ASSET_ALIASES[normalized]

    exact = [ticker for ticker, label in TICKER_LABELS.items() if normalize_asset_query(label) == normalized]
    if len(exact) == 1:
        return exact[0]
    if len(exact) > 1:
        raise ValueError("동일 이름 자산이 여러 개입니다. 티커를 직접 입력해 주세요.")

    alias_rows = aliases_by_ticker()
    partial = []
    for ticker, label in TICKER_LABELS.items():
        candidates = [label, ticker, display_label(ticker), *alias_rows.get(ticker, [])]
        if normalized and any(normalized in normalize_asset_query(candidate) for candidate in candidates):
            partial.append(ticker)
    if len(partial) == 1:
        return partial[0]
    if len(partial) > 1:
        raise ValueError("검색 결과가 여러 개입니다. 더 정확한 자산명 또는 티커를 입력해 주세요.")

    raise ValueError("지원하지 않는 자산입니다. 목록에서 정확한 자산을 선택해 주세요.")


def parse_float(value):
    if value is None or value == "":
        return None
    try:
        return float(value)
    except ValueError:
        return value


def build_run_id():
    return datetime.now().strftime("%Y%m%dT%H%M%S%f") + f"-{uuid.uuid4().hex[:8]}"


def parse_max_combo_size(value):
    try:
        parsed = int(value if value not in (None, "") else 4)
    except (TypeError, ValueError) as exc:
        raise ValueError("최대 조합 수는 숫자여야 합니다.") from exc
    return max(1, min(parsed, 4))


def display_name(ticker):
    ticker = str(ticker or "")
    return TICKER_LABELS.get(ticker, ticker)


def humanize_combo(label):
    return " + ".join(display_label(part.strip()) for part in str(label or "").split(" + ") if part.strip())


def humanize_scenario(scenario):
    scenario = str(scenario or "")
    if scenario.startswith("기존 포트폴리오"):
        return scenario
    for prefix in ["제안(1:1) - ", "참고안(1:1) - ", "차선후보(1:1) - "]:
        if scenario.startswith(prefix):
            ticker = scenario[len(prefix):].strip()
            return f"{prefix}{display_label(ticker)}"
    for prefix in ["제안(다자산) - ", "참고안(다자산) - ", "차선후보(다자산) - "]:
        if scenario.startswith(prefix):
            combo = scenario[len(prefix):].strip()
            return f"{prefix}{humanize_combo(combo)}"
    m = re.match(r"기준\((.+?) 100%\)", scenario)
    if m:
        return f"기준({display_label(m.group(1))} 100%)"
    return scenario


def read_csv_rows(path):
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        rows = []
        for row in csv.DictReader(f):
            rows.append({k: parse_float(v) for k, v in row.items()})
        return rows


def read_json(path, fallback=None):
    if not path.exists():
        return fallback
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def read_json_or_csv_rows(path):
    if not path:
        return []
    if Path(path).suffix.lower() == ".csv":
        return read_csv_rows(Path(path))
    return read_json(Path(path), []) or []


def read_product_manifest():
    manifest_path = ROOT / "outputs" / "latest_manifest.json"
    payload = read_json(manifest_path, {}) if manifest_path.exists() else {}
    return payload if isinstance(payload, dict) else {}


def read_active_manifest():
    manifest_path = SCENARIO_OUTPUT_DIR / "latest_manifest.json"
    payload = read_json(manifest_path, {}) if manifest_path.exists() else {}
    return payload if isinstance(payload, dict) else {}


def resolve_any_artifact(raw_path, default_dir=None):
    if not raw_path:
        return None
    candidate = Path(str(raw_path))
    candidates = []
    if candidate.is_absolute():
        candidates.append(candidate)
    else:
        candidates.extend(
            [
                ROOT / candidate,
                ROOT.parent / candidate,
                SCENARIO_OUTPUT_DIR / candidate,
            ]
        )
        if default_dir:
            candidates.append(Path(default_dir) / candidate)
    for path in candidates:
        if path.exists():
            return path
    return None


def resolve_product_artifact(manifest, key, default_dir=None):
    artifacts = manifest.get("artifacts", {}) if isinstance(manifest, dict) else {}
    raw_path = artifacts.get(key) if isinstance(artifacts, dict) else None
    raw_path = raw_path or manifest.get(f"{key}_path") or manifest.get(key)
    return resolve_any_artifact(raw_path, default_dir=default_dir)


def resolve_active_gated_recommendation_artifact(manifest, key):
    path = resolve_product_artifact(manifest, key, default_dir=OUTPUT_REPORT_DIR)
    if not path:
        return None, f"missing active gated recommendation artifact: {key}"
    if "_backtest_gated" not in path.name:
        return None, f"active recommendation artifact is not backtest-gated: {key}={path.name}"
    return path, ""


def active_bundle(manifest=None):
    manifest = manifest or read_product_manifest()
    bundle = manifest.get("active_bundle", {}) if isinstance(manifest, dict) else {}
    return bundle if isinstance(bundle, dict) else {}


def normalized_event_overlay_status(raw_status=None):
    status = dict(DEFAULT_EVENT_OVERLAY_STATUS)
    if isinstance(raw_status, dict):
        status.update({key: value for key, value in raw_status.items() if value not in (None, "")})
    return status


def active_data_version(manifest=None):
    manifest = manifest or read_product_manifest()
    bundle = active_bundle(manifest)
    return str(bundle.get("data_version") or manifest.get("data_version") or "").strip()


def parse_money_value(value):
    if value in (None, ""):
        return None
    try:
        parsed = float(str(value).replace(",", "").strip())
    except (TypeError, ValueError) as exc:
        raise ValueError("금액 또는 수량을 숫자로 해석할 수 없습니다.") from exc
    return parsed


def ticker_currency(ticker):
    if ticker == "__CASH__":
        return "KRW"
    if str(ticker).endswith(".KS") or str(ticker).startswith("^KS"):
        return "KRW"
    return "USD"


def raw_market_path_for_data_version(data_version=None):
    if data_version:
        candidate = OUTPUT_RAW_DIR / f"raw_market_daily_{data_version}.csv"
        if candidate.exists():
            return candidate
    return latest_path(OUTPUT_RAW_DIR, "raw_market_daily_*.csv")


def raw_fx_path_for_data_version(data_version=None):
    if data_version:
        candidate = OUTPUT_RAW_DIR / f"raw_fx_daily_{data_version}.csv"
        if candidate.exists():
            return candidate
    return latest_path(OUTPUT_RAW_DIR, "raw_fx_daily_*.csv")


def latest_market_price_map(data_version=None):
    path = raw_market_path_for_data_version(data_version)
    if not path:
        return {}, None
    cache_key = (str(path.resolve()), path.stat().st_mtime_ns)
    if cache_key in _MARKET_PRICE_CACHE:
        return _MARKET_PRICE_CACHE[cache_key], path

    latest = {}
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            ticker = str(row.get("ticker") or "").strip()
            if not ticker:
                continue
            date_value = str(row.get("date") or "")
            price = parse_float(row.get("adj_close") or row.get("close"))
            if not isinstance(price, (int, float)):
                continue
            previous = latest.get(ticker)
            if previous and str(previous.get("asOfDate") or "") > date_value:
                continue
            latest[ticker] = {
                "ticker": ticker,
                "latestPrice": float(price),
                "currency": row.get("currency") or ticker_currency(ticker),
                "asOfDate": date_value,
                "source": row.get("source") or "raw_market_cache",
                "assetClass": row.get("asset_class"),
                "ingestedAt": row.get("ingested_at"),
                "dataMode": "cache",
            }
    _MARKET_PRICE_CACHE.clear()
    _MARKET_PRICE_CACHE[cache_key] = latest
    return latest, path


def latest_fx_quote(data_version=None):
    path = raw_fx_path_for_data_version(data_version)
    if not path:
        return {
            "pair": "USD/KRW",
            "rate": None,
            "asOfDate": None,
            "source": None,
            "dataMode": "unavailable",
            "error": "USD/KRW 환율 캐시 파일을 찾지 못했습니다.",
        }
    cache_key = (str(path.resolve()), path.stat().st_mtime_ns)
    if cache_key in _FX_PRICE_CACHE:
        return _FX_PRICE_CACHE[cache_key]

    latest = None
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            rate = parse_float(row.get("close"))
            if not isinstance(rate, (int, float)):
                continue
            date_value = str(row.get("date") or "")
            if latest and str(latest.get("asOfDate") or "") > date_value:
                continue
            latest = {
                "pair": "USD/KRW",
                "rate": float(rate),
                "asOfDate": date_value,
                "source": row.get("source") or "raw_fx_cache",
                "ingestedAt": row.get("ingested_at"),
                "dataMode": "cache",
            }
    if latest is None:
        latest = {
            "pair": "USD/KRW",
            "rate": None,
            "asOfDate": None,
            "source": "raw_fx_cache",
            "dataMode": "unavailable",
            "error": "USD/KRW 환율 행을 찾지 못했습니다.",
        }
    _FX_PRICE_CACHE.clear()
    _FX_PRICE_CACHE[cache_key] = latest
    return latest


def yahoo_symbol_for_ticker(ticker):
    if ticker == "KRW=X":
        return "KRW=X"
    return ticker


def fetch_yahoo_quote(ticker, timeout=4):
    symbol = yahoo_symbol_for_ticker(ticker)
    query = urllib.parse.urlencode({"symbols": symbol})
    url = f"https://query1.finance.yahoo.com/v7/finance/quote?{query}"
    request = urllib.request.Request(url, headers={"User-Agent": "HedgeMate/1.0"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
    results = payload.get("quoteResponse", {}).get("result", [])
    if not results:
        raise RuntimeError(f"Yahoo quote result is empty for {ticker}")
    row = results[0]
    price = row.get("regularMarketPrice") or row.get("postMarketPrice") or row.get("preMarketPrice")
    if price is None:
        raise RuntimeError(f"Yahoo quote price is missing for {ticker}")
    market_time = row.get("regularMarketTime")
    as_of = datetime.fromtimestamp(market_time).isoformat(timespec="seconds") if market_time else datetime.now().isoformat(timespec="seconds")
    return {
        "ticker": ticker,
        "latestPrice": float(price),
        "currency": row.get("currency") or ticker_currency(ticker),
        "asOfDate": as_of,
        "source": "yahoo_quote",
        "assetClass": None,
        "dataMode": "live",
    }


def lookup_price(asset, quantity=None, amount_krw=None, use_live=False, data_version=None):
    ticker = resolve_asset_query(asset)
    warnings = []
    errors = []
    amount_value = parse_money_value(amount_krw)
    quantity_value = parse_money_value(quantity)
    if amount_value is not None and amount_value <= 0:
        errors.append("KRW 금액은 0보다 커야 합니다.")
    if quantity_value is not None and quantity_value <= 0:
        errors.append("수량은 0보다 커야 합니다.")

    if ticker == "__CASH__":
        krw_value = amount_value if amount_value is not None else quantity_value
        if krw_value is None:
            errors.append("현금은 KRW 금액을 입력해야 합니다.")
            krw_value = 0.0
        return {
            "input": asset,
            "resolvedTicker": ticker,
            "displayName": "현금",
            "displayLabel": "현금",
            "assetClass": "cash",
            "currency": "KRW",
            "latestPrice": 1.0,
            "unitPriceKrw": 1.0,
            "priceAsOf": display_reference_date(),
            "fxRate": 1.0,
            "fxAsOf": display_reference_date(),
            "quantity": quantity_value,
            "amountKrw": amount_value,
            "marketValueKrw": float(krw_value or 0.0),
            "impliedQuantity": float(krw_value or 0.0),
            "valuationBasis": "amount" if amount_value is not None else "cash",
            "dataMode": "cash",
            "warnings": warnings,
            "errors": errors,
        }

    price_payload = None
    if use_live:
        try:
            price_payload = fetch_yahoo_quote(ticker)
        except Exception as exc:
            warnings.append(f"실시간 가격 조회 실패, 캐시 사용 시도: {exc}")

    if price_payload is None:
        price_map, raw_path = latest_market_price_map(data_version or active_data_version())
        price_payload = price_map.get(ticker)
        if price_payload:
            warnings.append(f"실시간 가격이 아니라 로컬 캐시를 사용했습니다: {raw_path.name if raw_path else 'unknown'}")

    if price_payload is None:
        message = f"{ticker} 가격 데이터를 찾지 못했습니다."
        if amount_value is None:
            errors.append(message)
        else:
            warnings.append(message + " KRW 금액 입력값으로 평가액을 계산했습니다.")
        price_payload = {
            "ticker": ticker,
            "latestPrice": None,
            "currency": ticker_currency(ticker),
            "asOfDate": None,
            "source": None,
            "assetClass": None,
            "dataMode": "unavailable",
        }

    currency = price_payload.get("currency") or ticker_currency(ticker)
    fx_payload = {"rate": 1.0, "asOfDate": price_payload.get("asOfDate"), "dataMode": "not_required", "source": "KRW"}
    if currency != "KRW":
        fx_payload = latest_fx_quote(data_version or active_data_version())
        if fx_payload.get("rate") is None:
            if amount_value is None:
                errors.append(f"{currency}/KRW 환율 데이터를 찾지 못했습니다.")
            else:
                warnings.append(f"{currency}/KRW 환율 데이터를 찾지 못했습니다. KRW 금액 입력값으로 평가액을 계산했습니다.")
        elif fx_payload.get("dataMode") == "cache":
            warnings.append("해외자산 KRW 환산에 USD/KRW 로컬 캐시를 사용했습니다.")

    latest_price = price_payload.get("latestPrice")
    fx_rate = fx_payload.get("rate") if currency != "KRW" else 1.0
    unit_price_krw = float(latest_price) * float(fx_rate) if latest_price is not None and fx_rate is not None else None
    valuation_basis = "amount" if amount_value is not None else "quantity" if quantity_value is not None else None
    market_value_krw = None
    implied_quantity = None
    if amount_value is not None:
        market_value_krw = amount_value
        if latest_price and fx_rate:
            implied_quantity = amount_value / (float(latest_price) * float(fx_rate))
    elif quantity_value is not None and latest_price and fx_rate:
        market_value_krw = quantity_value * float(latest_price) * float(fx_rate)
    elif quantity_value is None:
        errors.append("KRW 금액 또는 보유 수량 중 하나는 입력해야 합니다.")

    return {
        "input": asset,
        "resolvedTicker": ticker,
        "displayName": display_name(ticker),
        "displayLabel": display_label(ticker),
        "assetClass": price_payload.get("assetClass"),
        "currency": currency,
        "latestPrice": latest_price,
        "unitPriceKrw": unit_price_krw,
        "priceAsOf": price_payload.get("asOfDate"),
        "priceSource": price_payload.get("source"),
        "fxRate": fx_rate,
        "fxAsOf": fx_payload.get("asOfDate"),
        "fxSource": fx_payload.get("source"),
        "quantity": quantity_value,
        "amountKrw": amount_value,
        "marketValueKrw": market_value_krw,
        "impliedQuantity": implied_quantity,
        "valuationBasis": valuation_basis,
        "dataMode": price_payload.get("dataMode"),
        "warnings": warnings,
        "errors": errors,
    }


def preview_portfolio(payload):
    raw_rows = (payload or {}).get("portfolioRows") or []
    if not isinstance(raw_rows, list) or not raw_rows:
        raise ValueError("포트폴리오 자산 행이 필요합니다.")
    use_live = bool((payload or {}).get("useLivePrices"))
    data_version = (payload or {}).get("dataVersion") or active_data_version()
    rows = []
    errors = []
    warnings = []
    seen = {}
    total_value = 0.0
    for index, item in enumerate(raw_rows):
        asset = (item or {}).get("asset") or (item or {}).get("ticker")
        try:
            row = lookup_price(
                asset,
                quantity=(item or {}).get("quantity"),
                amount_krw=(item or {}).get("amountKrw"),
                use_live=use_live,
                data_version=data_version,
            )
        except ValueError as exc:
            row = {
                "input": asset,
                "resolvedTicker": None,
                "displayName": str(asset or ""),
                "marketValueKrw": None,
                "warnings": [],
                "errors": [str(exc)],
            }
        row["rowIndex"] = index
        ticker = row.get("resolvedTicker")
        if ticker:
            if ticker in seen:
                row.setdefault("errors", []).append(f"중복 자산입니다: {display_name(ticker)}")
            seen[ticker] = index
        if row.get("errors"):
            errors.extend(f"{row.get('displayName') or asset}: {error}" for error in row["errors"])
        if row.get("warnings"):
            warnings.extend(f"{row.get('displayName') or asset}: {warning}" for warning in row["warnings"])
        value = row.get("marketValueKrw")
        if isinstance(value, (int, float)):
            total_value += float(value)
        rows.append(row)

    if total_value <= 0:
        errors.append("총 평가액이 0원입니다.")

    for row in rows:
        value = row.get("marketValueKrw")
        row["weightPct"] = (float(value) / total_value * 100.0) if total_value > 0 and isinstance(value, (int, float)) else None
        if isinstance(row.get("weightPct"), (int, float)) and row["weightPct"] > 50:
            row.setdefault("warnings", []).append("단일 자산 비중이 50%를 초과합니다.")

    analysis_rows = [
        {"ticker": row["resolvedTicker"], "weight_pct": row["weightPct"]}
        for row in rows
        if row.get("resolvedTicker") and isinstance(row.get("weightPct"), (int, float)) and row["weightPct"] > 0
    ]
    non_cash_analysis_rows = [row for row in analysis_rows if row.get("ticker") != "__CASH__"]
    if not non_cash_analysis_rows:
        errors.append("현금 단독 입력은 헷지 분석 기준으로 사용할 수 없습니다.")
    elif len(non_cash_analysis_rows) > 1 or len(analysis_rows) > 1:
        try:
            validate_portfolio_weights(analysis_rows)
        except ValueError as exc:
            errors.append(str(exc))
    return {
        "ok": not errors,
        "canRunAnalysis": not errors and total_value > 0,
        "dataVersion": data_version,
        "totalMarketValueKrw": total_value,
        "rows": rows,
        "analysisRows": analysis_rows,
        "errors": errors,
        "warnings": warnings,
    }


def manifest_artifact_status(manifest):
    rows = []
    for key, value in (manifest.get("artifacts", {}) if isinstance(manifest, dict) else {}).items():
        path = resolve_any_artifact(value)
        rows.append({"key": key, "path": value, "exists": bool(path), "resolvedPath": str(path) if path else None})
    return rows


def active_backtest_price_gap_summary(manifest):
    path = resolve_product_artifact(manifest, "backtestCsv", OUTPUT_VALIDATION_DIR)
    if not path:
        return {"outOfPriceRangeRows": 0, "caseNames": []}
    rows = read_csv_rows(path)
    gap_rows = [row for row in rows if str(row.get("price_window_status") or "").upper() == "OUT_OF_PRICE_RANGE"]
    case_names = unique_case_labels(gap_rows)
    return {"outOfPriceRangeRows": len(gap_rows), "caseNames": case_names}


def parse_weight_float(value):
    try:
        return float(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


def current_portfolio_fingerprint(path=None):
    path = path or INPUT_DIR / "portfolio_weights.csv"
    if not path or not Path(path).exists():
        return None
    weights = {}
    with Path(path).open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            ticker = str(row.get("ticker") or "").strip()
            weight = parse_weight_float(row.get("weight_pct"))
            if ticker and weight is not None:
                weights[ticker] = weights.get(ticker, 0.0) + weight
    total = sum(max(0.0, weight) for weight in weights.values())
    if total <= 0:
        return None
    normalized = {
        ticker: round(max(0.0, weight) / total * 100.0, PORTFOLIO_FINGERPRINT_DIGITS)
        for ticker, weight in sorted(weights.items())
        if max(0.0, weight) > 0
    }
    canonical = "|".join(f"{ticker}:{weight:.{PORTFOLIO_FINGERPRINT_DIGITS}f}" for ticker, weight in normalized.items())
    return {
        "hash": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
        "ticker_count": len(normalized),
        "total_weight_pct": round(sum(normalized.values()), PORTFOLIO_FINGERPRINT_DIGITS),
        "tickers": list(normalized),
        "path": str(Path(path)),
    }


def manifest_portfolio_fingerprint(manifest, bundle):
    payload = manifest.get("portfolio_input_fingerprint") if isinstance(manifest, dict) else None
    if not isinstance(payload, dict):
        payload = bundle.get("portfolio_input_fingerprint") if isinstance(bundle, dict) else None
    return payload if isinstance(payload, dict) else None


def active_scenario_snapshot_metadata(manifest, bundle):
    scenario_run = bundle.get("scenario_run") or manifest.get("active_scenario_run")
    if not scenario_run:
        return {}
    metadata_path = SCENARIO_REPORT_DIR / f"scenario_snapshot_metadata_{scenario_run}.json"
    payload = read_json(metadata_path, {}) if metadata_path.exists() else {}
    return payload if isinstance(payload, dict) else {}


def load_data_freshness(reference_date=None):
    reference_date = reference_date or datetime.now().date()
    manifest = read_product_manifest()
    bundle = active_bundle(manifest)
    data_version = active_data_version(manifest)
    data_date = None
    if re.fullmatch(r"\d{8}", data_version or ""):
        data_date = datetime.strptime(data_version, "%Y%m%d").date()
    status = manifest.get("freshness_status") or bundle.get("freshness_status") or "UNKNOWN"
    artifact_rows = manifest_artifact_status(manifest)
    missing = [row for row in artifact_rows if not row["exists"]]
    price_gap_summary = active_backtest_price_gap_summary(manifest)
    active_portfolio = manifest_portfolio_fingerprint(manifest, bundle)
    current_portfolio = current_portfolio_fingerprint()
    portfolio_input_mismatch = bool(
        active_portfolio
        and current_portfolio
        and active_portfolio.get("hash")
        and current_portfolio.get("hash")
        and active_portfolio.get("hash") != current_portfolio.get("hash")
    )
    recommendation_portfolio_mismatch = bool(manifest.get("portfolio_input_mismatch") or bundle.get("portfolio_input_mismatch"))
    scenario_as_of = bundle.get("scenario_vector_as_of_date") or manifest.get("scenario_vector_as_of_date")
    scenario_snapshot = active_scenario_snapshot_metadata(manifest, bundle)
    scenario_data_version = str(scenario_snapshot.get("data_version") or "").strip()
    scenario_date = None
    if scenario_as_of:
        try:
            scenario_date = datetime.strptime(str(scenario_as_of)[:10], "%Y-%m-%d").date()
        except ValueError:
            scenario_date = None
    scenario_lag_days = (data_date - scenario_date).days if data_date and scenario_date else None
    scenario_version_mismatch = bool(data_version and scenario_data_version and scenario_data_version != data_version)
    is_today = bool(data_date and data_date == reference_date)
    needs_refresh = (
        (not is_today)
        or status != "FRESH"
        or bool(missing)
        or price_gap_summary["outOfPriceRangeRows"] > 0
        or scenario_version_mismatch
        or portfolio_input_mismatch
        or recommendation_portfolio_mismatch
    )
    reasons = list(manifest.get("stale_reasons") or bundle.get("stale_reasons") or [])
    def add_reason(text):
        if text and text not in reasons:
            reasons.append(text)

    if not is_today:
        add_reason(f"data_version {data_version or '-'} is not today {reference_date.strftime('%Y%m%d')}")
    if scenario_version_mismatch:
        add_reason(
            f"scenario data_version {scenario_data_version} does not match active data_version {data_version}"
        )
    if missing:
        add_reason("missing artifacts: " + ", ".join(row["key"] for row in missing))
    if price_gap_summary["outOfPriceRangeRows"] > 0:
        names = ", ".join(price_gap_summary["caseNames"][:3])
        add_reason(
            f"historical stress price coverage gap: {price_gap_summary['outOfPriceRangeRows']} rows"
            + (f" ({names})" if names else "")
        )
    if portfolio_input_mismatch:
        add_reason("portfolio input mismatch: current portfolio_weights.csv differs from the active bundle")
    if recommendation_portfolio_mismatch:
        if not any(str(reason).startswith("portfolio input mismatch: active recommendation weights") for reason in reasons):
            add_reason("portfolio input mismatch: active recommendation weights do not match the active portfolio input")
    return {
        "status": "current" if not needs_refresh else "stale",
        "needsRefresh": needs_refresh,
        "skipHeavyRefresh": not needs_refresh,
        "referenceDate": reference_date.isoformat(),
        "dataVersion": data_version,
        "scenarioDataVersion": scenario_data_version or None,
        "scenarioVectorAsOfDate": scenario_as_of,
        "scenarioVectorLagDays": scenario_lag_days,
        "scenarioAnchorCoverageRatio": scenario_snapshot.get("anchor_ticker_coverage_ratio"),
        "scenarioDataQualityStatus": scenario_snapshot.get("data_quality_status"),
        "generatedAtUtc": bundle.get("generated_at_utc") or manifest.get("generated_at_utc"),
        "freshnessStatus": status,
        "reasons": reasons,
        "artifactStatus": artifact_rows,
        "backtestPriceGapSummary": price_gap_summary,
        "portfolioInputMismatch": portfolio_input_mismatch,
        "recommendationPortfolioMismatch": recommendation_portfolio_mismatch,
        "activePortfolioFingerprint": active_portfolio,
        "currentPortfolioFingerprint": current_portfolio,
        "eventOverlayStatus": normalized_event_overlay_status(manifest.get("event_overlay_status")),
    }


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


def final_run_id_from_filename(filename):
    name = Path(str(filename or "")).name
    m = re.search(r"final_market_state_daily_(.+)\.csv$", name)
    return m.group(1) if m else None


def latest_path(directory, pattern):
    paths = [path for path in directory.glob(pattern) if path.is_file()]
    if not paths:
        return None
    return max(paths, key=lambda path: (path.stat().st_mtime, path.name))


def latest_run_id_from_files(directory, pattern, regex):
    path = latest_path(directory, pattern)
    if not path:
        return None
    match = re.search(regex, path.name)
    return match.group(1) if match else None


def fallback_product_manifest():
    scenario_manifest = read_active_manifest()
    final_run = scenario_manifest.get("active_final_run") or final_run_id_from_filename(scenario_manifest.get("active_final_market_state"))
    scenario_run = scenario_manifest.get("active_scenario_run") or final_run
    hedge_run = latest_run_id_from_files(OUTPUT_PROCESSED_DIR, "features_summary_*.csv", r"features_summary_(.+)\.csv$")
    backtest_run = latest_run_id_from_files(OUTPUT_VALIDATION_DIR, "walk_forward_backtest_*.csv", r"walk_forward_backtest_(.+)\.csv$")
    reasons = ["active product manifest is missing; fallback discovery is not formal recommendation evidence"]
    if not final_run:
        reasons.append("시장국면 final run을 찾지 못했습니다")
    if not hedge_run:
        reasons.append("HedgeMate 추천 run을 찾지 못했습니다")
    if not backtest_run:
        reasons.append("backtest run을 찾지 못했습니다")
    status = "FRESH" if not reasons else "INCOMPLETE"
    return {
        "manifest_version": "hedgemate_active_bundle_fallback_v1",
        "freshness_status": status,
        "stale_reasons": reasons,
        "active_bundle": {
            "scenario_run": scenario_run,
            "final_market_state_run": final_run,
            "hedgemate_run": hedge_run,
            "backtest_run": backtest_run,
            "data_version": scenario_manifest.get("data_version"),
            "scenario_vector_as_of_date": scenario_manifest.get("scenario_vector_as_of_date") or scenario_manifest.get("final_market_state_as_of_date"),
            "generated_at_utc": datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
            "freshness_status": status,
            "stale_reasons": reasons,
        },
        "event_overlay_status": dict(DEFAULT_EVENT_OVERLAY_STATUS),
    }


def find_available_run_ids(processed_dir=OUTPUT_PROCESSED_DIR):
    run_ids = set()
    for path in processed_dir.glob("features_summary_*.csv"):
        m = re.search(r"features_summary_(.+)\.csv$", path.name)
        if m:
            run_ids.add(m.group(1))
    ordered = sorted(run_ids, reverse=True)
    bundle = active_bundle()
    active_run = bundle.get("hedgemate_run") or read_product_manifest().get("active_hedgemate_run")
    if active_run and active_run in ordered:
        ordered = [active_run] + [run_id for run_id in ordered if run_id != active_run]
    return ordered


def find_scenario_run_ids(final_dir=SCENARIO_FINAL_DIR):
    run_ids = {}
    for path in final_dir.glob("final_market_state_daily_*.csv"):
        m = re.search(r"final_market_state_daily_(.+)\.csv$", path.name)
        if m:
            run_ids[m.group(1)] = path.stat().st_mtime
    ordered = [
        run_id
        for run_id, _ in sorted(run_ids.items(), key=lambda item: (item[1], item[0]), reverse=True)
    ]
    product_bundle = active_bundle()
    manifest = read_active_manifest()
    active_run = (
        product_bundle.get("final_market_state_run")
        or read_product_manifest().get("active_final_run")
        or manifest.get("active_final_run")
        or final_run_id_from_filename(manifest.get("active_final_market_state"))
    )
    if active_run and active_run in ordered:
        ordered = [active_run] + [run_id for run_id in ordered if run_id != active_run]
    return ordered


def parse_summary_markdown(path):
    meta = {}
    next_actions = []
    if not path.exists():
        return meta, next_actions

    in_next_actions = False
    with path.open("r", encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line:
                continue
            if line.startswith("## "):
                in_next_actions = line.startswith("## 6. 다음 액션")
                continue
            if in_next_actions and line.startswith("- "):
                next_actions.append(line[2:].strip())
                continue
            if line.startswith("- ") and ":" in line:
                key, value = line[2:].split(":", 1)
                meta[key.strip()] = value.strip()
    return meta, next_actions


def parse_single_asset_ticker(compare_rows):
    if not compare_rows:
        return None
    scenario = str(compare_rows[0].get("scenario", ""))
    m = re.search(r"기준\((.+?) 100%\)", scenario)
    return m.group(1) if m else None


def safe_rel_artifact(rel_path):
    rel_path = rel_path.lstrip("/")
    candidates = [(ROOT / rel_path).resolve(), (ROOT.parent / rel_path).resolve()]
    allowed_roots = [
        OUTPUT_RAW_DIR.resolve(),
        OUTPUT_PROCESSED_DIR.resolve(),
        OUTPUT_REPORT_DIR.resolve(),
        OUTPUT_VALIDATION_DIR.resolve(),
        DOC_RESULT_DIR.resolve(),
        SCENARIO_OUTPUT_DIR.resolve(),
    ]
    for abs_path in candidates:
        if any(root == abs_path or root in abs_path.parents for root in allowed_roots) and abs_path.exists():
            return abs_path
    return None


def latest_generated_at(run_id):
    candidates = [
        OUTPUT_PROCESSED_DIR / f"features_summary_{run_id}.csv",
        OUTPUT_PROCESSED_DIR / f"asset_risk_sensitivity_{run_id}.csv",
        OUTPUT_REPORT_DIR / f"portfolio_compare_{run_id}.csv",
        OUTPUT_REPORT_DIR / f"single_asset_compare_{run_id}.csv",
        OUTPUT_REPORT_DIR / f"asset_sensitivity_summary_{run_id}.md",
        DOC_RESULT_DIR / f"01_실행결과_{run_id}.md",
    ]
    existing = [p for p in candidates if p.exists()]
    if not existing:
        return None
    ts = max(p.stat().st_mtime for p in existing)
    return datetime.fromtimestamp(ts).isoformat(timespec="seconds")


def display_reference_date():
    return datetime.now().date().isoformat()


def parse_weights_snapshot(raw_value):
    if not raw_value:
        return []
    try:
        payload = json.loads(raw_value)
    except (TypeError, ValueError, json.JSONDecodeError):
        return []
    items = []
    for ticker, weight in payload.items():
        try:
            weight_value = float(weight)
        except (TypeError, ValueError):
            continue
        items.append(
            {
                "ticker": ticker,
                "displayName": display_label(ticker),
                "weightPct": weight_value,
            }
        )
    items.sort(key=lambda item: item["weightPct"], reverse=True)
    return items


def choose_best_detail(*row_groups):
    rows = []
    for group in row_groups:
        if not group:
            continue
        rows.extend(group)

    if not rows:
        return None
    recommendation_rank = {
        "PASS_RECOMMEND": 0,
        "REFERENCE_ONLY": 1,
        "INSUFFICIENT_DATA": 2,
        "FAIL_GATE": 3,
    }
    gate_rank = {"PASS": 0, "WARN": 1, "FAIL": 2}
    best = min(
        rows,
        key=lambda row: (
            recommendation_rank.get(str(row.get("recommendation_status") or ""), 9),
            gate_rank.get(str(row.get("status") or ""), 9),
            -(row.get("final_score") if isinstance(row.get("final_score"), (int, float)) else float("-inf")),
            str(row.get("candidate_label") or row.get("candidate_combo") or row.get("candidate_ticker") or ""),
        ),
    )
    enriched = dict(best)
    enrich_candidate_display(enriched)
    if not enriched.get("displayLabel"):
        enriched["displayLabel"] = humanize_scenario(enriched.get("scenario", ""))
    enriched["weights"] = parse_weights_snapshot(enriched.get("weights_snapshot"))
    return enriched


def parse_json_object(raw_value):
    if not raw_value:
        return {}
    try:
        payload = json.loads(raw_value)
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def enrich_candidate_display(row):
    if row.get("candidate_combo"):
        row["displayLabel"] = humanize_combo(row.get("candidate_combo"))
    elif row.get("candidate_ticker"):
        row["displayLabel"] = display_label(row.get("candidate_ticker"))
    elif row.get("candidate_label"):
        row["displayLabel"] = humanize_combo(row.get("candidate_label"))
    return row


def enrich_execution_plan(row):
    share_counts = parse_json_object(row.get("hedge_share_counts"))
    if share_counts:
        plan = []
        for ticker, quantity in share_counts.items():
            try:
                whole_quantity = int(float(quantity))
            except (TypeError, ValueError):
                continue
            if whole_quantity <= 0:
                continue
            try:
                price = lookup_price(ticker, quantity=whole_quantity)
                used_krw = price.get("marketValueKrw")
                if used_krw is None and price.get("latestPrice") and price.get("fxRate"):
                    used_krw = whole_quantity * float(price["latestPrice"]) * float(price["fxRate"])
                plan.append(
                    {
                        "ticker": ticker,
                        "displayName": display_label(ticker),
                        "targetAmountKrw": used_krw,
                        "latestPrice": price.get("latestPrice"),
                        "currency": price.get("currency"),
                        "fxRate": price.get("fxRate"),
                        "priceAsOf": price.get("priceAsOf"),
                        "impliedQuantity": whole_quantity,
                        "wholeShareQuantity": whole_quantity,
                        "estimatedUsedKrw": used_krw,
                        "estimatedCashLeftKrw": None,
                        "warnings": price.get("warnings", []),
                        "errors": price.get("errors", []),
                    }
                )
            except Exception as exc:
                plan.append({"ticker": ticker, "displayName": display_label(ticker), "targetAmountKrw": None, "errors": [str(exc)]})
        if plan:
            row["executionPlan"] = plan
            if isinstance(row.get("hedge_cash_left_krw"), (int, float)):
                row["executionNote"] = f"정수주 매수 기준 실행안 · 후보 전체 예상 잔액 {row['hedge_cash_left_krw']:.0f}원"
            return row

    budget = row.get("hedge_invested_krw") or row.get("hedge_budget_krw")
    if not isinstance(budget, (int, float)) or budget <= 0:
        row["executionPlan"] = []
        row["executionNote"] = "KRW 포트폴리오 금액으로 실행한 run이 아니어서 실제 매수 가능 수량은 포트폴리오 금액 입력 후 계산됩니다."
        return row

    allocations = parse_json_object(row.get("allocation_weights"))
    if not allocations:
        ticker = row.get("candidate_ticker")
        allocations = {ticker: 100.0} if ticker else {}
    total_weight = sum(float(value) for value in allocations.values() if str(value).strip())
    plan = []
    for ticker, weight in allocations.items():
        try:
            share = float(weight) / total_weight if total_weight > 0 else 0
        except (TypeError, ValueError):
            continue
        amount_krw = float(budget) * share
        try:
            price = lookup_price(ticker, amount_krw=amount_krw)
            quantity = price.get("impliedQuantity")
            whole_quantity = int(quantity) if isinstance(quantity, (int, float)) and quantity > 0 else None
            used_krw = None
            cash_left = None
            if whole_quantity is not None and price.get("latestPrice") and price.get("fxRate"):
                used_krw = whole_quantity * float(price["latestPrice"]) * float(price["fxRate"])
                cash_left = amount_krw - used_krw
            plan.append(
                {
                    "ticker": ticker,
                    "displayName": display_label(ticker),
                    "targetAmountKrw": amount_krw,
                    "latestPrice": price.get("latestPrice"),
                    "currency": price.get("currency"),
                    "fxRate": price.get("fxRate"),
                    "priceAsOf": price.get("priceAsOf"),
                    "impliedQuantity": quantity,
                    "wholeShareQuantity": whole_quantity,
                    "estimatedUsedKrw": used_krw,
                    "estimatedCashLeftKrw": cash_left,
                    "warnings": price.get("warnings", []),
                    "errors": price.get("errors", []),
                }
            )
        except Exception as exc:
            plan.append({"ticker": ticker, "displayName": display_label(ticker), "targetAmountKrw": amount_krw, "errors": [str(exc)]})
    row["executionPlan"] = plan
    row["executionNote"] = ""
    return row


def parse_portfolio_text(raw_text):
    rows = []
    for raw_line in str(raw_text or "").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if "," not in line:
            raise ValueError("포트폴리오 입력은 'TICKER,비중' 형식이어야 합니다.")
        ticker, weight = line.split(",", 1)
        ticker = ticker.strip().upper()
        try:
            weight_pct = float(weight.strip())
        except ValueError as exc:
            raise ValueError("비중 숫자를 해석할 수 없습니다. 'TICKER,비중' 형식을 확인해 주세요.") from exc
        rows.append({"ticker": ticker, "weight_pct": weight_pct})
    if not rows:
        raise ValueError("포트폴리오 입력이 비어 있습니다.")
    return rows


def parse_portfolio_rows(raw_rows):
    rows = []
    total_amount_krw = 0.0
    seen_tickers = set()
    for item in raw_rows or []:
        ticker = resolve_asset_query(item.get("asset") or item.get("ticker"))
        if ticker in seen_tickers:
            raise ValueError(f"동일 자산은 한 번만 추가할 수 있습니다: {display_name(ticker)}")
        seen_tickers.add(ticker)
        try:
            amount_krw = float(item.get("amountKrw"))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{ticker} 금액을 숫자로 해석할 수 없습니다.") from exc
        if amount_krw <= 0:
            raise ValueError(f"{ticker} 금액은 0보다 커야 합니다.")
        rows.append({"ticker": ticker, "amount_krw": amount_krw})
        total_amount_krw += amount_krw

    if not rows:
        raise ValueError("포트폴리오 자산이 비어 있습니다.")

    return [
        {"ticker": row["ticker"], "weight_pct": (row["amount_krw"] / total_amount_krw) * 100.0}
        for row in rows
    ], total_amount_krw


def validate_portfolio_weights(rows, max_weight_pct=50.0):
    if not rows:
        raise ValueError("포트폴리오 입력이 비어 있습니다.")

    total = sum(float(row.get("weight_pct", 0.0)) for row in rows)
    if abs(total - 100.0) > 1e-6:
        raise ValueError(f"비중 합계가 100이 아닙니다. (현재 {total:.6f})")

    for row in sorted(rows, key=lambda item: item["ticker"]):
        ticker = row["ticker"]
        weight_pct = float(row.get("weight_pct", 0.0))
        if weight_pct < 0:
            raise ValueError(f"음수 비중 금지 위반 - {ticker}={weight_pct:.4f}%")
        if max_weight_pct is not None and weight_pct > max_weight_pct + 1e-9:
            raise ValueError(f"단일 자산 최대 {max_weight_pct:.1f}% 초과 - {ticker}={weight_pct:.4f}%")


def parse_budget_list_text(raw_value):
    values = []
    seen = set()
    for chunk in str(raw_value or "").split(","):
        token = chunk.strip()
        if not token:
            continue
        value = float(token)
        if value <= 0:
            raise ValueError("헷지 예산 퍼센트는 0보다 커야 합니다.")
        rounded = round(value, 8)
        if rounded not in seen:
            seen.add(rounded)
            values.append(value)
    if not values:
        raise ValueError("헷지 예산이 비어 있습니다.")
    return values


def build_hedge_budget_arg(payload, base_amount_krw=None):
    raw_budget_krw = (payload or {}).get("hedgeBudgetKrw")
    if raw_budget_krw not in (None, ""):
        if base_amount_krw in (None, 0):
            raise ValueError("KRW 헷지 예산을 사용하려면 기준 금액이 필요합니다.")
        try:
            hedge_budget_krw = float(raw_budget_krw)
        except (TypeError, ValueError) as exc:
            raise ValueError("헷지 예산(KRW)을 숫자로 해석할 수 없습니다.") from exc
        if hedge_budget_krw <= 0:
            raise ValueError("헷지 예산(KRW)은 0보다 커야 합니다.")
        hedge_budget_pct = (hedge_budget_krw / float(base_amount_krw)) * 100.0
        if hedge_budget_pct <= 0:
            raise ValueError("헷지 예산 퍼센트가 0 이하입니다.")
        return f"{hedge_budget_pct:.4f}".rstrip("0").rstrip(".")

    return ",".join(str(int(v)) if float(v).is_integer() else str(v) for v in parse_budget_list_text((payload or {}).get("hedgeBudgets") or "10,20,30"))


def write_portfolio_input(rows, job_id=None):
    INPUT_DIR.mkdir(parents=True, exist_ok=True)
    suffix = f"_{job_id}" if job_id else f"_{uuid.uuid4().hex[:8]}"
    path = INPUT_DIR / f"portfolio_weights{suffix}.csv"
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["ticker", "weight_pct"])
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    return path


def extract_run_id_from_stdout(stdout):
    match = re.search(r"FEATURE=.*?features_summary_(.+?)\.csv", stdout or "")
    return match.group(1) if match else None


def hedge_run_ready_for_product_update(run_id):
    if not run_id:
        return False
    required = [
        OUTPUT_PROCESSED_DIR / f"features_summary_{run_id}.csv",
        OUTPUT_PROCESSED_DIR / f"asset_scenario_sensitivity_{run_id}.csv",
        OUTPUT_REPORT_DIR / f"portfolio_1to1_hedge_{run_id}.csv",
        OUTPUT_REPORT_DIR / f"portfolio_multi_hedge_{run_id}.csv",
    ]
    return all(path.exists() for path in required)


def active_bundle_context_for_update():
    manifest = read_product_manifest()
    bundle = active_bundle(manifest)
    scenario_run = bundle.get("scenario_run") or manifest.get("active_scenario_run")
    final_run = bundle.get("final_market_state_run") or manifest.get("active_final_run") or scenario_run
    data_version = bundle.get("data_version") or manifest.get("data_version") or active_data_version(manifest)
    if not scenario_run or not final_run or not data_version:
        return {}
    return {
        "manifest": manifest,
        "scenarioRun": str(scenario_run),
        "finalRun": str(final_run),
        "dataVersion": str(data_version),
        "scenarioVectorAsOfDate": bundle.get("scenario_vector_as_of_date") or manifest.get("scenario_vector_as_of_date"),
    }


def add_artifact_arg(cmd, manifest, arg_name, artifact_key, default_dir=None):
    path = resolve_product_artifact(manifest, artifact_key, default_dir=default_dir)
    if path:
        cmd.extend([arg_name, str(path)])


def build_product_update_commands(
    hedge_run_id,
    historical_validation_run_id="phase10a-wave5-20260514",
    portfolio_input_path=None,
    recommendation_scope="portfolio",
    data_version=None,
):
    context = active_bundle_context_for_update()
    if not context:
        return [], None
    resolved_data_version = str(data_version or context["dataVersion"])
    backtest_run_id = f"backtest-{hedge_run_id}"
    suffix = "backtest_gated"
    if recommendation_scope == "single_asset":
        one_input = OUTPUT_REPORT_DIR / f"single_asset_hedge_1to1_{hedge_run_id}.csv"
        multi_input = OUTPUT_REPORT_DIR / f"single_asset_hedge_multi_{hedge_run_id}.csv"
        one_output = OUTPUT_REPORT_DIR / f"single_asset_hedge_1to1_{hedge_run_id}_{suffix}.csv"
        multi_output = OUTPUT_REPORT_DIR / f"single_asset_hedge_multi_{hedge_run_id}_{suffix}.csv"
    else:
        recommendation_scope = "portfolio"
        one_input = OUTPUT_REPORT_DIR / f"portfolio_1to1_hedge_{hedge_run_id}.csv"
        multi_input = OUTPUT_REPORT_DIR / f"portfolio_multi_hedge_{hedge_run_id}.csv"
        one_output = OUTPUT_REPORT_DIR / f"portfolio_1to1_hedge_{hedge_run_id}_{suffix}.csv"
        multi_output = OUTPUT_REPORT_DIR / f"portfolio_multi_hedge_{hedge_run_id}_{suffix}.csv"
    python = sys.executable
    backtest_cmd = [
        python,
        str(ROOT / "scripts" / "run_scenario_backtest.py"),
        "--run-id",
        backtest_run_id,
        "--historical-validation-run-id",
        historical_validation_run_id,
        "--hedgemate-run-id",
        hedge_run_id,
        "--data-version",
        resolved_data_version,
        "--recommendation-scope",
        recommendation_scope,
    ]
    if portfolio_input_path:
        backtest_cmd.extend(["--portfolio-input", str(portfolio_input_path)])
    gate_cmd = [
        python,
        str(ROOT / "scripts" / "apply_backtest_gate.py"),
        "--hedgemate-run-id",
        hedge_run_id,
        "--backtest-run-id",
        backtest_run_id,
        "--one-to-one-path",
        str(one_input),
        "--multi-path",
        str(multi_input),
        "--one-output-path",
        str(one_output),
        "--multi-output-path",
        str(multi_output),
        "--output-suffix",
        suffix,
    ]
    update_cmd = [
        python,
        str(ROOT / "scripts" / "update_active_bundle.py"),
        "--scenario-run-id",
        context["scenarioRun"],
        "--final-run-id",
        context["finalRun"],
        "--hedgemate-run-id",
        hedge_run_id,
        "--backtest-run-id",
        backtest_run_id,
        "--data-version",
        resolved_data_version,
        "--features",
        str(OUTPUT_PROCESSED_DIR / f"features_summary_{hedge_run_id}.csv"),
        "--asset-scenario-sensitivity",
        str(OUTPUT_PROCESSED_DIR / f"asset_scenario_sensitivity_{hedge_run_id}.csv"),
        "--portfolio-1to1",
        str(one_output),
        "--portfolio-multi",
        str(multi_output),
        "--recommendation-status-qa",
        str(OUTPUT_REPORT_DIR / f"recommendation_status_qa_post_backtest_{hedge_run_id}_{suffix}.md"),
        "--backtest-csv",
        str(OUTPUT_VALIDATION_DIR / f"walk_forward_backtest_{backtest_run_id}.csv"),
        "--backtest-summary",
        str(OUTPUT_REPORT_DIR / f"walk_forward_backtest_summary_{backtest_run_id}.md"),
        "--backtest-gate-summary",
        str(OUTPUT_REPORT_DIR / f"backtest_gate_summary_{hedge_run_id}_{suffix}.md"),
        "--backtest-attribution-csv",
        str(OUTPUT_REPORT_DIR / f"backtest_attribution_{backtest_run_id}.csv"),
        "--backtest-attribution-summary",
        str(OUTPUT_REPORT_DIR / f"backtest_attribution_{backtest_run_id}.md"),
        "--formal-gate-audit-csv",
        str(OUTPUT_REPORT_DIR / f"formal_gate_audit_{hedge_run_id}_{suffix}.csv"),
        "--formal-gate-audit-summary",
        str(OUTPUT_REPORT_DIR / f"formal_gate_audit_{hedge_run_id}_{suffix}.md"),
    ]
    if portfolio_input_path:
        update_cmd.extend(["--portfolio-input", str(portfolio_input_path)])
    if context.get("scenarioVectorAsOfDate"):
        update_cmd.extend(["--scenario-vector-as-of-date", str(context["scenarioVectorAsOfDate"])])
    manifest = context["manifest"]
    add_artifact_arg(update_cmd, manifest, "--scenario-vector", "scenarioVector", SCENARIO_VECTOR_DIR)
    add_artifact_arg(update_cmd, manifest, "--final-scenario-vector", "finalScenarioVector", SCENARIO_VECTOR_DIR)
    add_artifact_arg(update_cmd, manifest, "--final-market-state", "finalMarketState", SCENARIO_FINAL_DIR)
    add_artifact_arg(update_cmd, manifest, "--scenario-confidence", "scenarioConfidence", SCENARIO_FINAL_DIR)
    add_artifact_arg(update_cmd, manifest, "--top-active-scenarios", "topActiveScenarios", SCENARIO_FINAL_DIR)
    add_artifact_arg(update_cmd, manifest, "--final-metadata", "finalMetadata", SCENARIO_REPORT_DIR)
    add_artifact_arg(update_cmd, manifest, "--event-overlay-metadata", "eventOverlayMetadata", SCENARIO_REPORT_DIR)
    add_artifact_arg(update_cmd, manifest, "--final-runbook", "finalRunbook", OUTPUT_REPORT_DIR)
    return [backtest_cmd, gate_cmd, update_cmd], backtest_run_id


def prepare_run_request(payload, job_id=None):
    if not isinstance(payload, dict):
        raise ValueError("JSON 객체 요청이 필요합니다.")

    mode = str((payload or {}).get("mode") or "").strip()
    max_combo_size = parse_max_combo_size((payload or {}).get("maxComboSize"))
    run_id = str((payload or {}).get("runId") or build_run_id())
    cmd = [
        sys.executable,
        str(ROOT / "scripts" / "run_data_pipeline.py"),
        "--max-combo-size",
        str(max_combo_size),
        "--run-id",
        run_id,
    ]
    manifest = read_product_manifest()
    data_version = (payload or {}).get("dataVersion") or active_data_version(manifest)
    if data_version:
        cmd.extend(["--data-version", str(data_version)])
    if bool((payload or {}).get("forceRefreshRaw")):
        cmd.append("--force-refresh-raw")
    scenario_vector = resolve_product_artifact(manifest, "finalScenarioVector", default_dir=SCENARIO_VECTOR_DIR)
    if scenario_vector:
        cmd.extend(["--scenario-vector", str(scenario_vector)])
    prepared = {
        "_prepared_request": True,
        "jobId": job_id,
        "runId": run_id,
        "cmd": cmd,
        "dataVersion": str(data_version) if data_version else None,
    }

    if mode == "single_asset":
        single_asset = resolve_asset_query((payload or {}).get("singleAsset"))
        base_amount_krw = (payload or {}).get("baseAmountKrw")
        if base_amount_krw in (None, ""):
            hedge_budgets = build_hedge_budget_arg(payload)
            cmd.extend(["--hedge-budgets", hedge_budgets])
        else:
            try:
                base_amount_krw = float(base_amount_krw)
            except (TypeError, ValueError) as exc:
                raise ValueError("단일 자산 보유 금액(KRW)을 숫자로 해석할 수 없습니다.") from exc
            if base_amount_krw <= 0:
                raise ValueError("단일 자산 보유 금액(KRW)은 0보다 커야 합니다.")
            raw_budget_krw = (payload or {}).get("hedgeBudgetKrw")
            if raw_budget_krw in (None, ""):
                hedge_budgets = build_hedge_budget_arg(payload, base_amount_krw=base_amount_krw)
                cmd.extend(["--hedge-budgets", hedge_budgets])
            else:
                cmd.extend(["--base-total-krw", str(base_amount_krw), "--hedge-budgets-krw", str(float(raw_budget_krw))])
        cmd.extend(["--single-asset", single_asset])
        prepared["mode"] = "single_asset"
        prepared["backtestPortfolioInputPath"] = str(write_portfolio_input([{"ticker": single_asset, "weight_pct": 100.0}], job_id=job_id))
        return prepared

    if mode == "portfolio":
        portfolio_rows = (payload or {}).get("portfolioRows")
        if portfolio_rows:
            preview = preview_portfolio(payload)
            if not preview["canRunAnalysis"]:
                raise ValueError("; ".join(preview["errors"]) or "포트폴리오 preview를 분석 입력으로 변환할 수 없습니다.")
            rows = preview["analysisRows"]
            total_amount_krw = preview["totalMarketValueKrw"]
            if len(rows) == 1:
                single_asset = rows[0]["ticker"]
                if single_asset == "__CASH__":
                    raise ValueError("현금 단독 입력은 단일자산 헷지 분석 기준으로 사용할 수 없습니다.")
                raw_budget_krw = (payload or {}).get("hedgeBudgetKrw")
                if raw_budget_krw not in (None, "") and total_amount_krw not in (None, 0):
                    cmd.extend(["--base-total-krw", str(total_amount_krw), "--hedge-budgets-krw", str(float(raw_budget_krw))])
                else:
                    hedge_budgets = build_hedge_budget_arg(payload, base_amount_krw=total_amount_krw)
                    cmd.extend(["--hedge-budgets", hedge_budgets])
                cmd.extend(["--single-asset", single_asset])
                prepared["mode"] = "single_asset"
                prepared["singleAsset"] = single_asset
                prepared["backtestPortfolioInputPath"] = str(write_portfolio_input([{"ticker": single_asset, "weight_pct": 100.0}], job_id=job_id))
                return prepared
        else:
            rows = parse_portfolio_text((payload or {}).get("portfolioText"))
            total_amount_krw = None
        validate_portfolio_weights(rows)
        raw_budget_krw = (payload or {}).get("hedgeBudgetKrw")
        if raw_budget_krw not in (None, "") and total_amount_krw not in (None, 0):
            cmd.extend(["--base-total-krw", str(total_amount_krw), "--hedge-budgets-krw", str(float(raw_budget_krw))])
        else:
            hedge_budgets = build_hedge_budget_arg(payload, base_amount_krw=total_amount_krw)
            cmd.extend(["--hedge-budgets", hedge_budgets])
        portfolio_input_path = write_portfolio_input(rows, job_id=job_id)
        cmd.extend(["--portfolio-input", str(portfolio_input_path)])
        prepared["mode"] = "portfolio"
        prepared["portfolioInputPath"] = str(portfolio_input_path)
        prepared["backtestPortfolioInputPath"] = str(portfolio_input_path)
        return prepared

    raise ValueError("mode는 single_asset 또는 portfolio 여야 합니다.")


def _snapshot_run_job(job_id):
    with RUN_JOBS_LOCK:
        job = RUN_JOBS.get(job_id)
        return dict(job) if job else None


def _update_run_job(job_id, **fields):
    with RUN_JOBS_LOCK:
        if job_id not in RUN_JOBS:
            return None
        RUN_JOBS[job_id].update(fields)
        return dict(RUN_JOBS[job_id])


def _cleanup_prepared_artifacts(prepared_request):
    paths = {
        (prepared_request or {}).get("portfolioInputPath"),
        (prepared_request or {}).get("backtestPortfolioInputPath"),
    }
    for portfolio_input_path in paths:
        if not portfolio_input_path:
            continue
        try:
            Path(portfolio_input_path).unlink(missing_ok=True)
        except OSError:
            pass


def _run_pipeline_job(job_id, prepared_request, runner):
    try:
        result = run_pipeline_for_request(
            prepared_request,
            runner=runner,
            status_callback=lambda stage: _update_run_job(job_id, stage=stage),
        )
        _update_run_job(
            job_id,
            status="completed",
            runId=result.get("runId"),
            result=result,
            error=None,
            completedAt=datetime.now().isoformat(timespec="seconds"),
        )
    except Exception as exc:
        _update_run_job(
            job_id,
            status="failed",
            error=str(exc),
            completedAt=datetime.now().isoformat(timespec="seconds"),
        )
    finally:
        _cleanup_prepared_artifacts(prepared_request)


def launch_run_job(payload, runner=subprocess.run, thread_factory=threading.Thread):
    job_id = uuid.uuid4().hex
    prepared_request = payload if (payload or {}).get("_prepared_request") else prepare_run_request(payload, job_id=job_id)
    with RUN_JOBS_LOCK:
        RUN_JOBS[job_id] = {
            "jobId": job_id,
            "status": "running",
            "stage": "queued",
            "runId": None,
            "error": None,
            "result": None,
            "startedAt": datetime.now().isoformat(timespec="seconds"),
            "completedAt": None,
        }
    worker = thread_factory(target=_run_pipeline_job, args=(job_id, prepared_request, runner), daemon=True)
    worker.start()
    return _snapshot_run_job(job_id)


def _run_refresh_market_data_job(job_id, payload, runner):
    data_version = str((payload or {}).get("dataVersion") or datetime.now().strftime("%Y%m%d"))
    run_stamp = str((payload or {}).get("runStamp") or data_version)
    max_combo_size = parse_max_combo_size((payload or {}).get("maxComboSize") or 2)
    _update_run_job(job_id, stage="running refresh pipeline")
    cleanup_paths = []
    portfolio_context = {
        "requested": refresh_payload_has_portfolio_context(payload),
        "applied": False,
        "reason": "no_portfolio_context_requested",
    }
    cmd = [
        sys.executable,
        str(ROOT / "scripts" / "refresh_product_bundle.py"),
        "--data-version",
        data_version,
        "--run-stamp",
        run_stamp,
        "--max-combo-size",
        str(max_combo_size),
    ]
    if (payload or {}).get("portfolioRows"):
        preview = preview_portfolio(payload)
        if not preview["canRunAnalysis"]:
            portfolio_context.update(
                {
                    "applied": False,
                    "reason": "portfolio_context_omitted_preview_error: "
                    + ("; ".join(preview.get("errors") or []) or "portfolio preview cannot be converted into analysis input."),
                }
            )
            preview = None
        if preview:
            portfolio_context.update(
                {
                    "reason": "portfolio_context_pending_validation",
                    "totalMarketValueKrw": preview.get("totalMarketValueKrw"),
                    "rowCount": len(preview.get("analysisRows") or []),
                }
            )
            rows = [
                row
                for row in preview["analysisRows"]
                if row.get("ticker") and row.get("ticker") != "__CASH__"
            ]
            try:
                validate_portfolio_weights(rows)
            except ValueError as exc:
                portfolio_context.update({"applied": False, "reason": f"portfolio_context_omitted_invalid_weights: {exc}"})
                rows = []
            if rows:
                total_amount_krw = preview["totalMarketValueKrw"]
                raw_budget_krw = (payload or {}).get("hedgeBudgetKrw")
                if raw_budget_krw not in (None, "") and total_amount_krw not in (None, 0):
                    budget_args = ["--base-total-krw", str(total_amount_krw), "--hedge-budgets-krw", str(float(raw_budget_krw))]
                    portfolio_context["hedgeBudgetKrw"] = float(raw_budget_krw)
                else:
                    budget_args = ["--hedge-budgets", build_hedge_budget_arg(payload, base_amount_krw=total_amount_krw)]
                portfolio_input_path = write_portfolio_input(rows, job_id=job_id)
                cleanup_paths.append(portfolio_input_path)
                cmd.extend(["--portfolio-input", str(portfolio_input_path)])
                cmd.extend(budget_args)
                portfolio_context.update(
                    {
                        "applied": True,
                        "reason": "portfolio_context_applied",
                        "portfolioInputPath": str(portfolio_input_path),
                        "totalMarketValueKrw": total_amount_krw,
                        "rowCount": len(rows),
                    }
                )
    else:
        raw_base_total_krw = (payload or {}).get("baseTotalKrw") or (payload or {}).get("baseAmountKrw")
        raw_budget_krw = (payload or {}).get("hedgeBudgetKrw")
        if raw_base_total_krw not in (None, "") and raw_budget_krw not in (None, ""):
            base_total_krw = float(raw_base_total_krw)
            if base_total_krw <= 0:
                raise ValueError("baseTotalKrw must be greater than zero.")
            hedge_budget_krw = float(raw_budget_krw)
            cmd.extend(["--base-total-krw", str(base_total_krw), "--hedge-budgets-krw", str(hedge_budget_krw)])
            portfolio_context.update(
                {
                    "applied": True,
                    "reason": "portfolio_amount_context_applied_without_portfolio_rows",
                    "totalMarketValueKrw": base_total_krw,
                    "hedgeBudgetKrw": hedge_budget_krw,
                }
            )
    if bool((payload or {}).get("forceRefreshRaw")):
        cmd.append("--force-refresh-raw")
    try:
        completed = runner(
            cmd,
            cwd=str(ROOT.parent),
            capture_output=True,
            text=True,
            check=False,
        )
        if completed.returncode != 0:
            raise RuntimeError(completed.stderr.strip() or completed.stdout.strip() or "시장데이터 갱신 pipeline 실패")
        _update_run_job(
            job_id,
            status="completed",
            stage="complete",
            result={"ok": True, "dataVersion": data_version, "stdout": completed.stdout, "portfolioContext": portfolio_context},
            error=None,
            completedAt=datetime.now().isoformat(timespec="seconds"),
        )
    finally:
        for path in cleanup_paths:
            try:
                Path(path).unlink(missing_ok=True)
            except OSError:
                pass


def refresh_payload_has_portfolio_context(payload):
    payload = payload or {}
    if payload.get("portfolioRows"):
        return True
    raw_base_total_krw = payload.get("baseTotalKrw") or payload.get("baseAmountKrw")
    raw_budget_krw = payload.get("hedgeBudgetKrw")
    return raw_base_total_krw not in (None, "") and raw_budget_krw not in (None, "")


def launch_refresh_market_data_job(payload=None, runner=subprocess.run, thread_factory=threading.Thread):
    force = bool((payload or {}).get("force"))
    has_portfolio_context = refresh_payload_has_portfolio_context(payload)
    freshness = load_data_freshness()
    job_id = uuid.uuid4().hex
    with RUN_JOBS_LOCK:
        RUN_JOBS[job_id] = {
            "jobId": job_id,
            "jobType": "market_data_refresh",
            "status": "queued",
            "stage": "queued",
            "runId": None,
            "error": None,
            "result": None,
            "freshness": freshness,
            "startedAt": datetime.now().isoformat(timespec="seconds"),
            "completedAt": None,
        }
    if freshness.get("skipHeavyRefresh") and not force and not has_portfolio_context:
        _update_run_job(
            job_id,
            status="skipped_latest",
            stage="skipped_latest",
            result={
                "ok": True,
                "skipped": True,
                "reason": "이미 오늘 기준 최신 데이터입니다.",
                "freshness": freshness,
                "portfolioContext": {
                    "requested": False,
                    "applied": False,
                    "reason": "skipped_latest_without_portfolio_context",
                },
            },
            completedAt=datetime.now().isoformat(timespec="seconds"),
        )
        return _snapshot_run_job(job_id)

    def worker_target():
        try:
            _update_run_job(job_id, status="running", stage="refreshing")
            _run_refresh_market_data_job(job_id, payload or {}, runner)
        except Exception as exc:
            _update_run_job(
                job_id,
                status="failed",
                stage="failed",
                error=str(exc),
                completedAt=datetime.now().isoformat(timespec="seconds"),
            )

    worker = thread_factory(target=worker_target, daemon=True)
    worker.start()
    return _snapshot_run_job(job_id)


def run_pipeline_for_request(payload, runner=subprocess.run, status_callback=None):
    prepared_request = payload if (payload or {}).get("_prepared_request") else prepare_run_request(payload, job_id=(payload or {}).get("jobId"))
    cmd = list(prepared_request["cmd"])

    if status_callback:
        status_callback("running HedgeMate analysis")
    completed = runner(
        cmd,
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or completed.stdout.strip() or "파이프라인 실행 실패")
    run_id = extract_run_id_from_stdout(completed.stdout)
    run_id = run_id or prepared_request.get("runId") or (find_available_run_ids()[0] if find_available_run_ids() else None)
    product_bundle_updated = False
    backtest_run_id = None
    if hedge_run_ready_for_product_update(run_id):
        followup_commands, backtest_run_id = build_product_update_commands(
            run_id,
            portfolio_input_path=prepared_request.get("backtestPortfolioInputPath"),
            recommendation_scope=prepared_request.get("mode") or "portfolio",
            data_version=prepared_request.get("dataVersion"),
        )
        for followup_cmd in followup_commands:
            command_text = " ".join(str(part) for part in followup_cmd)
            if status_callback:
                if "run_scenario_backtest.py" in command_text:
                    status_callback("running scenario backtest")
                elif "apply_backtest_gate.py" in command_text:
                    status_callback("applying backtest gate")
                elif "update_active_bundle.py" in command_text:
                    status_callback("updating active dashboard bundle")
            followup = runner(
                followup_cmd,
                cwd=str(ROOT.parent),
                capture_output=True,
                text=True,
                check=False,
            )
            if followup.returncode != 0:
                raise RuntimeError(followup.stderr.strip() or followup.stdout.strip() or "product bundle 갱신 실패")
        product_bundle_updated = bool(followup_commands)
    if status_callback:
        status_callback("completed")
    return {
        "ok": True,
        "runId": run_id,
        "backtestRunId": backtest_run_id,
        "productBundleUpdated": product_bundle_updated,
        "stdout": completed.stdout,
    }


def artifact_rel_from_path(path):
    if not path:
        return None
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = (SCENARIO_RESEARCH_ROOT / candidate).resolve()
    else:
        candidate = candidate.resolve()
    try:
        return str(candidate.relative_to(ROOT.parent.resolve())).replace("\\", "/")
    except ValueError:
        return None


def scenario_artifact(path):
    if not path:
        return None
    return artifact_rel_from_path(path)


def markdown_bullets(path, limit=8):
    if not path or not path.exists():
        return []
    bullets = []
    with path.open("r", encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.strip()
            if line.startswith("- "):
                bullets.append(line[2:].strip())
                if len(bullets) >= limit:
                    break
    return bullets


def latest_scenario_validation_payload():
    metadata_path = latest_path(SCENARIO_REPORT_DIR, "historical_validation_metadata_*.json")
    metadata = read_json(metadata_path, {}) if metadata_path else {}
    validation_path = None
    review_path = None
    if metadata:
        validation_csv = metadata.get("validation_csv")
        validation_review = metadata.get("validation_review")
        validation_path = Path(validation_csv) if validation_csv else None
        review_path = Path(validation_review) if validation_review else None
    if not validation_path or not validation_path.exists():
        validation_path = latest_path(SCENARIO_VALIDATION_DIR, "historical_validation_cases_*.csv")
    if not review_path or not review_path.exists():
        review_path = latest_path(SCENARIO_REPORT_DIR, "historical_validation_review_*.md")
    return {
        "metadata": metadata,
        "cases": read_csv_rows(validation_path)[:12] if validation_path else [],
        "reviewBullets": markdown_bullets(review_path, limit=8) if review_path else [],
        "artifacts": {
            "validationCsv": scenario_artifact(validation_path),
            "validationReview": scenario_artifact(review_path),
            "validationMetadata": scenario_artifact(metadata_path),
        },
    }


def state_counts(rows):
    counts = {}
    for row in rows:
        state = row.get("final_display_state") or row.get("display_state") or row.get("final_state") or "UNKNOWN"
        counts[str(state)] = counts.get(str(state), 0) + 1
    return [{"state": key, "count": counts[key]} for key in sorted(counts)]


def lens_summary(rows):
    grouped = {}
    for row in rows:
        lens = str(row.get("lens") or "unknown")
        current = grouped.setdefault(lens, {"lens": lens, "count": 0, "topScore": None, "topScenario": None})
        current["count"] += 1
        score = row.get("final_score")
        if isinstance(score, (int, float)) and (current["topScore"] is None or score > current["topScore"]):
            current["topScore"] = score
            current["topScenario"] = row.get("scenario_name_ko") or row.get("scenario_name") or row.get("scenario_code")
    return sorted(grouped.values(), key=lambda item: (item["topScore"] is None, -(item["topScore"] or 0), item["lens"]))


def scenario_state_run_id_from_metadata(metadata, fallback):
    state_path = metadata.get("state_path")
    if not state_path:
        return fallback
    m = re.search(r"scenario_state_daily_(.+)\.csv$", Path(str(state_path)).name)
    return m.group(1) if m else fallback


def build_data_freshness_note(display_date, data_date, snapshot_metadata):
    if not display_date or not data_date or str(display_date) == str(data_date):
        return ""
    last_dates = snapshot_metadata.get("last_date_by_ticker", {}) if isinstance(snapshot_metadata, dict) else {}
    core_tickers = ["SPY", "QQQ", "TLT", "DIA", "VTI", "^VIX"]
    lagging = [ticker for ticker in core_tickers if last_dates.get(ticker) and str(last_dates[ticker]) < str(display_date)]
    if lagging:
        preview = ", ".join(lagging[:4])
        suffix = " 등" if len(lagging) > 4 else ""
        return f"미국 ETF 일봉({preview}{suffix})이 {data_date}까지 확인되어 최종 일봉을 그 날짜에 맞췄습니다."
    return f"최종 시나리오 일봉은 공통 커버리지가 충분한 {data_date}까지 확정됐습니다."


def load_scenario_dashboard_data(run_id=None):
    product_manifest = read_product_manifest()
    product_bundle = active_bundle(product_manifest)
    manifest = read_active_manifest()
    runs = find_scenario_run_ids()
    manifest_run_id = (
        product_bundle.get("final_market_state_run")
        or product_manifest.get("active_final_run")
        or manifest.get("active_final_run")
        or final_run_id_from_filename(manifest.get("active_final_market_state"))
    )
    target_run_id = run_id or manifest_run_id or (runs[0] if runs else None)
    if not target_run_id:
        raise FileNotFoundError("Scenario research run not found")

    final_path = SCENARIO_FINAL_DIR / f"final_market_state_daily_{target_run_id}.csv"
    if not run_id and not final_path.exists() and runs:
        target_run_id = runs[0]
        final_path = SCENARIO_FINAL_DIR / f"final_market_state_daily_{target_run_id}.csv"
    if not final_path.exists():
        raise FileNotFoundError(f"Scenario research run not found: {target_run_id}")

    confidence_path = SCENARIO_FINAL_DIR / f"scenario_confidence_{target_run_id}.csv"
    top_path = SCENARIO_FINAL_DIR / f"top_active_scenarios_{target_run_id}.json"
    metadata_path = SCENARIO_REPORT_DIR / f"final_market_state_metadata_{target_run_id}.json"
    summary_path = SCENARIO_REPORT_DIR / f"final_market_state_summary_{target_run_id}.md"
    vector_path = (
        resolve_product_artifact(product_manifest, "finalScenarioVector", SCENARIO_VECTOR_DIR)
        or resolve_product_artifact(product_manifest, "scenarioVector", SCENARIO_VECTOR_DIR)
        or resolve_manifest_artifact(manifest, "active_scenario_vector_json", SCENARIO_VECTOR_DIR)
        or resolve_manifest_artifact(manifest, "active_scenario_vector", SCENARIO_VECTOR_DIR)
        or latest_path(SCENARIO_VECTOR_DIR, "current_scenario_vector_*.json")
    )
    nowcast_path = latest_path(SCENARIO_NOWCAST_DIR, "current_intraday_nowcast_*.json")
    event_metadata_path = resolve_product_artifact(product_manifest, "eventOverlayMetadata", SCENARIO_REPORT_DIR) or latest_path(SCENARIO_REPORT_DIR, "event_overlay_metadata_*.json")
    event_review_path = latest_path(SCENARIO_REPORT_DIR, "event_overlay_review_*.md")
    event_daily_path = latest_path(SCENARIO_EVENT_DIR, "event_overlay_daily_*.csv")
    integration_dashboard_path = latest_path(SCENARIO_REPORT_DIR, "integration_review_dashboard_*.html")
    phase4_dashboard_path = latest_path(SCENARIO_REPORT_DIR, "phase4_review_dashboard_*.html")
    phase5_dashboard_path = latest_path(SCENARIO_REPORT_DIR, "phase5_event_overlay_dashboard_*.html")

    final_rows = read_csv_rows(final_path)
    top_payload = read_json(top_path, {}) or {}
    metadata = read_json(metadata_path, {}) or {}
    scenario_state_run_id = scenario_state_run_id_from_metadata(metadata, target_run_id)
    snapshot_metadata_path = SCENARIO_REPORT_DIR / f"scenario_snapshot_metadata_{scenario_state_run_id}.json"
    snapshot_metadata = read_json(snapshot_metadata_path, {}) if snapshot_metadata_path.exists() else {}
    vector_rows = read_json_or_csv_rows(vector_path)
    nowcast_rows = read_json(nowcast_path, []) if nowcast_path else []
    event_metadata = read_json(event_metadata_path, {}) if event_metadata_path else {}
    validation = latest_scenario_validation_payload()

    data_as_of_date = top_payload.get("date") or metadata.get("date")
    if not data_as_of_date and final_rows:
        data_as_of_date = max(str(row.get("date")) for row in final_rows if row.get("date"))
    display_as_of_date = display_reference_date()
    data_freshness_note = build_data_freshness_note(display_as_of_date, data_as_of_date, snapshot_metadata)
    rows_for_date = [row for row in final_rows if str(row.get("date")) == str(data_as_of_date)] if data_as_of_date else []
    if not rows_for_date:
        rows_for_date = final_rows[-20:]

    top_market_rows = sorted(
        rows_for_date,
        key=lambda row: row.get("final_score") if isinstance(row.get("final_score"), (int, float)) else float("-inf"),
        reverse=True,
    )[:12]
    vector_leaders = sorted(
        vector_rows if isinstance(vector_rows, list) else [],
        key=lambda row: row.get("score") if isinstance(row.get("score"), (int, float)) else float("-inf"),
        reverse=True,
    )[:8]
    nowcast_leaders = sorted(
        nowcast_rows if isinstance(nowcast_rows, list) else [],
        key=lambda row: row.get("score") if isinstance(row.get("score"), (int, float)) else float("-inf"),
        reverse=True,
    )[:8]

    artifacts = {
        "finalMarketState": scenario_artifact(final_path),
        "scenarioConfidence": scenario_artifact(confidence_path),
        "topActiveJson": scenario_artifact(top_path),
        "finalSummary": scenario_artifact(summary_path),
        "finalMetadata": scenario_artifact(metadata_path),
        "scenarioVector": scenario_artifact(vector_path),
        "nowcastVector": scenario_artifact(nowcast_path),
        "eventOverlayDaily": scenario_artifact(event_daily_path),
        "eventOverlayMetadata": scenario_artifact(event_metadata_path),
        "eventOverlayReview": scenario_artifact(event_review_path),
        "integrationDashboard": scenario_artifact(integration_dashboard_path),
        "phase4Dashboard": scenario_artifact(phase4_dashboard_path),
        "phase5Dashboard": scenario_artifact(phase5_dashboard_path),
    }
    artifacts.update(validation.get("artifacts", {}))
    artifacts = {key: value for key, value in artifacts.items() if value}

    return {
        "runId": target_run_id,
        "runs": runs,
        "asOfDate": display_as_of_date,
        "dataAsOfDate": data_as_of_date,
        "generatedAt": datetime.fromtimestamp(final_path.stat().st_mtime).isoformat(timespec="seconds"),
        "meta": {
            "pipelinePhase": metadata.get("pipeline_phase"),
            "engineVersion": top_payload.get("merge_engine_version") or metadata.get("merge_engine_version"),
            "finalRowCount": metadata.get("final_row_count") or len(final_rows),
            "overlayRowCount": metadata.get("overlay_row_count"),
            "validationCases": validation.get("metadata", {}).get("case_count"),
            "validationOkCases": validation.get("metadata", {}).get("ok_case_count"),
            "eventArticleCount": event_metadata.get("article_count"),
            "anchorDate": snapshot_metadata.get("anchor_date"),
            "dataQualityStatus": snapshot_metadata.get("data_quality_status"),
        },
        "dataFreshnessNote": data_freshness_note,
        "summaryBullets": markdown_bullets(summary_path, limit=8),
        "topActiveScenarios": top_payload.get("top_active_scenarios", []),
        "topMarketRows": top_market_rows,
        "stateCounts": state_counts(rows_for_date),
        "lensSummary": lens_summary(rows_for_date),
        "scenarioVectorLeaders": vector_leaders,
        "nowcastLeaders": nowcast_leaders,
        "eventOverlay": {
            "metadata": event_metadata,
            "rows": read_csv_rows(event_daily_path)[:10] if event_daily_path else [],
            "reviewBullets": markdown_bullets(event_review_path, limit=6) if event_review_path else [],
        },
        "validation": validation,
        "artifacts": artifacts,
    }


def load_dashboard_data(run_id, product_manifest=None):
    features_path = OUTPUT_PROCESSED_DIR / f"features_summary_{run_id}.csv"
    if not features_path.exists():
        raise FileNotFoundError(f"Run not found: {run_id}")
    product_manifest = read_product_manifest() if product_manifest is None else product_manifest
    product_bundle = active_bundle(product_manifest)
    use_active_artifacts = run_id == (product_bundle.get("hedgemate_run") or product_manifest.get("active_hedgemate_run"))

    result_md = DOC_RESULT_DIR / f"01_실행결과_{run_id}.md"
    review_md = DOC_RESULT_DIR / f"03_결과검토_{run_id}.md"
    draft_md = DOC_RESULT_DIR / f"02_분석리포트_초안_{run_id}.md"

    summary_meta, next_actions = parse_summary_markdown(result_md)
    features = read_csv_rows(features_path)
    asset_sensitivities = read_csv_rows(OUTPUT_PROCESSED_DIR / f"asset_risk_sensitivity_{run_id}.csv")
    dq_rows = read_csv_rows(OUTPUT_REPORT_DIR / f"dq_result_{run_id}.csv")
    top_hedges = read_csv_rows(OUTPUT_REPORT_DIR / f"hes_components_{run_id}.csv")
    portfolio_compare = read_csv_rows(OUTPUT_REPORT_DIR / f"portfolio_compare_{run_id}.csv")
    single_asset_compare = read_csv_rows(OUTPUT_REPORT_DIR / f"single_asset_compare_{run_id}.csv")
    recommendation_artifact_warnings = []
    if use_active_artifacts:
        portfolio_multi_path, warning = resolve_active_gated_recommendation_artifact(product_manifest, "portfolioMulti")
        if warning:
            recommendation_artifact_warnings.append(warning)
        portfolio_1to1_path, warning = resolve_active_gated_recommendation_artifact(product_manifest, "portfolio1to1")
        if warning:
            recommendation_artifact_warnings.append(warning)
    else:
        portfolio_multi_path = OUTPUT_REPORT_DIR / f"portfolio_multi_hedge_{run_id}.csv"
        portfolio_1to1_path = OUTPUT_REPORT_DIR / f"portfolio_1to1_hedge_{run_id}.csv"
    portfolio_multi = read_csv_rows(portfolio_multi_path) if portfolio_multi_path else []
    portfolio_1to1 = read_csv_rows(portfolio_1to1_path) if portfolio_1to1_path else []
    single_asset_multi = read_csv_rows(OUTPUT_REPORT_DIR / f"single_asset_hedge_multi_{run_id}.csv")
    single_asset_1to1 = read_csv_rows(OUTPUT_REPORT_DIR / f"single_asset_hedge_1to1_{run_id}.csv")
    metric_validation = read_csv_rows(OUTPUT_REPORT_DIR / f"metric_validation_{run_id}.csv")

    worst_risk_assets = sorted(
        [row for row in features if row.get("mdd_1y_krw") is not None],
        key=lambda row: row["mdd_1y_krw"],
    )[:8]

    for row in top_hedges:
        row["displayName"] = display_name(row.get("ticker"))
    for row in worst_risk_assets:
        row["displayName"] = display_name(row.get("ticker"))
    for row in asset_sensitivities:
        row["displayName"] = display_name(row.get("ticker"))
    for row in portfolio_compare:
        row["displayScenario"] = humanize_scenario(row.get("scenario"))
    for row in single_asset_compare:
        row["displayScenario"] = humanize_scenario(row.get("scenario"))
    for row in portfolio_multi + portfolio_1to1 + single_asset_multi + single_asset_1to1:
        enrich_candidate_display(row)
        enrich_execution_plan(row)

    dq_summary = {"pass": 0, "warn": 0, "fail": 0}
    for row in dq_rows:
        status = str(row.get("status", "")).lower()
        if status == "pass":
            dq_summary["pass"] += 1
        elif status == "warn":
            dq_summary["warn"] += 1
        elif status == "fail":
            dq_summary["fail"] += 1

    validation_summary = {
        "pass": sum(1 for row in metric_validation if row.get("status") == "PASS"),
        "fail": sum(1 for row in metric_validation if row.get("status") == "FAIL"),
    }

    product_artifacts = product_manifest.get("artifacts", {}) if isinstance(product_manifest.get("artifacts"), dict) else {}
    artifacts = {
        "marketRaw": f"outputs/raw/raw_market_daily_{run_id}.csv",
        "fxRaw": f"outputs/raw/raw_fx_daily_{run_id}.csv",
        "benchmarkRaw": f"outputs/raw/raw_benchmark_daily_{run_id}.csv",
        "features": f"outputs/processed/features_summary_{run_id}.csv",
        "assetSensitivity": f"outputs/processed/asset_risk_sensitivity_{run_id}.csv",
        "dq": f"outputs/reports/dq_result_{run_id}.csv",
        "hes": f"outputs/reports/hes_components_{run_id}.csv",
        "assetSensitivitySummary": f"outputs/reports/asset_sensitivity_summary_{run_id}.md",
        "portfolioCompare": f"outputs/reports/portfolio_compare_{run_id}.csv",
        "portfolio1to1": product_artifacts.get("portfolio1to1") if use_active_artifacts else f"outputs/reports/portfolio_1to1_hedge_{run_id}.csv",
        "portfolioMulti": product_artifacts.get("portfolioMulti") if use_active_artifacts else f"outputs/reports/portfolio_multi_hedge_{run_id}.csv",
        "singleAssetCompare": f"outputs/reports/single_asset_compare_{run_id}.csv",
        "singleAsset1to1": f"outputs/reports/single_asset_hedge_1to1_{run_id}.csv",
        "singleAssetMulti": f"outputs/reports/single_asset_hedge_multi_{run_id}.csv",
        "resultMd": f"docs/STEP_1/04_실행결과/01_실행결과_{run_id}.md",
        "draftMd": f"docs/STEP_1/04_실행결과/02_분석리포트_초안_{run_id}.md",
        "reviewMd": f"docs/STEP_1/04_실행결과/03_결과검토_{run_id}.md",
    }

    base_portfolio_weights = []
    input_path = None
    if product_bundle:
        input_path = product_bundle.get("portfolio_input_fingerprint", {}).get("path")
    if not input_path and product_manifest:
        input_path = product_manifest.get("portfolio_input_fingerprint", {}).get("path")
    
    if input_path:
        full_path = ROOT / input_path
        if full_path.exists():
            base_portfolio_weights = read_csv_rows(full_path)
    if not base_portfolio_weights:
        fallback_path = ROOT / "inputs" / "portfolio_weights.csv"
        if fallback_path.exists():
            base_portfolio_weights = read_csv_rows(fallback_path)
            
    for row in base_portfolio_weights:
        if "weight_pct" in row:
            try:
                row["weightPct"] = float(row["weight_pct"])
            except ValueError:
                row["weightPct"] = 0.0

    return {
        "runId": run_id,
        "generatedAt": latest_generated_at(run_id),
        "singleAssetTicker": parse_single_asset_ticker(single_asset_compare),
        "meta": {
            "baseCurrency": "KRW",
            "analysisPeriod": summary_meta.get("분석기간"),
            "targetTickers": summary_meta.get("대상 티커"),
            "fetchedTickers": summary_meta.get("수집 성공 티커"),
            "stressDays": summary_meta.get("위기구간(stress) 일수"),
            "benchmark": summary_meta.get("위기구간 벤치마크"),
            "cachedRaw": summary_meta.get("raw 재사용 여부(동일 data_version 재실행)"),
            "cachedFx": summary_meta.get("FX raw 재사용 여부"),
            "recommendationArtifactWarnings": recommendation_artifact_warnings,
            "usesActiveGatedRecommendations": bool(use_active_artifacts and not recommendation_artifact_warnings),
        },
        "dqSummary": dq_summary,
        "validationSummary": validation_summary,
        "portfolioCompare": portfolio_compare,
        "singleAssetCompare": single_asset_compare,
        "portfolioOneToOne": portfolio_1to1,
        "portfolioMulti": portfolio_multi,
        "singleAssetOneToOne": single_asset_1to1,
        "singleAssetMulti": single_asset_multi,
        "portfolioBestDetail": choose_best_detail(portfolio_multi, portfolio_1to1),
        "singleAssetBestDetail": choose_best_detail(single_asset_multi, single_asset_1to1),
        "assetSensitivities": asset_sensitivities,
        "topHedges": top_hedges,
        "worstRiskAssets": worst_risk_assets,
        "basePortfolioWeights": base_portfolio_weights,
        "nextActions": next_actions,
        "artifacts": artifacts,
        "activeManifest": product_manifest if use_active_artifacts else {},
    }


def backtest_case_key(row):
    case_id = str(row.get("case_id") or "").strip()
    scenario = str(row.get("expected_scenario_code") or "").strip()
    case_name = str(row.get("case_name") or "").strip()
    if case_id:
        return case_id
    if scenario or case_name:
        return f"{scenario}|{case_name}"
    return ""


def backtest_case_label(row):
    return str(row.get("case_name") or row.get("case_id") or row.get("expected_scenario_code") or "").strip()


def is_target_backtest_row(row):
    return str(row.get("is_target_scenario") or "").strip().upper() in {"Y", "TRUE", "1"}


def numeric_values(rows, key):
    values = []
    for row in rows:
        value = row.get(key)
        if isinstance(value, (int, float)):
            values.append(float(value))
    return values


def number_summary(values, digits=2):
    if not values:
        return {"min": None, "avg": None, "max": None}
    return {
        "min": round(min(values), digits),
        "avg": round(sum(values) / len(values), digits),
        "max": round(max(values), digits),
    }


def unique_case_labels(rows):
    labels = {}
    for row in rows:
        key = backtest_case_key(row)
        if not key:
            continue
        labels[key] = backtest_case_label(row) or key
    return [labels[key] for key in sorted(labels)]


def pipe_separated_counts(rows, key):
    counts = {}
    for row in rows:
        for value in str(row.get(key) or "").split("|"):
            ticker = value.strip()
            if ticker:
                counts[ticker] = counts.get(ticker, 0) + 1
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))


def has_pipe_separated_value(row, key):
    return any(value.strip() for value in str(row.get(key) or "").split("|"))


def has_pipe_token(row, key, token):
    return token in {value.strip() for value in str(row.get(key) or "").split("|") if value.strip()}


def formal_gate_cash_baseline_summary(rows):
    lag_rows = [row for row in rows if has_pipe_token(row, "formal_gate_blockers", "cash_baseline_lag")]
    if not lag_rows:
        return {
            "lagCandidateRows": 0,
            "targetLagStressRows": 0,
            "avgCashNetStressDelta": number_summary([], digits=6),
            "topRows": [],
        }
    return {
        "lagCandidateRows": len(lag_rows),
        "targetLagStressRows": int(sum(parse_float(row.get("target_lags_cash_count")) or 0 for row in lag_rows)),
        "avgCashNetStressDelta": number_summary(numeric_values(lag_rows, "target_avg_cash_net_stress_delta"), digits=6),
        "minCashNetStressDelta": number_summary(numeric_values(lag_rows, "target_min_cash_net_stress_delta"), digits=6),
        "avgCashNetMddDelta": number_summary(numeric_values(lag_rows, "target_avg_cash_net_mdd_delta"), digits=6),
        "avgCashNetCvarDelta": number_summary(numeric_values(lag_rows, "target_avg_cash_net_cvar_delta"), digits=6),
        "topRows": lag_rows[:8],
    }


def formal_gate_bootstrap_summary(rows):
    blocked_rows = [
        row
        for row in rows
        if has_pipe_token(row, "formal_gate_blockers", "bootstrap_not_robust")
        or has_pipe_token(row, "formal_gate_blockers", "cash_bootstrap_not_robust")
    ]
    cash_blocked_rows = [row for row in rows if has_pipe_token(row, "formal_gate_blockers", "cash_bootstrap_not_robust")]
    if not blocked_rows:
        return {
            "notRobustCandidateRows": 0,
            "cashNotRobustCandidateRows": 0,
            "targetBootstrapRows": 0,
            "targetBootstrapRobustRows": 0,
            "targetCashBootstrapRows": 0,
            "targetCashBootstrapRobustRows": 0,
            "pImprove": number_summary([], digits=4),
            "cashPImprove": number_summary([], digits=4),
            "topRows": [],
        }
    return {
        "notRobustCandidateRows": len(blocked_rows),
        "cashNotRobustCandidateRows": len(cash_blocked_rows),
        "targetBootstrapRows": int(sum(parse_float(row.get("target_bootstrap_count")) or 0 for row in blocked_rows)),
        "targetBootstrapRobustRows": int(sum(parse_float(row.get("target_bootstrap_robust_count")) or 0 for row in blocked_rows)),
        "targetCashBootstrapRows": int(sum(parse_float(row.get("target_cash_bootstrap_count")) or 0 for row in blocked_rows)),
        "targetCashBootstrapRobustRows": int(sum(parse_float(row.get("target_cash_bootstrap_robust_count")) or 0 for row in blocked_rows)),
        "pImprove": number_summary(numeric_values(blocked_rows, "target_bootstrap_min_p_improve"), digits=4),
        "avgPImprove": number_summary(numeric_values(blocked_rows, "target_bootstrap_avg_p_improve"), digits=4),
        "cashPImprove": number_summary(numeric_values(blocked_rows, "target_cash_bootstrap_min_p_improve"), digits=4),
        "cashAvgPImprove": number_summary(numeric_values(blocked_rows, "target_cash_bootstrap_avg_p_improve"), digits=4),
        "topRows": blocked_rows[:8],
    }


def is_short_evaluation_row(row, min_days=60):
    value = parse_float(row.get("evaluation_day_count"))
    return value is not None and value < min_days


def price_coverage_blocker_type(no_common_rows, pre_inception_rows, missing_price_rows):
    if not no_common_rows and not missing_price_rows:
        return "PRICE_COVERED_FOR_EVALUATED_WINDOWS"
    if missing_price_rows and pre_inception_rows:
        return "MIXED_PRE_INCEPTION_AND_MISSING_PRICE"
    if missing_price_rows:
        return "MISSING_PRICE_DATA"
    if no_common_rows and len(pre_inception_rows) == len(no_common_rows):
        return "PRE_INCEPTION_ONLY"
    if pre_inception_rows:
        return "PRE_INCEPTION_PARTIAL"
    return "OTHER_PRICE_WINDOW_GAP"


def backtest_quality_level(summary):
    if summary["rowCount"] <= 0 or summary["evaluatedRows"] <= 0:
        return "MISSING"
    if summary["targetEvaluatedRows"] <= 0 or summary["evaluatedCaseCount"] < 3:
        return "LOW"
    if summary["insufficientCaseCount"] > 0 or (summary["evaluationDays"]["min"] or 0) < 60 or summary["evaluatedCaseCount"] < 8:
        return "MEDIUM"
    return "HIGH"


def backtest_quality_warnings(summary):
    warnings = []
    if summary.get("cashLagRows", 0) > 0:
        warnings.append(f"현금화 기준보다 약한 hedge stress 결과 {summary['cashLagRows']}건")
    if summary.get("priceGapCaseCount", 0) > 0:
        names = ", ".join(summary.get("priceGapCaseNames", [])[:3])
        warnings.append(f"가격 히스토리 범위 밖 stress case {summary['priceGapCaseCount']}개: {names}")
    if summary.get("noCommonPriceCaseCount", 0) > 0:
        names = ", ".join(summary.get("noCommonPriceCaseNames", [])[:3])
        warnings.append(f"공통 가격일이 없어 직접검증 불가 stress case {summary['noCommonPriceCaseCount']}개: {names}")
    if summary.get("priceCoverageBlockerType") == "PRE_INCEPTION_ONLY":
        warnings.append("가격 공백은 missing data가 아니라 현재 포트폴리오 종목의 상장 전 stress window에서 발생했습니다.")
    if summary["insufficientCaseCount"] > 0:
        names = ", ".join(summary["insufficientCaseNames"][:3])
        warnings.append(f"검증 불가 stress case {summary['insufficientCaseCount']}개: {names}")
    min_days = summary["evaluationDays"]["min"]
    if min_days is not None and min_days < 60:
        names = ", ".join(summary.get("shortEvaluationCaseNames", [])[:3])
        suffix = f": {names}" if names else ""
        warnings.append(f"가장 짧은 평가 구간이 {min_days:g}거래일이라 장기 stress 검증으로는 약합니다{suffix}.")
    if summary["targetEvaluatedRows"] <= 0:
        warnings.append("후보의 대상 시나리오와 직접 맞는 백테스트가 없습니다.")
    if summary["evaluatedCaseCount"] < 8:
        warnings.append(f"평가된 stress case가 {summary['evaluatedCaseCount']}개라 regime 표본이 제한적입니다.")
    if summary.get("targetBootstrapRows", 0) > 0 and summary.get("targetBootstrapRobustRows", 0) < summary.get("targetBootstrapRows", 0):
        warnings.append("대상 stress case 전체에서 bootstrap 신뢰가 충분히 강하지 않습니다.")
    if summary.get("targetCashBootstrapRows", 0) > 0 and summary.get("targetCashBootstrapRobustRows", 0) < summary.get("targetCashBootstrapRows", 0):
        warnings.append("대상 stress case 전체에서 cash-baseline 대비 bootstrap 신뢰가 충분히 강하지 않습니다.")
    if summary.get("preInceptionTickerCounts"):
        tickers = ", ".join(list(summary["preInceptionTickerCounts"])[:5])
        warnings.append(f"Pre-inception price history blocks stress validation for: {tickers}")
    if summary.get("missingPriceTickerCounts"):
        tickers = ", ".join(list(summary["missingPriceTickerCounts"])[:5])
        warnings.append(f"Missing price history blocks stress validation for: {tickers}")
    return warnings


def build_backtest_coverage_summary(rows):
    evaluated = [row for row in rows if str(row.get("backtest_status") or "").upper() == "EVALUATED"]
    insufficient = [row for row in rows if str(row.get("backtest_status") or "").upper() == "INSUFFICIENT_HISTORY"]
    short_evaluation_rows = [row for row in evaluated if is_short_evaluation_row(row)]
    price_gap_rows = [row for row in rows if str(row.get("price_window_status") or "").upper() == "OUT_OF_PRICE_RANGE"]
    no_common_price_rows = [row for row in rows if str(row.get("price_window_status") or "").upper() in {"NO_COMMON_PRICE_DATES", "PRICE_DATA_MISSING"}]
    pre_inception_rows = [row for row in rows if has_pipe_separated_value(row, "pre_inception_tickers")]
    missing_price_rows = [row for row in rows if has_pipe_separated_value(row, "missing_price_tickers")]
    cash_lag_rows = [row for row in rows if str(row.get("hedge_vs_cash_verdict") or "").upper() == "LAGS_CASH"]
    target_rows = [row for row in rows if is_target_backtest_row(row)]
    target_evaluated = [row for row in target_rows if str(row.get("backtest_status") or "").upper() == "EVALUATED"]
    target_worsened = [row for row in target_evaluated if str(row.get("verdict") or "").upper() == "WORSENED"]
    target_improved = [row for row in target_evaluated if str(row.get("verdict") or "").upper() == "IMPROVED"]
    target_insufficient = [row for row in target_rows if str(row.get("verdict") or "").upper() == "INSUFFICIENT_HISTORY"]
    target_bootstrap_rows = [row for row in target_evaluated if str(row.get("bootstrap_confidence") or "").strip()]
    target_bootstrap_robust = [
        row for row in target_bootstrap_rows if str(row.get("bootstrap_confidence") or "").upper() == "ROBUST_IMPROVE"
    ]
    target_bootstrap_uncertain = [
        row for row in target_bootstrap_rows if str(row.get("bootstrap_confidence") or "").upper() == "UNCERTAIN"
    ]
    target_bootstrap_worse = [
        row for row in target_bootstrap_rows if str(row.get("bootstrap_confidence") or "").upper() == "ROBUST_WORSE"
    ]
    target_cash_bootstrap_rows = [row for row in target_evaluated if str(row.get("cash_bootstrap_confidence") or "").strip()]
    target_cash_bootstrap_robust = [
        row for row in target_cash_bootstrap_rows if str(row.get("cash_bootstrap_confidence") or "").upper() == "ROBUST_IMPROVE"
    ]
    target_cash_bootstrap_uncertain = [
        row for row in target_cash_bootstrap_rows if str(row.get("cash_bootstrap_confidence") or "").upper() == "UNCERTAIN"
    ]
    target_cash_bootstrap_worse = [
        row for row in target_cash_bootstrap_rows if str(row.get("cash_bootstrap_confidence") or "").upper() == "ROBUST_WORSE"
    ]
    evaluated_case_names = unique_case_labels(evaluated)
    insufficient_case_names = unique_case_labels(insufficient)
    short_evaluation_case_names = unique_case_labels(short_evaluation_rows)
    price_gap_case_names = unique_case_labels(price_gap_rows)
    no_common_price_case_names = unique_case_labels(no_common_price_rows)
    pre_inception_case_names = unique_case_labels(pre_inception_rows)
    missing_price_case_names = unique_case_labels(missing_price_rows)
    price_window_status_counts = {}
    cash_verdict_counts = {}
    bootstrap_confidence_counts = {}
    cash_bootstrap_confidence_counts = {}
    for row in rows:
        status = str(row.get("price_window_status") or "").strip() or "UNKNOWN"
        price_window_status_counts[status] = price_window_status_counts.get(status, 0) + 1
        cash_status = str(row.get("hedge_vs_cash_verdict") or "").strip()
        if cash_status:
            cash_verdict_counts[cash_status] = cash_verdict_counts.get(cash_status, 0) + 1
        bootstrap_status = str(row.get("bootstrap_confidence") or "").strip()
        if bootstrap_status:
            bootstrap_confidence_counts[bootstrap_status] = bootstrap_confidence_counts.get(bootstrap_status, 0) + 1
        cash_bootstrap_status = str(row.get("cash_bootstrap_confidence") or "").strip()
        if cash_bootstrap_status:
            cash_bootstrap_confidence_counts[cash_bootstrap_status] = cash_bootstrap_confidence_counts.get(cash_bootstrap_status, 0) + 1
    summary = {
        "rowCount": len(rows),
        "evaluatedRows": len(evaluated),
        "insufficientRows": len(insufficient),
        "shortEvaluationRows": len(short_evaluation_rows),
        "outOfPriceRangeRows": len(price_gap_rows),
        "noCommonPriceRows": len(no_common_price_rows),
        "preInceptionBlockedRows": len(pre_inception_rows),
        "missingPriceBlockedRows": len(missing_price_rows),
        "cashLagRows": len(cash_lag_rows),
        "targetEvaluatedRows": len(target_evaluated),
        "targetImprovedRows": len(target_improved),
        "targetWorsenedRows": len(target_worsened),
        "targetInsufficientRows": len(target_insufficient),
        "evaluatedCaseCount": len(evaluated_case_names),
        "insufficientCaseCount": len(insufficient_case_names),
        "shortEvaluationCaseCount": len(short_evaluation_case_names),
        "priceGapCaseCount": len(price_gap_case_names),
        "noCommonPriceCaseCount": len(no_common_price_case_names),
        "preInceptionBlockedCaseCount": len(pre_inception_case_names),
        "missingPriceBlockedCaseCount": len(missing_price_case_names),
        "evaluatedCaseNames": evaluated_case_names[:12],
        "insufficientCaseNames": insufficient_case_names[:12],
        "shortEvaluationCaseNames": short_evaluation_case_names[:12],
        "priceGapCaseNames": price_gap_case_names[:12],
        "noCommonPriceCaseNames": no_common_price_case_names[:12],
        "preInceptionBlockedCaseNames": pre_inception_case_names[:12],
        "missingPriceBlockedCaseNames": missing_price_case_names[:12],
        "priceCoverageBlockerType": price_coverage_blocker_type(no_common_price_rows, pre_inception_rows, missing_price_rows),
        "priceWindowStatusCounts": price_window_status_counts,
        "priceBlockingTickerCounts": pipe_separated_counts(rows, "price_blocking_tickers"),
        "preInceptionTickerCounts": pipe_separated_counts(rows, "pre_inception_tickers"),
        "missingPriceTickerCounts": pipe_separated_counts(rows, "missing_price_tickers"),
        "cashBaselineVerdictCounts": cash_verdict_counts,
        "evaluatedScenarioCount": len({str(row.get("expected_scenario_code") or "") for row in evaluated if row.get("expected_scenario_code")}),
        "evaluationDays": number_summary(numeric_values(evaluated, "evaluation_day_count")),
        "priceCoverageRatio": number_summary(numeric_values(evaluated, "price_coverage_ratio")),
        "implementationCost": number_summary(numeric_values(evaluated, "implementation_cost"), digits=6),
        "recurringRebalanceCost": number_summary(numeric_values(evaluated, "recurring_rebalance_cost"), digits=6),
        "totalPathCost": number_summary(numeric_values(evaluated, "total_path_cost"), digits=6),
        "transactionCostBps": number_summary(numeric_values(evaluated, "transaction_cost_bps")),
        "slippageBps": number_summary(numeric_values(evaluated, "slippage_bps")),
        "bootstrapConfidenceCounts": bootstrap_confidence_counts,
        "cashBootstrapConfidenceCounts": cash_bootstrap_confidence_counts,
        "targetBootstrapRows": len(target_bootstrap_rows),
        "targetBootstrapRobustRows": len(target_bootstrap_robust),
        "targetBootstrapUncertainRows": len(target_bootstrap_uncertain),
        "targetBootstrapWorseRows": len(target_bootstrap_worse),
        "targetBootstrapPImprove": number_summary(numeric_values(target_bootstrap_rows, "net_stress_delta_p_improve"), digits=4),
        "targetCashBootstrapRows": len(target_cash_bootstrap_rows),
        "targetCashBootstrapRobustRows": len(target_cash_bootstrap_robust),
        "targetCashBootstrapUncertainRows": len(target_cash_bootstrap_uncertain),
        "targetCashBootstrapWorseRows": len(target_cash_bootstrap_worse),
        "targetCashBootstrapPImprove": number_summary(numeric_values(target_cash_bootstrap_rows, "cash_net_stress_delta_p_improve"), digits=4),
    }
    summary["qualityLevel"] = backtest_quality_level(summary)
    summary["warnings"] = backtest_quality_warnings(summary)
    return summary


def load_backtest_payload(manifest):
    path = resolve_product_artifact(manifest, "backtestCsv", OUTPUT_VALIDATION_DIR)
    rows = read_csv_rows(path) if path else []
    formal_gate_audit_path = resolve_product_artifact(manifest, "formalGateAuditCsv", OUTPUT_REPORT_DIR)
    formal_gate_rows = read_csv_rows(formal_gate_audit_path) if formal_gate_audit_path else []
    verdict_counts = {}
    status_counts_payload = {}
    for row in rows:
        verdict = str(row.get("verdict") or "UNKNOWN")
        verdict_counts[verdict] = verdict_counts.get(verdict, 0) + 1
        status = str(row.get("backtest_status") or "UNKNOWN")
        status_counts_payload[status] = status_counts_payload.get(status, 0) + 1
    return {
        "rows": rows[:40],
        "rowCount": len(rows),
        "verdictCounts": verdict_counts,
        "statusCounts": status_counts_payload,
        "coverageSummary": build_backtest_coverage_summary(rows),
        "summaryArtifact": scenario_artifact(resolve_product_artifact(manifest, "backtestSummary", OUTPUT_REPORT_DIR)),
        "gateSummaryArtifact": scenario_artifact(resolve_product_artifact(manifest, "backtestGateSummary", OUTPUT_REPORT_DIR)),
        "attributionCsvArtifact": scenario_artifact(resolve_product_artifact(manifest, "backtestAttributionCsv", OUTPUT_REPORT_DIR)),
        "attributionSummaryArtifact": scenario_artifact(resolve_product_artifact(manifest, "backtestAttributionSummary", OUTPUT_REPORT_DIR)),
        "formalGateAuditCsvArtifact": scenario_artifact(formal_gate_audit_path),
        "formalGateAuditSummaryArtifact": scenario_artifact(resolve_product_artifact(manifest, "formalGateAuditSummary", OUTPUT_REPORT_DIR)),
        "formalGateAuditSummary": {
            "rowCount": len(formal_gate_rows),
            "blockerCounts": pipe_separated_counts(formal_gate_rows, "formal_gate_blockers"),
            "statusCounts": {
                status: sum(1 for row in formal_gate_rows if str(row.get("recommendation_status") or "") == status)
                for status in sorted({str(row.get("recommendation_status") or "") for row in formal_gate_rows if row.get("recommendation_status")})
            },
            "cashBaselineAudit": formal_gate_cash_baseline_summary(formal_gate_rows),
            "bootstrapAudit": formal_gate_bootstrap_summary(formal_gate_rows),
            "topRows": formal_gate_rows[:12],
        },
    }


def recommendation_rows_from_hedge(hedge):
    hedge = hedge or {}
    single_asset_rows = [
        row
        for key in ("singleAssetOneToOne", "singleAssetMulti")
        for row in hedge.get(key, []) or []
        if row and (row.get("candidate_ticker") or row.get("candidate_combo"))
    ]
    single_asset_rows_are_gated = any(row.get("backtest_gate_status") for row in single_asset_rows)
    selected_rows = (
        single_asset_rows
        if hedge.get("singleAssetTicker") and single_asset_rows_are_gated
        else [
            row
            for key in ("portfolioOneToOne", "portfolioMulti")
            for row in hedge.get(key, []) or []
            if row and (row.get("candidate_ticker") or row.get("candidate_combo"))
        ]
    )
    return [row for row in selected_rows if row.get("recommendation_status")]


def recommendation_status_counts(rows):
    counts = {
        "PASS_RECOMMEND": 0,
        "REFERENCE_ONLY": 0,
        "FAIL_GATE": 0,
        "INSUFFICIENT_DATA": 0,
    }
    for row in rows or []:
        status = str(row.get("recommendation_status") or "UNKNOWN")
        counts[status] = counts.get(status, 0) + 1
    return counts


def event_overlay_trade_gate_allowed(event_status):
    if event_status is None:
        return True
    usage = str(
        event_status.get("trade_gate_usage")
        or event_status.get("recommendation_usage")
        or ""
    ).strip().lower()
    return usage in {"enabled", "trade_gate_enabled", "live_trade_gate_enabled", "production_trade_gate_enabled"}


def build_recommendation_decision(hedge, backtest, data_freshness, event_status=None):
    rows = recommendation_rows_from_hedge(hedge)
    counts = recommendation_status_counts(rows)
    coverage = (backtest or {}).get("coverageSummary") or {}
    formal_gate_summary = (backtest or {}).get("formalGateAuditSummary") or {}
    cash_baseline_audit = formal_gate_summary.get("cashBaselineAudit") or {}
    bootstrap_audit = formal_gate_summary.get("bootstrapAudit") or {}
    reasons = []
    blockers = []

    freshness_status = str((data_freshness or {}).get("status") or "").lower()
    if freshness_status == "stale":
        reason_text = "; ".join((data_freshness or {}).get("reasons") or []) or "시장/시나리오 기준일이 맞지 않습니다."
        blockers.append("stale_data")
        reasons.append(f"데이터 갱신 확인 필요: {reason_text}")

    if counts.get("PASS_RECOMMEND", 0) <= 0:
        blockers.append("no_formal_recommendation")
        reasons.append("백테스트 게이트를 통과한 정식 추천 후보가 없습니다.")

    if not coverage.get("rowCount"):
        blockers.append("missing_backtest")
        reasons.append("과거 stress backtest 산출물이 없어 실행 추천으로 승격할 수 없습니다.")

    quality_level = str(coverage.get("qualityLevel") or "").upper()
    if coverage.get("rowCount") and quality_level and quality_level != "HIGH":
        blockers.append("validation_quality_not_high")
        reasons.append(f"Backtest 검증 강도가 {quality_level}이라 HIGH 기준에 미달해 정식 실행 추천을 차단합니다.")

    if not event_overlay_trade_gate_allowed(event_status):
        blockers.append("event_overlay_not_trade_safe")
        reasons.append("이벤트 오버레이가 fixture/review-only 상태이거나 trade gate 사용으로 활성화되지 않아 정식 실행 추천을 차단합니다.")

    cash_lag_rows = int(coverage.get("cashLagRows") or 0)
    if cash_lag_rows > 0:
        reasons.append(f"{cash_lag_rows}개 검증행에서 같은 금액을 현금으로 남기는 기준보다 약했습니다.")

    no_common_cases = int(coverage.get("noCommonPriceCaseCount") or 0)
    if no_common_cases > 0:
        if coverage.get("priceCoverageBlockerType") == "PRE_INCEPTION_ONLY":
            tickers = ", ".join(list((coverage.get("preInceptionTickerCounts") or {}).keys())[:5])
            reasons.append(f"{no_common_cases}개 stress case는 missing price가 아니라 상장 전 가격 이력 한계로 직접 검증하지 못했습니다: {tickers}")
        else:
            reasons.append(f"{no_common_cases}개 stress case는 공통 가격일 부족으로 직접 검증하지 못했습니다.")

    insufficient_cases = int(coverage.get("insufficientCaseCount") or 0)
    if insufficient_cases > 0:
        reasons.append(f"{insufficient_cases}개 stress case는 히스토리 부족으로 충분히 검증되지 않았습니다.")

    evaluated_cases = int(coverage.get("evaluatedCaseCount") or 0)
    if coverage.get("rowCount") and evaluated_cases < 8:
        reasons.append(f"평가된 stress case가 {evaluated_cases}개라 regime 표본이 제한적입니다.")

    can_execute = not blockers
    if can_execute:
        state = "FORMAL_RECOMMENDATION_AVAILABLE"
        severity = "ok"
        title = "정식 추천 후보가 있습니다."
        copy = "그래도 헷지 후보는 현금 보유 기준, stress 표본, 데이터 기준일을 함께 확인한 뒤 실행해야 합니다."
        section_title = "정식 추천과 검증 근거"
        section_copy = "정식 추천 후보를 먼저 보여주고, 참고/탈락 후보는 비교 감사용으로 분리합니다."
    elif "stale_data" in blockers:
        state = "BLOCKED_STALE_DATA"
        severity = "danger"
        title = "데이터 기준일이 맞지 않아 실행 추천을 차단했습니다."
        copy = "가격 데이터와 시나리오 스냅샷 기준일이 어긋난 상태에서는 좋은 후보처럼 보여도 실행 추천으로 취급하지 않습니다."
        section_title = "실행 추천 차단 · 후보 감사 목록"
        section_copy = "아래 항목은 현재 실행 권고가 아니라, 갱신 후 다시 검증해야 할 후보 목록입니다."
    elif counts.get("PASS_RECOMMEND", 0) <= 0:
        state = "NO_FORMAL_RECOMMENDATION"
        severity = "danger" if counts.get("FAIL_GATE", 0) else "warning"
        title = "현재 검증 기준에서 실행 추천 가능한 헷지 후보가 없습니다."
        copy = "참고용 후보가 있더라도 현금화 기준 대비 초과효과, 직접 stress 표본, backtest evidence가 부족하면 추천으로 보지 않습니다."
        section_title = "실행 추천 불가 · 후보 감사 목록"
        section_copy = "아래 카드는 매수 권고가 아니라 왜 탈락/참고 판정을 받았는지 확인하는 감사 목록입니다."
    else:
        state = "BLOCKED_VALIDATION"
        severity = "warning"
        title = "검증 조건이 약해 실행 추천을 보류했습니다."
        copy = "정식 추천 후보가 일부 있어도 backtest 산출물이나 stress 검증 조건이 약하면 실행 후보로 취급하지 않습니다."
        section_title = "추천 보류 · 후보 감사 목록"
        section_copy = "아래 후보는 추가 검증 전까지 실행 권고가 아닙니다."

    return {
        "state": state,
        "severity": severity,
        "canExecuteRecommendations": can_execute,
        "title": title,
        "copy": copy,
        "sectionTitle": section_title,
        "sectionCopy": section_copy,
        "primaryReasons": reasons[:8],
        "blockers": blockers,
        "statusCounts": counts,
        "candidateCount": len(rows),
        "formalRecommendationCount": counts.get("PASS_RECOMMEND", 0),
        "referenceOnlyCount": counts.get("REFERENCE_ONLY", 0),
        "failGateCount": counts.get("FAIL_GATE", 0),
        "cashLagRows": cash_lag_rows,
        "cashBaselineAudit": cash_baseline_audit,
        "bootstrapAudit": bootstrap_audit,
        "evaluatedStressCaseCount": evaluated_cases,
        "insufficientStressCaseCount": insufficient_cases,
        "noCommonPriceStressCaseCount": no_common_cases,
    }


ACTION_STATUSES = ("FORMAL_ACTION", "REVIEW_ACTION", "RESEARCH_ONLY", "FAIL_ACTION", "NO_ACTION")
ACTION_STATUS_ALIASES = {
    "FORMAL": "FORMAL_ACTION",
    "FORMAL_RECOMMENDATION": "FORMAL_ACTION",
    "PASS_RECOMMEND": "FORMAL_ACTION",
    "REVIEW": "REVIEW_ACTION",
    "REVIEW_ONLY": "REVIEW_ACTION",
    "REFERENCE_ONLY": "REVIEW_ACTION",
    "REFERENCE": "REVIEW_ACTION",
    "RESEARCH": "RESEARCH_ONLY",
    "RESEARCH_ONLY": "RESEARCH_ONLY",
    "INFO_ONLY": "RESEARCH_ONLY",
    "FAIL": "FAIL_ACTION",
    "FAILED": "FAIL_ACTION",
    "FAIL_GATE": "FAIL_ACTION",
    "BLOCKED": "FAIL_ACTION",
    "NO_ACTION": "NO_ACTION",
    "NONE": "NO_ACTION",
    "NO_VALID_ACTION": "NO_ACTION",
    "INSUFFICIENT_DATA": "NO_ACTION",
}
ACTION_STATUS_FIELDS = (
    "action_status",
    "actionStatus",
    "action_plan_status",
    "actionPlanStatus",
    "action_decision",
    "actionDecision",
    "decision_status",
    "decisionStatus",
    "status",
    "recommendation_status",
)
ACTION_PLAN_SCOPE = "SELECTED_ACTIONS_ONLY"
ACTION_CANDIDATES_SCOPE = "FULL_EVALUATED_ACTION_CANDIDATES"
ACTION_DECISION_COUNT_BASIS = "hedgeActionPlan_selected_actions_only"


def action_payload_shape():
    return {
        "portfolioVulnerabilityAttribution": {
            "type": "array",
            "scope": "portfolio_holding_vulnerability_attribution_rows",
            "countedByActionPlanDecision": False,
        },
        "portfolioVulnerabilitySummary": {
            "type": "summary",
            "scope": "portfolio_vulnerability_summary",
            "countedByActionPlanDecision": False,
        },
        "hedgeActionCandidates": {
            "type": "array",
            "scope": ACTION_CANDIDATES_SCOPE,
            "countedByActionPlanDecision": False,
        },
        "hedgeActionPlan": {
            "type": "array",
            "scope": ACTION_PLAN_SCOPE,
            "jsonSourceKey": "selected_actions",
            "countedByActionPlanDecision": True,
        },
        "hedgeActionPlanSummary": {
            "type": "summary",
            "scope": "selected_action_plan_summary",
            "countedByActionPlanDecision": False,
        },
        "actionPlanDecision": {
            "type": "decision",
            "countBasis": ACTION_DECISION_COUNT_BASIS,
            "countedRowSet": "hedgeActionPlan",
            "countedRowScope": ACTION_PLAN_SCOPE,
        },
    }


def row_keys_for_optional_artifact(key):
    if key == "hedgeActionPlan":
        return ("selected_actions", "action_plan", "actions", "rows", "items", "records")
    if key == "hedgeActionCandidates":
        return ("action_candidates", "candidates", "rows", "items", "records")
    if key == "portfolioVulnerabilityAttribution":
        return ("attribution", "portfolio_vulnerability_attribution", "rows", "items", "records")
    return ("rows", "items", "records")


def _split_action_list(value):
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [part.strip() for part in str(value or "").replace(",", "|").split("|") if part.strip()]


def _parse_weight_json_for_api(value):
    if not value:
        return {}
    if isinstance(value, dict):
        return value
    try:
        payload = json.loads(value)
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _float_for_api(value, default=0.0):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    if math.isnan(number):
        return default
    return number


def enrich_attribution_contract_aliases(row):
    if not isinstance(row, dict):
        return row
    row.setdefault("scenario", row.get("scenario_code") or row.get("risk_sleeve") or "")
    row.setdefault("asset_ticker", row.get("ticker") or row.get("holding_ticker") or "")
    row.setdefault("source_asset", row.get("ticker") if row.get("source_or_offset") == "source" else row.get("source_asset", ""))
    row.setdefault("current_weight", row.get("weight_pct") or row.get("current_weight_pct") or row.get("weight") or "")
    row.setdefault("current_weight_pct", row.get("weight_pct") or row.get("current_weight") or "")
    row.setdefault("scenario_activation_weight", row.get("scenario_weight") or row.get("scenario_context_weight") or "")
    row.setdefault("asset_scenario_beta", row.get("signed_sensitivity") or row.get("scenario_beta") or "")
    row.setdefault("weighted_contribution", row.get("vulnerability_contribution") or row.get("risk_contribution") or "")
    row.setdefault("contribution_pct", row.get("sleeve_contribution_pct") or row.get("contribution_pct_of_sleeve") or "")
    row.setdefault("contribution_pct_of_sleeve", row.get("sleeve_contribution_pct") or row.get("contribution_pct") or "")
    row.setdefault("contribution_pct_of_total", row.get("portfolio_contribution_pct") or "")
    row.setdefault("plain_korean_reason", row.get("plain_reason_ko") or row.get("reason_ko") or "")
    return row


def _action_expected_effect_for_api(row):
    if row.get("expected_effect"):
        return row["expected_effect"]
    pieces = []
    vuln_delta = _float_for_api(row.get("vulnerability_delta"), None)
    if vuln_delta is not None:
        pieces.append(f"취약성 {'감소' if vuln_delta < 0 else '증가'} {abs(vuln_delta):.4f}")
    for key, label, good_positive in [
        ("cvar_delta", "CVaR", True),
        ("mdd_delta", "MDD", True),
        ("stress_delta", "stress", True),
        ("sharpe_delta", "Sharpe", True),
    ]:
        delta = _float_for_api(row.get(key), None)
        if delta is None:
            continue
        improved = delta >= 0 if good_positive else delta < 0
        pieces.append(f"{label} {'개선' if improved else '악화'}")
    return "; ".join(pieces) if pieces else "전후 지표 계산값이 없어 정성 근거를 확인해야 합니다."


def _action_status_reason_for_api(row):
    if row.get("status_reason_ko"):
        return row["status_reason_ko"]
    status = normalize_action_status(row)
    if status == "FORMAL_ACTION":
        return "기존 formal recommendation gate를 통과한 실행 가능 액션입니다."
    if status == "REVIEW_ACTION":
        return "리스크 완화 효과는 있으나 기존 formal gate를 통과하지 못해 검토 후보로 유지합니다."
    if status == "FAIL_ACTION":
        return f"기준 미통과: {row.get('constraint_reasons') or row.get('rejected_reason_ko') or '취약성 또는 핵심 지표 개선이 부족합니다.'}"
    if status == "NO_ACTION":
        return "제약 조건 안에서 유효한 bounded action을 만들지 못했습니다."
    return "실행 추천과 분리된 리서치 전용 후보입니다."


def enrich_action_contract_aliases(row):
    if not isinstance(row, dict):
        return row
    status = normalize_action_status(row)
    before = _parse_weight_json_for_api(row.get("before_weights_json") or row.get("beforeWeightsJson"))
    after = _parse_weight_json_for_api(row.get("after_weights_json") or row.get("afterWeightsJson"))
    source_asset = row.get("source_asset") or row.get("holding_ticker") or (_split_action_list(row.get("source_tickers"))[:1] or [""])[0]
    hedge_asset = row.get("hedge_asset") or row.get("candidate_ticker") or (_split_action_list(row.get("candidate_tickers"))[:1] or [""])[0]
    row.setdefault("action_status", status)
    row.setdefault("scenario", row.get("risk_sleeve") or row.get("vulnerability_id") or "")
    row.setdefault("source_asset", source_asset)
    row.setdefault("hedge_asset", hedge_asset)
    row.setdefault("scenario_weight", row.get("scenario_activation_weight") or "")
    row.setdefault("contribution_pct", row.get("source_contribution_pct") or row.get("contribution_pct_of_sleeve") or "")
    row.setdefault("contribution_pct_of_sleeve", row.get("source_contribution_pct") or row.get("contribution_pct") or "")
    if source_asset:
        row.setdefault("current_weight", before.get(source_asset, row.get("source_current_weight_pct", "")))
        row.setdefault("proposed_weight", after.get(source_asset, row.get("source_proposed_weight_pct", "")))
        row.setdefault("source_current_weight_pct", before.get(source_asset, row.get("current_weight", "")))
        row.setdefault("source_proposed_weight_pct", after.get(source_asset, row.get("proposed_weight", "")))
    if hedge_asset:
        row.setdefault("hedge_current_weight_pct", before.get(hedge_asset, ""))
        row.setdefault("hedge_proposed_weight_pct", after.get(hedge_asset, ""))
    row.setdefault("action_reason_ko", row.get("plain_korean_reason") or row.get("reason_ko") or "")
    row.setdefault("plain_korean_reason", row.get("action_reason_ko") or "")
    row.setdefault("status_reason_ko", _action_status_reason_for_api(row))
    row.setdefault("expected_effect", _action_expected_effect_for_api(row))
    if status == "FORMAL_ACTION":
        row.setdefault("rejected_reason_ko", "")
    else:
        row.setdefault(
            "rejected_reason_ko",
            row.get("constraint_reasons")
            or "기존 formal gate, stress/backtest 근거, CVaR·MDD 안정성 중 일부가 부족해 정식 추천에서 제외했습니다.",
        )
    row.setdefault("can_execute_action", status == "FORMAL_ACTION")
    return row


def enrich_optional_rows_contract(key, rows):
    if key == "portfolioVulnerabilityAttribution":
        return [enrich_attribution_contract_aliases(row) for row in rows]
    if key in {"hedgeActionPlan", "hedgeActionCandidates"}:
        return [enrich_action_contract_aliases(row) for row in rows]
    return rows


def load_optional_rows_artifact(manifest, key):
    path = resolve_product_artifact(manifest, key, default_dir=OUTPUT_REPORT_DIR)
    if not path:
        return [], None, f"missing action artifact: {key}"
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return enrich_optional_rows_contract(key, read_csv_rows(path)), scenario_artifact(path), ""
    if suffix == ".json":
        try:
            payload = read_json(path, [])
        except (OSError, json.JSONDecodeError) as exc:
            return [], scenario_artifact(path), f"failed to read action artifact: {key}={path.name}: {exc}"
        if isinstance(payload, list):
            return enrich_optional_rows_contract(key, payload), scenario_artifact(path), ""
        if isinstance(payload, dict):
            for rows_key in row_keys_for_optional_artifact(key):
                rows = payload.get(rows_key)
                if isinstance(rows, list):
                    return enrich_optional_rows_contract(key, rows), scenario_artifact(path), ""
        return [], scenario_artifact(path), f"action artifact has no row array: {key}"
    return [], scenario_artifact(path), f"action artifact is not a supported row artifact: {key}={path.name}"


def load_optional_summary_artifact(manifest, key):
    empty = {"text": "", "rows": [], "data": None, "artifact": None}
    path = resolve_product_artifact(manifest, key, default_dir=OUTPUT_REPORT_DIR)
    if not path:
        return empty, f"missing action artifact: {key}"
    artifact = scenario_artifact(path)
    suffix = path.suffix.lower()
    try:
        if suffix == ".csv":
            return {"text": "", "rows": read_csv_rows(path), "data": None, "artifact": artifact}, ""
        if suffix == ".json":
            return {"text": "", "rows": [], "data": read_json(path, {}), "artifact": artifact}, ""
        return {"text": path.read_text(encoding="utf-8"), "rows": [], "data": None, "artifact": artifact}, ""
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        payload = dict(empty)
        payload["artifact"] = artifact
        return payload, f"failed to read action artifact: {key}={path.name}: {exc}"


def load_action_plan_metadata(manifest):
    path = resolve_product_artifact(manifest, "hedgeActionPlan", default_dir=OUTPUT_REPORT_DIR)
    if not path or path.suffix.lower() != ".json":
        return {}
    try:
        payload = read_json(path, {})
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(payload, dict):
        return {}
    row_keys = set(row_keys_for_optional_artifact("hedgeActionPlan"))
    return {key: value for key, value in payload.items() if key not in row_keys}


def normalize_action_status(row):
    if not isinstance(row, dict):
        return "NO_ACTION"
    for field in ACTION_STATUS_FIELDS:
        raw = row.get(field)
        if raw in (None, ""):
            continue
        status = str(raw).strip().upper().replace("-", "_").replace(" ", "_")
        return ACTION_STATUS_ALIASES.get(status, status if status in ACTION_STATUSES else "NO_ACTION")
    return "NO_ACTION"


def append_unique(values, value):
    if value and value not in values:
        values.append(value)


def selected_action_type_counts(action_rows):
    counts = {}
    for row in action_rows or []:
        action_type = str(row.get("action_type") or "UNKNOWN")
        counts[action_type] = counts.get(action_type, 0) + 1
    return dict(sorted(counts.items()))


def selected_risk_sleeve_counts(action_rows):
    counts = {}
    for row in action_rows or []:
        sleeve = str(row.get("risk_sleeve") or "UNKNOWN")
        counts[sleeve] = counts.get(sleeve, 0) + 1
    return dict(sorted(counts.items()))


def replace_sleeve_decision_for_api(action_rows, action_plan_metadata=None):
    action_plan_metadata = action_plan_metadata or {}
    raw = action_plan_metadata.get("replace_sleeve_decision") or {}
    type_counts = selected_action_type_counts(action_rows)
    selected_count = int(raw.get("selected_count") or type_counts.get("REPLACE_SLEEVE") or 0)
    candidate_count = int(raw.get("candidate_count") or 0)
    if selected_count > 0:
        absence_code = ""
        absence_ko = ""
    else:
        absence_code = raw.get("absence_reason_code") or "NO_SELECTED_REPLACE_SLEEVE"
        absence_ko = raw.get("absence_reason_ko") or "selected action plan에 REPLACE_SLEEVE가 없습니다."
    return {
        "actionType": "REPLACE_SLEEVE",
        "candidateCount": candidate_count,
        "selectedCount": selected_count,
        "presentInCandidates": bool(raw.get("present_in_candidates") or candidate_count > 0),
        "presentInSelected": selected_count > 0,
        "absenceReasonCode": absence_code,
        "absenceReasonKo": absence_ko,
    }


def build_action_plan_decision(action_rows, recommendation_decision=None, artifact_warnings=None, action_plan_metadata=None):
    recommendation_decision = recommendation_decision or {}
    artifact_warnings = [warning for warning in (artifact_warnings or []) if warning]
    action_plan_metadata = action_plan_metadata or {}
    status_counts = {status: 0 for status in ACTION_STATUSES}
    for row in action_rows or []:
        status_counts[normalize_action_status(row)] += 1

    formal_count = status_counts["FORMAL_ACTION"]
    review_count = status_counts["REVIEW_ACTION"]
    research_count = status_counts["RESEARCH_ONLY"]
    fail_count = status_counts["FAIL_ACTION"]
    no_action_count = status_counts["NO_ACTION"]
    blockers = []
    reasons = []
    reasons_ko = []
    upgrade_requirements = []

    if not action_rows:
        append_unique(blockers, "no_action_plan")
        reasons.append("No bounded hedge action plan is available for the active portfolio.")
        reasons_ko.append("현재 active run에 선택된 bounded hedge action plan이 없습니다.")
        upgrade_requirements.append("portfolioVulnerabilityAttribution, hedgeActionCandidates, hedgeActionPlan 산출물을 먼저 생성해야 합니다.")
    elif formal_count <= 0:
        append_unique(blockers, "no_formal_action")
        if review_count > 0:
            reasons.append("Review actions can reduce risk but are not formal executable recommendations.")
            reasons_ko.append("취약성을 낮추는 REVIEW_ACTION은 있지만 기존 formal recommendation gate를 통과한 FORMAL_ACTION은 없습니다.")
            upgrade_requirements.append("REVIEW_ACTION 후보가 stress/backtest, CVaR, MDD, 거래 제약 검증을 추가로 통과해야 합니다.")
        elif research_count > 0:
            reasons.append("Only research-only instruments are present; they are not executable hedge actions.")
            reasons_ko.append("현재 선택된 후보는 리서치 전용 성격이라 실행 추천으로 표시하지 않습니다.")
            upgrade_requirements.append("인버스·레버리지·옵션·변동성 상품이 아닌 실행 가능한 hedge 후보가 필요합니다.")
        elif fail_count > 0:
            reasons.append("Action candidates fail the vulnerability or gate checks.")
            reasons_ko.append("후보 액션이 취약성 개선 또는 gate 조건을 통과하지 못했습니다.")
            upgrade_requirements.append("CVaR/MDD/stress 악화 원인을 해소하거나 turnover·집중도 제약을 만족해야 합니다.")
        else:
            reasons.append("The active portfolio has no valid bounded hedge action.")
            reasons_ko.append("현재 포트폴리오 취약성에 대해 제약 조건 안에서 유효한 bounded action이 없습니다.")
            upgrade_requirements.append("헷지 후보 universe, 민감도 매핑, 또는 허용 turnover 조건을 재검토해야 합니다.")

    gate_allows_execution = bool(recommendation_decision.get("canExecuteRecommendations"))
    recommendation_blockers = recommendation_decision.get("blockers") or []
    if formal_count > 0 and not gate_allows_execution:
        for blocker in recommendation_blockers:
            append_unique(blockers, blocker)
        if not recommendation_blockers:
            append_unique(blockers, "formal_recommendation_gate_blocked")
        reasons.append("Formal actions are present but the existing recommendation gate blocks execution.")
        reasons_ko.append("FORMAL_ACTION row는 있으나 기존 추천 gate가 아직 실행을 허용하지 않습니다.")
        upgrade_requirements.append("기존 recommendationDecision의 blocker를 해소해야 canExecuteAction=true가 됩니다.")

    if research_count > 0:
        reasons.append("Research-only actions remain separated from executable recommendations.")
        reasons_ko.append("리서치 전용 후보는 실행 추천 수에 포함하지 않습니다.")
    if artifact_warnings:
        reasons.append("Some action-plan artifacts are missing or unreadable; fallback payloads were returned.")
        reasons_ko.append("일부 action artifact가 없거나 읽히지 않아 fallback payload가 포함됐습니다.")
        upgrade_requirements.append("latest_manifest.json의 action artifact 경로와 active bundle을 확인해야 합니다.")

    can_execute = formal_count > 0 and gate_allows_execution
    if can_execute and not reasons:
        reasons.append("At least one formal action passed the existing recommendation gate.")
        reasons_ko.append("최소 하나의 FORMAL_ACTION이 기존 추천 gate를 통과했습니다.")

    if not upgrade_requirements and not can_execute:
        upgrade_requirements.append("추가 검증 결과가 충분해질 때까지 REVIEW_ACTION은 실행 전 검토 후보로만 표시합니다.")
    why_no_formal_ko = " ".join(reasons_ko[:4]) if formal_count <= 0 or not can_execute else ""

    return {
        "formalActionCount": formal_count,
        "reviewActionCount": review_count,
        "researchOnlyCount": research_count,
        "failActionCount": fail_count,
        "noActionCount": no_action_count,
        "canExecuteAction": can_execute,
        "blockers": blockers,
        "primaryReasons": reasons[:8],
        "primaryReasonsKo": reasons_ko[:8],
        "whyNoFormalRecommendationKo": why_no_formal_ko,
        "formalActionBlockersKo": reasons_ko[:8],
        "formalActionUpgradeRequirements": upgrade_requirements[:8],
        "userFacingDecisionKo": "정식 실행 가능" if can_execute else ("검토 액션만 있음" if review_count > 0 else "실행 액션 없음"),
        "statusCounts": status_counts,
        "selectedActionCount": len(action_rows or []),
        "candidateCount": len(action_rows or []),
        "countBasis": ACTION_DECISION_COUNT_BASIS,
        "countedRowSet": "hedgeActionPlan",
        "countedRowScope": ACTION_PLAN_SCOPE,
        "excludedRowSets": ["hedgeActionCandidates", "portfolioVulnerabilityAttribution"],
        "selectedActionTypeCounts": selected_action_type_counts(action_rows),
        "selectedRiskSleeveCounts": selected_risk_sleeve_counts(action_rows),
        "actionTypeCoverage": action_plan_metadata.get("action_type_coverage") or {},
        "sleeveSelectionCoverage": action_plan_metadata.get("sleeve_selection_coverage") or [],
        "replaceSleeveDecision": replace_sleeve_decision_for_api(action_rows, action_plan_metadata),
        "selectionPolicy": action_plan_metadata.get("selection_policy") or {},
        "artifactWarnings": artifact_warnings,
    }


def load_action_plan_payload(manifest, recommendation_decision=None):
    warnings = []
    artifacts = {}

    attribution, artifacts["portfolioVulnerabilityAttribution"], warning = load_optional_rows_artifact(
        manifest, "portfolioVulnerabilityAttribution"
    )
    if warning:
        warnings.append(warning)
    candidates, artifacts["hedgeActionCandidates"], warning = load_optional_rows_artifact(manifest, "hedgeActionCandidates")
    if warning:
        warnings.append(warning)
    action_plan, artifacts["hedgeActionPlan"], warning = load_optional_rows_artifact(manifest, "hedgeActionPlan")
    if warning:
        warnings.append(warning)
    action_plan_metadata = load_action_plan_metadata(manifest)
    vulnerability_summary, warning = load_optional_summary_artifact(manifest, "portfolioVulnerabilitySummary")
    artifacts["portfolioVulnerabilitySummary"] = vulnerability_summary.get("artifact")
    if warning:
        warnings.append(warning)
    action_plan_summary, warning = load_optional_summary_artifact(manifest, "hedgeActionPlanSummary")
    artifacts["hedgeActionPlanSummary"] = action_plan_summary.get("artifact")
    if warning:
        warnings.append(warning)

    return {
        "actionPayloadShape": action_payload_shape(),
        "hedgeActionCandidatesScope": ACTION_CANDIDATES_SCOPE,
        "hedgeActionPlanScope": ACTION_PLAN_SCOPE,
        "portfolioVulnerabilityAttribution": attribution,
        "portfolioVulnerabilitySummary": vulnerability_summary,
        "hedgeActionCandidates": candidates,
        "hedgeActionPlan": action_plan,
        "hedgeActionPlanMeta": action_plan_metadata,
        "hedgeActionPlanSummary": action_plan_summary,
        "actionPlanArtifacts": artifacts,
        "actionArtifactWarnings": warnings,
        "actionPlanDecision": build_action_plan_decision(action_plan, recommendation_decision, warnings, action_plan_metadata),
    }


def load_product_dashboard_data():
    manifest = read_product_manifest()
    if not manifest:
        manifest = fallback_product_manifest()
    bundle = active_bundle(manifest)
    if not bundle:
        raise FileNotFoundError("HedgeMate active bundle manifest not found")
    hedge_run = bundle.get("hedgemate_run") or manifest.get("active_hedgemate_run")
    final_run = bundle.get("final_market_state_run") or manifest.get("active_final_run")
    if not hedge_run or not final_run:
        raise FileNotFoundError("Active bundle is missing hedge or scenario run")
    hedge = load_dashboard_data(hedge_run, product_manifest=manifest)
    scenario = load_scenario_dashboard_data(final_run)
    data_freshness = load_data_freshness()
    backtest = load_backtest_payload(manifest)
    event_overlay_status = normalized_event_overlay_status(manifest.get("event_overlay_status"))
    recommendation_decision = build_recommendation_decision(hedge, backtest, data_freshness, event_overlay_status)
    action_payload = load_action_plan_payload(manifest, recommendation_decision)
    return {
        "serverContractVersion": "action_contract_v2",
        "manifest": manifest,
        "activeBundle": bundle,
        "freshnessStatus": manifest.get("freshness_status") or bundle.get("freshness_status"),
        "staleReasons": manifest.get("stale_reasons") or bundle.get("stale_reasons") or [],
        "dataFreshness": data_freshness,
        "hedge": hedge,
        "scenario": scenario,
        "backtest": backtest,
        "recommendationDecision": recommendation_decision,
        "eventOverlayStatus": event_overlay_status,
        **action_payload,
    }


def load_service_status():
    manifest = read_product_manifest()
    bundle = active_bundle(manifest)
    status = {
        "ok": True,
        "service": "HedgeMate dashboard",
        "activeScenarioRun": bundle.get("scenario_run") or manifest.get("active_scenario_run"),
        "activeFinalRun": bundle.get("final_market_state_run") or manifest.get("active_final_run"),
        "activeHedgemateRun": bundle.get("hedgemate_run") or manifest.get("active_hedgemate_run"),
        "activeBacktestRun": bundle.get("backtest_run") or manifest.get("active_backtest_run"),
        "dataVersion": bundle.get("data_version") or manifest.get("data_version"),
        "freshnessStatus": manifest.get("freshness_status") or bundle.get("freshness_status"),
        "generatedAtUtc": bundle.get("generated_at_utc") or manifest.get("generated_at_utc"),
    }
    try:
        dashboard = load_product_dashboard_data()
    except FileNotFoundError as exc:
        status.update({"ok": False, "error": str(exc)})
        return status

    decision = dashboard.get("recommendationDecision") or {}
    freshness = dashboard.get("dataFreshness") or {}
    event_status = dashboard.get("eventOverlayStatus") or freshness.get("eventOverlayStatus") or {}
    status.update(
        {
            "freshnessStatus": freshness.get("freshnessStatus") or dashboard.get("freshnessStatus") or status.get("freshnessStatus"),
            "needsRefresh": freshness.get("needsRefresh"),
            "recommendationState": decision.get("state"),
            "canExecuteRecommendations": decision.get("canExecuteRecommendations"),
            "blockers": decision.get("blockers") or [],
            "formalRecommendationCount": decision.get("formalRecommendationCount"),
            "referenceOnlyCount": decision.get("referenceOnlyCount"),
            "failGateCount": decision.get("failGateCount"),
            "eventOverlayMode": event_status.get("mode"),
            "eventOverlayTradeGateUsage": event_status.get("trade_gate_usage"),
        }
    )
    return status


class DashboardHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(WEB_DIR), **kwargs)

    def _is_local_client(self):
        return self.client_address[0] in LOCALHOST_CLIENTS

    def _reject_non_local_client(self):
        if self._is_local_client():
            return False
        self._json_response({"error": "local requests only"}, status=HTTPStatus.FORBIDDEN)
        return True

    def _send_common_security_headers(self):
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Cross-Origin-Resource-Policy", "same-origin")
        self.send_header("Content-Security-Policy", CONTENT_SECURITY_POLICY)

    def do_GET(self):
        parsed = urlparse(self.path)
        if (parsed.path.startswith("/api/") or parsed.path.startswith("/artifact/")) and self._reject_non_local_client():
            return
        if parsed.path == "/api/health":
            return self._json_response({"ok": True})
        if parsed.path == "/api/status":
            status = load_service_status()
            http_status = HTTPStatus.OK if status.get("ok") else HTTPStatus.SERVICE_UNAVAILABLE
            return self._json_response(status, status=http_status)
        if parsed.path == "/api/runs":
            runs = find_available_run_ids()
            return self._json_response({"runs": runs, "latestRunId": runs[0] if runs else None})
        if parsed.path == "/api/scenario-runs":
            runs = find_scenario_run_ids()
            return self._json_response({"runs": runs, "latestRunId": runs[0] if runs else None})
        if parsed.path == "/api/assets":
            return self._json_response({"assets": asset_options()})
        if parsed.path == "/api/data-freshness":
            return self._json_response(load_data_freshness())
        if parsed.path == "/api/active-bundle":
            manifest = read_product_manifest()
            if not manifest:
                return self._json_response({"error": "No active bundle available"}, status=HTTPStatus.NOT_FOUND)
            return self._json_response(manifest)
        if parsed.path == "/api/product-dashboard":
            try:
                return self._json_response(load_product_dashboard_data())
            except FileNotFoundError as exc:
                return self._json_response({"error": str(exc)}, status=HTTPStatus.NOT_FOUND)
        if parsed.path == "/api/dashboard":
            params = parse_qs(parsed.query)
            requested = params.get("run_id", [None])[0]
            runs = find_available_run_ids()
            run_id = requested or (runs[0] if runs else None)
            if not run_id:
                return self._json_response({"error": "No runs available"}, status=HTTPStatus.NOT_FOUND)
            try:
                return self._json_response(load_dashboard_data(run_id))
            except FileNotFoundError as exc:
                return self._json_response({"error": str(exc)}, status=HTTPStatus.NOT_FOUND)
        if parsed.path == "/api/scenario-dashboard":
            params = parse_qs(parsed.query)
            requested = params.get("run_id", [None])[0]
            try:
                return self._json_response(load_scenario_dashboard_data(requested))
            except FileNotFoundError as exc:
                return self._json_response({"error": str(exc)}, status=HTTPStatus.NOT_FOUND)
        if parsed.path == "/api/run-status":
            params = parse_qs(parsed.query)
            job_id = params.get("job_id", [None])[0]
            if not job_id:
                return self._json_response({"error": "job_id is required"}, status=HTTPStatus.BAD_REQUEST)
            job = _snapshot_run_job(job_id)
            if not job:
                return self._json_response({"error": f"Job not found: {job_id}"}, status=HTTPStatus.NOT_FOUND)
            return self._json_response(job)
        if parsed.path.startswith("/artifact/"):
            rel_path = unquote(parsed.path[len("/artifact/"):])
            artifact_path = safe_rel_artifact(rel_path)
            if not artifact_path:
                self.send_error(HTTPStatus.NOT_FOUND, "Artifact not found")
                return
            return self._serve_file(artifact_path)
        if parsed.path == "/favicon.ico":
            self.send_response(HTTPStatus.NO_CONTENT)
            self.send_header("Cache-Control", "public, max-age=86400")
            self.end_headers()
            return
        static_files = {"/", "/index.html", "/app.js", "/unified.js", "/styles.css", "/scenario.html", "/scenario.js", "/logic.html", "/logic.js"}
        if parsed.path in static_files:
            rel = "index.html" if parsed.path in {"/", "/index.html"} else parsed.path.lstrip("/")
            return self._serve_file(WEB_DIR / rel)
        return super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path not in {"/api/run", "/api/price-lookup", "/api/portfolio/preview", "/api/refresh-market-data"}:
            self.send_error(HTTPStatus.NOT_FOUND, "Unknown endpoint")
            return
        if self._reject_non_local_client():
            return
        content_type = (self.headers.get("Content-Type") or "").split(";", 1)[0].strip().lower()
        if content_type != "application/json":
            return self._json_response({"error": "application/json 요청만 허용됩니다."}, status=HTTPStatus.UNSUPPORTED_MEDIA_TYPE)
        try:
            payload = self._read_json_body()
            if parsed.path == "/api/price-lookup":
                return self._json_response(
                    lookup_price(
                        payload.get("asset") or payload.get("ticker"),
                        quantity=payload.get("quantity"),
                        amount_krw=payload.get("amountKrw"),
                        use_live=bool(payload.get("useLivePrices")),
                    )
                )
            if parsed.path == "/api/portfolio/preview":
                return self._json_response(preview_portfolio(payload))
            if parsed.path == "/api/refresh-market-data":
                result = launch_refresh_market_data_job(payload)
                status = HTTPStatus.OK if result.get("status") == "skipped_latest" else HTTPStatus.ACCEPTED
                return self._json_response(result, status=status)
            prepared_request = prepare_run_request(payload)
            result = launch_run_job(prepared_request)
            return self._json_response(result, status=HTTPStatus.ACCEPTED)
        except ValueError as exc:
            return self._json_response({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
        except RuntimeError as exc:
            return self._json_response({"error": str(exc)}, status=HTTPStatus.INTERNAL_SERVER_ERROR)

    def _read_json_body(self):
        length = int(self.headers.get("Content-Length", "0"))
        try:
            return json.loads(self.rfile.read(length).decode("utf-8")) if length > 0 else {}
        except json.JSONDecodeError as exc:
            raise ValueError("잘못된 JSON 요청입니다.") from exc

    def _json_response(self, payload, status=HTTPStatus.OK):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        self._send_common_security_headers()
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _serve_file(self, path):
        content = path.read_bytes()
        mime, _ = mimetypes.guess_type(str(path))
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", (mime or "application/octet-stream") + ("; charset=utf-8" if mime and mime.startswith("text/") else ""))
        if path.suffix in {".html", ".js", ".css"}:
            self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
            self.send_header("Pragma", "no-cache")
            self.send_header("Expires", "0")
        self._send_common_security_headers()
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def log_message(self, format, *args):
        return


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Serve HedgeMate dashboard UI")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8080)
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    server = ThreadingHTTPServer((args.host, args.port), DashboardHandler)
    print(f"HedgeMate dashboard running at http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
