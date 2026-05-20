#!/usr/bin/env python3
"""Apply cost-adjusted backtest evidence to HedgeMate recommendation outputs."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / "outputs" / "reports"
VALIDATION_DIR = ROOT / "outputs" / "validation"

BACKTEST_COLUMNS = [
    "backtest_gate_status",
    "backtest_total_evaluated_count",
    "backtest_total_worsened_count",
    "backtest_target_evaluated_count",
    "backtest_target_improved_count",
    "backtest_target_mixed_count",
    "backtest_target_worsened_count",
    "backtest_target_insufficient_history_count",
    "backtest_target_beats_cash_count",
    "backtest_target_mixed_cash_count",
    "backtest_target_lags_cash_count",
    "backtest_target_bootstrap_count",
    "backtest_target_bootstrap_robust_count",
    "backtest_target_bootstrap_uncertain_count",
    "backtest_target_bootstrap_min_p_improve",
    "backtest_target_bootstrap_avg_p_improve",
    "backtest_target_cash_bootstrap_count",
    "backtest_target_cash_bootstrap_robust_count",
    "backtest_target_cash_bootstrap_uncertain_count",
    "backtest_target_cash_bootstrap_min_p_improve",
    "backtest_target_cash_bootstrap_avg_p_improve",
    "backtest_target_avg_cash_net_stress_delta",
    "backtest_target_min_cash_net_stress_delta",
    "backtest_target_avg_cash_net_mdd_delta",
    "backtest_target_min_cash_net_mdd_delta",
    "backtest_target_avg_cash_net_cvar_delta",
    "backtest_target_min_cash_net_cvar_delta",
    "backtest_target_max_turnover",
    "backtest_context_worsened_count",
    "backtest_evaluated_count",
    "backtest_improved_count",
    "backtest_mixed_count",
    "backtest_worsened_count",
    "backtest_insufficient_history_count",
    "backtest_reason",
    "liquidity_order_notional_krw",
    "liquidity_adv_usage_pct",
    "liquidity_capacity_status",
    "formal_gate_blockers",
    "formal_gate_blocker_count",
    "formal_gate_blocker_summary",
    "user_recommendation_label",
    "active_adverse_scenarios",
]

FORMAL_GATE_AUDIT_FIELDS = [
    "candidate_source",
    "candidate_name",
    "recommendation_status",
    "backtest_gate_status",
    "formal_gate_blockers",
    "formal_gate_blocker_count",
    "target_evaluated_count",
    "target_improved_count",
    "target_worsened_count",
    "target_insufficient_history_count",
    "target_lags_cash_count",
    "target_bootstrap_robust_count",
    "target_bootstrap_count",
    "target_bootstrap_min_p_improve",
    "target_bootstrap_avg_p_improve",
    "target_cash_bootstrap_robust_count",
    "target_cash_bootstrap_count",
    "target_cash_bootstrap_min_p_improve",
    "target_cash_bootstrap_avg_p_improve",
    "target_avg_cash_net_stress_delta",
    "target_min_cash_net_stress_delta",
    "target_avg_cash_net_mdd_delta",
    "target_min_cash_net_mdd_delta",
    "target_avg_cash_net_cvar_delta",
    "target_min_cash_net_cvar_delta",
    "target_max_turnover",
    "combo_min_adv_60",
    "liquidity_order_notional_krw",
    "liquidity_adv_usage_pct",
    "liquidity_capacity_status",
    "formal_readiness_score",
    "backtest_reason",
    "reference_reason",
    "gate_fail_reasons",
]

FORMAL_BLOCKER_LABELS = {
    "fail_gate": "Candidate failed a hard gate.",
    "validation_missing": "Candidate has no matching backtest evidence.",
    "validation_insufficient": "Target stress validation has insufficient history.",
    "validation_thin": "Target stress validation sample is too small for formal use.",
    "target_worsened": "Target stress backtest worsened risk metrics.",
    "cash_baseline_lag": "Hedge lags a cash-only de-risking baseline in target stress.",
    "bootstrap_not_robust": "Target stress bootstrap confidence is not robust.",
    "cash_bootstrap_not_robust": "Target stress cash-baseline bootstrap confidence is not robust.",
    "liquidity_below_formal": "60-day ADV evidence is missing or below the formal threshold.",
    "turnover_above_formal": "Target stress turnover is above the formal threshold.",
    "return_drag_reference": "Pre-backtest scoring kept the candidate reference-only because of return drag.",
    "reference_only": "Candidate remains reference-only after formal gate checks.",
    "unclassified_non_formal": "Candidate is not formal, but no known blocker code was assigned.",
}

STATUS_LABELS = {
    "PASS_RECOMMEND": "정식 추천 가능",
    "REFERENCE_ONLY": "참고용 후보",
    "FAIL_GATE": "기준 미통과",
    "INSUFFICIENT_DATA": "데이터 부족",
}
STATUS_ORDER = ["PASS_RECOMMEND", "REFERENCE_ONLY", "FAIL_GATE", "INSUFFICIENT_DATA"]
MIN_TARGET_EVALUATED_FOR_FORMAL = 2
MIN_FORMAL_ADV_60_KRW = 100_000_000_000.0
MAX_FORMAL_TURNOVER = 0.50
MAX_FORMAL_ADV_USAGE_PCT = 10.0

ATTRIBUTION_METRICS = [
    ("net_cvar_delta", "net_CVaR"),
    ("net_mdd_delta", "net_MDD"),
    ("net_stress_loss_delta", "net_stress_loss"),
    ("cost_adjusted_return_drag", "cost_adjusted_return_drag"),
    ("hedge_vs_cash_net_cvar_delta", "cash_net_CVaR"),
    ("hedge_vs_cash_net_mdd_delta", "cash_net_MDD"),
    ("hedge_vs_cash_net_stress_loss_delta", "cash_net_stress_loss"),
    ("cvar_delta", "CVaR"),
    ("mdd_delta", "MDD"),
    ("stress_loss_delta", "stress_loss"),
    ("return_drag", "return_drag"),
]

ATTRIBUTION_FIELDS = [
    "candidate_label",
    "expected_scenario_code",
    "case_count",
    "evaluated_count",
    "improved_count",
    "mixed_count",
    "worsened_count",
    "insufficient_history_count",
    "worsened_rate",
    "avg_cvar_delta",
    "avg_mdd_delta",
    "avg_stress_loss_delta",
    "avg_return_drag",
    "avg_implementation_cost",
    "avg_recurring_rebalance_cost",
    "avg_total_path_cost",
    "avg_net_cvar_delta",
    "avg_net_mdd_delta",
    "avg_net_stress_loss_delta",
    "avg_cost_adjusted_return_drag",
    "cash_beats_count",
    "cash_mixed_count",
    "cash_lags_count",
    "avg_hedge_vs_cash_cvar_delta",
    "avg_hedge_vs_cash_mdd_delta",
    "avg_hedge_vs_cash_stress_loss_delta",
    "metric_worsened_counts",
    "worst_metric",
    "worst_metric_delta",
    "worst_case_name",
]


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return [dict(row) for row in csv.DictReader(f)]


def write_csv_rows(path: Path, rows: list[dict[str, str]], base_fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(base_fieldnames or [])
    seen = set(fieldnames)
    for row in rows:
        for key in row:
            if key not in seen:
                fieldnames.append(key)
                seen.add(key)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def append_reason(existing: str, reason: str) -> str:
    existing = str(existing or "").strip()
    if not existing:
        return reason
    if reason in existing:
        return existing
    return f"{existing}; {reason}"


def candidate_key(row: dict[str, str], source: str) -> str:
    explicit = str(row.get("candidate_key") or "").strip()
    if explicit:
        return explicit
    source_value = str(row.get("candidate_source") or source or "").strip()
    if source == "multi":
        label = str(row.get("candidate_combo") or row.get("candidate_label") or "").strip()
    else:
        label = str(row.get("candidate_ticker") or row.get("candidate_label") or "").strip()
    weights = str(row.get("weights_snapshot") or "").strip()
    budget = str(row.get("hedge_budget_pct") or row.get("hedge_weight_pct") or "").strip()
    if weights or budget:
        return "|".join([source_value, label, weights or budget])
    return label


def summarize_backtest(backtest_rows: list[dict[str, str]]) -> dict[str, dict[str, int | str]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in backtest_rows:
        key = str(row.get("candidate_key") or row.get("candidate_label") or "").strip()
        if key:
            grouped[key].append(row)

    summary = {}
    for key, rows in grouped.items():
        evaluated = [row for row in rows if str(row.get("backtest_status") or "").upper() == "EVALUATED"]
        verdicts = Counter(str(row.get("verdict") or "").upper() for row in rows)
        if any("is_target_scenario" in row for row in rows):
            target_rows = [row for row in rows if str(row.get("is_target_scenario") or "").upper() in {"Y", "TRUE", "1"}]
            context_rows = [row for row in rows if str(row.get("is_target_scenario") or "").upper() not in {"Y", "TRUE", "1"}]
        else:
            target_rows = rows
            context_rows = []
        target_evaluated = [row for row in target_rows if str(row.get("backtest_status") or "").upper() == "EVALUATED"]
        target_verdicts = Counter(str(row.get("verdict") or "").upper() for row in target_rows)
        target_cash_verdicts = Counter(str(row.get("hedge_vs_cash_verdict") or "").upper() for row in target_evaluated)
        target_bootstrap_rows = [row for row in target_evaluated if parse_float(row.get("net_stress_delta_p_improve")) is not None]
        target_bootstrap_robust = [
            row
            for row in target_bootstrap_rows
            if str(row.get("bootstrap_confidence") or "").upper() == "ROBUST_IMPROVE"
        ]
        target_bootstrap_p_values = [
            parse_float(row.get("net_stress_delta_p_improve"))
            for row in target_bootstrap_rows
        ]
        target_bootstrap_p_values = [value for value in target_bootstrap_p_values if value is not None]
        target_cash_bootstrap_rows = [
            row for row in target_evaluated if parse_float(row.get("cash_net_stress_delta_p_improve")) is not None
        ]
        target_cash_bootstrap_robust = [
            row
            for row in target_cash_bootstrap_rows
            if str(row.get("cash_bootstrap_confidence") or "").upper() == "ROBUST_IMPROVE"
        ]
        target_cash_bootstrap_p_values = [
            parse_float(row.get("cash_net_stress_delta_p_improve"))
            for row in target_cash_bootstrap_rows
        ]
        target_cash_bootstrap_p_values = [value for value in target_cash_bootstrap_p_values if value is not None]
        target_turnover_values = [parse_float(row.get("turnover")) for row in target_evaluated]
        target_turnover_values = [value for value in target_turnover_values if value is not None]
        context_verdicts = Counter(str(row.get("verdict") or "").upper() for row in context_rows)
        summary[key] = {
            "candidate_key": key,
            "candidate_label": str(rows[0].get("candidate_label") or key),
            "row_count": len(rows),
            "evaluated_count": len(evaluated),
            "improved_count": verdicts.get("IMPROVED", 0),
            "mixed_count": verdicts.get("MIXED", 0),
            "worsened_count": verdicts.get("WORSENED", 0),
            "insufficient_history_count": verdicts.get("INSUFFICIENT_HISTORY", 0),
            "target_row_count": len(target_rows),
            "target_evaluated_count": len(target_evaluated),
            "target_improved_count": target_verdicts.get("IMPROVED", 0),
            "target_mixed_count": target_verdicts.get("MIXED", 0),
            "target_worsened_count": target_verdicts.get("WORSENED", 0),
            "target_insufficient_history_count": target_verdicts.get("INSUFFICIENT_HISTORY", 0),
            "target_beats_cash_count": target_cash_verdicts.get("BEATS_CASH", 0),
            "target_mixed_cash_count": target_cash_verdicts.get("MIXED_CASH", 0),
            "target_lags_cash_count": target_cash_verdicts.get("LAGS_CASH", 0),
            "target_bootstrap_count": len(target_bootstrap_rows),
            "target_bootstrap_robust_count": len(target_bootstrap_robust),
            "target_bootstrap_uncertain_count": len(target_bootstrap_rows) - len(target_bootstrap_robust),
            "target_bootstrap_min_p_improve": safe_round(min(target_bootstrap_p_values), 6) if target_bootstrap_p_values else "",
            "target_bootstrap_avg_p_improve": safe_round(sum(target_bootstrap_p_values) / len(target_bootstrap_p_values), 6) if target_bootstrap_p_values else "",
            "target_cash_bootstrap_count": len(target_cash_bootstrap_rows),
            "target_cash_bootstrap_robust_count": len(target_cash_bootstrap_robust),
            "target_cash_bootstrap_uncertain_count": len(target_cash_bootstrap_rows) - len(target_cash_bootstrap_robust),
            "target_cash_bootstrap_min_p_improve": safe_round(min(target_cash_bootstrap_p_values), 6) if target_cash_bootstrap_p_values else "",
            "target_cash_bootstrap_avg_p_improve": safe_round(sum(target_cash_bootstrap_p_values) / len(target_cash_bootstrap_p_values), 6) if target_cash_bootstrap_p_values else "",
            "target_avg_cash_net_stress_delta": safe_round(average_metric(target_evaluated, "hedge_vs_cash_net_stress_loss_delta")),
            "target_min_cash_net_stress_delta": safe_round(min_metric(target_evaluated, "hedge_vs_cash_net_stress_loss_delta")),
            "target_avg_cash_net_mdd_delta": safe_round(average_metric(target_evaluated, "hedge_vs_cash_net_mdd_delta")),
            "target_min_cash_net_mdd_delta": safe_round(min_metric(target_evaluated, "hedge_vs_cash_net_mdd_delta")),
            "target_avg_cash_net_cvar_delta": safe_round(average_metric(target_evaluated, "hedge_vs_cash_net_cvar_delta")),
            "target_min_cash_net_cvar_delta": safe_round(min_metric(target_evaluated, "hedge_vs_cash_net_cvar_delta")),
            "target_max_turnover": safe_round(max(target_turnover_values), 6) if target_turnover_values else "",
            "context_worsened_count": context_verdicts.get("WORSENED", 0),
        }
    return summary


def parse_float(value: object) -> float | None:
    try:
        text = str(value or "").strip()
        if not text:
            return None
        return float(text)
    except (TypeError, ValueError):
        return None


def safe_round(value: float | None, digits: int = 6) -> str:
    if value is None:
        return ""
    return str(round(value, digits))


def liquidity_order_notional(row: dict[str, str]) -> float | None:
    for key in ["hedge_invested_krw", "hedge_budget_krw"]:
        value = parse_float(row.get(key))
        if value is not None and value > 0:
            return value
    return None


def liquidity_adv_usage_pct(row: dict[str, str]) -> float | None:
    adv_60 = parse_float(row.get("combo_min_adv_60"))
    notional = liquidity_order_notional(row)
    if adv_60 is None or adv_60 <= 0 or notional is None:
        return None
    return 100.0 * notional / adv_60


def liquidity_capacity_status(row: dict[str, str]) -> str:
    adv_60 = parse_float(row.get("combo_min_adv_60"))
    notional = liquidity_order_notional(row)
    usage_pct = liquidity_adv_usage_pct(row)
    if adv_60 is None:
        return "MISSING_ADV"
    if notional is None:
        if adv_60 < MIN_FORMAL_ADV_60_KRW:
            return "BELOW_FORMAL_ADV_FLOOR_NO_ORDER_SIZE"
        return "OK_ADV_FLOOR_NO_ORDER_SIZE"
    if usage_pct is None:
        return "MISSING_ADV"
    if usage_pct > MAX_FORMAL_ADV_USAGE_PCT:
        return "ORDER_SIZE_ABOVE_ADV_USAGE_LIMIT"
    if usage_pct > MAX_FORMAL_ADV_USAGE_PCT / 2:
        return "ORDER_SIZE_ADV_USAGE_WATCH"
    return "ORDER_SIZE_ADV_USAGE_OK"


def attach_liquidity_audit(row: dict[str, str]) -> None:
    row["liquidity_order_notional_krw"] = safe_round(liquidity_order_notional(row), 2)
    row["liquidity_adv_usage_pct"] = safe_round(liquidity_adv_usage_pct(row), 4)
    row["liquidity_capacity_status"] = liquidity_capacity_status(row)


def formal_liquidity_reason(row: dict[str, str]) -> str:
    adv_60 = parse_float(row.get("combo_min_adv_60"))
    if adv_60 is None:
        return "candidate 60-day ADV liquidity evidence is missing; formal recommendation blocked"
    usage_pct = liquidity_adv_usage_pct(row)
    if usage_pct is not None:
        if usage_pct > MAX_FORMAL_ADV_USAGE_PCT:
            return (
                f"estimated hedge notional uses {usage_pct:.2f}% of 60-day ADV, above formal limit "
                f"{MAX_FORMAL_ADV_USAGE_PCT:.2f}%"
            )
        return ""
    if adv_60 < MIN_FORMAL_ADV_60_KRW:
        return (
            f"candidate 60-day ADV {adv_60:,.0f} KRW is below formal threshold "
            f"{MIN_FORMAL_ADV_60_KRW:,.0f} KRW"
        )
    return ""


def formal_turnover_reason(max_turnover: float | None) -> str:
    if max_turnover is not None and max_turnover > MAX_FORMAL_TURNOVER:
        return (
            f"target stress backtest turnover {max_turnover:.2f} exceeds formal threshold "
            f"{MAX_FORMAL_TURNOVER:.2f}"
        )
    return ""


def formal_gate_blocker_codes(row: dict[str, str]) -> list[str]:
    blockers: list[str] = []
    status = str(row.get("recommendation_status") or "").upper()
    gate_status = str(row.get("backtest_gate_status") or "").upper()
    target_evaluated = parse_int(row.get("backtest_target_evaluated_count"))
    target_worsened = parse_int(row.get("backtest_target_worsened_count"))
    target_insufficient = parse_int(row.get("backtest_target_insufficient_history_count"))
    target_lags_cash = parse_int(row.get("backtest_target_lags_cash_count"))
    bootstrap_count = parse_int(row.get("backtest_target_bootstrap_count"))
    bootstrap_robust = parse_int(row.get("backtest_target_bootstrap_robust_count"))
    cash_bootstrap_count = parse_int(row.get("backtest_target_cash_bootstrap_count"))
    cash_bootstrap_robust = parse_int(row.get("backtest_target_cash_bootstrap_robust_count"))
    target_max_turnover = parse_float(row.get("backtest_target_max_turnover"))
    reference_reason = str(row.get("reference_reason") or "")

    if status == "FAIL_GATE":
        blockers.append("fail_gate")
    if gate_status == "VALIDATION_MISSING":
        blockers.append("validation_missing")
    if target_worsened > 0:
        blockers.append("target_worsened")
    if target_evaluated <= 0 or target_insufficient > 0:
        blockers.append("validation_insufficient")
    elif target_evaluated < MIN_TARGET_EVALUATED_FOR_FORMAL:
        blockers.append("validation_thin")
    if target_lags_cash > 0:
        blockers.append("cash_baseline_lag")
    if bootstrap_count > 0 and bootstrap_robust < target_evaluated:
        blockers.append("bootstrap_not_robust")
    if cash_bootstrap_count > 0 and cash_bootstrap_robust < target_evaluated:
        blockers.append("cash_bootstrap_not_robust")
    if formal_liquidity_reason(row):
        blockers.append("liquidity_below_formal")
    if formal_turnover_reason(target_max_turnover):
        blockers.append("turnover_above_formal")
    if "annual return drag" in reference_reason.lower():
        blockers.append("return_drag_reference")
    if status == "REFERENCE_ONLY":
        blockers.append("reference_only")

    deduped: list[str] = []
    seen = set()
    for blocker in blockers:
        if blocker not in seen:
            deduped.append(blocker)
            seen.add(blocker)
    if status != "PASS_RECOMMEND" and not deduped:
        deduped.append("unclassified_non_formal")
    return deduped


def attach_formal_gate_blockers(row: dict[str, str]) -> None:
    attach_liquidity_audit(row)
    blockers = formal_gate_blocker_codes(row)
    row["formal_gate_blockers"] = "|".join(blockers)
    row["formal_gate_blocker_count"] = str(len(blockers))
    row["formal_gate_blocker_summary"] = "; ".join(FORMAL_BLOCKER_LABELS.get(code, code) for code in blockers)


def average_metric(rows: list[dict[str, str]], field: str) -> float | None:
    values = [parse_float(row.get(field)) for row in rows]
    values = [value for value in values if value is not None]
    if not values:
        return None
    return sum(values) / len(values)


def min_metric(rows: list[dict[str, str]], field: str) -> float | None:
    values = [parse_float(row.get(field)) for row in rows]
    values = [value for value in values if value is not None]
    return min(values) if values else None


def metric_worsened_counts(rows: list[dict[str, str]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for field, label in ATTRIBUTION_METRICS:
        count = 0
        for row in rows:
            value = parse_float(row.get(field))
            if value is not None and value < 0:
                count += 1
        counts[label] = count
    return counts


def worst_metric_for_rows(rows: list[dict[str, str]]) -> tuple[str, float | None, str]:
    worst_metric = ""
    worst_delta: float | None = None
    worst_case = ""
    for row in rows:
        for field, label in ATTRIBUTION_METRICS:
            value = parse_float(row.get(field))
            if value is None:
                continue
            if worst_delta is None or value < worst_delta:
                worst_metric = label
                worst_delta = value
                worst_case = str(row.get("case_name") or row.get("case_id") or "")
    return worst_metric, worst_delta, worst_case


def build_backtest_attribution(backtest_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    grouped: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in backtest_rows:
        candidate = str(row.get("candidate_label") or "").strip()
        scenario = str(row.get("expected_scenario_code") or "").strip()
        if candidate and scenario:
            grouped[(candidate, scenario)].append(row)

    attribution_rows: list[dict[str, str]] = []
    for (candidate, scenario), rows in sorted(grouped.items()):
        evaluated = [row for row in rows if str(row.get("backtest_status") or "").upper() == "EVALUATED"]
        verdicts = Counter(str(row.get("verdict") or "").upper() for row in rows)
        worsened = verdicts.get("WORSENED", 0)
        evaluated_count = len(evaluated)
        worsened_rate = (worsened / evaluated_count) if evaluated_count else 0.0
        metric_counts = metric_worsened_counts(evaluated)
        cash_verdicts = Counter(str(row.get("hedge_vs_cash_verdict") or "").upper() for row in evaluated)
        worst_metric, worst_delta, worst_case = worst_metric_for_rows(evaluated)
        attribution_rows.append(
            {
                "candidate_label": candidate,
                "expected_scenario_code": scenario,
                "case_count": str(len(rows)),
                "evaluated_count": str(evaluated_count),
                "improved_count": str(verdicts.get("IMPROVED", 0)),
                "mixed_count": str(verdicts.get("MIXED", 0)),
                "worsened_count": str(worsened),
                "insufficient_history_count": str(verdicts.get("INSUFFICIENT_HISTORY", 0)),
                "worsened_rate": safe_round(worsened_rate, 4),
                "avg_cvar_delta": safe_round(average_metric(evaluated, "cvar_delta")),
                "avg_mdd_delta": safe_round(average_metric(evaluated, "mdd_delta")),
                "avg_stress_loss_delta": safe_round(average_metric(evaluated, "stress_loss_delta")),
                "avg_return_drag": safe_round(average_metric(evaluated, "return_drag")),
                "avg_implementation_cost": safe_round(average_metric(evaluated, "implementation_cost")),
                "avg_recurring_rebalance_cost": safe_round(average_metric(evaluated, "recurring_rebalance_cost")),
                "avg_total_path_cost": safe_round(average_metric(evaluated, "total_path_cost")),
                "avg_net_cvar_delta": safe_round(average_metric(evaluated, "net_cvar_delta")),
                "avg_net_mdd_delta": safe_round(average_metric(evaluated, "net_mdd_delta")),
                "avg_net_stress_loss_delta": safe_round(average_metric(evaluated, "net_stress_loss_delta")),
                "avg_cost_adjusted_return_drag": safe_round(average_metric(evaluated, "cost_adjusted_return_drag")),
                "cash_beats_count": str(cash_verdicts.get("BEATS_CASH", 0)),
                "cash_mixed_count": str(cash_verdicts.get("MIXED_CASH", 0)),
                "cash_lags_count": str(cash_verdicts.get("LAGS_CASH", 0)),
                "avg_hedge_vs_cash_cvar_delta": safe_round(average_metric(evaluated, "hedge_vs_cash_cvar_delta")),
                "avg_hedge_vs_cash_mdd_delta": safe_round(average_metric(evaluated, "hedge_vs_cash_mdd_delta")),
                "avg_hedge_vs_cash_stress_loss_delta": safe_round(average_metric(evaluated, "hedge_vs_cash_stress_loss_delta")),
                "metric_worsened_counts": "; ".join(f"{key}={value}" for key, value in metric_counts.items()),
                "worst_metric": worst_metric,
                "worst_metric_delta": safe_round(worst_delta),
                "worst_case_name": worst_case,
            }
        )
    return attribution_rows


def write_backtest_attribution_csv(path: Path, attribution_rows: list[dict[str, str]]) -> None:
    write_csv_rows(path, attribution_rows, ATTRIBUTION_FIELDS)


def top_attribution_rows(attribution_rows: list[dict[str, str]], limit: int = 8) -> list[dict[str, str]]:
    return sorted(
        attribution_rows,
        key=lambda row: (
            -parse_int(row.get("worsened_count")),
            -(parse_float(row.get("worsened_rate")) or 0.0),
            str(row.get("candidate_label") or ""),
            str(row.get("expected_scenario_code") or ""),
        ),
    )[:limit]


def write_backtest_attribution_md(path: Path, attribution_rows: list[dict[str, str]]) -> None:
    total_rows = len(attribution_rows)
    total_evaluated = sum(parse_int(row.get("evaluated_count")) for row in attribution_rows)
    total_worsened = sum(parse_int(row.get("worsened_count")) for row in attribution_rows)
    total_improved = sum(parse_int(row.get("improved_count")) for row in attribution_rows)
    lines = [
        "# Backtest Attribution",
        "",
        f"- attribution_rows: {total_rows}",
        f"- evaluated_count: {total_evaluated}",
        f"- improved_count: {total_improved}",
        f"- worsened_count: {total_worsened}",
        "",
        "## Top Worsened Candidate/Scenario Pairs",
        "",
        "| candidate | scenario | evaluated | worsened | worsened_rate | worst_metric | worst_delta | worst_case |",
        "|---|---|---:|---:|---:|---|---:|---|",
    ]
    for row in top_attribution_rows(attribution_rows):
        lines.append(
            "| {candidate} | {scenario} | {evaluated} | {worsened} | {rate} | {metric} | {delta} | {case} |".format(
                candidate=str(row.get("candidate_label") or "").replace("|", "/"),
                scenario=str(row.get("expected_scenario_code") or "").replace("|", "/"),
                evaluated=row.get("evaluated_count") or "0",
                worsened=row.get("worsened_count") or "0",
                rate=row.get("worsened_rate") or "0",
                metric=row.get("worst_metric") or "-",
                delta=row.get("worst_metric_delta") or "",
                case=str(row.get("worst_case_name") or "").replace("|", "/"),
            )
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def gate_row(row: dict[str, str], evidence: dict[str, int | str] | None) -> dict[str, str]:
    gated = dict(row)
    original_status = str(gated.get("recommendation_status") or "").upper()
    gated["active_adverse_scenarios"] = str(gated.get("risk_bucket_match") or "").strip()

    if evidence is None:
        gate_status = "VALIDATION_MISSING"
        reason = "backtest summary missing for candidate; 검증 미완료"
        if original_status == "PASS_RECOMMEND":
            gated["recommendation_status"] = "REFERENCE_ONLY"
            gated["reference_reason"] = append_reason(gated.get("reference_reason", ""), reason)
        gated["backtest_evaluated_count"] = "0"
        gated["backtest_improved_count"] = "0"
        gated["backtest_mixed_count"] = "0"
        gated["backtest_worsened_count"] = "0"
        gated["backtest_insufficient_history_count"] = "0"
        gated["backtest_total_evaluated_count"] = "0"
        gated["backtest_total_worsened_count"] = "0"
        gated["backtest_target_evaluated_count"] = "0"
        gated["backtest_target_improved_count"] = "0"
        gated["backtest_target_mixed_count"] = "0"
        gated["backtest_target_worsened_count"] = "0"
        gated["backtest_target_insufficient_history_count"] = "0"
        gated["backtest_target_beats_cash_count"] = "0"
        gated["backtest_target_mixed_cash_count"] = "0"
        gated["backtest_target_lags_cash_count"] = "0"
        gated["backtest_target_bootstrap_count"] = "0"
        gated["backtest_target_bootstrap_robust_count"] = "0"
        gated["backtest_target_bootstrap_uncertain_count"] = "0"
        gated["backtest_target_bootstrap_min_p_improve"] = ""
        gated["backtest_target_bootstrap_avg_p_improve"] = ""
        gated["backtest_target_cash_bootstrap_count"] = "0"
        gated["backtest_target_cash_bootstrap_robust_count"] = "0"
        gated["backtest_target_cash_bootstrap_uncertain_count"] = "0"
        gated["backtest_target_cash_bootstrap_min_p_improve"] = ""
        gated["backtest_target_cash_bootstrap_avg_p_improve"] = ""
        gated["backtest_target_avg_cash_net_stress_delta"] = ""
        gated["backtest_target_min_cash_net_stress_delta"] = ""
        gated["backtest_target_avg_cash_net_mdd_delta"] = ""
        gated["backtest_target_min_cash_net_mdd_delta"] = ""
        gated["backtest_target_avg_cash_net_cvar_delta"] = ""
        gated["backtest_target_min_cash_net_cvar_delta"] = ""
        gated["backtest_target_max_turnover"] = ""
        gated["backtest_context_worsened_count"] = "0"
        gated["backtest_gate_status"] = gate_status
        gated["backtest_reason"] = reason
        gated["user_recommendation_label"] = STATUS_LABELS.get(gated.get("recommendation_status"), gated.get("recommendation_status", ""))
        attach_formal_gate_blockers(gated)
        return gated

    total_evaluated = int(evidence.get("evaluated_count", 0) or 0)
    total_worsened = int(evidence.get("worsened_count", 0) or 0)
    evaluated = int(evidence.get("target_evaluated_count", evidence.get("evaluated_count", 0)) or 0)
    improved = int(evidence.get("target_improved_count", evidence.get("improved_count", 0)) or 0)
    mixed = int(evidence.get("target_mixed_count", evidence.get("mixed_count", 0)) or 0)
    worsened = int(evidence.get("target_worsened_count", evidence.get("worsened_count", 0)) or 0)
    insufficient = int(evidence.get("target_insufficient_history_count", evidence.get("insufficient_history_count", 0)) or 0)
    beats_cash = int(evidence.get("target_beats_cash_count", 0) or 0)
    mixed_cash = int(evidence.get("target_mixed_cash_count", 0) or 0)
    lags_cash = int(evidence.get("target_lags_cash_count", 0) or 0)
    bootstrap_count = int(evidence.get("target_bootstrap_count", 0) or 0)
    bootstrap_robust = int(evidence.get("target_bootstrap_robust_count", 0) or 0)
    bootstrap_uncertain = int(evidence.get("target_bootstrap_uncertain_count", 0) or 0)
    bootstrap_min_p = str(evidence.get("target_bootstrap_min_p_improve") or "")
    cash_bootstrap_count = int(evidence.get("target_cash_bootstrap_count", 0) or 0)
    cash_bootstrap_robust = int(evidence.get("target_cash_bootstrap_robust_count", 0) or 0)
    cash_bootstrap_uncertain = int(evidence.get("target_cash_bootstrap_uncertain_count", 0) or 0)
    cash_bootstrap_min_p = str(evidence.get("target_cash_bootstrap_min_p_improve") or "")
    target_max_turnover = parse_float(evidence.get("target_max_turnover"))
    context_worsened = int(evidence.get("context_worsened_count", 0) or 0)
    liquidity_reason = formal_liquidity_reason(gated)
    turnover_reason = formal_turnover_reason(target_max_turnover)

    if worsened > 0:
        gate_status = "FAIL_BACKTEST"
        reason = "target-scenario backtest worsened risk metrics; 정식 추천 불가"
        gated["recommendation_status"] = "FAIL_GATE"
        gated["gate_fail_reasons"] = append_reason(gated.get("gate_fail_reasons", ""), reason)
    elif evaluated <= 0:
        gate_status = "VALIDATION_INSUFFICIENT"
        reason = "target-scenario historical validation has insufficient history; 검증 부족"
        if original_status == "PASS_RECOMMEND":
            gated["recommendation_status"] = "REFERENCE_ONLY"
            gated["reference_reason"] = append_reason(gated.get("reference_reason", ""), reason)
    elif insufficient > 0:
        gate_status = "PARTIAL_VALIDATION"
        reason = "target-scenario backtest has non-worsened evidence but incomplete history; 참고용 후보"
        if original_status == "PASS_RECOMMEND":
            gated["recommendation_status"] = "REFERENCE_ONLY"
            gated["reference_reason"] = append_reason(gated.get("reference_reason", ""), reason)
    elif evaluated < MIN_TARGET_EVALUATED_FOR_FORMAL:
        gate_status = "VALIDATION_THIN"
        reason = f"target-scenario backtest has only {evaluated} evaluated stress case; 표본 부족"
        if original_status == "PASS_RECOMMEND":
            gated["recommendation_status"] = "REFERENCE_ONLY"
            gated["reference_reason"] = append_reason(gated.get("reference_reason", ""), reason)
    elif lags_cash > 0:
        gate_status = "REFERENCE_ONLY_CASH_BASELINE"
        reason = f"target-scenario hedge did not beat cash-only de-risking in {lags_cash} stress case"
        if original_status == "PASS_RECOMMEND":
            gated["recommendation_status"] = "REFERENCE_ONLY"
            gated["reference_reason"] = append_reason(gated.get("reference_reason", ""), reason)
    elif bootstrap_count > 0 and bootstrap_robust < evaluated:
        gate_status = "REFERENCE_ONLY_BOOTSTRAP"
        reason = "target-scenario bootstrap confidence is not robust enough for a formal recommendation"
        if original_status == "PASS_RECOMMEND":
            gated["recommendation_status"] = "REFERENCE_ONLY"
            gated["reference_reason"] = append_reason(gated.get("reference_reason", ""), reason)
    elif cash_bootstrap_count > 0 and cash_bootstrap_robust < evaluated:
        gate_status = "REFERENCE_ONLY_CASH_BOOTSTRAP"
        reason = "target-scenario cash-baseline bootstrap confidence is not robust enough for a formal recommendation"
        if original_status == "PASS_RECOMMEND":
            gated["recommendation_status"] = "REFERENCE_ONLY"
            gated["reference_reason"] = append_reason(gated.get("reference_reason", ""), reason)
    elif liquidity_reason:
        gate_status = "REFERENCE_ONLY_LIQUIDITY"
        reason = liquidity_reason
        if original_status == "PASS_RECOMMEND":
            gated["recommendation_status"] = "REFERENCE_ONLY"
            gated["reference_reason"] = append_reason(gated.get("reference_reason", ""), reason)
    elif turnover_reason:
        gate_status = "REFERENCE_ONLY_TURNOVER"
        reason = turnover_reason
        if original_status == "PASS_RECOMMEND":
            gated["recommendation_status"] = "REFERENCE_ONLY"
            gated["reference_reason"] = append_reason(gated.get("reference_reason", ""), reason)
    elif improved <= 0 and mixed > 0:
        gate_status = "REFERENCE_ONLY_BACKTEST"
        reason = "target-scenario walk-forward backtest is mixed; 참고용 후보"
        if original_status == "PASS_RECOMMEND":
            gated["recommendation_status"] = "REFERENCE_ONLY"
            gated["reference_reason"] = append_reason(gated.get("reference_reason", ""), reason)
    else:
        gate_status = "VALIDATED"
        reason = "target-scenario walk-forward backtest has evaluated non-worsened evidence"
        if context_worsened > 0:
            reason = f"{reason}; non-target scenarios worsened {context_worsened} times"

    gated["backtest_gate_status"] = gate_status
    gated["backtest_total_evaluated_count"] = str(total_evaluated)
    gated["backtest_total_worsened_count"] = str(total_worsened)
    gated["backtest_target_evaluated_count"] = str(evaluated)
    gated["backtest_target_improved_count"] = str(improved)
    gated["backtest_target_mixed_count"] = str(mixed)
    gated["backtest_target_worsened_count"] = str(worsened)
    gated["backtest_target_insufficient_history_count"] = str(insufficient)
    gated["backtest_target_beats_cash_count"] = str(beats_cash)
    gated["backtest_target_mixed_cash_count"] = str(mixed_cash)
    gated["backtest_target_lags_cash_count"] = str(lags_cash)
    gated["backtest_target_bootstrap_count"] = str(bootstrap_count)
    gated["backtest_target_bootstrap_robust_count"] = str(bootstrap_robust)
    gated["backtest_target_bootstrap_uncertain_count"] = str(bootstrap_uncertain)
    gated["backtest_target_bootstrap_min_p_improve"] = bootstrap_min_p
    gated["backtest_target_bootstrap_avg_p_improve"] = str(evidence.get("target_bootstrap_avg_p_improve") or "")
    gated["backtest_target_cash_bootstrap_count"] = str(cash_bootstrap_count)
    gated["backtest_target_cash_bootstrap_robust_count"] = str(cash_bootstrap_robust)
    gated["backtest_target_cash_bootstrap_uncertain_count"] = str(cash_bootstrap_uncertain)
    gated["backtest_target_cash_bootstrap_min_p_improve"] = cash_bootstrap_min_p
    gated["backtest_target_cash_bootstrap_avg_p_improve"] = str(evidence.get("target_cash_bootstrap_avg_p_improve") or "")
    gated["backtest_target_avg_cash_net_stress_delta"] = str(evidence.get("target_avg_cash_net_stress_delta") or "")
    gated["backtest_target_min_cash_net_stress_delta"] = str(evidence.get("target_min_cash_net_stress_delta") or "")
    gated["backtest_target_avg_cash_net_mdd_delta"] = str(evidence.get("target_avg_cash_net_mdd_delta") or "")
    gated["backtest_target_min_cash_net_mdd_delta"] = str(evidence.get("target_min_cash_net_mdd_delta") or "")
    gated["backtest_target_avg_cash_net_cvar_delta"] = str(evidence.get("target_avg_cash_net_cvar_delta") or "")
    gated["backtest_target_min_cash_net_cvar_delta"] = str(evidence.get("target_min_cash_net_cvar_delta") or "")
    gated["backtest_target_max_turnover"] = safe_round(target_max_turnover, 6)
    gated["backtest_context_worsened_count"] = str(context_worsened)
    gated["backtest_evaluated_count"] = str(evaluated)
    gated["backtest_improved_count"] = str(improved)
    gated["backtest_mixed_count"] = str(mixed)
    gated["backtest_worsened_count"] = str(worsened)
    gated["backtest_insufficient_history_count"] = str(insufficient)
    gated["backtest_reason"] = reason
    gated["user_recommendation_label"] = STATUS_LABELS.get(gated.get("recommendation_status"), gated.get("recommendation_status", ""))
    attach_formal_gate_blockers(gated)
    return gated


def gate_recommendations(rows: list[dict[str, str]], source: str, backtest_summary: dict[str, dict[str, int | str]]) -> list[dict[str, str]]:
    gated_rows = []
    for row in rows:
        key = candidate_key(row, source)
        evidence = backtest_summary.get(key)
        if evidence is None:
            legacy_key = str(row.get("candidate_combo") or row.get("candidate_ticker") or row.get("candidate_label") or "").strip()
            evidence = backtest_summary.get(legacy_key)
        gated_rows.append(gate_row(row, evidence))
    return gated_rows


def status_counts(rows: list[dict[str, str]]) -> dict[str, int]:
    counts = Counter(str(row.get("recommendation_status") or "UNKNOWN") for row in rows)
    return dict(sorted(counts.items()))


def parse_int(value: object) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def candidate_name(row: dict[str, str]) -> str:
    return str(
        row.get("candidate_ticker")
        or row.get("candidate_combo")
        or row.get("candidate_label")
        or "-"
    )


def status_counts_ordered(rows: list[dict[str, str]]) -> dict[str, int]:
    counts = Counter(str(row.get("recommendation_status") or "UNKNOWN") for row in rows)
    ordered = {status: counts.get(status, 0) for status in STATUS_ORDER}
    for status, count in sorted(counts.items()):
        if status not in ordered:
            ordered[status] = count
    return ordered


def gate_status_counts(rows: list[dict[str, str]]) -> dict[str, int]:
    counts = Counter(str(row.get("backtest_gate_status") or "UNKNOWN") for row in rows)
    return dict(sorted(counts.items()))


def formal_blocker_counts(rows: list[dict[str, str]]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for row in rows:
        for blocker in str(row.get("formal_gate_blockers") or "").split("|"):
            blocker = blocker.strip()
            if blocker:
                counts[blocker] += 1
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))


def build_formal_gate_audit_rows(
    one_to_one_rows: list[dict[str, str]],
    multi_rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    rows = []
    for source, source_rows in [("one_to_one", one_to_one_rows), ("multi", multi_rows)]:
        for row in source_rows:
            blockers = str(row.get("formal_gate_blockers") or "")
            rows.append(
                {
                    "candidate_source": source,
                    "candidate_name": candidate_name(row),
                    "recommendation_status": str(row.get("recommendation_status") or ""),
                    "backtest_gate_status": str(row.get("backtest_gate_status") or ""),
                    "formal_gate_blockers": blockers,
                    "formal_gate_blocker_count": str(row.get("formal_gate_blocker_count") or "0"),
                    "target_evaluated_count": str(row.get("backtest_target_evaluated_count") or "0"),
                    "target_improved_count": str(row.get("backtest_target_improved_count") or "0"),
                    "target_worsened_count": str(row.get("backtest_target_worsened_count") or "0"),
                    "target_insufficient_history_count": str(row.get("backtest_target_insufficient_history_count") or "0"),
                    "target_lags_cash_count": str(row.get("backtest_target_lags_cash_count") or "0"),
                    "target_bootstrap_robust_count": str(row.get("backtest_target_bootstrap_robust_count") or "0"),
                    "target_bootstrap_count": str(row.get("backtest_target_bootstrap_count") or "0"),
                    "target_bootstrap_min_p_improve": str(row.get("backtest_target_bootstrap_min_p_improve") or ""),
                    "target_bootstrap_avg_p_improve": str(row.get("backtest_target_bootstrap_avg_p_improve") or ""),
                    "target_cash_bootstrap_robust_count": str(row.get("backtest_target_cash_bootstrap_robust_count") or "0"),
                    "target_cash_bootstrap_count": str(row.get("backtest_target_cash_bootstrap_count") or "0"),
                    "target_cash_bootstrap_min_p_improve": str(row.get("backtest_target_cash_bootstrap_min_p_improve") or ""),
                    "target_cash_bootstrap_avg_p_improve": str(row.get("backtest_target_cash_bootstrap_avg_p_improve") or ""),
                    "target_avg_cash_net_stress_delta": str(row.get("backtest_target_avg_cash_net_stress_delta") or ""),
                    "target_min_cash_net_stress_delta": str(row.get("backtest_target_min_cash_net_stress_delta") or ""),
                    "target_avg_cash_net_mdd_delta": str(row.get("backtest_target_avg_cash_net_mdd_delta") or ""),
                    "target_min_cash_net_mdd_delta": str(row.get("backtest_target_min_cash_net_mdd_delta") or ""),
                    "target_avg_cash_net_cvar_delta": str(row.get("backtest_target_avg_cash_net_cvar_delta") or ""),
                    "target_min_cash_net_cvar_delta": str(row.get("backtest_target_min_cash_net_cvar_delta") or ""),
                    "target_max_turnover": str(row.get("backtest_target_max_turnover") or ""),
                    "combo_min_adv_60": str(row.get("combo_min_adv_60") or ""),
                    "liquidity_order_notional_krw": str(row.get("liquidity_order_notional_krw") or ""),
                    "liquidity_adv_usage_pct": str(row.get("liquidity_adv_usage_pct") or ""),
                    "liquidity_capacity_status": str(row.get("liquidity_capacity_status") or ""),
                    "formal_readiness_score": formal_readiness_score(row),
                    "backtest_reason": str(row.get("backtest_reason") or ""),
                    "reference_reason": str(row.get("reference_reason") or ""),
                    "gate_fail_reasons": str(row.get("gate_fail_reasons") or ""),
                }
            )
    return sorted(
        rows,
        key=lambda row: (
            -(parse_float(row.get("formal_readiness_score")) or 0.0),
            parse_int(row.get("formal_gate_blocker_count")),
            row.get("candidate_source") or "",
            row.get("candidate_name") or "",
        ),
    )


def write_formal_gate_audit_csv(path: Path, rows: list[dict[str, str]]) -> None:
    write_csv_rows(path, rows, FORMAL_GATE_AUDIT_FIELDS)


def formal_readiness_score(row: dict[str, str]) -> str:
    status = str(row.get("recommendation_status") or "").upper()
    if status == "PASS_RECOMMEND":
        return "100"
    target_evaluated = parse_int(row.get("backtest_target_evaluated_count"))
    target_lags_cash = parse_int(row.get("backtest_target_lags_cash_count"))
    min_p = parse_float(row.get("backtest_target_bootstrap_min_p_improve"))
    cash_min_p = parse_float(row.get("backtest_target_cash_bootstrap_min_p_improve"))
    robustness_p = min(value for value in [min_p, cash_min_p] if value is not None) if min_p is not None or cash_min_p is not None else None
    blockers = set(str(row.get("formal_gate_blockers") or "").split("|"))
    liquidity_ok = "liquidity_below_formal" not in blockers
    turnover_ok = "turnover_above_formal" not in blockers
    hard_fail = "fail_gate" in blockers or "target_worsened" in blockers

    score = 0.0
    score += min(1.0, target_evaluated / max(1, MIN_TARGET_EVALUATED_FOR_FORMAL)) * 20.0
    if target_evaluated > 0:
        score += max(0.0, 1.0 - (target_lags_cash / target_evaluated)) * 20.0
    if robustness_p is not None:
        score += max(0.0, min(1.0, robustness_p)) * 20.0
    if liquidity_ok:
        score += 20.0
    if turnover_ok:
        score += 10.0
    if not hard_fail:
        score += 10.0
    return safe_round(score, 2)


def write_formal_gate_audit_md(path: Path, rows: list[dict[str, str]]) -> None:
    blocker_counts = formal_blocker_counts(rows)
    status_counts_payload = status_counts_ordered(rows)
    lines = [
        "# Formal Gate Audit",
        "",
        f"- candidate_rows: {len(rows)}",
        f"- status_counts: `{json.dumps(status_counts_payload, ensure_ascii=False)}`",
        "",
        "## Blocker Counts",
        "",
    ]
    if blocker_counts:
        for blocker, count in blocker_counts.items():
            lines.append(f"- {blocker}: {count} - {FORMAL_BLOCKER_LABELS.get(blocker, blocker)}")
    else:
        lines.append("- none")
    liquidity_counts = Counter(str(row.get("liquidity_capacity_status") or "UNKNOWN") for row in rows)
    lines.extend(
        [
            "",
            "## Liquidity Capacity Audit",
            "",
        ]
    )
    for status, count in sorted(liquidity_counts.items()):
        lines.append(f"- {status}: {count}")
    lines.extend(
        [
            "",
            "| candidate | source | status | ADV KRW | order KRW | ADV usage % | capacity status |",
            "|---|---|---|---:|---:|---:|---|",
        ]
    )
    for row in sorted(rows, key=lambda item: (item.get("liquidity_capacity_status") or "", item.get("candidate_name") or ""))[:12]:
        lines.append(
            "| {candidate} | {source} | {status} | {adv} | {order} | {usage} | {capacity} |".format(
                candidate=str(row.get("candidate_name") or "").replace("|", "/"),
                source=row.get("candidate_source") or "",
                status=row.get("recommendation_status") or "",
                adv=row.get("combo_min_adv_60") or "",
                order=row.get("liquidity_order_notional_krw") or "",
                usage=row.get("liquidity_adv_usage_pct") or "",
                capacity=row.get("liquidity_capacity_status") or "",
            )
        )
    lines.extend(
        [
            "",
            "## Highest-friction Candidates",
            "",
            "| candidate | source | status | readiness | blockers | target eval | cash lags | robust/boot | min p | cash robust/boot | cash min p | min cash stress | reason |",
            "|---|---|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---|",
        ]
    )
    highest_friction = sorted(rows, key=lambda row: (-parse_int(row.get("formal_gate_blocker_count")), parse_float(row.get("formal_readiness_score")) or 0.0, row.get("candidate_name") or ""))[:12]
    for row in highest_friction:
        reason = str(row.get("backtest_reason") or row.get("reference_reason") or row.get("gate_fail_reasons") or "").replace("|", "/")
        lines.append(
            "| {candidate} | {source} | {status} | {readiness} | {blockers} | {target_eval} | {cash_lags} | {robust}/{boot} | {min_p} | {cash_robust}/{cash_boot} | {cash_min_p} | {cash_min} | {reason} |".format(
                candidate=str(row.get("candidate_name") or "").replace("|", "/"),
                source=row.get("candidate_source") or "",
                status=row.get("recommendation_status") or "",
                readiness=row.get("formal_readiness_score") or "",
                blockers=str(row.get("formal_gate_blockers") or "").replace("|", ", "),
                target_eval=row.get("target_evaluated_count") or "0",
                cash_lags=row.get("target_lags_cash_count") or "0",
                robust=row.get("target_bootstrap_robust_count") or "0",
                boot=row.get("target_bootstrap_count") or "0",
                min_p=row.get("target_bootstrap_min_p_improve") or "",
                cash_robust=row.get("target_cash_bootstrap_robust_count") or "0",
                cash_boot=row.get("target_cash_bootstrap_count") or "0",
                cash_min_p=row.get("target_cash_bootstrap_min_p_improve") or "",
                cash_min=row.get("target_min_cash_net_stress_delta") or "",
                reason=reason,
            )
        )
    lines.extend(
        [
            "",
            "## Closest Formal Near-misses",
            "",
            "| candidate | source | status | readiness | blockers | target eval | cash lags | robust/boot | min p | cash robust/boot | cash min p | avg cash stress | reason |",
            "|---|---|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---|",
        ]
    )
    near_misses = [row for row in rows if row.get("recommendation_status") == "REFERENCE_ONLY"]
    near_misses = sorted(
        near_misses,
        key=lambda row: (
            -(parse_float(row.get("formal_readiness_score")) or 0.0),
            parse_int(row.get("formal_gate_blocker_count")),
            row.get("candidate_name") or "",
        ),
    )[:12]
    for row in near_misses:
        reason = str(row.get("backtest_reason") or row.get("reference_reason") or row.get("gate_fail_reasons") or "").replace("|", "/")
        lines.append(
            "| {candidate} | {source} | {status} | {readiness} | {blockers} | {target_eval} | {cash_lags} | {robust}/{boot} | {min_p} | {cash_robust}/{cash_boot} | {cash_min_p} | {cash_avg} | {reason} |".format(
                candidate=str(row.get("candidate_name") or "").replace("|", "/"),
                source=row.get("candidate_source") or "",
                status=row.get("recommendation_status") or "",
                readiness=row.get("formal_readiness_score") or "",
                blockers=str(row.get("formal_gate_blockers") or "").replace("|", ", "),
                target_eval=row.get("target_evaluated_count") or "0",
                cash_lags=row.get("target_lags_cash_count") or "0",
                robust=row.get("target_bootstrap_robust_count") or "0",
                boot=row.get("target_bootstrap_count") or "0",
                min_p=row.get("target_bootstrap_min_p_improve") or "",
                cash_robust=row.get("target_cash_bootstrap_robust_count") or "0",
                cash_boot=row.get("target_cash_bootstrap_count") or "0",
                cash_min_p=row.get("target_cash_bootstrap_min_p_improve") or "",
                cash_avg=row.get("target_avg_cash_net_stress_delta") or "",
                reason=reason,
            )
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_post_backtest_qa(
    path: Path,
    payload: dict[str, object],
    one_to_one_rows: list[dict[str, str]],
    multi_rows: list[dict[str, str]],
    attribution_rows: list[dict[str, str]] | None = None,
) -> None:
    rows = list(one_to_one_rows) + list(multi_rows)
    attribution_rows = attribution_rows or []
    recommendation_counts = status_counts_ordered(rows)
    gate_counts = gate_status_counts(rows)
    blocker_counts = formal_blocker_counts(rows)
    worsened_formal = [
        row
        for row in rows
        if row.get("recommendation_status") == "PASS_RECOMMEND"
        and parse_int(row.get("backtest_worsened_count")) > 0
    ]
    insufficient_as_success = [
        row
        for row in rows
        if row.get("recommendation_status") == "PASS_RECOMMEND"
        and parse_int(row.get("backtest_evaluated_count")) <= 0
        and parse_int(row.get("backtest_insufficient_history_count")) > 0
    ]

    lines = [
        "# HedgeMate Recommendation Status QA (Post-Backtest)",
        "",
        f"- generated_at_utc: {payload['generated_at_utc']}",
        f"- hedgemate_run_id: {payload['hedgemate_run_id']}",
        f"- backtest_run_id: {payload['backtest_run_id']}",
        "- basis: post-backtest gated recommendation CSVs",
        f"- portfolio_1to1_gated_csv: {payload['portfolio_1to1_gated_csv']}",
        f"- portfolio_multi_gated_csv: {payload['portfolio_multi_gated_csv']}",
        "",
        "## Status Counts",
        "",
    ]
    lines.extend(f"- {status}: {recommendation_counts.get(status, 0)}" for status in STATUS_ORDER)
    extra_statuses = [status for status in recommendation_counts if status not in STATUS_ORDER]
    lines.extend(f"- {status}: {recommendation_counts[status]}" for status in extra_statuses)
    lines.extend(
        [
            "",
            "## Backtest Gate Counts",
            "",
        ]
    )
    if gate_counts:
        lines.extend(f"- {status}: {count}" for status, count in gate_counts.items())
    else:
        lines.append("- none")
    lines.extend(["", "## Formal Gate Blocker Counts", ""])
    if blocker_counts:
        lines.extend(f"- {blocker}: {count}" for blocker, count in blocker_counts.items())
    else:
        lines.append("- none")

    if attribution_rows:
        total_evaluated = sum(parse_int(row.get("evaluated_count")) for row in attribution_rows)
        total_worsened = sum(parse_int(row.get("worsened_count")) for row in attribution_rows)
        total_improved = sum(parse_int(row.get("improved_count")) for row in attribution_rows)
        lines.extend(
            [
                "",
                "## Backtest Attribution Summary",
                "",
                f"- attribution_csv: {payload.get('backtest_attribution_csv')}",
                f"- attribution_md: {payload.get('backtest_attribution_md')}",
                f"- evaluated_count: {total_evaluated}",
                f"- improved_count: {total_improved}",
                f"- worsened_count: {total_worsened}",
                "",
                "| candidate | scenario | evaluated | worsened | worsened_rate | worst_metric | worst_delta | worst_case |",
                "|---|---|---:|---:|---:|---|---:|---|",
            ]
        )
        for row in top_attribution_rows(attribution_rows, limit=10):
            lines.append(
                "| {candidate} | {scenario} | {evaluated} | {worsened} | {rate} | {metric} | {delta} | {case} |".format(
                    candidate=str(row.get("candidate_label") or "").replace("|", "/"),
                    scenario=str(row.get("expected_scenario_code") or "").replace("|", "/"),
                    evaluated=row.get("evaluated_count") or "0",
                    worsened=row.get("worsened_count") or "0",
                    rate=row.get("worsened_rate") or "0",
                    metric=row.get("worst_metric") or "-",
                    delta=row.get("worst_metric_delta") or "",
                    case=str(row.get("worst_case_name") or "").replace("|", "/"),
                )
            )

    if recommendation_counts.get("PASS_RECOMMEND", 0) == 0:
        lines.extend(
            [
                "",
                "## Zero Formal Recommendation Message",
                "",
                "- 현재 검증 기준에서 정식 추천 가능한 후보는 없습니다. 참고용 후보는 있으나, backtest evidence가 부족하거나 일부 구간에서 위험 악화가 확인되어 정식 추천으로 분류하지 않았습니다.",
            ]
        )

    lines.extend(
        [
            "",
            "## Policy Audit",
            "",
            f"- WORSENED candidates still marked PASS_RECOMMEND: {len(worsened_formal)}",
            f"- INSUFFICIENT_HISTORY-only candidates marked as successful PASS_RECOMMEND: {len(insufficient_as_success)}",
            "- Missing backtest evidence is treated as validation missing and cannot upgrade a formal recommendation.",
            "- Combination candidates require evidence for the same combination; component evidence alone is not used for upgrade.",
            "",
            "## Examples By Final Status",
            "",
            "| recommendation_status | candidate | backtest_gate_status | worsened | insufficient_history | reason |",
            "|---|---|---|---:|---:|---|",
        ]
    )
    for status in STATUS_ORDER:
        examples = [row for row in rows if row.get("recommendation_status") == status][:10]
        if not examples:
            lines.append(f"| {status} | - | - | 0 | 0 | no rows in this run |")
            continue
        for row in examples:
            reason = (
                row.get("backtest_reason")
                or row.get("gate_fail_reasons")
                or row.get("reference_reason")
                or ""
            )
            reason = str(reason).replace("|", "/")
            lines.append(
                f"| {status} | {candidate_name(row)} | {row.get('backtest_gate_status') or '-'} | "
                f"{parse_int(row.get('backtest_worsened_count'))} | "
                f"{parse_int(row.get('backtest_insufficient_history_count'))} | {reason} |"
            )

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_summary(path: Path, payload: dict[str, object]) -> None:
    lines = [
        "# Backtest Gate Summary",
        "",
        f"- generated_at_utc: {payload['generated_at_utc']}",
        f"- hedgemate_run_id: {payload['hedgemate_run_id']}",
        f"- backtest_run_id: {payload['backtest_run_id']}",
        f"- one_to_one_rows: {payload['one_to_one_rows']}",
        f"- multi_rows: {payload['multi_rows']}",
        f"- one_to_one_status_counts: `{json.dumps(payload['one_to_one_status_counts'], ensure_ascii=False)}`",
        f"- multi_status_counts: `{json.dumps(payload['multi_status_counts'], ensure_ascii=False)}`",
        f"- post_backtest_qa_md: {payload.get('post_backtest_qa_md')}",
        f"- backtest_attribution_csv: {payload.get('backtest_attribution_csv')}",
        f"- backtest_attribution_md: {payload.get('backtest_attribution_md')}",
        f"- formal_gate_audit_csv: {payload.get('formal_gate_audit_csv')}",
        f"- formal_gate_audit_md: {payload.get('formal_gate_audit_md')}",
        f"- formal_gate_blocker_counts: `{json.dumps(payload.get('formal_gate_blocker_counts') or {}, ensure_ascii=False)}`",
        "",
        "## Policy",
        "",
        "- Backtest verdicts are treated as cost-adjusted when cost fields are present.",
        "- WORSENED candidates are not allowed to remain PASS_RECOMMEND.",
        "- INSUFFICIENT_HISTORY is shown as validation insufficient, never as success.",
        f"- Formal recommendations require at least {MIN_TARGET_EVALUATED_FOR_FORMAL} evaluated target stress cases.",
        "- Formal recommendations must beat a cash-only de-risking baseline in target stress cases.",
        "- If portfolio and cash-baseline bootstrap confidence fields are present, every evaluated target stress case must be ROBUST_IMPROVE for a formal recommendation.",
        f"- Formal recommendations require combo_min_adv_60 of at least {MIN_FORMAL_ADV_60_KRW:,.0f} KRW.",
        f"- Formal recommendations require target max turnover no higher than {MAX_FORMAL_TURNOVER:.2f}.",
        "- Candidates without matching backtest evidence are downgraded from formal recommendation to reference-only.",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def apply_backtest_gate(
    hedgemate_run_id: str,
    backtest_run_id: str,
    one_to_one_path: Path | None = None,
    multi_path: Path | None = None,
    backtest_path: Path | None = None,
    one_output_path: Path | None = None,
    multi_output_path: Path | None = None,
    output_suffix: str = "backtest_gated",
) -> dict[str, object]:
    one_to_one_path = one_to_one_path or REPORT_DIR / f"portfolio_1to1_hedge_{hedgemate_run_id}.csv"
    multi_path = multi_path or REPORT_DIR / f"portfolio_multi_hedge_{hedgemate_run_id}.csv"
    backtest_path = backtest_path or VALIDATION_DIR / f"walk_forward_backtest_{backtest_run_id}.csv"

    one_to_one_rows = read_csv_rows(one_to_one_path)
    multi_rows = read_csv_rows(multi_path)
    backtest_rows = read_csv_rows(backtest_path)
    backtest_summary = summarize_backtest(backtest_rows)
    attribution_rows = build_backtest_attribution(backtest_rows)

    one_to_one_gated = gate_recommendations(one_to_one_rows, "one_to_one", backtest_summary)
    multi_gated = gate_recommendations(multi_rows, "multi", backtest_summary)

    one_output = one_output_path or REPORT_DIR / f"portfolio_1to1_hedge_{hedgemate_run_id}_{output_suffix}.csv"
    multi_output = multi_output_path or REPORT_DIR / f"portfolio_multi_hedge_{hedgemate_run_id}_{output_suffix}.csv"
    summary_json = REPORT_DIR / f"backtest_gate_summary_{hedgemate_run_id}_{output_suffix}.json"
    summary_md = REPORT_DIR / f"backtest_gate_summary_{hedgemate_run_id}_{output_suffix}.md"
    post_qa_md = REPORT_DIR / f"recommendation_status_qa_post_backtest_{hedgemate_run_id}_{output_suffix}.md"
    attribution_csv = REPORT_DIR / f"backtest_attribution_{backtest_run_id}.csv"
    attribution_md = REPORT_DIR / f"backtest_attribution_{backtest_run_id}.md"
    formal_audit_rows = build_formal_gate_audit_rows(one_to_one_gated, multi_gated)
    formal_audit_csv = REPORT_DIR / f"formal_gate_audit_{hedgemate_run_id}_{output_suffix}.csv"
    formal_audit_md = REPORT_DIR / f"formal_gate_audit_{hedgemate_run_id}_{output_suffix}.md"

    one_fields = list(one_to_one_rows[0].keys()) if one_to_one_rows else []
    multi_fields = list(multi_rows[0].keys()) if multi_rows else []
    write_csv_rows(one_output, one_to_one_gated, one_fields + [c for c in BACKTEST_COLUMNS if c not in one_fields])
    write_csv_rows(multi_output, multi_gated, multi_fields + [c for c in BACKTEST_COLUMNS if c not in multi_fields])
    write_backtest_attribution_csv(attribution_csv, attribution_rows)
    write_backtest_attribution_md(attribution_md, attribution_rows)
    write_formal_gate_audit_csv(formal_audit_csv, formal_audit_rows)
    write_formal_gate_audit_md(formal_audit_md, formal_audit_rows)

    generated_at_utc = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    blocker_counts = formal_blocker_counts(formal_audit_rows)
    payload: dict[str, object] = {
        "generated_at_utc": generated_at_utc,
        "hedgemate_run_id": hedgemate_run_id,
        "backtest_run_id": backtest_run_id,
        "backtest_csv": str(backtest_path),
        "portfolio_1to1_gated_csv": str(one_output),
        "portfolio_multi_gated_csv": str(multi_output),
        "summary_md": str(summary_md),
        "post_backtest_qa_md": str(post_qa_md),
        "backtest_attribution_csv": str(attribution_csv),
        "backtest_attribution_md": str(attribution_md),
        "formal_gate_audit_csv": str(formal_audit_csv),
        "formal_gate_audit_md": str(formal_audit_md),
        "one_to_one_rows": len(one_to_one_gated),
        "multi_rows": len(multi_gated),
        "one_to_one_status_counts": status_counts(one_to_one_gated),
        "multi_status_counts": status_counts(multi_gated),
        "backtest_candidate_count": len(backtest_summary),
        "backtest_attribution_count": len(attribution_rows),
        "formal_gate_blocker_counts": blocker_counts,
    }
    write_post_backtest_qa(post_qa_md, payload, one_to_one_gated, multi_gated, attribution_rows)
    summary_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_summary(summary_md, payload)
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Apply backtest gate to HedgeMate recommendation CSVs")
    parser.add_argument("--hedgemate-run-id", required=True)
    parser.add_argument("--backtest-run-id", required=True)
    parser.add_argument("--one-to-one-path", type=Path)
    parser.add_argument("--multi-path", type=Path)
    parser.add_argument("--backtest-path", type=Path)
    parser.add_argument("--one-output-path", type=Path)
    parser.add_argument("--multi-output-path", type=Path)
    parser.add_argument("--output-suffix", default="backtest_gated")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = apply_backtest_gate(
        hedgemate_run_id=args.hedgemate_run_id,
        backtest_run_id=args.backtest_run_id,
        one_to_one_path=args.one_to_one_path,
        multi_path=args.multi_path,
        backtest_path=args.backtest_path,
        one_output_path=args.one_output_path,
        multi_output_path=args.multi_output_path,
        output_suffix=args.output_suffix,
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
