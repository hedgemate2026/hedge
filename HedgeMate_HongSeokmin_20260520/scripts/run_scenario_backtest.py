#!/usr/bin/env python3
"""Phase 10D API-free formation-path, cost-adjusted scenario backtest.

The script intentionally uses local, reviewed artifacts only:
- scenario_research historical validation cases
- HedgeMate recommendation outputs
- HedgeMate cached raw market prices

It does not fetch live data and it does not call any API-key provider.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import random
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent
SCENARIO_ROOT = REPO_ROOT / "scenario_research"
OUTPUT_REPORT_DIR = ROOT / "outputs" / "reports"
OUTPUT_VALIDATION_DIR = ROOT / "outputs" / "validation"
RAW_DIR = ROOT / "outputs" / "raw"
DEFAULT_PORTFOLIO_INPUT = ROOT / "inputs" / "portfolio_weights.csv"

BACKTEST_ENGINE_VERSION = "phase10e_rebalance_cost_path_walk_forward_v1"
MIN_EVALUATION_DAYS = 60
MIN_SHORT_EVENT_DAYS = 20
MIN_PRICE_COVERAGE = 0.90
CASH_TICKER = "__CASH__"
DEFAULT_TRANSACTION_COST_BPS = 10.0
DEFAULT_SLIPPAGE_BPS = 5.0
DEFAULT_REBALANCE_FREQUENCY = "formation_only"
DEFAULT_BOOTSTRAP_ITERATIONS = 200
DEFAULT_BOOTSTRAP_CI_LEVEL = 0.95

BACKTEST_FIELDS = [
    "case_id",
    "case_name",
    "expected_scenario_code",
    "detection_status",
    "data_sufficiency",
    "candidate_label",
    "candidate_key",
    "candidate_source",
    "candidate_target_scenarios",
    "is_target_scenario",
    "hedge_budget_pct",
    "weights_snapshot",
    "recommendation_status",
    "formation_date",
    "evaluation_start",
    "evaluation_end",
    "evaluation_day_count",
    "price_coverage_ratio",
    "price_window_status",
    "price_blocking_tickers",
    "pre_inception_tickers",
    "missing_price_tickers",
    "first_price_date",
    "last_price_date",
    "backtest_status",
    "base_cvar_95",
    "proposed_cvar_95",
    "cvar_delta",
    "cash_baseline_cvar_95",
    "hedge_vs_cash_cvar_delta",
    "base_mdd",
    "proposed_mdd",
    "mdd_delta",
    "cash_baseline_mdd",
    "hedge_vs_cash_mdd_delta",
    "base_stress_window_loss",
    "proposed_stress_window_loss",
    "stress_loss_delta",
    "cash_baseline_stress_window_loss",
    "hedge_vs_cash_stress_loss_delta",
    "base_annual_return",
    "proposed_annual_return",
    "return_drag",
    "hedge_vs_cash_verdict",
    "turnover",
    "transaction_cost_bps",
    "slippage_bps",
    "total_cost_bps",
    "rebalance_frequency",
    "implementation_cost",
    "recurring_rebalance_cost",
    "total_path_cost",
    "proposed_net_cvar_95",
    "net_cvar_delta",
    "hedge_vs_cash_net_cvar_delta",
    "proposed_net_mdd",
    "net_mdd_delta",
    "hedge_vs_cash_net_mdd_delta",
    "proposed_net_stress_window_loss",
    "net_stress_loss_delta",
    "hedge_vs_cash_net_stress_loss_delta",
    "proposed_net_annual_return",
    "cost_adjusted_return_drag",
    "hedge_vs_cash_net_verdict",
    "bootstrap_iterations",
    "bootstrap_ci_level",
    "bootstrap_seed",
    "net_stress_delta_ci_low",
    "net_stress_delta_ci_high",
    "net_stress_delta_p_improve",
    "bootstrap_confidence",
    "cash_bootstrap_iterations",
    "cash_bootstrap_seed",
    "cash_net_stress_delta_ci_low",
    "cash_net_stress_delta_ci_high",
    "cash_net_stress_delta_p_improve",
    "cash_bootstrap_confidence",
    "verdict",
    "notes",
    "engine_version",
]


def load_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(path)
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def parse_float(value, default=None):
    if value in (None, ""):
        return default
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    if math.isnan(parsed) or math.isinf(parsed):
        return default
    return parsed


def parse_date(value: str) -> date:
    return date.fromisoformat(value)


def pct_weights_from_rows(rows: list[dict[str, str]]) -> dict[str, float]:
    weights = {}
    for row in rows:
        ticker = (row.get("ticker") or "").strip()
        weight = parse_float(row.get("weight_pct"), 0.0) or 0.0
        if ticker and weight > 0:
            weights[ticker] = weight / 100.0
    total = sum(weights.values())
    if total > 0:
        weights = {ticker: weight / total for ticker, weight in weights.items()}
    return weights


def weights_from_snapshot(row: dict[str, str]) -> dict[str, float]:
    raw = row.get("weights_snapshot") or ""
    if raw:
        try:
            payload = json.loads(raw)
            weights = {ticker: (parse_float(weight, 0.0) or 0.0) / 100.0 for ticker, weight in payload.items()}
            return {ticker: weight for ticker, weight in weights.items() if weight > 0}
        except json.JSONDecodeError:
            pass
    ticker = row.get("candidate_ticker") or ""
    weight = parse_float(row.get("hedge_weight_pct"), 0.0) or 0.0
    return {ticker: weight / 100.0} if ticker and weight > 0 else {}


def candidate_label(row: dict[str, str]) -> str:
    return row.get("candidate_ticker") or row.get("candidate_combo") or row.get("candidate_label") or "-"


def candidate_source(row: dict[str, str]) -> str:
    return row.get("_candidate_source") or row.get("candidate_source") or ("multi" if row.get("candidate_combo") else "one_to_one")


def candidate_key(row: dict[str, str]) -> str:
    label = candidate_label(row)
    weights = row.get("weights_snapshot") or ""
    budget = row.get("hedge_budget_pct") or row.get("hedge_weight_pct") or ""
    return "|".join([candidate_source(row), label, weights or budget])


def split_scenarios(value: str) -> set[str]:
    return {item.strip() for item in str(value or "").split("|") if item.strip()}


def candidate_target_scenarios(row: dict[str, str]) -> str:
    return row.get("risk_bucket_match") or row.get("active_adverse_scenarios") or ""


def is_target_case(candidate: dict[str, str], scenario_code: str) -> bool:
    targets = split_scenarios(candidate_target_scenarios(candidate))
    return bool(scenario_code and scenario_code in targets)


def select_representative_candidates(recommendation_rows: list[dict[str, str]], limit=12) -> list[dict[str, str]]:
    status_rank = {"PASS_RECOMMEND": 0, "REFERENCE_ONLY": 1, "FAIL_GATE": 2, "INSUFFICIENT_DATA": 3}
    preferred = [row for row in recommendation_rows if weights_from_snapshot(row)]
    preferred.sort(
        key=lambda row: (
            status_rank.get(str(row.get("recommendation_status") or ""), 9),
            -(parse_float(row.get("final_score"), -1.0) or -1.0),
            candidate_label(row),
            parse_float(row.get("hedge_budget_pct") or row.get("hedge_weight_pct"), 0.0) or 0.0,
        )
    )
    if limit is not None and limit <= 0:
        seen_keys = set()
        selected = []
        for row in preferred:
            key = candidate_key(row)
            if key in seen_keys:
                continue
            selected.append(row)
            seen_keys.add(key)
        return selected

    seen = set()
    selected = []
    for row in preferred:
        label = candidate_label(row)
        if label in seen:
            continue
        selected.append(row)
        seen.add(label)
        if len(selected) >= limit:
            break
    return selected


def load_price_maps(raw_market_path: Path) -> dict[str, list[tuple[str, float]]]:
    prices = defaultdict(list)
    for row in load_csv(raw_market_path):
        ticker = row.get("ticker")
        price = parse_float(row.get("adj_close"))
        if ticker and price and price > 0:
            prices[ticker].append((row.get("date", ""), price))
    for ticker in list(prices):
        prices[ticker].sort(key=lambda item: item[0])
    return dict(prices)


def return_maps_from_prices(price_maps: dict[str, list[tuple[str, float]]]) -> dict[str, dict[str, float]]:
    output = {}
    for ticker, series in price_maps.items():
        ret_map = {}
        for (prev_date, prev_price), (cur_date, cur_price) in zip(series, series[1:]):
            if prev_price > 0 and cur_price > 0:
                ret_map[cur_date] = cur_price / prev_price - 1.0
        output[ticker] = ret_map
    return output


def portfolio_daily_returns(weights: dict[str, float], return_maps: dict[str, dict[str, float]], start_date: str, end_date: str):
    """Fixed-weight daily returns, equivalent to daily target-weight rebalancing before costs."""
    all_dates = sorted(
        {
            date_str
            for ticker in weights
            for date_str in return_maps.get(ticker, {})
            if start_date <= date_str <= end_date
        }
    )
    rows = []
    for date_str in all_dates:
        weighted = 0.0
        used_weight = 0.0
        for ticker, weight in weights.items():
            if ticker == CASH_TICKER:
                used_weight += weight
                continue
            value = return_maps.get(ticker, {}).get(date_str)
            if value is None:
                continue
            weighted += weight * value
            used_weight += weight
        if used_weight >= 0.80:
            rows.append((date_str, weighted / used_weight))
    return rows


def portfolio_formation_returns(weights: dict[str, float], return_maps: dict[str, dict[str, float]], start_date: str, end_date: str):
    all_dates = sorted(
        {
            date_str
            for ticker in weights
            for date_str in return_maps.get(ticker, {})
            if start_date <= date_str <= end_date
        }
    )
    values = {ticker: max(0.0, weight) for ticker, weight in weights.items() if weight > 0}
    total = sum(values.values())
    if total <= 0:
        return []
    values = {ticker: weight / total for ticker, weight in values.items()}
    rows = []
    for date_str in all_dates:
        previous_total = sum(values.values())
        if previous_total <= 0:
            break
        covered_value = 0.0
        for ticker, value in values.items():
            if ticker == CASH_TICKER or return_maps.get(ticker, {}).get(date_str) is not None:
                covered_value += value
        if covered_value / previous_total < 0.80:
            continue
        for ticker, value in list(values.items()):
            if ticker == CASH_TICKER:
                continue
            daily_return = return_maps.get(ticker, {}).get(date_str)
            if daily_return is not None:
                values[ticker] = value * (1.0 + daily_return)
        new_total = sum(values.values())
        rows.append((date_str, (new_total / previous_total) - 1.0))
    return rows


def normalized_positive_weights(weights: dict[str, float]) -> dict[str, float]:
    values = {ticker: max(0.0, weight) for ticker, weight in weights.items() if weight > 0}
    total = sum(values.values())
    if total <= 0:
        return {}
    return {ticker: weight / total for ticker, weight in values.items()}


def should_rebalance(previous_date: str | None, current_date: str, rebalance_frequency: str) -> bool:
    frequency = str(rebalance_frequency or "").lower()
    if frequency == "daily":
        return True
    if previous_date is None:
        return False
    if frequency == "monthly":
        previous = date.fromisoformat(previous_date)
        current = date.fromisoformat(current_date)
        return (previous.year, previous.month) != (current.year, current.month)
    return False


def portfolio_path_result(
    weights: dict[str, float],
    return_maps: dict[str, dict[str, float]],
    start_date: str,
    end_date: str,
    rebalance_frequency: str = DEFAULT_REBALANCE_FREQUENCY,
    transaction_cost_bps: float = 0.0,
    slippage_bps: float = 0.0,
) -> tuple[list[tuple[str, float]], float]:
    frequency = str(rebalance_frequency or "").lower()
    if frequency == "formation_only":
        return portfolio_formation_returns(weights, return_maps, start_date, end_date), 0.0

    target_weights = normalized_positive_weights(weights)
    if not target_weights:
        return [], 0.0
    all_dates = sorted(
        {
            date_str
            for ticker in target_weights
            for date_str in return_maps.get(ticker, {})
            if start_date <= date_str <= end_date
        }
    )
    values = dict(target_weights)
    rows = []
    total_cost = 0.0
    previous_date = None
    total_cost_bps = max(0.0, transaction_cost_bps) + max(0.0, slippage_bps)
    for date_str in all_dates:
        previous_total = sum(values.values())
        if previous_total <= 0:
            break
        covered_value = 0.0
        for ticker, value in values.items():
            if ticker == CASH_TICKER or return_maps.get(ticker, {}).get(date_str) is not None:
                covered_value += value
        if covered_value / previous_total < 0.80:
            previous_date = date_str
            continue

        for ticker, value in list(values.items()):
            if ticker == CASH_TICKER:
                continue
            daily_return = return_maps.get(ticker, {}).get(date_str)
            if daily_return is not None:
                values[ticker] = value * (1.0 + daily_return)
        after_market_total = sum(values.values())
        after_cost_total = after_market_total

        if should_rebalance(previous_date, date_str, frequency):
            turnover_value = 0.5 * sum(
                abs(target_weights.get(ticker, 0.0) * after_market_total - values.get(ticker, 0.0))
                for ticker in set(target_weights) | set(values)
            ) / after_market_total
            cost_fraction = implementation_cost_fraction(turnover_value, transaction_cost_bps, slippage_bps)
            after_cost_total = after_market_total * (1.0 - cost_fraction)
            total_cost += after_market_total * cost_fraction
            values = {ticker: weight * after_cost_total for ticker, weight in target_weights.items()}

        rows.append((date_str, (after_cost_total / previous_total) - 1.0))
        previous_date = date_str
    return rows, total_cost


def portfolio_path_returns(
    weights: dict[str, float],
    return_maps: dict[str, dict[str, float]],
    start_date: str,
    end_date: str,
    rebalance_frequency: str = DEFAULT_REBALANCE_FREQUENCY,
):
    rows, _ = portfolio_path_result(weights, return_maps, start_date, end_date, rebalance_frequency)
    return rows


def required_evaluation_days(expected_days: int) -> int:
    return min(MIN_EVALUATION_DAYS, max(MIN_SHORT_EVENT_DAYS, math.ceil(expected_days * MIN_PRICE_COVERAGE)))


def delimited_ticker_counts(rows: list[dict[str, object]], key: str) -> Counter:
    counts = Counter()
    for row in rows:
        for value in str(row.get(key) or "").split("|"):
            ticker = value.strip()
            if ticker:
                counts[ticker] += 1
    return counts


def price_window_diagnostics(
    base_weights: dict[str, float],
    proposed_weights: dict[str, float],
    return_maps: dict[str, dict[str, float]],
    start_date: str,
    end_date: str,
    rebalance_frequency: str = DEFAULT_REBALANCE_FREQUENCY,
) -> dict[str, object]:
    tickers = set(base_weights) | set(proposed_weights)
    ticker_diagnostics = {}
    price_blocking_tickers = []
    pre_inception_tickers = []
    missing_price_tickers = []
    for ticker in sorted(tickers):
        if ticker == CASH_TICKER:
            continue
        dates = sorted(return_maps.get(ticker, {}))
        window_dates = [date_str for date_str in dates if start_date <= date_str <= end_date] if start_date and end_date else []
        first = dates[0] if dates else ""
        last = dates[-1] if dates else ""
        status = "WINDOW_AVAILABLE" if window_dates else "WINDOW_MISSING"
        if not dates:
            missing_price_tickers.append(ticker)
            price_blocking_tickers.append(ticker)
            status = "PRICE_DATA_MISSING"
        elif start_date and end_date and end_date < first:
            pre_inception_tickers.append(ticker)
            price_blocking_tickers.append(ticker)
            status = "PRE_INCEPTION"
        elif start_date and end_date and (start_date > last or not window_dates):
            price_blocking_tickers.append(ticker)
            status = "OUT_OF_EVENT_RANGE"
        ticker_diagnostics[ticker] = {
            "first_price_date": first,
            "last_price_date": last,
            "event_return_days": len(window_dates),
            "status": status,
        }
    available_dates = sorted(
        {
            date_str
            for ticker in tickers
            for date_str in return_maps.get(ticker, {})
        }
    )
    base_series = (
        portfolio_path_returns(base_weights, return_maps, start_date, end_date, rebalance_frequency)
        if start_date and end_date
        else []
    )
    comparison_weights = proposed_weights or base_weights
    proposed_series = (
        portfolio_path_returns(comparison_weights, return_maps, start_date, end_date, rebalance_frequency)
        if start_date and end_date and comparison_weights
        else []
    )
    common_dates = sorted({date for date, _ in base_series} & {date for date, _ in proposed_series})
    expected_days = max(1, len(base_series), len(proposed_series))
    coverage_ratio = len(common_dates) / expected_days

    if not start_date or not end_date:
        status = "EVENT_WINDOW_MISSING"
    elif not available_dates:
        status = "PRICE_DATA_MISSING"
    elif end_date < available_dates[0] or start_date > available_dates[-1]:
        status = "OUT_OF_PRICE_RANGE"
    elif not common_dates:
        status = "NO_COMMON_PRICE_DATES"
    elif coverage_ratio < MIN_PRICE_COVERAGE:
        status = "PARTIAL_PRICE_COVERAGE"
    else:
        status = "PRICE_WINDOW_AVAILABLE"

    return {
        "status": status,
        "price_blocking_tickers": price_blocking_tickers,
        "pre_inception_tickers": pre_inception_tickers,
        "missing_price_tickers": missing_price_tickers,
        "ticker_diagnostics": ticker_diagnostics,
        "first_price_date": available_dates[0] if available_dates else "",
        "last_price_date": available_dates[-1] if available_dates else "",
        "base_series": base_series,
        "proposed_series": proposed_series,
        "common_dates": common_dates,
        "expected_days": expected_days,
        "coverage_ratio": coverage_ratio,
    }


def insufficient_history_note(case, diagnostics: dict[str, object]) -> str:
    status = diagnostics.get("status") or "UNKNOWN"
    first_price_date = diagnostics.get("first_price_date") or "-"
    last_price_date = diagnostics.get("last_price_date") or "-"
    start_date = case.get("active_date") or case.get("watch_date") or case.get("start_date") or "-"
    end_date = case.get("end_date") or "-"
    blockers = diagnostics.get("price_blocking_tickers") or []
    pre_inception = diagnostics.get("pre_inception_tickers") or []
    missing = diagnostics.get("missing_price_tickers") or []
    detail_parts = []
    if pre_inception:
        detail_parts.append(f"Pre-inception tickers: {', '.join(pre_inception[:8])}.")
    if missing:
        detail_parts.append(f"Missing price tickers: {', '.join(missing[:8])}.")
    if blockers and not detail_parts:
        detail_parts.append(f"Blocking tickers: {', '.join(blockers[:8])}.")
    detail_text = f" {' '.join(detail_parts)}" if detail_parts else ""
    if status == "OUT_OF_PRICE_RANGE":
        return (
            "Historical scenario engine has no rows for this case window; "
            f"requested {start_date}..{end_date} is outside cached return history {first_price_date}..{last_price_date}."
            f"{detail_text}"
        )
    if status == "PRICE_DATA_MISSING":
        return (
            "Historical scenario engine has no rows, and no cached return history exists for the portfolio/candidate tickers."
            f"{detail_text}"
        )
    if status in {"NO_COMMON_PRICE_DATES", "PARTIAL_PRICE_COVERAGE"}:
        return (
            "Historical scenario engine has no rows, and cached prices do not provide enough common days "
            f"for {start_date}..{end_date}."
            f"{detail_text}"
        )
    return "Historical scenario engine has no rows for this case window."


def cumulative_return(returns: list[float]):
    if not returns:
        return None
    acc = 1.0
    for value in returns:
        acc *= 1.0 + value
    return acc - 1.0


def max_drawdown_from_returns(returns: list[float]):
    if not returns:
        return None
    nav = 1.0
    peak = 1.0
    worst = 0.0
    for value in returns:
        nav *= 1.0 + value
        peak = max(peak, nav)
        worst = min(worst, nav / peak - 1.0)
    return worst


def cvar_95(returns: list[float]):
    if not returns:
        return None
    ordered = sorted(returns)
    count = max(1, math.ceil(len(ordered) * 0.05))
    return sum(ordered[:count]) / count


def annual_return(returns: list[float]):
    if not returns:
        return None
    total = cumulative_return(returns)
    if total is None or total <= -1.0:
        return None
    return (1.0 + total) ** (252.0 / len(returns)) - 1.0


def turnover(base_weights: dict[str, float], proposed_weights: dict[str, float]) -> float:
    tickers = set(base_weights) | set(proposed_weights)
    return 0.5 * sum(abs(proposed_weights.get(ticker, 0.0) - base_weights.get(ticker, 0.0)) for ticker in tickers)


def implementation_cost_fraction(turnover_value: float, transaction_cost_bps: float, slippage_bps: float) -> float:
    total_bps = max(0.0, transaction_cost_bps) + max(0.0, slippage_bps)
    return max(0.0, turnover_value) * total_bps / 10_000.0


def returns_after_implementation_cost(returns: list[float], implementation_cost: float) -> list[float]:
    if not returns:
        return []
    adjusted = list(returns)
    adjusted[0] = adjusted[0] - implementation_cost
    return adjusted


def stable_bootstrap_seed(*parts: object) -> int:
    text = "|".join(str(part or "") for part in parts)
    digest = hashlib.blake2b(text.encode("utf-8"), digest_size=8).hexdigest()
    return int(digest, 16)


def percentile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    q = min(1.0, max(0.0, q))
    ordered = sorted(values)
    position = (len(ordered) - 1) * q
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def bootstrap_net_stress_delta(
    base_returns: list[float],
    proposed_net_returns: list[float],
    iterations: int,
    ci_level: float,
    seed: int,
) -> dict[str, float | int | str]:
    if len(base_returns) != len(proposed_net_returns) or len(base_returns) < 2 or iterations <= 0:
        return {
            "bootstrap_iterations": 0,
            "bootstrap_ci_level": ci_level,
            "bootstrap_seed": seed,
            "net_stress_delta_ci_low": "",
            "net_stress_delta_ci_high": "",
            "net_stress_delta_p_improve": "",
            "bootstrap_confidence": "INSUFFICIENT_SAMPLE",
        }
    rng = random.Random(seed)
    count = len(base_returns)
    deltas: list[float] = []
    for _ in range(iterations):
        indices = [rng.randrange(count) for _ in range(count)]
        base_sample = [base_returns[index] for index in indices]
        proposed_sample = [proposed_net_returns[index] for index in indices]
        base_total = cumulative_return(base_sample)
        proposed_total = cumulative_return(proposed_sample)
        if base_total is not None and proposed_total is not None:
            deltas.append(proposed_total - base_total)
    if not deltas:
        return {
            "bootstrap_iterations": 0,
            "bootstrap_ci_level": ci_level,
            "bootstrap_seed": seed,
            "net_stress_delta_ci_low": "",
            "net_stress_delta_ci_high": "",
            "net_stress_delta_p_improve": "",
            "bootstrap_confidence": "INSUFFICIENT_SAMPLE",
        }
    tail = (1.0 - ci_level) / 2.0
    low = percentile(deltas, tail)
    high = percentile(deltas, 1.0 - tail)
    p_improve = sum(1 for value in deltas if value > 0) / len(deltas)
    if low is not None and low > 0 and p_improve >= ci_level:
        confidence = "ROBUST_IMPROVE"
    elif high is not None and high < 0 and p_improve <= 1.0 - ci_level:
        confidence = "ROBUST_WORSE"
    else:
        confidence = "UNCERTAIN"
    return {
        "bootstrap_iterations": len(deltas),
        "bootstrap_ci_level": ci_level,
        "bootstrap_seed": seed,
        "net_stress_delta_ci_low": low,
        "net_stress_delta_ci_high": high,
        "net_stress_delta_p_improve": p_improve,
        "bootstrap_confidence": confidence,
    }


def cash_baseline_weights(base_weights: dict[str, float], proposed_weights: dict[str, float]) -> dict[str, float]:
    retained_base = {
        ticker: proposed_weights.get(ticker, 0.0)
        for ticker in base_weights
        if proposed_weights.get(ticker, 0.0) > 0
    }
    if not retained_base:
        hedge_weight = sum(
            weight
            for ticker, weight in proposed_weights.items()
            if ticker not in base_weights and ticker != CASH_TICKER
        )
        retained_scale = max(0.0, min(1.0, 1.0 - hedge_weight))
        retained_base = {ticker: weight * retained_scale for ticker, weight in base_weights.items() if weight > 0}
    cash_weight = max(0.0, 1.0 - sum(retained_base.values()))
    if cash_weight > 0:
        retained_base[CASH_TICKER] = cash_weight
    return retained_base


def relative_verdict(deltas: list[float | None], positive_label: str, negative_label: str, mixed_label: str) -> str:
    valid = [value for value in deltas if value is not None]
    if not valid:
        return ""
    improved_count = sum(1 for value in valid if value > 0)
    worsened_count = sum(1 for value in valid if value < 0)
    if improved_count >= 2:
        return positive_label
    if worsened_count >= 2:
        return negative_label
    return mixed_label


def resolve_historical_validation_path(run_id: str) -> Path:
    return SCENARIO_ROOT / "outputs" / "validation" / f"historical_validation_cases_{run_id}.csv"


def resolve_recommendation_rows(hedgemate_run_id: str, recommendation_scope: str = "portfolio") -> list[dict[str, str]]:
    rows = []
    if recommendation_scope == "single_asset":
        specs = [("single_asset_hedge_1to1", "one_to_one"), ("single_asset_hedge_multi", "multi")]
    else:
        specs = [("portfolio_1to1_hedge", "one_to_one"), ("portfolio_multi_hedge", "multi")]
    for prefix, source in specs:
        path = OUTPUT_REPORT_DIR / f"{prefix}_{hedgemate_run_id}.csv"
        if path.exists():
            for row in load_csv(path):
                row["_candidate_source"] = source
                rows.append(row)
    return rows


def evaluate_case_candidate(
    case,
    candidate,
    base_weights,
    return_maps,
    transaction_cost_bps: float = DEFAULT_TRANSACTION_COST_BPS,
    slippage_bps: float = DEFAULT_SLIPPAGE_BPS,
    rebalance_frequency: str = DEFAULT_REBALANCE_FREQUENCY,
    bootstrap_iterations: int = DEFAULT_BOOTSTRAP_ITERATIONS,
    bootstrap_ci_level: float = DEFAULT_BOOTSTRAP_CI_LEVEL,
):
    case_id = case.get("case_id") or case.get("case_code")
    detection_status = case.get("detection_status") or case.get("validation_status")
    scenario_code = case.get("expected_scenario_code") or case.get("scenario_code", "")
    target_scenarios = candidate_target_scenarios(candidate) if candidate else ""
    is_target = "Y" if candidate and is_target_case(candidate, scenario_code) else "N"
    proposed_weights = weights_from_snapshot(candidate) if candidate else {}
    turnover_value = turnover(base_weights, proposed_weights)
    total_cost_bps = max(0.0, transaction_cost_bps) + max(0.0, slippage_bps)
    implementation_cost = implementation_cost_fraction(turnover_value, transaction_cost_bps, slippage_bps)
    evaluation_start = case.get("active_date") or case.get("watch_date") or case.get("start_date") or ""
    evaluation_end = case.get("end_date") or ""
    diagnostics = price_window_diagnostics(
        base_weights,
        proposed_weights,
        return_maps,
        evaluation_start,
        evaluation_end,
        rebalance_frequency,
    )
    if detection_status == "INSUFFICIENT_HISTORY" and diagnostics["status"] != "PRICE_WINDOW_AVAILABLE":
        return {
            "case_id": case_id,
            "case_name": case.get("case_name", ""),
            "expected_scenario_code": scenario_code,
            "detection_status": detection_status,
            "data_sufficiency": case.get("data_sufficiency", "INSUFFICIENT_HISTORY"),
            "candidate_label": candidate_label(candidate) if candidate else "-",
            "candidate_key": candidate_key(candidate) if candidate else "-",
            "candidate_source": candidate_source(candidate) if candidate else "",
            "candidate_target_scenarios": target_scenarios,
            "is_target_scenario": is_target,
            "hedge_budget_pct": candidate.get("hedge_budget_pct") or candidate.get("hedge_weight_pct") or "" if candidate else "",
            "weights_snapshot": candidate.get("weights_snapshot", "") if candidate else "",
            "recommendation_status": candidate.get("recommendation_status", "") if candidate else "",
            "formation_date": evaluation_start,
            "evaluation_start": evaluation_start,
            "evaluation_end": evaluation_end,
            "evaluation_day_count": len(diagnostics["common_dates"]),
            "price_coverage_ratio": round(diagnostics["coverage_ratio"], 6),
            "price_window_status": diagnostics["status"],
            "price_blocking_tickers": "|".join(diagnostics["price_blocking_tickers"]),
            "pre_inception_tickers": "|".join(diagnostics["pre_inception_tickers"]),
            "missing_price_tickers": "|".join(diagnostics["missing_price_tickers"]),
            "first_price_date": diagnostics["first_price_date"],
            "last_price_date": diagnostics["last_price_date"],
            "backtest_status": "INSUFFICIENT_HISTORY",
            "turnover": round(turnover_value, 8),
            "transaction_cost_bps": round(transaction_cost_bps, 4),
            "slippage_bps": round(slippage_bps, 4),
            "total_cost_bps": round(total_cost_bps, 4),
            "rebalance_frequency": rebalance_frequency,
            "implementation_cost": round(implementation_cost, 8),
            "recurring_rebalance_cost": 0.0,
            "total_path_cost": round(implementation_cost, 8),
            "bootstrap_iterations": 0,
            "bootstrap_ci_level": bootstrap_ci_level,
            "bootstrap_seed": "",
            "bootstrap_confidence": "INSUFFICIENT_SAMPLE",
            "cash_bootstrap_iterations": 0,
            "cash_bootstrap_seed": "",
            "cash_net_stress_delta_ci_low": "",
            "cash_net_stress_delta_ci_high": "",
            "cash_net_stress_delta_p_improve": "",
            "cash_bootstrap_confidence": "INSUFFICIENT_SAMPLE",
            "verdict": "INSUFFICIENT_HISTORY",
            "notes": insufficient_history_note(case, diagnostics),
            "engine_version": BACKTEST_ENGINE_VERSION,
        }

    base_series = diagnostics["base_series"]
    proposed_series = diagnostics["proposed_series"]
    common_dates = diagnostics["common_dates"]
    base_by_date = dict(base_series)
    proposed_by_date = dict(proposed_series)
    base_returns = [base_by_date[date_str] for date_str in common_dates]
    proposed_returns = [proposed_by_date[date_str] for date_str in common_dates]
    proposed_periodic_net_series, recurring_rebalance_cost = portfolio_path_result(
        proposed_weights,
        return_maps,
        evaluation_start,
        evaluation_end,
        rebalance_frequency,
        transaction_cost_bps,
        slippage_bps,
    )
    proposed_periodic_net_by_date = dict(proposed_periodic_net_series)
    proposed_periodic_net_returns = [proposed_periodic_net_by_date.get(date_str) for date_str in common_dates]
    proposed_periodic_net_returns = [
        value if value is not None else proposed_by_date[date_str]
        for value, date_str in zip(proposed_periodic_net_returns, common_dates)
    ]
    proposed_net_returns = returns_after_implementation_cost(proposed_periodic_net_returns, implementation_cost)
    cash_weights = cash_baseline_weights(base_weights, proposed_weights)
    cash_series = portfolio_path_returns(cash_weights, return_maps, evaluation_start, evaluation_end, rebalance_frequency)
    cash_by_date = dict(cash_series)
    cash_returns = [cash_by_date.get(date_str) for date_str in common_dates]
    cash_returns = [value for value in cash_returns if value is not None]
    expected_days = diagnostics["expected_days"]
    coverage_ratio = diagnostics["coverage_ratio"]
    required_days = required_evaluation_days(expected_days)

    common = {
        "case_id": case_id,
        "case_name": case.get("case_name", ""),
        "expected_scenario_code": scenario_code,
        "detection_status": detection_status,
        "data_sufficiency": case.get("data_sufficiency", ""),
        "candidate_label": candidate_label(candidate),
        "candidate_key": candidate_key(candidate),
        "candidate_source": candidate_source(candidate),
        "candidate_target_scenarios": target_scenarios,
        "is_target_scenario": is_target,
        "hedge_budget_pct": candidate.get("hedge_budget_pct") or candidate.get("hedge_weight_pct") or "",
        "weights_snapshot": candidate.get("weights_snapshot", ""),
        "recommendation_status": candidate.get("recommendation_status", ""),
        "formation_date": evaluation_start,
        "evaluation_start": evaluation_start,
        "evaluation_end": evaluation_end,
        "evaluation_day_count": len(common_dates),
        "price_coverage_ratio": round(coverage_ratio, 6),
        "price_window_status": diagnostics["status"],
        "price_blocking_tickers": "|".join(diagnostics["price_blocking_tickers"]),
        "pre_inception_tickers": "|".join(diagnostics["pre_inception_tickers"]),
        "missing_price_tickers": "|".join(diagnostics["missing_price_tickers"]),
        "first_price_date": diagnostics["first_price_date"],
        "last_price_date": diagnostics["last_price_date"],
        "turnover": round(turnover_value, 8),
        "transaction_cost_bps": round(transaction_cost_bps, 4),
        "slippage_bps": round(slippage_bps, 4),
        "total_cost_bps": round(total_cost_bps, 4),
        "rebalance_frequency": rebalance_frequency,
        "implementation_cost": round(implementation_cost, 8),
        "recurring_rebalance_cost": round(recurring_rebalance_cost, 8),
        "total_path_cost": round(implementation_cost + recurring_rebalance_cost, 8),
        "bootstrap_iterations": 0,
        "bootstrap_ci_level": bootstrap_ci_level,
        "bootstrap_seed": "",
        "bootstrap_confidence": "INSUFFICIENT_SAMPLE",
        "cash_bootstrap_iterations": 0,
        "cash_bootstrap_seed": "",
        "cash_net_stress_delta_ci_low": "",
        "cash_net_stress_delta_ci_high": "",
        "cash_net_stress_delta_p_improve": "",
        "cash_bootstrap_confidence": "INSUFFICIENT_SAMPLE",
        "engine_version": BACKTEST_ENGINE_VERSION,
    }
    if len(common_dates) < required_days or coverage_ratio < MIN_PRICE_COVERAGE:
        return {
            **common,
            "backtest_status": "INSUFFICIENT_EVALUATION_WINDOW",
            "verdict": "INSUFFICIENT_HISTORY",
            "notes": (
                f"Need at least {required_days} common days and {MIN_PRICE_COVERAGE:.0%} coverage for this event window. "
                f"Price window status: {diagnostics['status']}."
            ),
        }

    base_cvar = cvar_95(base_returns)
    proposed_cvar = cvar_95(proposed_returns)
    proposed_net_cvar = cvar_95(proposed_net_returns)
    cash_cvar = cvar_95(cash_returns) if len(cash_returns) == len(common_dates) else None
    base_mdd = max_drawdown_from_returns(base_returns)
    proposed_mdd = max_drawdown_from_returns(proposed_returns)
    proposed_net_mdd = max_drawdown_from_returns(proposed_net_returns)
    cash_mdd = max_drawdown_from_returns(cash_returns) if len(cash_returns) == len(common_dates) else None
    base_loss = cumulative_return(base_returns)
    proposed_loss = cumulative_return(proposed_returns)
    proposed_net_loss = cumulative_return(proposed_net_returns)
    cash_loss = cumulative_return(cash_returns) if len(cash_returns) == len(common_dates) else None
    base_ann = annual_return(base_returns)
    proposed_ann = annual_return(proposed_returns)
    proposed_net_ann = annual_return(proposed_net_returns)
    cvar_delta = (proposed_cvar - base_cvar) if proposed_cvar is not None and base_cvar is not None else None
    net_cvar_delta = (proposed_net_cvar - base_cvar) if proposed_net_cvar is not None and base_cvar is not None else None
    hedge_vs_cash_cvar_delta = (proposed_cvar - cash_cvar) if proposed_cvar is not None and cash_cvar is not None else None
    hedge_vs_cash_net_cvar_delta = (proposed_net_cvar - cash_cvar) if proposed_net_cvar is not None and cash_cvar is not None else None
    mdd_delta = (proposed_mdd - base_mdd) if proposed_mdd is not None and base_mdd is not None else None
    net_mdd_delta = (proposed_net_mdd - base_mdd) if proposed_net_mdd is not None and base_mdd is not None else None
    hedge_vs_cash_mdd_delta = (proposed_mdd - cash_mdd) if proposed_mdd is not None and cash_mdd is not None else None
    hedge_vs_cash_net_mdd_delta = (proposed_net_mdd - cash_mdd) if proposed_net_mdd is not None and cash_mdd is not None else None
    stress_delta = (proposed_loss - base_loss) if proposed_loss is not None and base_loss is not None else None
    net_stress_delta = (proposed_net_loss - base_loss) if proposed_net_loss is not None and base_loss is not None else None
    hedge_vs_cash_stress_delta = (proposed_loss - cash_loss) if proposed_loss is not None and cash_loss is not None else None
    hedge_vs_cash_net_stress_delta = (proposed_net_loss - cash_loss) if proposed_net_loss is not None and cash_loss is not None else None
    return_drag = (proposed_ann - base_ann) if proposed_ann is not None and base_ann is not None else None
    cost_adjusted_return_drag = (proposed_net_ann - base_ann) if proposed_net_ann is not None and base_ann is not None else None
    improved_count = sum(1 for value in [net_cvar_delta, net_mdd_delta, net_stress_delta] if value is not None and value > 0)
    worsened_count = sum(1 for value in [net_cvar_delta, net_mdd_delta, net_stress_delta] if value is not None and value < 0)
    verdict = "IMPROVED" if improved_count >= 2 else "WORSENED" if worsened_count >= 2 else "MIXED"
    bootstrap_seed = stable_bootstrap_seed(case_id, scenario_code, candidate_key(candidate), evaluation_start, evaluation_end)
    bootstrap = bootstrap_net_stress_delta(
        base_returns,
        proposed_net_returns,
        bootstrap_iterations,
        bootstrap_ci_level,
        bootstrap_seed,
    )
    cash_bootstrap_seed = stable_bootstrap_seed(
        case_id,
        scenario_code,
        candidate_key(candidate),
        evaluation_start,
        evaluation_end,
        "cash_baseline",
    )
    cash_bootstrap = bootstrap_net_stress_delta(
        cash_returns,
        proposed_net_returns,
        bootstrap_iterations,
        bootstrap_ci_level,
        cash_bootstrap_seed,
    )
    hedge_vs_cash_verdict = relative_verdict(
        [hedge_vs_cash_net_cvar_delta, hedge_vs_cash_net_mdd_delta, hedge_vs_cash_net_stress_delta],
        "BEATS_CASH",
        "LAGS_CASH",
        "MIXED_CASH",
    )
    note = (
        "Cost-adjusted walk-forward uses cached local adjusted close returns; "
        "formation_only uses a buy-and-hold return path; monthly/daily modes deduct recurring rebalance costs; "
        "implementation cost is applied once at formation; "
        "no live data or API-key provider."
    )
    if detection_status == "INSUFFICIENT_HISTORY":
        note = (
            "Historical scenario engine has no detection rows for this case window; "
            "metrics were evaluated directly from cached event-window prices with implementation costs."
        )
    return {
        **common,
        "backtest_status": "EVALUATED",
        "base_cvar_95": round(base_cvar, 8),
        "proposed_cvar_95": round(proposed_cvar, 8),
        "cvar_delta": round(cvar_delta, 8),
        "cash_baseline_cvar_95": round(cash_cvar, 8) if cash_cvar is not None else "",
        "hedge_vs_cash_cvar_delta": round(hedge_vs_cash_cvar_delta, 8) if hedge_vs_cash_cvar_delta is not None else "",
        "base_mdd": round(base_mdd, 8),
        "proposed_mdd": round(proposed_mdd, 8),
        "mdd_delta": round(mdd_delta, 8),
        "cash_baseline_mdd": round(cash_mdd, 8) if cash_mdd is not None else "",
        "hedge_vs_cash_mdd_delta": round(hedge_vs_cash_mdd_delta, 8) if hedge_vs_cash_mdd_delta is not None else "",
        "base_stress_window_loss": round(base_loss, 8),
        "proposed_stress_window_loss": round(proposed_loss, 8),
        "stress_loss_delta": round(stress_delta, 8),
        "cash_baseline_stress_window_loss": round(cash_loss, 8) if cash_loss is not None else "",
        "hedge_vs_cash_stress_loss_delta": round(hedge_vs_cash_stress_delta, 8) if hedge_vs_cash_stress_delta is not None else "",
        "base_annual_return": round(base_ann, 8) if base_ann is not None else "",
        "proposed_annual_return": round(proposed_ann, 8) if proposed_ann is not None else "",
        "return_drag": round(return_drag, 8) if return_drag is not None else "",
        "hedge_vs_cash_verdict": hedge_vs_cash_verdict,
        "proposed_net_cvar_95": round(proposed_net_cvar, 8),
        "net_cvar_delta": round(net_cvar_delta, 8),
        "hedge_vs_cash_net_cvar_delta": round(hedge_vs_cash_net_cvar_delta, 8) if hedge_vs_cash_net_cvar_delta is not None else "",
        "proposed_net_mdd": round(proposed_net_mdd, 8),
        "net_mdd_delta": round(net_mdd_delta, 8),
        "hedge_vs_cash_net_mdd_delta": round(hedge_vs_cash_net_mdd_delta, 8) if hedge_vs_cash_net_mdd_delta is not None else "",
        "proposed_net_stress_window_loss": round(proposed_net_loss, 8),
        "net_stress_loss_delta": round(net_stress_delta, 8),
        "hedge_vs_cash_net_stress_loss_delta": round(hedge_vs_cash_net_stress_delta, 8) if hedge_vs_cash_net_stress_delta is not None else "",
        "proposed_net_annual_return": round(proposed_net_ann, 8) if proposed_net_ann is not None else "",
        "cost_adjusted_return_drag": round(cost_adjusted_return_drag, 8) if cost_adjusted_return_drag is not None else "",
        "hedge_vs_cash_net_verdict": hedge_vs_cash_verdict,
        "bootstrap_iterations": bootstrap["bootstrap_iterations"],
        "bootstrap_ci_level": bootstrap["bootstrap_ci_level"],
        "bootstrap_seed": bootstrap["bootstrap_seed"],
        "net_stress_delta_ci_low": round(bootstrap["net_stress_delta_ci_low"], 8) if bootstrap["net_stress_delta_ci_low"] != "" else "",
        "net_stress_delta_ci_high": round(bootstrap["net_stress_delta_ci_high"], 8) if bootstrap["net_stress_delta_ci_high"] != "" else "",
        "net_stress_delta_p_improve": round(bootstrap["net_stress_delta_p_improve"], 6) if bootstrap["net_stress_delta_p_improve"] != "" else "",
        "bootstrap_confidence": bootstrap["bootstrap_confidence"],
        "cash_bootstrap_iterations": cash_bootstrap["bootstrap_iterations"],
        "cash_bootstrap_seed": cash_bootstrap["bootstrap_seed"],
        "cash_net_stress_delta_ci_low": round(cash_bootstrap["net_stress_delta_ci_low"], 8) if cash_bootstrap["net_stress_delta_ci_low"] != "" else "",
        "cash_net_stress_delta_ci_high": round(cash_bootstrap["net_stress_delta_ci_high"], 8) if cash_bootstrap["net_stress_delta_ci_high"] != "" else "",
        "cash_net_stress_delta_p_improve": round(cash_bootstrap["net_stress_delta_p_improve"], 6) if cash_bootstrap["net_stress_delta_p_improve"] != "" else "",
        "cash_bootstrap_confidence": cash_bootstrap["bootstrap_confidence"],
        "verdict": verdict,
        "notes": note,
    }


def render_summary(
    rows,
    run_id,
    historical_run_id,
    hedgemate_run_id,
    transaction_cost_bps: float = DEFAULT_TRANSACTION_COST_BPS,
    slippage_bps: float = DEFAULT_SLIPPAGE_BPS,
    rebalance_frequency: str = DEFAULT_REBALANCE_FREQUENCY,
    bootstrap_iterations: int = DEFAULT_BOOTSTRAP_ITERATIONS,
    bootstrap_ci_level: float = DEFAULT_BOOTSTRAP_CI_LEVEL,
):
    status_counts = Counter(row.get("backtest_status") for row in rows)
    verdict_counts = Counter(row.get("verdict") for row in rows)
    price_window_counts = Counter(row.get("price_window_status") for row in rows)
    price_blocking_counts = delimited_ticker_counts(rows, "price_blocking_tickers")
    pre_inception_counts = delimited_ticker_counts(rows, "pre_inception_tickers")
    missing_price_counts = delimited_ticker_counts(rows, "missing_price_tickers")
    cash_verdict_counts = Counter(row.get("hedge_vs_cash_verdict") for row in rows)
    lines = [
        "# Phase 10E Rebalance-cost Path Walk-forward Backtest",
        "",
        f"- run_id: `{run_id}`",
        f"- historical_validation_run_id: `{historical_run_id}`",
        f"- hedgemate_run_id: `{hedgemate_run_id}`",
        f"- engine_version: `{BACKTEST_ENGINE_VERSION}`",
        "- data_mode: API-free cached raw market prices",
        f"- transaction_cost_bps: {transaction_cost_bps:g}",
        f"- slippage_bps: {slippage_bps:g}",
        f"- rebalance_frequency: `{rebalance_frequency}`",
        f"- bootstrap_iterations: {bootstrap_iterations}",
        f"- bootstrap_ci_level: {bootstrap_ci_level:g}",
        "- return_path_model: formation_only uses buy-and-hold weights; monthly/daily modes rebalance to target weights",
        "- implementation_cost_model: one-time formation turnover cost deducted from proposed returns",
        "- recurring_rebalance_cost_model: monthly/daily modes deduct turnover cost at each scheduled rebalance",
        f"- evaluated_rows: {status_counts['EVALUATED']}",
        f"- insufficient_history_rows: {status_counts['INSUFFICIENT_HISTORY']}",
        f"- insufficient_evaluation_window_rows: {status_counts['INSUFFICIENT_EVALUATION_WINDOW']}",
        f"- out_of_price_range_rows: {price_window_counts['OUT_OF_PRICE_RANGE']}",
        f"- beats_cash_rows: {cash_verdict_counts['BEATS_CASH']}",
        f"- lags_cash_rows: {cash_verdict_counts['LAGS_CASH']}",
        "",
        "## Verdict Counts",
    ]
    for key in ["IMPROVED", "MIXED", "WORSENED", "INSUFFICIENT_HISTORY"]:
        lines.append(f"- {key}: {verdict_counts.get(key, 0)}")
    lines.extend(["", "## Hedge vs Cash Baseline"])
    for key in ["BEATS_CASH", "MIXED_CASH", "LAGS_CASH"]:
        lines.append(f"- {key}: {cash_verdict_counts.get(key, 0)}")
    lines.extend(["", "## Price Window Counts"])
    for key, value in sorted(price_window_counts.items()):
        if key:
            lines.append(f"- {key}: {value}")
    lines.extend(["", "## Price Blocking Tickers"])
    if price_blocking_counts:
        for key, value in sorted(price_blocking_counts.items(), key=lambda item: (-item[1], item[0])):
            lines.append(f"- {key}: {value}")
    else:
        lines.append("- none")
    lines.extend(["", "## Pre-inception Tickers"])
    if pre_inception_counts:
        for key, value in sorted(pre_inception_counts.items(), key=lambda item: (-item[1], item[0])):
            lines.append(f"- {key}: {value}")
    else:
        lines.append("- none")
    lines.extend(["", "## Missing Price Tickers"])
    if missing_price_counts:
        for key, value in sorted(missing_price_counts.items(), key=lambda item: (-item[1], item[0])):
            lines.append(f"- {key}: {value}")
    else:
        lines.append("- none")
    lines.extend(
        [
            "",
            "## Notes",
            "- Verdict counts use cost-adjusted proposed returns.",
            "- Bootstrap intervals resample paired daily base/proposed-net returns by candidate and stress case.",
            "- Insufficient-history cases are never counted as successful detection or backtest wins.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Run Phase 10E API-free rebalance-cost path walk-forward backtest.")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--historical-validation-run-id", required=True)
    parser.add_argument("--hedgemate-run-id", required=True)
    parser.add_argument("--data-version", default="20260512")
    parser.add_argument("--portfolio-input", type=Path, default=DEFAULT_PORTFOLIO_INPUT)
    parser.add_argument("--candidate-limit", type=int, default=0, help="0 means evaluate every candidate/allocation row with a weights_snapshot.")
    parser.add_argument("--recommendation-scope", choices=["portfolio", "single_asset"], default="portfolio")
    parser.add_argument("--transaction-cost-bps", type=float, default=DEFAULT_TRANSACTION_COST_BPS)
    parser.add_argument("--slippage-bps", type=float, default=DEFAULT_SLIPPAGE_BPS)
    parser.add_argument("--rebalance-frequency", choices=["formation_only", "monthly", "daily"], default=DEFAULT_REBALANCE_FREQUENCY)
    parser.add_argument("--bootstrap-iterations", type=int, default=DEFAULT_BOOTSTRAP_ITERATIONS)
    parser.add_argument("--bootstrap-ci-level", type=float, default=DEFAULT_BOOTSTRAP_CI_LEVEL)
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    cases = load_csv(resolve_historical_validation_path(args.historical_validation_run_id))
    recommendation_rows = resolve_recommendation_rows(args.hedgemate_run_id, args.recommendation_scope)
    candidates = select_representative_candidates(recommendation_rows, limit=args.candidate_limit)
    base_weights = pct_weights_from_rows(load_csv(args.portfolio_input))
    raw_market_path = RAW_DIR / f"raw_market_daily_{args.data_version}.csv"
    return_maps = return_maps_from_prices(load_price_maps(raw_market_path))

    rows = []
    for case in cases:
        if (case.get("detection_status") or case.get("validation_status")) == "INSUFFICIENT_HISTORY":
            for candidate in candidates or [{}]:
                rows.append(
                    evaluate_case_candidate(
                        case,
                        candidate,
                        base_weights,
                        return_maps,
                        transaction_cost_bps=args.transaction_cost_bps,
                        slippage_bps=args.slippage_bps,
                        rebalance_frequency=args.rebalance_frequency,
                        bootstrap_iterations=args.bootstrap_iterations,
                        bootstrap_ci_level=args.bootstrap_ci_level,
                    )
                )
            continue
        for candidate in candidates:
            rows.append(
                evaluate_case_candidate(
                    case,
                    candidate,
                    base_weights,
                    return_maps,
                    transaction_cost_bps=args.transaction_cost_bps,
                    slippage_bps=args.slippage_bps,
                    rebalance_frequency=args.rebalance_frequency,
                    bootstrap_iterations=args.bootstrap_iterations,
                    bootstrap_ci_level=args.bootstrap_ci_level,
                )
            )

    output_csv = OUTPUT_VALIDATION_DIR / f"walk_forward_backtest_{args.run_id}.csv"
    summary_md = OUTPUT_REPORT_DIR / f"walk_forward_backtest_summary_{args.run_id}.md"
    metadata_json = OUTPUT_REPORT_DIR / f"walk_forward_backtest_metadata_{args.run_id}.json"
    write_csv(output_csv, BACKTEST_FIELDS, rows)
    summary_md.write_text(
        render_summary(
            rows,
            args.run_id,
            args.historical_validation_run_id,
            args.hedgemate_run_id,
            transaction_cost_bps=args.transaction_cost_bps,
            slippage_bps=args.slippage_bps,
            rebalance_frequency=args.rebalance_frequency,
            bootstrap_iterations=args.bootstrap_iterations,
            bootstrap_ci_level=args.bootstrap_ci_level,
        ),
        encoding="utf-8",
    )
    metadata_json.write_text(
        json.dumps(
            {
                "run_id": args.run_id,
                "pipeline_phase": "phase10e_rebalance_cost_path_walk_forward_backtest",
                "api_free": True,
                "engine_version": BACKTEST_ENGINE_VERSION,
                "transaction_cost_bps": args.transaction_cost_bps,
                "slippage_bps": args.slippage_bps,
                "rebalance_frequency": args.rebalance_frequency,
                "bootstrap_iterations": args.bootstrap_iterations,
                "bootstrap_ci_level": args.bootstrap_ci_level,
                "return_path_model": "formation_only_buy_and_hold_or_scheduled_rebalance",
                "implementation_cost_model": "one_time_formation_turnover_cost",
                "recurring_rebalance_cost_model": "scheduled_turnover_cost_when_monthly_or_daily",
                "historical_validation_run_id": args.historical_validation_run_id,
                "hedgemate_run_id": args.hedgemate_run_id,
                "raw_market_path": str(raw_market_path),
                "backtest_csv": str(output_csv),
                "summary_md": str(summary_md),
                "row_count": len(rows),
                "evaluated_row_count": sum(1 for row in rows if row.get("backtest_status") == "EVALUATED"),
                "insufficient_history_row_count": sum(1 for row in rows if row.get("backtest_status") == "INSUFFICIENT_HISTORY"),
                "out_of_price_range_row_count": sum(1 for row in rows if row.get("price_window_status") == "OUT_OF_PRICE_RANGE"),
                "beats_cash_row_count": sum(1 for row in rows if row.get("hedge_vs_cash_verdict") == "BEATS_CASH"),
                "lags_cash_row_count": sum(1 for row in rows if row.get("hedge_vs_cash_verdict") == "LAGS_CASH"),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(f"WALK_FORWARD_BACKTEST={output_csv}")
    print(f"WALK_FORWARD_BACKTEST_SUMMARY={summary_md}")
    print(f"WALK_FORWARD_BACKTEST_METADATA={metadata_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
