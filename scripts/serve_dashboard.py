#!/usr/bin/env python3
import argparse
import csv
import json
import mimetypes
import re
import subprocess
import sys
import threading
import uuid
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
LOCALHOST_CLIENTS = {"127.0.0.1", "::1", "::ffff:127.0.0.1"}
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
    "TLT": "장기국채 ETF",
    "IEF": "중기국채 ETF",
    "SHY": "단기국채 ETF",
    "LQD": "우량회사채 ETF",
    "HYG": "하이일드채권 ETF",
    "TIP": "물가연동채 ETF",
    "GLD": "금 ETF(GLD)",
    "IAU": "금 ETF(IAU)",
    "DBC": "원자재 ETF",
    "USO": "원유 ETF",
    "XLE": "에너지 섹터 ETF",
    "XLP": "필수소비재 ETF",
    "XLU": "유틸리티 ETF",
    "XLV": "헬스케어 ETF",
    "ITA": "방산 ETF(ITA)",
    "PPA": "방산 ETF(PPA)",
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


def normalize_asset_query(value):
    return re.sub(r"[^0-9A-Za-z가-힣]+", "", str(value or "").strip()).lower()


def asset_options():
    rows = []
    for ticker, label in sorted(TICKER_LABELS.items(), key=lambda item: (item[1], item[0])):
        if ticker == "__CASH__":
            continue
        rows.append({"ticker": ticker, "label": label, "searchText": f"{label} {ticker}"})
    return rows


def resolve_asset_query(query):
    raw = str(query or "").strip()
    if not raw:
        raise ValueError("자산명이 비어 있습니다.")

    upper = raw.upper()
    if upper in TICKER_LABELS:
        return upper

    normalized = normalize_asset_query(raw)
    exact = [ticker for ticker, label in TICKER_LABELS.items() if normalize_asset_query(label) == normalized]
    if len(exact) == 1:
        return exact[0]
    if len(exact) > 1:
        raise ValueError("동일 이름 자산이 여러 개입니다. 티커를 직접 입력해 주세요.")

    partial = [
        ticker
        for ticker, label in TICKER_LABELS.items()
        if normalized and normalized in normalize_asset_query(label)
    ]
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
    return " + ".join(display_name(part.strip()) for part in str(label or "").split(" + ") if part.strip())


def humanize_scenario(scenario):
    scenario = str(scenario or "")
    if scenario.startswith("기존 포트폴리오"):
        return scenario
    for prefix in ["제안(1:1) - ", "참고안(1:1) - ", "차선후보(1:1) - "]:
        if scenario.startswith(prefix):
            ticker = scenario[len(prefix):].strip()
            return f"{prefix}{display_name(ticker)}"
    for prefix in ["제안(다자산) - ", "참고안(다자산) - ", "차선후보(다자산) - "]:
        if scenario.startswith(prefix):
            combo = scenario[len(prefix):].strip()
            return f"{prefix}{humanize_combo(combo)}"
    m = re.match(r"기준\((.+?) 100%\)", scenario)
    if m:
        return f"기준({display_name(m.group(1))} 100%)"
    return scenario


def read_csv_rows(path):
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        rows = []
        for row in csv.DictReader(f):
            rows.append({k: parse_float(v) for k, v in row.items()})
        return rows


def find_available_run_ids(processed_dir=OUTPUT_PROCESSED_DIR):
    run_ids = set()
    for path in processed_dir.glob("features_summary_*.csv"):
        m = re.search(r"features_summary_(.+)\.csv$", path.name)
        if m:
            run_ids.add(m.group(1))
    return sorted(run_ids, reverse=True)


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
    abs_path = (ROOT / rel_path).resolve()
    allowed_roots = [OUTPUT_RAW_DIR.resolve(), OUTPUT_PROCESSED_DIR.resolve(), OUTPUT_REPORT_DIR.resolve(), DOC_RESULT_DIR.resolve()]
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
                "displayName": display_name(ticker),
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
    passing = [row for row in rows if row.get("status") == "PASS"]
    target = passing or [row for row in rows if row.get("final_score") is not None] or rows
    best = max(
        target,
        key=lambda row: (
            row.get("final_score") if isinstance(row.get("final_score"), (int, float)) else float("-inf"),
            str(row.get("candidate_label") or row.get("candidate_combo") or row.get("candidate_ticker") or ""),
        ),
    )
    enriched = dict(best)
    if enriched.get("candidate_ticker"):
        enriched["displayLabel"] = display_name(enriched["candidate_ticker"])
    elif enriched.get("candidate_combo"):
        enriched["displayLabel"] = humanize_combo(enriched["candidate_combo"])
    else:
        enriched["displayLabel"] = humanize_scenario(enriched.get("scenario", ""))
    enriched["weights"] = parse_weights_snapshot(enriched.get("weights_snapshot"))
    return enriched


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
    prepared = {
        "_prepared_request": True,
        "jobId": job_id,
        "runId": run_id,
        "cmd": cmd,
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
        return prepared

    if mode == "portfolio":
        portfolio_rows = (payload or {}).get("portfolioRows")
        if portfolio_rows:
            rows, total_amount_krw = parse_portfolio_rows(portfolio_rows)
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
    portfolio_input_path = (prepared_request or {}).get("portfolioInputPath")
    if portfolio_input_path:
        try:
            Path(portfolio_input_path).unlink(missing_ok=True)
        except OSError:
            pass


def _run_pipeline_job(job_id, prepared_request, runner):
    try:
        result = run_pipeline_for_request(prepared_request, runner=runner)
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
            "runId": None,
            "error": None,
            "result": None,
            "startedAt": datetime.now().isoformat(timespec="seconds"),
            "completedAt": None,
        }
    worker = thread_factory(target=_run_pipeline_job, args=(job_id, prepared_request, runner), daemon=True)
    worker.start()
    return _snapshot_run_job(job_id)


def run_pipeline_for_request(payload, runner=subprocess.run):
    prepared_request = payload if (payload or {}).get("_prepared_request") else prepare_run_request(payload, job_id=(payload or {}).get("jobId"))
    cmd = list(prepared_request["cmd"])

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
    return {
        "ok": True,
        "runId": run_id or prepared_request.get("runId") or (find_available_run_ids()[0] if find_available_run_ids() else None),
        "stdout": completed.stdout,
    }


def load_dashboard_data(run_id):
    features_path = OUTPUT_PROCESSED_DIR / f"features_summary_{run_id}.csv"
    if not features_path.exists():
        raise FileNotFoundError(f"Run not found: {run_id}")

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
    portfolio_multi = read_csv_rows(OUTPUT_REPORT_DIR / f"portfolio_multi_hedge_{run_id}.csv")
    portfolio_1to1 = read_csv_rows(OUTPUT_REPORT_DIR / f"portfolio_1to1_hedge_{run_id}.csv")
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
        "portfolio1to1": f"outputs/reports/portfolio_1to1_hedge_{run_id}.csv",
        "portfolioMulti": f"outputs/reports/portfolio_multi_hedge_{run_id}.csv",
        "singleAssetCompare": f"outputs/reports/single_asset_compare_{run_id}.csv",
        "singleAsset1to1": f"outputs/reports/single_asset_hedge_1to1_{run_id}.csv",
        "singleAssetMulti": f"outputs/reports/single_asset_hedge_multi_{run_id}.csv",
        "resultMd": f"docs/STEP_1/04_실행결과/01_실행결과_{run_id}.md",
        "draftMd": f"docs/STEP_1/04_실행결과/02_분석리포트_초안_{run_id}.md",
        "reviewMd": f"docs/STEP_1/04_실행결과/03_결과검토_{run_id}.md",
    }

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
        },
        "dqSummary": dq_summary,
        "validationSummary": validation_summary,
        "portfolioCompare": portfolio_compare,
        "singleAssetCompare": single_asset_compare,
        "portfolioBestDetail": choose_best_detail(portfolio_multi, portfolio_1to1),
        "singleAssetBestDetail": choose_best_detail(single_asset_multi, single_asset_1to1),
        "assetSensitivities": asset_sensitivities,
        "topHedges": top_hedges,
        "worstRiskAssets": worst_risk_assets,
        "nextActions": next_actions,
        "artifacts": artifacts,
    }


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
        if parsed.path == "/api/runs":
            runs = find_available_run_ids()
            return self._json_response({"runs": runs, "latestRunId": runs[0] if runs else None})
        if parsed.path == "/api/assets":
            return self._json_response({"assets": asset_options()})
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
        if parsed.path in {"/", "/index.html", "/app.js", "/styles.css"}:
            rel = "index.html" if parsed.path in {"/", "/index.html"} else parsed.path.lstrip("/")
            return self._serve_file(WEB_DIR / rel)
        return super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path != "/api/run":
            self.send_error(HTTPStatus.NOT_FOUND, "Unknown endpoint")
            return
        if self._reject_non_local_client():
            return
        content_type = (self.headers.get("Content-Type") or "").split(";", 1)[0].strip().lower()
        if content_type != "application/json":
            return self._json_response({"error": "application/json 요청만 허용됩니다."}, status=HTTPStatus.UNSUPPORTED_MEDIA_TYPE)
        length = int(self.headers.get("Content-Length", "0"))
        try:
            try:
                payload = json.loads(self.rfile.read(length).decode("utf-8")) if length > 0 else {}
            except json.JSONDecodeError as exc:
                raise ValueError("잘못된 JSON 요청입니다.") from exc
            prepared_request = prepare_run_request(payload)
            result = launch_run_job(prepared_request)
            return self._json_response(result, status=HTTPStatus.ACCEPTED)
        except ValueError as exc:
            return self._json_response({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
        except RuntimeError as exc:
            return self._json_response({"error": str(exc)}, status=HTTPStatus.INTERNAL_SERVER_ERROR)

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
