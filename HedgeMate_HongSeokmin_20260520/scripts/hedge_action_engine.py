#!/usr/bin/env python3
"""Portfolio vulnerability attribution and bounded hedge action generation.

This module intentionally sits beside the formal recommendation gate. It explains
which holdings drive each risk sleeve and proposes bounded add/trim/replace
actions without weakening the existing PASS_RECOMMEND gate.
"""

from __future__ import annotations

import csv
import json
import math
from collections import defaultdict
from pathlib import Path


ACTION_STATUS_FORMAL = "FORMAL_ACTION"
ACTION_STATUS_REVIEW = "REVIEW_ACTION"
ACTION_STATUS_RESEARCH = "RESEARCH_ONLY"
ACTION_STATUS_FAIL = "FAIL_ACTION"
ACTION_STATUS_NO_ACTION = "NO_ACTION"

ACTION_TYPE_ADD = "ADD_HEDGE"
ACTION_TYPE_TRIM = "TRIM_AND_HEDGE"
ACTION_TYPE_REPLACE = "REPLACE_SLEEVE"

RISK_SLEEVE_DEFINITIONS = {
    "semiconductor_ai_cycle": {
        "label_ko": "AI·반도체 사이클",
        "scenario_codes": {"semiconductor_ai_cycle_shock"},
        "defensive_candidates": ["SHY", "IEF", "GLD", "IAU", "UUP"],
    },
    "rate_shock_growth_duration": {
        "label_ko": "장기금리·성장주 듀레이션",
        "scenario_codes": {"higher_for_longer_long_rate_shock"},
        "defensive_candidates": ["SHY", "IEF", "TIP", "GLD", "IAU"],
    },
    "usdkrw_fx_korea": {
        "label_ko": "달러강세·원화약세",
        "scenario_codes": {"usd_strength_krw_weakness"},
        "defensive_candidates": ["UUP", "SHY", "IEF", "GLD", "IAU"],
    },
    "recession_liquidity_stress": {
        "label_ko": "침체·유동성 스트레스",
        "scenario_codes": {"slowdown_recession_deflation_risk", "acute_global_stress_liquidity_crunch"},
        "defensive_candidates": ["SHY", "IEF", "TLT", "GLD", "IAU", "XLV", "XLU"],
    },
    "inflation_energy_shock": {
        "label_ko": "물가·에너지 재상승",
        "scenario_codes": {"stagflation_reinflation_energy_shock"},
        "defensive_candidates": ["GLD", "IAU", "DBC", "USO", "XLE", "TIP"],
    },
    "geopolitical_supply_chain": {
        "label_ko": "지정학·공급망 충격",
        "scenario_codes": {"geopolitical_escalation_supply_shock", "china_trade_fragmentation_shock"},
        "defensive_candidates": ["GLD", "IAU", "USO", "DBC", "PPA", "ITA", "SHY", "IEF"],
    },
    "korea_domestic_credit": {
        "label_ko": "한국 내수·신용 스트레스",
        "scenario_codes": {"korea_domestic_financial_stress"},
        "defensive_candidates": ["UUP", "SHY", "IEF", "GLD", "IAU"],
    },
}

ATTRIBUTION_FIELDS = [
    "risk_sleeve",
    "risk_sleeve_label_ko",
    "scenario_code",
    "scenario",
    "scenario_name_ko",
    "ticker",
    "asset_ticker",
    "source_asset",
    "asset_name",
    "asset_class",
    "weight_pct",
    "current_weight",
    "current_weight_pct",
    "scenario_weight",
    "scenario_activation_weight",
    "signed_sensitivity",
    "asset_scenario_beta",
    "abs_sensitivity",
    "vulnerability_contribution",
    "weighted_contribution",
    "sleeve_contribution_pct",
    "contribution_pct",
    "contribution_pct_of_sleeve",
    "portfolio_contribution_pct",
    "contribution_pct_of_total",
    "source_or_offset",
    "plain_reason_ko",
    "plain_korean_reason",
    "evidence_quality",
    "gate_eligible",
]

ACTION_FIELDS = [
    "action_id",
    "action_status",
    "action_type",
    "risk_sleeve",
    "risk_sleeve_label_ko",
    "scenario",
    "risk_scenario_codes",
    "source_tickers",
    "source_asset",
    "offset_tickers",
    "candidate_tickers",
    "hedge_asset",
    "candidate_label",
    "linked_recommendation_status",
    "formal_gate_source",
    "scenario_weight",
    "before_sleeve_vulnerability",
    "after_sleeve_vulnerability",
    "vulnerability_delta",
    "vulnerability_improve_pct",
    "source_contribution_pct",
    "contribution_pct",
    "contribution_pct_of_sleeve",
    "current_weight",
    "proposed_weight",
    "source_current_weight_pct",
    "source_proposed_weight_pct",
    "hedge_current_weight_pct",
    "hedge_proposed_weight_pct",
    "base_cvar_95",
    "proposed_cvar_95",
    "cvar_delta",
    "base_mdd",
    "proposed_mdd",
    "mdd_delta",
    "base_beta_sp500_krw",
    "proposed_beta_sp500_krw",
    "beta_delta",
    "base_stress_avg_ret_krw",
    "proposed_stress_avg_ret_krw",
    "stress_delta",
    "base_sharpe_krw_proxy",
    "proposed_sharpe_krw_proxy",
    "sharpe_delta",
    "metric_source",
    "metric_coverage_reason",
    "turnover_pct",
    "existing_portfolio_kept_pct",
    "max_single_trim_pct",
    "constraint_status",
    "constraint_reasons",
    "action_reason_ko",
    "status_reason_ko",
    "plain_korean_reason",
    "expected_effect",
    "rejected_reason_ko",
    "can_execute_action",
    "selected_in_action_plan",
    "selection_reason_ko",
    "not_selected_reason_ko",
    "before_weights_json",
    "after_weights_json",
]


def _to_float(value, default=None):
    if value in (None, ""):
        return default
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    if math.isnan(number):
        return default
    return number


def _normalise_weights_pct(weights):
    normalised = {}
    for ticker, raw_weight in (weights or {}).items():
        weight = _to_float(raw_weight, 0.0) or 0.0
        if weight <= 0:
            continue
        normalised[str(ticker)] = weight * 100.0 if weight <= 1.0 else weight
    return normalised


def _scenario_state_weight(row):
    raw_state = str(row.get("raw_state") or "").upper()
    if raw_state == "OFF":
        return 0.0
    explicit = _to_float(row.get("scenario_trade_gate_weight"), None)
    if explicit is None:
        explicit = _to_float(row.get("scenario_context_weight"), None)
    if explicit is not None:
        return max(0.0, explicit)
    state = str(row.get("display_state") or row.get("final_display_state") or row.get("state_label") or raw_state).upper()
    return {
        "STRONG": 1.0,
        "STRESS": 1.0,
        "ACTIVE": 0.8,
        "WATCH": 0.45,
        "PROVISIONAL": 0.25,
        "OFF": 0.0,
    }.get(state, 0.0)


def _scenario_weight_map(scenario_rows):
    weights = {}
    for row in scenario_rows or []:
        code = row.get("scenario_code")
        if code:
            weights[code] = _scenario_state_weight(row)
    return weights


def _signed_sensitivity(row):
    for key in ("scenario_beta", "scenario_return_beta", "scenario_downside_beta"):
        value = _to_float(row.get(key), None)
        if value is not None:
            return value
    magnitude = abs(_to_float(row.get("magnitude"), 0.0) or 0.0)
    direction = str(row.get("direction") or "").lower()
    if direction == "negative":
        return -magnitude
    if direction == "positive":
        return magnitude
    return 0.0


def _row_scenario_weight(row, scenario_weights):
    code = row.get("scenario_code")
    if code in scenario_weights:
        return scenario_weights[code]
    explicit = _to_float(row.get("scenario_trade_gate_weight"), None)
    if explicit is None:
        explicit = _to_float(row.get("scenario_context_weight"), None)
    if explicit is not None:
        return max(0.0, explicit)
    active_hit = _to_float(row.get("active_hit_count"), None)
    if active_hit is not None:
        return 1.0 if active_hit > 0 else 0.0
    return 1.0


def _sleeves_for_scenario(scenario_code, risk_sleeves=None):
    definitions = risk_sleeves or RISK_SLEEVE_DEFINITIONS
    return [
        sleeve
        for sleeve, definition in definitions.items()
        if scenario_code in definition.get("scenario_codes", set())
    ]


def build_portfolio_vulnerability_attribution(
    portfolio_weights,
    asset_scenario_sensitivity_rows,
    scenario_rows=None,
    risk_sleeves=None,
):
    """Return detailed holding-level attribution rows and sleeve summary."""
    definitions = risk_sleeves or RISK_SLEEVE_DEFINITIONS
    weights_pct = _normalise_weights_pct(portfolio_weights)
    scenario_weights = _scenario_weight_map(scenario_rows)
    rows = []

    for row in asset_scenario_sensitivity_rows or []:
        ticker = row.get("ticker")
        if ticker not in weights_pct:
            continue
        scenario_code = row.get("scenario_code")
        scenario_weight = _row_scenario_weight(row, scenario_weights)
        if scenario_weight <= 0:
            continue
        signed = _signed_sensitivity(row)
        weight_pct = weights_pct[ticker]
        contribution = (weight_pct / 100.0) * signed * scenario_weight
        if abs(contribution) < 1e-12 and abs(signed) < 1e-12:
            role = "neutral"
        elif contribution > 0:
            role = "source"
        else:
            role = "offset"
        for sleeve in _sleeves_for_scenario(scenario_code, definitions):
            definition = definitions[sleeve]
            sleeve_label = definition.get("label_ko", sleeve)
            rows.append(
                {
                    "risk_sleeve": sleeve,
                    "risk_sleeve_label_ko": sleeve_label,
                    "scenario_code": scenario_code,
                    "scenario_name_ko": row.get("scenario_name_ko") or row.get("scenario_name") or scenario_code,
                    "ticker": ticker,
                    "asset_name": row.get("asset_name") or ticker,
                    "asset_class": row.get("asset_class") or "",
                    "weight_pct": round(weight_pct, 6),
                    "scenario_weight": round(scenario_weight, 6),
                    "signed_sensitivity": round(signed, 6),
                    "abs_sensitivity": round(abs(signed), 6),
                    "vulnerability_contribution": round(contribution, 8),
                    "source_or_offset": role,
                    "plain_reason_ko": _plain_attribution_reason_ko(ticker, sleeve_label, role, weight_pct, contribution),
                    "evidence_quality": row.get("evidence_quality") or "",
                    "gate_eligible": row.get("gate_eligible") or "",
                }
            )

    summary = _build_attribution_summary(rows, definitions)
    _add_contribution_percentages(rows, summary)
    return rows, summary


def _plain_attribution_reason_ko(ticker, sleeve_label, role, weight_pct, contribution):
    contribution_text = f"{abs(contribution):.4f}"
    weight_text = f"{weight_pct:.1f}%"
    if role == "source":
        return f"{ticker} 비중 {weight_text}가 {sleeve_label} 취약성을 키우는 방향으로 {contribution_text}만큼 기여합니다."
    if role == "offset":
        return f"{ticker} 비중 {weight_text}가 {sleeve_label} 취약성을 일부 상쇄합니다."
    return f"{ticker} 비중 {weight_text}는 현재 {sleeve_label} 취약성에 큰 영향을 주지 않습니다."


def _aggregate_holdings(rows, role):
    totals = defaultdict(float)
    for row in rows:
        if row["source_or_offset"] == role:
            totals[row["ticker"]] += float(row["vulnerability_contribution"])
    if role == "offset":
        key_func = lambda item: item[1]
    else:
        key_func = lambda item: -item[1]
    return [
        {"ticker": ticker, "contribution": round(value, 8)}
        for ticker, value in sorted(totals.items(), key=key_func)
    ]


def _build_attribution_summary(rows, definitions):
    by_sleeve = defaultdict(list)
    for row in rows:
        by_sleeve[row["risk_sleeve"]].append(row)

    sleeves = []
    for sleeve, definition in definitions.items():
        sleeve_rows = by_sleeve.get(sleeve, [])
        gross_source = sum(float(row["vulnerability_contribution"]) for row in sleeve_rows if row["source_or_offset"] == "source")
        gross_offset = sum(float(row["vulnerability_contribution"]) for row in sleeve_rows if row["source_or_offset"] == "offset")
        net = gross_source + gross_offset
        sleeves.append(
            {
                "risk_sleeve": sleeve,
                "risk_sleeve_label_ko": definition.get("label_ko", sleeve),
                "scenario_codes": sorted(definition.get("scenario_codes", set())),
                "net_vulnerability": round(net, 8),
                "gross_source": round(gross_source, 8),
                "gross_offset": round(gross_offset, 8),
                "source_holdings": _aggregate_holdings(sleeve_rows, "source"),
                "offset_holdings": _aggregate_holdings(sleeve_rows, "offset"),
            }
        )
    sleeves.sort(key=lambda row: row["net_vulnerability"], reverse=True)
    return {
        "portfolio_total_vulnerability": round(sum(max(row["net_vulnerability"], 0.0) for row in sleeves), 8),
        "risk_sleeves": sleeves,
    }


def _add_contribution_percentages(rows, summary):
    sleeve_source_totals = {
        sleeve["risk_sleeve"]: float(sleeve.get("gross_source") or 0.0)
        for sleeve in summary.get("risk_sleeves", [])
    }
    portfolio_total = float(summary.get("portfolio_total_vulnerability") or 0.0)
    for row in rows:
        contribution = float(row.get("vulnerability_contribution") or 0.0)
        sleeve_total = sleeve_source_totals.get(row["risk_sleeve"], 0.0)
        if contribution > 0 and sleeve_total > 0:
            row["sleeve_contribution_pct"] = round(contribution / sleeve_total * 100.0, 4)
        else:
            row["sleeve_contribution_pct"] = 0.0
        if contribution > 0 and portfolio_total > 0:
            row["portfolio_contribution_pct"] = round(contribution / portfolio_total * 100.0, 4)
        else:
            row["portfolio_contribution_pct"] = 0.0
        _add_attribution_aliases(row)


def _add_attribution_aliases(row):
    """Keep old attribution fields while exposing a stable product contract."""
    role = row.get("source_or_offset")
    row["scenario"] = row.get("scenario_code", "")
    row["asset_ticker"] = row.get("ticker", "")
    row["source_asset"] = row.get("ticker", "") if role == "source" else ""
    row["current_weight"] = row.get("weight_pct", 0.0)
    row["current_weight_pct"] = row.get("weight_pct", 0.0)
    row["scenario_activation_weight"] = row.get("scenario_weight", 0.0)
    row["asset_scenario_beta"] = row.get("signed_sensitivity", 0.0)
    row["weighted_contribution"] = row.get("vulnerability_contribution", 0.0)
    row["contribution_pct"] = row.get("sleeve_contribution_pct", 0.0)
    row["contribution_pct_of_sleeve"] = row.get("sleeve_contribution_pct", 0.0)
    row["contribution_pct_of_total"] = row.get("portfolio_contribution_pct", 0.0)
    row["plain_korean_reason"] = row.get("plain_reason_ko", "")
    return row


def _sensitivity_index(asset_scenario_sensitivity_rows, scenario_rows=None, risk_sleeves=None):
    definitions = risk_sleeves or RISK_SLEEVE_DEFINITIONS
    scenario_weights = _scenario_weight_map(scenario_rows)
    index = defaultdict(lambda: defaultdict(float))
    for row in asset_scenario_sensitivity_rows or []:
        ticker = row.get("ticker")
        scenario_code = row.get("scenario_code")
        if not ticker or not scenario_code:
            continue
        scenario_weight = _row_scenario_weight(row, scenario_weights)
        if scenario_weight <= 0:
            continue
        signed = _signed_sensitivity(row)
        for sleeve in _sleeves_for_scenario(scenario_code, definitions):
            index[ticker][sleeve] += signed * scenario_weight
    return index


def _portfolio_sleeve_vulnerability(weights_pct, sensitivity_index, sleeve):
    total = 0.0
    for ticker, weight_pct in weights_pct.items():
        total += (weight_pct / 100.0) * sensitivity_index.get(ticker, {}).get(sleeve, 0.0)
    return total


def _parse_candidate_tickers(row):
    if row.get("candidate_ticker"):
        return [str(row["candidate_ticker"])]
    raw = row.get("candidate_combo") or row.get("candidate_label") or ""
    if not raw:
        return []
    return [part.strip() for part in str(raw).split("+") if part.strip()]


def _parse_weights_snapshot(row):
    raw = row.get("weights_snapshot")
    if not raw:
        return {}
    try:
        payload = json.loads(raw)
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    return _normalise_weights_pct(payload)


def _candidate_label(row, tickers):
    return row.get("candidate_combo") or row.get("candidate_ticker") or row.get("candidate_label") or " + ".join(tickers)


def _is_research_only_candidate(row, tickers):
    role = str(row.get("candidate_role") or "").lower()
    label = " ".join(tickers + [str(row.get("candidate_label") or "")]).upper()
    research_tokens = ("INVERSE", "LEVER", "2X", "3X", "OPTION", "PUT", "CALL", "VIX", "UVXY", "SVXY", "SQQQ", "TQQQ")
    return role == "research_only" or any(token in label for token in research_tokens)


def _candidate_offsets_sleeve(tickers, sensitivity_index, sleeve):
    return sum(sensitivity_index.get(ticker, {}).get(sleeve, 0.0) for ticker in tickers) < 0


def _candidate_mentions_sleeve(row, sleeve):
    scenarios = set(str(row.get("risk_bucket_match") or "").split("|"))
    sleeve_scenarios = RISK_SLEEVE_DEFINITIONS.get(sleeve, {}).get("scenario_codes", set())
    return bool(scenarios & sleeve_scenarios)


def metric_fields_from_recommendation(row, action_type=None):
    metric = {
        "base_cvar_95": row.get("base_cvar_95"),
        "proposed_cvar_95": row.get("proposed_cvar_95"),
        "cvar_delta": _metric_delta(row.get("proposed_cvar_95"), row.get("base_cvar_95")),
        "base_mdd": row.get("base_mdd"),
        "proposed_mdd": row.get("proposed_mdd"),
        "mdd_delta": _metric_delta(row.get("proposed_mdd"), row.get("base_mdd")),
        "base_beta_sp500_krw": row.get("base_beta_sp500_krw"),
        "proposed_beta_sp500_krw": row.get("proposed_beta_sp500_krw"),
        "beta_delta": _metric_delta(row.get("proposed_beta_sp500_krw"), row.get("base_beta_sp500_krw")),
        "base_stress_avg_ret_krw": row.get("base_stress_avg_ret_krw"),
        "proposed_stress_avg_ret_krw": row.get("proposed_stress_avg_ret_krw"),
        "stress_delta": _metric_delta(row.get("proposed_stress_avg_ret_krw"), row.get("base_stress_avg_ret_krw")),
        "base_sharpe_krw_proxy": row.get("base_sharpe_krw_proxy"),
        "proposed_sharpe_krw_proxy": row.get("proposed_sharpe_krw_proxy"),
        "sharpe_delta": _metric_delta(row.get("proposed_sharpe_krw_proxy"), row.get("base_sharpe_krw_proxy")),
        "metric_source": "linked_recommendation_row",
        "metric_coverage_reason": "",
    }
    if action_type and action_type != ACTION_TYPE_ADD:
        metric["metric_source"] = "linked_candidate_placeholder"
        metric["metric_coverage_reason"] = "pipeline metric enrichment should recompute this bounded action from before/after weights"
    if all(metric.get(key) in (None, "") for key in ["base_cvar_95", "proposed_cvar_95", "base_mdd", "proposed_mdd"]):
        metric["metric_source"] = ""
        metric["metric_coverage_reason"] = "metrics not available from linked recommendation row"
    return metric


def empty_metric_fields(reason):
    return {
        "base_cvar_95": None,
        "proposed_cvar_95": None,
        "cvar_delta": None,
        "base_mdd": None,
        "proposed_mdd": None,
        "mdd_delta": None,
        "base_beta_sp500_krw": None,
        "proposed_beta_sp500_krw": None,
        "beta_delta": None,
        "base_stress_avg_ret_krw": None,
        "proposed_stress_avg_ret_krw": None,
        "stress_delta": None,
        "base_sharpe_krw_proxy": None,
        "proposed_sharpe_krw_proxy": None,
        "sharpe_delta": None,
        "metric_source": "",
        "metric_coverage_reason": reason,
    }


def _metric_delta(after, before):
    after_value = _to_float(after, None)
    before_value = _to_float(before, None)
    if after_value is None or before_value is None:
        return None
    return round(after_value - before_value, 8)


def _scale_existing_and_add(base_weights_pct, tickers, add_pct):
    if not tickers or add_pct <= 0:
        return dict(base_weights_pct)
    scaled = {ticker: weight * (1.0 - add_pct / 100.0) for ticker, weight in base_weights_pct.items()}
    each = add_pct / len(tickers)
    for ticker in tickers:
        scaled[ticker] = scaled.get(ticker, 0.0) + each
    return _clean_weights(scaled)


def _trim_and_add(base_weights_pct, source_tickers, candidate_tickers, trim_pct):
    after = dict(base_weights_pct)
    trimmed = 0.0
    for ticker in source_tickers:
        if trimmed >= trim_pct:
            break
        current = after.get(ticker, 0.0)
        amount = min(5.0, trim_pct - trimmed, current)
        if amount <= 0:
            continue
        after[ticker] = current - amount
        trimmed += amount
    if candidate_tickers and trimmed > 0:
        each = trimmed / len(candidate_tickers)
        for ticker in candidate_tickers:
            after[ticker] = after.get(ticker, 0.0) + each
    return _clean_weights(after)


def _clean_weights(weights_pct):
    return {ticker: round(weight, 6) for ticker, weight in weights_pct.items() if weight > 1e-9}


def _turnover_pct(before, after):
    tickers = set(before) | set(after)
    return sum(abs(after.get(ticker, 0.0) - before.get(ticker, 0.0)) for ticker in tickers)


def _existing_kept_pct(before, after):
    return sum(min(before.get(ticker, 0.0), after.get(ticker, 0.0)) for ticker in before)


def _constraint_check(before, after, max_turnover_pct, min_existing_kept_pct, concentration_cap_pct, max_candidate_weight_pct, candidate_tickers):
    reasons = []
    turnover = _turnover_pct(before, after)
    kept = _existing_kept_pct(before, after)
    if turnover > max_turnover_pct + 1e-9:
        reasons.append(f"turnover {turnover:.2f}% > {max_turnover_pct:.2f}%")
    if kept < min_existing_kept_pct - 1e-9:
        reasons.append(f"existing kept {kept:.2f}% < {min_existing_kept_pct:.2f}%")
    max_weight = max(after.values(), default=0.0)
    if max_weight > concentration_cap_pct + 1e-9:
        reasons.append(f"concentration cap {max_weight:.2f}% > {concentration_cap_pct:.2f}%")
    for ticker in candidate_tickers:
        if after.get(ticker, 0.0) > max_candidate_weight_pct + 1e-9:
            reasons.append(f"candidate cap {ticker} {after[ticker]:.2f}% > {max_candidate_weight_pct:.2f}%")
    return ("PASS" if not reasons else "FAIL", reasons, turnover, kept)


def _action_status(action_type, linked_status, vulnerability_delta, constraint_status, is_research_only):
    if is_research_only:
        return ACTION_STATUS_RESEARCH
    if constraint_status != "PASS" or vulnerability_delta >= 0:
        return ACTION_STATUS_FAIL
    if action_type == ACTION_TYPE_ADD and linked_status == "PASS_RECOMMEND":
        return ACTION_STATUS_FORMAL
    return ACTION_STATUS_REVIEW


def _json_weights(weights):
    return json.dumps({ticker: round(weight, 6) for ticker, weight in sorted(weights.items())}, ensure_ascii=False, sort_keys=True)


def _parse_weights_json(value):
    if not value:
        return {}
    if isinstance(value, dict):
        return {str(ticker): _to_float(weight, 0.0) or 0.0 for ticker, weight in value.items()}
    try:
        payload = json.loads(value)
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    if not isinstance(payload, dict):
        return {}
    return {str(ticker): _to_float(weight, 0.0) or 0.0 for ticker, weight in payload.items()}


def _first_pipe_value(value):
    if isinstance(value, (list, tuple)):
        return str(value[0]) if value else ""
    return str(value or "").split("|")[0].strip()


def _risk_scenario_codes_for_action(row):
    raw = row.get("risk_scenario_codes")
    if raw:
        return raw
    sleeve = row.get("risk_sleeve")
    scenarios = RISK_SLEEVE_DEFINITIONS.get(sleeve, {}).get("scenario_codes", set())
    return "|".join(sorted(scenarios))


def _metric_delta_text(row, key, label, pct=False, good_when_lower=True):
    delta = _to_float(row.get(key), None)
    if delta is None:
        return ""
    value = delta * 100.0 if pct else delta
    unit = "%p" if pct else ""
    improved = delta < 0 if good_when_lower else delta > 0
    direction = "개선" if improved else "악화"
    return f"{label} {abs(value):.2f}{unit} {direction}"


def _expected_effect_ko(row):
    pieces = []
    delta = _to_float(row.get("vulnerability_delta"), None)
    if delta is not None:
        direction = "감소" if delta < 0 else "증가"
        pieces.append(f"취약성 {abs(delta):.4f} {direction}")
    for key, label, pct, lower in [
        ("cvar_delta", "CVaR", True, False),
        ("mdd_delta", "MDD", True, False),
        ("stress_delta", "stress", True, False),
        ("sharpe_delta", "Sharpe", False, False),
    ]:
        text = _metric_delta_text(row, key, label, pct=pct, good_when_lower=lower)
        if text:
            pieces.append(text)
    return "; ".join(pieces) if pieces else "before/after 성과 지표를 계산할 수 없어 취약성 변화만 참고해야 합니다."


def _status_reason_ko(row):
    status = row.get("action_status")
    linked = row.get("linked_recommendation_status") or "UNKNOWN"
    constraints = row.get("constraint_reasons") or ""
    metric_reason = row.get("metric_coverage_reason") or ""
    if status == ACTION_STATUS_FORMAL:
        return "기존 formal recommendation gate를 통과했고, bounded action 제약과 취약성 개선 조건을 만족했습니다."
    if status == ACTION_STATUS_REVIEW:
        return (
            f"취약성 완화 효과는 있으나 linked recommendation status가 {linked}라서 "
            "정식 실행 추천이 아니라 실행 전 검토 후보로 유지합니다."
        )
    if status == ACTION_STATUS_RESEARCH:
        return "인버스·레버리지·옵션·변동성 상품 등 연구용 후보 특성이 있어 실행 추천과 분리했습니다."
    if status == ACTION_STATUS_FAIL:
        reason = constraints or metric_reason or "취약성 개선, 성과 지표, 제약 조건 중 하나 이상을 만족하지 못했습니다."
        return f"기준 미통과: {reason}"
    if status == ACTION_STATUS_NO_ACTION:
        return "이 sleeve에서 20% turnover 이내의 유효한 bounded action을 만들지 못했습니다."
    return "액션 상태를 판정할 근거가 충분하지 않습니다."


def _rejected_reason_ko(row):
    status = row.get("action_status")
    if status == ACTION_STATUS_FORMAL:
        return ""
    if status == ACTION_STATUS_REVIEW:
        linked = row.get("linked_recommendation_status") or "UNKNOWN"
        return (
            f"FORMAL_ACTION 제외 사유: 기존 추천 gate 상태가 {linked}입니다. "
            "stress/backtest, CVaR·MDD 안정성, 거래 제약 검증이 추가로 충족되어야 정식 추천으로 올릴 수 있습니다."
        )
    if status == ACTION_STATUS_FAIL:
        return row.get("constraint_reasons") or row.get("status_reason_ko") or "핵심 리스크 또는 제약 조건이 악화되어 제외했습니다."
    if status == ACTION_STATUS_RESEARCH:
        return "실행 추천 대상이 아닌 리서치 전용 상품군입니다."
    if status == ACTION_STATUS_NO_ACTION:
        return "유효한 후보 조합이 없어 선택 가능한 액션이 없습니다."
    return ""


def finalize_action_row_contract(row):
    """Add stable aliases used by API/frontend without removing legacy columns."""
    before = _parse_weights_json(row.get("before_weights_json"))
    after = _parse_weights_json(row.get("after_weights_json"))
    source = row.get("source_asset") or _first_pipe_value(row.get("source_tickers"))
    hedge = row.get("hedge_asset") or _first_pipe_value(row.get("candidate_tickers"))
    source_before = before.get(source, 0.0) if source else 0.0
    source_after = after.get(source, source_before) if source else 0.0
    hedge_before = before.get(hedge, 0.0) if hedge else 0.0
    hedge_after = after.get(hedge, hedge_before) if hedge else 0.0

    row["scenario"] = row.get("risk_sleeve", "")
    row["risk_scenario_codes"] = _risk_scenario_codes_for_action(row)
    row["source_asset"] = source
    row["hedge_asset"] = hedge
    row["scenario_weight"] = row.get("scenario_weight", "")
    row["contribution_pct"] = row.get("source_contribution_pct", 0.0)
    row["contribution_pct_of_sleeve"] = row.get("source_contribution_pct", 0.0)
    row["current_weight"] = round(source_before, 6)
    row["proposed_weight"] = round(source_after, 6)
    row["source_current_weight_pct"] = round(source_before, 6)
    row["source_proposed_weight_pct"] = round(source_after, 6)
    row["hedge_current_weight_pct"] = round(hedge_before, 6)
    row["hedge_proposed_weight_pct"] = round(hedge_after, 6)
    row["status_reason_ko"] = _status_reason_ko(row)
    row["expected_effect"] = _expected_effect_ko(row)
    row["rejected_reason_ko"] = _rejected_reason_ko(row)
    row["can_execute_action"] = row.get("action_status") == ACTION_STATUS_FORMAL
    row.setdefault("selected_in_action_plan", False)
    row.setdefault("selection_reason_ko", "")
    row.setdefault("not_selected_reason_ko", "")
    return row


def build_hedge_action_candidates(
    portfolio_weights,
    attribution_summary,
    asset_scenario_sensitivity_rows,
    recommendation_rows=None,
    scenario_rows=None,
    expert_mode=False,
    max_actions_per_sleeve=12,
    max_turnover_pct=20.0,
    min_existing_kept_pct=80.0,
    concentration_cap_pct=50.0,
    max_candidate_weight_pct=20.0,
):
    """Build bounded add/trim/replace actions from vulnerability attribution."""
    before = _normalise_weights_pct(portfolio_weights)
    sensitivity_index = _sensitivity_index(asset_scenario_sensitivity_rows, scenario_rows)
    max_single_trim_pct = 10.0 if expert_mode else 5.0
    actions = []
    action_seq = 1

    candidate_rows = sorted(
        list(recommendation_rows or []),
        key=lambda row: (
            {"PASS_RECOMMEND": 0, "REFERENCE_ONLY": 1, "INSUFFICIENT_DATA": 2, "FAIL_GATE": 3}.get(row.get("recommendation_status"), 9),
            -(_to_float(row.get("final_score"), 0.0) or 0.0),
        ),
    )

    for sleeve in attribution_summary.get("risk_sleeves", []):
        sleeve_code = sleeve["risk_sleeve"]
        before_vuln = _portfolio_sleeve_vulnerability(before, sensitivity_index, sleeve_code)
        if before_vuln <= 0:
            continue
        source_tickers = [item["ticker"] for item in sleeve.get("source_holdings", [])]
        offset_tickers = [item["ticker"] for item in sleeve.get("offset_holdings", [])]
        trim_sources = [ticker for ticker in source_tickers if ticker not in set(offset_tickers)]
        sleeve_actions = []

        for rec_row in candidate_rows:
            candidate_tickers = _parse_candidate_tickers(rec_row)
            if not candidate_tickers:
                continue
            if not (_candidate_offsets_sleeve(candidate_tickers, sensitivity_index, sleeve_code) or _candidate_mentions_sleeve(rec_row, sleeve_code)):
                continue
            snapshot = _parse_weights_snapshot(rec_row)
            after_add = snapshot or _scale_existing_and_add(before, candidate_tickers, _to_float(rec_row.get("hedge_budget_pct"), 10.0) or 10.0)
            sleeve_actions.append(
                _make_action(
                    action_seq,
                    ACTION_TYPE_ADD,
                    sleeve,
                    source_tickers,
                    offset_tickers,
                    candidate_tickers,
                    rec_row,
                    before,
                    after_add,
                    before_vuln,
                    sensitivity_index,
                    max_single_trim_pct,
                    max_turnover_pct,
                    min_existing_kept_pct,
                    concentration_cap_pct,
                    max_candidate_weight_pct,
                )
            )
            action_seq += 1

            if trim_sources:
                after_trim = _trim_and_add(before, trim_sources[:1], candidate_tickers, max_single_trim_pct)
                sleeve_actions.append(
                    _make_action(
                        action_seq,
                        ACTION_TYPE_TRIM,
                        sleeve,
                        trim_sources[:1],
                        offset_tickers,
                        candidate_tickers,
                        rec_row,
                        before,
                        after_trim,
                        before_vuln,
                        sensitivity_index,
                        max_single_trim_pct,
                        max_turnover_pct,
                        min_existing_kept_pct,
                        concentration_cap_pct,
                        max_candidate_weight_pct,
                    )
                )
                action_seq += 1

        for proxy in RISK_SLEEVE_DEFINITIONS.get(sleeve_code, {}).get("defensive_candidates", []):
            if not trim_sources or proxy in before:
                continue
            if sensitivity_index.get(proxy, {}).get(sleeve_code, 0.0) > 0:
                continue
            proxy_row = {"candidate_ticker": proxy, "candidate_label": proxy, "recommendation_status": "REFERENCE_ONLY", "final_score": 0.0}
            after_replace = _trim_and_add(before, trim_sources[:2], [proxy], min(max_single_trim_pct * 2, max_turnover_pct / 2.0))
            sleeve_actions.append(
                _make_action(
                    action_seq,
                    ACTION_TYPE_REPLACE,
                    sleeve,
                    trim_sources[:2],
                    offset_tickers,
                    [proxy],
                    proxy_row,
                    before,
                    after_replace,
                    before_vuln,
                    sensitivity_index,
                    max_single_trim_pct,
                    max_turnover_pct,
                    min_existing_kept_pct,
                    concentration_cap_pct,
                    max_candidate_weight_pct,
                )
            )
            action_seq += 1
            break

        if not sleeve_actions:
            actions.append(_no_action_row(action_seq, sleeve, source_tickers, offset_tickers, before, before_vuln))
            action_seq += 1
            continue

        sleeve_actions = _dedupe_actions(sleeve_actions)
        sleeve_actions.sort(
            key=lambda row: (
                {"FORMAL_ACTION": 0, "REVIEW_ACTION": 1, "RESEARCH_ONLY": 2, "FAIL_ACTION": 3, "NO_ACTION": 4}.get(row["action_status"], 9),
                float(row["vulnerability_delta"]),
                float(row["turnover_pct"]),
            )
        )
        actions.extend(sleeve_actions[:max_actions_per_sleeve])

    return actions


def _dedupe_actions(rows):
    deduped = {}
    status_rank = {"FORMAL_ACTION": 0, "REVIEW_ACTION": 1, "RESEARCH_ONLY": 2, "FAIL_ACTION": 3, "NO_ACTION": 4}
    for row in rows:
        key = (
            row.get("action_type"),
            row.get("risk_sleeve"),
            row.get("source_tickers"),
            row.get("candidate_tickers"),
            row.get("after_weights_json"),
        )
        current = deduped.get(key)
        if current is None:
            deduped[key] = row
            continue
        challenger_score = (
            status_rank.get(row.get("action_status"), 9),
            float(row.get("vulnerability_delta") or 0.0),
            -float(row.get("before_sleeve_vulnerability") or 0.0),
        )
        current_score = (
            status_rank.get(current.get("action_status"), 9),
            float(current.get("vulnerability_delta") or 0.0),
            -float(current.get("before_sleeve_vulnerability") or 0.0),
        )
        if challenger_score < current_score:
            deduped[key] = row
    return list(deduped.values())


def _make_action(
    action_seq,
    action_type,
    sleeve,
    source_tickers,
    offset_tickers,
    candidate_tickers,
    rec_row,
    before,
    after,
    before_vuln,
    sensitivity_index,
    max_single_trim_pct,
    max_turnover_pct,
    min_existing_kept_pct,
    concentration_cap_pct,
    max_candidate_weight_pct,
):
    after_vuln = _portfolio_sleeve_vulnerability(after, sensitivity_index, sleeve["risk_sleeve"])
    delta = after_vuln - before_vuln
    improve_pct = ((before_vuln - after_vuln) / before_vuln * 100.0) if before_vuln > 0 else None
    source_contribution_pct = _source_contribution_pct_for_action(sleeve, source_tickers)
    constraint_status, reasons, turnover, kept = _constraint_check(
        before,
        after,
        max_turnover_pct,
        min_existing_kept_pct,
        concentration_cap_pct,
        max_candidate_weight_pct,
        candidate_tickers,
    )
    research_only = _is_research_only_candidate(rec_row, candidate_tickers)
    linked_status = rec_row.get("recommendation_status") or "UNKNOWN"
    status = _action_status(action_type, linked_status, delta, constraint_status, research_only)
    label = _candidate_label(rec_row, candidate_tickers)
    reason = _action_reason_ko(status, action_type, sleeve, source_tickers, candidate_tickers, linked_status, delta, reasons)
    row = {
        "action_id": f"action_{action_seq:03d}",
        "action_status": status,
        "action_type": action_type,
        "risk_sleeve": sleeve["risk_sleeve"],
        "risk_sleeve_label_ko": sleeve.get("risk_sleeve_label_ko", sleeve["risk_sleeve"]),
        "source_tickers": "|".join(source_tickers),
        "offset_tickers": "|".join(offset_tickers),
        "candidate_tickers": "|".join(candidate_tickers),
        "candidate_label": label,
        "linked_recommendation_status": linked_status,
        "formal_gate_source": "portfolio_recommendation_rows" if linked_status == "PASS_RECOMMEND" else "",
        "before_sleeve_vulnerability": round(before_vuln, 8),
        "after_sleeve_vulnerability": round(after_vuln, 8),
        "vulnerability_delta": round(delta, 8),
        "vulnerability_improve_pct": round(improve_pct, 4) if improve_pct is not None else None,
        "source_contribution_pct": round(source_contribution_pct, 4),
        "turnover_pct": round(turnover, 6),
        "existing_portfolio_kept_pct": round(kept, 6),
        "max_single_trim_pct": max_single_trim_pct,
        "constraint_status": constraint_status,
        "constraint_reasons": "; ".join(reasons),
        "action_reason_ko": reason,
        "plain_korean_reason": _plain_korean_reason(status, action_type, sleeve, source_tickers, candidate_tickers, delta, improve_pct),
        "before_weights_json": _json_weights(before),
        "after_weights_json": _json_weights(after),
    }
    row.update(metric_fields_from_recommendation(rec_row, action_type=action_type))
    return finalize_action_row_contract(row)


def _source_contribution_pct_for_action(sleeve, source_tickers):
    sources = {ticker for ticker in source_tickers if ticker}
    total = 0.0
    selected = 0.0
    for item in sleeve.get("source_holdings", []):
        contribution = float(item.get("contribution") or 0.0)
        total += max(contribution, 0.0)
        if item.get("ticker") in sources:
            selected += max(contribution, 0.0)
    if total <= 0:
        return 0.0
    return selected / total * 100.0


def _action_reason_ko(status, action_type, sleeve, sources, candidates, linked_status, delta, constraint_reasons):
    sleeve_label = sleeve.get("risk_sleeve_label_ko", sleeve.get("risk_sleeve"))
    if status == ACTION_STATUS_NO_ACTION:
        return f"{sleeve_label} 취약성에 대해 제약조건 안에서 유효한 액션을 찾지 못했습니다."
    if status == ACTION_STATUS_FAIL:
        why = "; ".join(constraint_reasons) if constraint_reasons else "취약성 개선이 확인되지 않았습니다."
        return f"{sleeve_label} 액션은 {why} 때문에 기준 미통과입니다."
    if status == ACTION_STATUS_RESEARCH:
        return f"{' + '.join(candidates)}는 {sleeve_label} 관련 리서치 전용 후보라 실행 추천이 아닙니다."
    verb = {
        ACTION_TYPE_ADD: "추가 헷지",
        ACTION_TYPE_TRIM: "원인 보유자산 일부 축소 후 헷지",
        ACTION_TYPE_REPLACE: "위험 sleeve 일부 교체",
    }.get(action_type, action_type)
    gate = "기존 formal gate 통과 후보" if linked_status == "PASS_RECOMMEND" else "정식 추천 기준은 미달해 검토 후보"
    return (
        f"{sleeve_label} 취약성을 만든 {', '.join(sources[:3]) or '보유자산'}에 대해 "
        f"{', '.join(candidates)}로 {verb}를 적용하면 sleeve 취약도 변화가 {delta:.4f}입니다. {gate}입니다."
    )


def _plain_korean_reason(status, action_type, sleeve, sources, candidates, delta, improve_pct):
    sleeve_label = sleeve.get("risk_sleeve_label_ko", sleeve.get("risk_sleeve"))
    source_text = ", ".join(sources[:3]) if sources else "특정 보유자산"
    candidate_text = ", ".join(candidates) if candidates else "대응 후보"
    if status == ACTION_STATUS_NO_ACTION:
        return f"{sleeve_label} 위험을 줄일 수 있는 20% 이내 조정안을 찾지 못했습니다."
    if status == ACTION_STATUS_FAIL:
        return f"{candidate_text} 조정은 {sleeve_label} 위험이나 핵심 제약을 충분히 개선하지 못했습니다."
    if status == ACTION_STATUS_RESEARCH:
        return f"{candidate_text}는 {sleeve_label} 위험과 관련은 있지만 실행 추천이 아니라 연구용 후보입니다."
    action_text = {
        ACTION_TYPE_ADD: "새로 더하는 방식",
        ACTION_TYPE_TRIM: "일부 줄이고 헷지를 더하는 방식",
        ACTION_TYPE_REPLACE: "위험 일부를 방어 후보로 바꾸는 방식",
    }.get(action_type, "조정")
    improve_text = f"{improve_pct:.1f}%" if improve_pct is not None else "일부"
    return f"{source_text} 때문에 커진 {sleeve_label} 위험을 {candidate_text}로 {action_text}으로 약 {improve_text} 낮추는 검토안입니다."


def _no_action_row(action_seq, sleeve, source_tickers, offset_tickers, before, before_vuln):
    row = {
        "action_id": f"action_{action_seq:03d}",
        "action_status": ACTION_STATUS_NO_ACTION,
        "action_type": "NO_ACTION",
        "risk_sleeve": sleeve["risk_sleeve"],
        "risk_sleeve_label_ko": sleeve.get("risk_sleeve_label_ko", sleeve["risk_sleeve"]),
        "source_tickers": "|".join(source_tickers),
        "offset_tickers": "|".join(offset_tickers),
        "candidate_tickers": "",
        "candidate_label": "",
        "linked_recommendation_status": "",
        "formal_gate_source": "",
        "before_sleeve_vulnerability": round(before_vuln, 8),
        "after_sleeve_vulnerability": round(before_vuln, 8),
        "vulnerability_delta": 0.0,
        "vulnerability_improve_pct": 0.0,
        "source_contribution_pct": 0.0,
        "turnover_pct": 0.0,
        "existing_portfolio_kept_pct": 100.0,
        "max_single_trim_pct": 0.0,
        "constraint_status": "PASS",
        "constraint_reasons": "",
        "action_reason_ko": f"{sleeve.get('risk_sleeve_label_ko', sleeve['risk_sleeve'])}에 대해 유효한 bounded action이 없습니다.",
        "plain_korean_reason": f"{sleeve.get('risk_sleeve_label_ko', sleeve['risk_sleeve'])} 위험을 줄일 수 있는 20% 이내 조정안을 찾지 못했습니다.",
        "before_weights_json": _json_weights(before),
        "after_weights_json": _json_weights(before),
    }
    row.update(empty_metric_fields("NO_ACTION has no after portfolio change to evaluate"))
    return finalize_action_row_contract(row)


ACTION_STATUS_RANK = {
    ACTION_STATUS_FORMAL: 0,
    ACTION_STATUS_REVIEW: 1,
    ACTION_STATUS_RESEARCH: 2,
    ACTION_STATUS_FAIL: 3,
    ACTION_STATUS_NO_ACTION: 4,
}
SELECTABLE_ACTION_STATUSES = {ACTION_STATUS_FORMAL, ACTION_STATUS_REVIEW}


def _action_selection_key(row):
    return (
        ACTION_STATUS_RANK.get(row.get("action_status"), 9),
        float(row.get("vulnerability_delta") or 0.0),
        float(row.get("turnover_pct") or 0.0),
        -float(row.get("source_contribution_pct") or 0.0),
        str(row.get("action_id") or ""),
    )


def _top_positive_sleeves(attribution_summary, limit):
    sleeves = []
    for sleeve in attribution_summary.get("risk_sleeves", []) or []:
        if float(sleeve.get("net_vulnerability") or 0.0) <= 0:
            continue
        sleeves.append(sleeve)
        if len(sleeves) >= limit:
            break
    return sleeves


def _source_concentration_pct(sleeve):
    sources = sleeve.get("source_holdings") or []
    gross = _to_float(sleeve.get("gross_source"), 0.0) or 0.0
    if gross <= 0 or not sources:
        return 0.0
    top = max((_to_float(item.get("contribution"), 0.0) or 0.0) for item in sources)
    return max(0.0, top / gross * 100.0)


def _action_improvement(row):
    delta = _to_float(row.get("vulnerability_delta"), 0.0) or 0.0
    return max(0.0, -delta)


def _best_by_type(rows, action_type):
    typed = [row for row in rows if row.get("action_type") == action_type]
    return sorted(typed, key=_action_selection_key)[0] if typed else None


def _choose_sleeve_action(rows, sleeve):
    rows = sorted(rows, key=_action_selection_key)
    formal = [row for row in rows if row.get("action_status") == ACTION_STATUS_FORMAL]
    if formal:
        return formal[0], "기존 formal gate를 통과한 액션이 있어 같은 sleeve 후보 중 우선 선택했습니다."

    concentration = _source_concentration_pct(sleeve)
    add = _best_by_type(rows, ACTION_TYPE_ADD)
    trim = _best_by_type(rows, ACTION_TYPE_TRIM)
    replace = _best_by_type(rows, ACTION_TYPE_REPLACE)
    best = rows[0] if rows else None

    if replace and concentration >= 60.0:
        trim_improve = _action_improvement(trim) if trim else 0.0
        if not trim or _action_improvement(replace) >= trim_improve * 0.95:
            return replace, "취약성 기여가 특정 sleeve에 강하게 집중되어 REPLACE_SLEEVE가 trim 대비 유사하거나 더 큰 개선을 보여 선택했습니다."

    if add and concentration < 35.0:
        trim_improve = _action_improvement(trim) if trim else 0.0
        if not trim or _action_improvement(add) >= trim_improve * 0.55:
            return add, "취약성이 여러 보유자산에 퍼져 있어 단순 비중 축소보다 ADD_HEDGE가 포트폴리오 유지 원칙에 더 적합해 선택했습니다."

    if trim:
        return trim, "취약성 기여가 큰 보유자산이 확인되어 단순 추가 헷지보다 TRIM_AND_HEDGE가 우선입니다."
    if add:
        return add, "trim 가능한 source holding이 제한적이어서 ADD_HEDGE를 선택했습니다."
    if replace:
        return replace, "ADD/TRIM 후보가 제한되어 REPLACE_SLEEVE를 선택했습니다."
    return best, "동일 sleeve에서 취약성 개선폭과 제약 조건을 기준으로 가장 나은 후보를 선택했습니다."


def _select_diverse_actions(action_rows, attribution_summary, max_selected=10):
    eligible = [row for row in action_rows or [] if row.get("action_status") in SELECTABLE_ACTION_STATUSES]
    by_sleeve = defaultdict(list)
    for row in eligible:
        by_sleeve[row.get("risk_sleeve")].append(row)
    for rows in by_sleeve.values():
        rows.sort(key=_action_selection_key)

    selected = []
    selected_ids = set()
    for sleeve in _top_positive_sleeves(attribution_summary, max_selected):
        rows = by_sleeve.get(sleeve.get("risk_sleeve")) or []
        if not rows:
            continue
        row, reason_ko = _choose_sleeve_action(rows, sleeve)
        if not row:
            continue
        row["selection_reason_ko"] = reason_ko
        selected.append(row)
        selected_ids.add(row.get("action_id"))
        if len(selected) >= max_selected:
            return selected

    for row in sorted(eligible, key=_action_selection_key):
        if row.get("action_id") in selected_ids:
            continue
        row["selection_reason_ko"] = row.get("selection_reason_ko") or "상위 sleeve 커버리지 이후 남은 후보 중 상태, 개선폭, turnover 기준으로 선택했습니다."
        selected.append(row)
        selected_ids.add(row.get("action_id"))
        if len(selected) >= max_selected:
            break
    return selected


def _mark_action_selection(action_rows, selected):
    selected_ids = {row.get("action_id") for row in selected or []}
    selected_by_sleeve = defaultdict(list)
    for row in selected or []:
        selected_by_sleeve[row.get("risk_sleeve")].append(row)
    for row in action_rows or []:
        is_selected = row.get("action_id") in selected_ids
        row["selected_in_action_plan"] = is_selected
        if is_selected:
            row["selection_reason_ko"] = row.get("selection_reason_ko") or "selected action plan에 포함된 액션입니다."
            row["not_selected_reason_ko"] = ""
        elif row.get("action_status") not in SELECTABLE_ACTION_STATUSES:
            row["not_selected_reason_ko"] = row.get("status_reason_ko") or "FORMAL_ACTION/REVIEW_ACTION 기준을 충족하지 못해 선택하지 않았습니다."
        elif selected_by_sleeve.get(row.get("risk_sleeve")):
            row["not_selected_reason_ko"] = "같은 risk sleeve에서 더 적합한 액션이 선택되어 후보 감사 목록에만 남겼습니다."
        else:
            row["not_selected_reason_ko"] = "selected action plan의 최대 개수와 상위 취약성 우선순위 때문에 선택하지 않았습니다."
        finalize_action_row_contract(row)


def _counts_by_field(rows, field):
    counts = defaultdict(int)
    for row in rows or []:
        counts[row.get(field) or "UNKNOWN"] += 1
    return dict(sorted(counts.items()))


def _sleeve_selection_coverage(attribution_summary, action_rows, selected, limit=7):
    selected_by_sleeve = defaultdict(list)
    eligible_by_sleeve = defaultdict(list)
    all_by_sleeve = defaultdict(list)
    for row in action_rows or []:
        sleeve = row.get("risk_sleeve")
        all_by_sleeve[sleeve].append(row)
        if row.get("action_status") in SELECTABLE_ACTION_STATUSES:
            eligible_by_sleeve[sleeve].append(row)
    for row in selected or []:
        selected_by_sleeve[row.get("risk_sleeve")].append(row)

    coverage = []
    for rank, sleeve in enumerate(_top_positive_sleeves(attribution_summary, limit), start=1):
        sleeve_code = sleeve.get("risk_sleeve")
        selected_rows = selected_by_sleeve.get(sleeve_code, [])
        eligible_rows = eligible_by_sleeve.get(sleeve_code, [])
        all_rows = all_by_sleeve.get(sleeve_code, [])
        if selected_rows:
            status = "SELECTED"
            reason_ko = "상위 취약성이라 selected action plan에 최소 1개 액션을 포함했습니다."
        elif eligible_rows:
            status = "ELIGIBLE_NOT_SELECTED"
            reason_ko = "실행 가능한 검토 액션은 있었지만 selected action plan의 최대 개수 제한 때문에 제외됐습니다."
        elif all_rows:
            status = "NO_SELECTABLE_ACTION"
            reason_ko = "후보는 있었지만 FORMAL_ACTION 또는 REVIEW_ACTION 기준을 만족한 액션이 없습니다."
        else:
            status = "NO_ACTION_CANDIDATE"
            reason_ko = "이 취약성에 대해 20% 이내 bounded action 후보를 만들지 못했습니다."
        coverage.append(
            {
                "rank": rank,
                "risk_sleeve": sleeve_code,
                "risk_sleeve_label_ko": sleeve.get("risk_sleeve_label_ko", sleeve_code),
                "net_vulnerability": sleeve.get("net_vulnerability"),
                "selected_action_count": len(selected_rows),
                "selectable_action_count": len(eligible_rows),
                "candidate_action_count": len(all_rows),
                "selected_action_ids": [row.get("action_id") for row in selected_rows],
                "coverage_status": status,
                "reason_ko": reason_ko,
            }
        )
    return coverage


def build_hedge_action_plan(run_id, portfolio_weights, attribution_summary, action_rows):
    for row in action_rows:
        finalize_action_row_contract(row)
    status_counts = defaultdict(int)
    type_counts = defaultdict(int)
    for row in action_rows:
        status_counts[row["action_status"]] += 1
        type_counts[row["action_type"]] += 1
    selected = _select_diverse_actions(action_rows, attribution_summary, max_selected=10)
    _mark_action_selection(action_rows, selected)
    selected_type_counts = defaultdict(int)
    for row in selected:
        selected_type_counts[row["action_type"]] += 1
    action_type_coverage = _action_type_coverage(type_counts, selected_type_counts, action_rows)
    return {
        "run_id": run_id,
        "engine_version": "hedge_action_engine_v1",
        "portfolio_weights": _normalise_weights_pct(portfolio_weights),
        "status_counts": dict(sorted(status_counts.items())),
        "action_type_counts": dict(sorted(type_counts.items())),
        "selected_action_type_counts": dict(sorted(selected_type_counts.items())),
        "selected_risk_sleeve_counts": _counts_by_field(selected, "risk_sleeve"),
        "action_type_coverage": action_type_coverage,
        "replace_sleeve_decision": _replace_sleeve_decision(action_type_coverage),
        "sleeve_selection_coverage": _sleeve_selection_coverage(attribution_summary, action_rows, selected),
        "top_vulnerabilities": attribution_summary.get("risk_sleeves", [])[:7],
        "selected_actions": selected,
        "selection_policy": {
            "scope": "SELECTED_ACTIONS_ONLY",
            "max_selected_actions": 10,
            "diversity_rule": "select_best_action_per_positive_top_vulnerability_before_global_fill",
            "count_basis": "selected_actions",
            "add_hedge_rule": "선두 source 기여도가 낮고 ADD_HEDGE 개선폭이 trim 후보의 55% 이상이면 포트폴리오 유지 원칙 때문에 ADD_HEDGE를 우선할 수 있습니다.",
            "trim_and_hedge_rule": "선두 source holding이 취약성을 크게 만들면 원인 비중을 줄이고 hedge를 더하는 TRIM_AND_HEDGE를 우선합니다.",
            "replace_sleeve_rule": "source 기여도가 매우 집중되고 REPLACE_SLEEVE 개선폭이 trim 대비 유사하거나 더 클 때만 선택합니다.",
            "no_action_rule": "20% turnover, 80% 기존 포트폴리오 유지, 집중도 제한 안에서 유효한 조합이 없을 때만 NO_ACTION으로 남깁니다.",
        },
        "policy": {
            "formal_gate_not_weakened": True,
            "max_turnover_pct": 20.0,
            "default_trim_pct": 5.0,
            "min_existing_portfolio_kept_pct": 80.0,
        },
    }


def _action_type_coverage(type_counts, selected_type_counts=None, action_rows=None):
    selected_type_counts = selected_type_counts or {}
    expected = [ACTION_TYPE_ADD, ACTION_TYPE_TRIM, ACTION_TYPE_REPLACE, "NO_ACTION"]
    reason_ko = {
        ACTION_TYPE_ADD: "기존 보유자산을 유지하면서 헷지를 더하는 후보입니다.",
        ACTION_TYPE_TRIM: "취약성 원인 보유자산을 일부 줄이고 헷지를 더하는 후보입니다.",
        ACTION_TYPE_REPLACE: "위험 sleeve 일부를 방어 proxy로 바꾸는 후보입니다.",
        "NO_ACTION": "유효한 bounded action이 없는 sleeve에만 생성됩니다.",
    }
    absent_ko = {
        ACTION_TYPE_ADD: "matching recommendation row가 없거나 제약조건 안에서 위험 개선이 확인되지 않아 생성되지 않았습니다.",
        ACTION_TYPE_TRIM: "trim 가능한 source holding이 없거나 offset holding만 있어 자동 trim을 막았습니다.",
        ACTION_TYPE_REPLACE: "대체 proxy가 이미 보유 중이거나 해당 sleeve를 방어하지 않아 생성되지 않았습니다.",
        "NO_ACTION": "모든 취약 sleeve에서 최소 하나 이상의 bounded action 후보가 생성되어 NO_ACTION row가 필요하지 않았습니다.",
    }
    coverage = {}
    for action_type in expected:
        count = int(type_counts.get(action_type, 0))
        selected_count = int(selected_type_counts.get(action_type, 0))
        if selected_count > 0:
            selected_absence_code = ""
            selected_absence_ko = ""
        elif count > 0:
            selected_absence_code = "NOT_SELECTED_BY_DIVERSITY_OR_SCORE"
            selected_absence_ko = "후보는 있었지만 selected action plan은 top vulnerability 다양성과 개선도 순서를 우선해 다른 액션을 선택했습니다."
        elif action_type == ACTION_TYPE_REPLACE:
            selected_absence_code = "NO_VALID_REPLACE_SLEEVE_CANDIDATE"
            selected_absence_ko = "REPLACE_SLEEVE 후보가 없습니다. 대체 proxy가 이미 보유 중이거나, 해당 sleeve를 방어하지 못했거나, bounded turnover/집중도 제약 안에서 취약성을 줄이지 못했습니다."
        else:
            selected_absence_code = "NO_VALID_ACTION_TYPE_CANDIDATE"
            selected_absence_ko = absent_ko[action_type]
        coverage[action_type] = {
            "count": count,
            "candidate_count": count,
            "selected_count": selected_count,
            "present": count > 0,
            "present_in_candidates": count > 0,
            "present_in_selected": selected_count > 0,
            "reason_ko": reason_ko[action_type] if count > 0 else absent_ko[action_type],
            "absence_reason_code": selected_absence_code,
            "absence_reason_ko": selected_absence_ko,
        }
    return coverage


def _replace_sleeve_decision(action_type_coverage):
    coverage = (action_type_coverage or {}).get(ACTION_TYPE_REPLACE, {})
    selected_count = int(coverage.get("selected_count") or 0)
    return {
        "action_type": ACTION_TYPE_REPLACE,
        "candidate_count": int(coverage.get("candidate_count") or coverage.get("count") or 0),
        "selected_count": selected_count,
        "present_in_candidates": bool(coverage.get("present_in_candidates")),
        "present_in_selected": selected_count > 0,
        "absence_reason_code": "" if selected_count > 0 else coverage.get("absence_reason_code", ""),
        "absence_reason_ko": "" if selected_count > 0 else coverage.get("absence_reason_ko", ""),
    }


def write_action_artifacts(
    run_id,
    processed_dir,
    report_dir,
    attribution_rows,
    attribution_summary,
    action_rows,
    action_plan,
):
    processed_dir = Path(processed_dir)
    report_dir = Path(report_dir)
    processed_dir.mkdir(parents=True, exist_ok=True)
    report_dir.mkdir(parents=True, exist_ok=True)

    attribution_csv = processed_dir / f"portfolio_vulnerability_attribution_{run_id}.csv"
    summary_json = report_dir / f"portfolio_vulnerability_summary_{run_id}.json"
    candidates_csv = report_dir / f"hedge_action_candidates_{run_id}.csv"
    plan_json = report_dir / f"hedge_action_plan_{run_id}.json"
    summary_md = report_dir / f"hedge_action_plan_summary_{run_id}.md"

    _write_csv(attribution_csv, ATTRIBUTION_FIELDS, attribution_rows)
    summary_json.write_text(json.dumps(attribution_summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _write_csv(candidates_csv, ACTION_FIELDS, action_rows)
    plan_json.write_text(json.dumps(action_plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    summary_md.write_text(_render_plan_summary_md(action_plan), encoding="utf-8")
    return {
        "portfolio_vulnerability_attribution": attribution_csv,
        "portfolio_vulnerability_summary": summary_json,
        "hedge_action_candidates": candidates_csv,
        "hedge_action_plan": plan_json,
        "hedge_action_plan_summary": summary_md,
    }


def _write_csv(path, fieldnames, rows):
    with Path(path).open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _render_plan_summary_md(plan):
    lines = [
        "# Hedge Action Plan",
        "",
        f"- run_id: {plan.get('run_id')}",
        f"- engine_version: {plan.get('engine_version')}",
        "- formal gate: 기존 PASS_RECOMMEND 기준을 완화하지 않음",
        "",
        "## Portfolio",
    ]
    for ticker, weight in (plan.get("portfolio_weights") or {}).items():
        lines.append(f"- {ticker}: {weight}%")
    lines.extend([
        "",
        "## Status Counts",
    ])
    for status, count in plan.get("status_counts", {}).items():
        lines.append(f"- {status}: {count}")
    lines.extend(["", "## Top Vulnerabilities"])
    for sleeve in plan.get("top_vulnerabilities", [])[:7]:
        sources = ", ".join(item["ticker"] for item in sleeve.get("source_holdings", [])[:3]) or "-"
        offsets = ", ".join(item["ticker"] for item in sleeve.get("offset_holdings", [])[:3]) or "-"
        lines.append(
            f"- {sleeve.get('risk_sleeve_label_ko')} ({sleeve.get('risk_sleeve')}): "
            f"net={sleeve.get('net_vulnerability')}, sources={sources}, offsets={offsets}"
        )
    lines.extend(["", "## Selected Actions"])
    selected = plan.get("selected_actions", [])
    if not selected:
        lines.append("- 선택된 FORMAL_ACTION/REVIEW_ACTION이 없습니다.")
    for action in selected:
        lines.append(
            f"- {action['action_status']} · {action['action_type']} · {action['risk_sleeve']}: "
            f"{action['candidate_label']} / delta={action['vulnerability_delta']} / turnover={action['turnover_pct']}% / "
            f"reason={action.get('selection_reason_ko') or action.get('plain_korean_reason')}"
        )
        lines.append(f"  - expected_effect: {action.get('expected_effect')}")
        if action.get("rejected_reason_ko"):
            lines.append(f"  - formal_action_gap: {action.get('rejected_reason_ko')}")
    lines.extend(["", "## Action Type Coverage"])
    for action_type, coverage in plan.get("action_type_coverage", {}).items():
        state = "present" if coverage.get("present") else "absent"
        selected_state = "selected" if coverage.get("present_in_selected") else "not selected"
        lines.append(
            f"- {action_type}: {state}, {selected_state}, count={coverage.get('count')}, "
            f"selected={coverage.get('selected_count')} · {coverage.get('reason_ko')}"
        )
        if coverage.get("absence_reason_ko"):
            lines.append(f"  - not_selected_reason: {coverage.get('absence_reason_ko')}")
    lines.extend(
        [
            "",
            "## Next Validation Needed",
            "- REVIEW_ACTION을 FORMAL_ACTION으로 올리려면 기존 formal recommendation gate, stress/backtest 근거, CVaR/MDD 안정성, 거래 제약 검증이 모두 충족되어야 합니다.",
            "- FORMAL_ACTION이 없을 때는 실행 추천이 아니라 실행 전 검토용 시뮬레이션으로만 해석해야 합니다.",
        ]
    )
    lines.append("")
    return "\n".join(lines)
