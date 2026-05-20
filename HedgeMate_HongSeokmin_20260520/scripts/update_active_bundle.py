#!/usr/bin/env python3
"""Build the product active bundle manifest for the HedgeMate dashboard."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from datetime import date, datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = ROOT.parent
SCENARIO_ROOT = WORKSPACE_ROOT / "scenario_research"
SCENARIO_OUTPUTS = SCENARIO_ROOT / "outputs"
OUTPUTS = ROOT / "outputs"
INPUTS = ROOT / "inputs"
MANIFEST_PATH = OUTPUTS / "latest_manifest.json"

SUSPICIOUS_RUN_TOKENS = ("deadbeef", "dummy")
DEFAULT_EVENT_OVERLAY_STATUS = {
    "mode": "reviewed_fixture",
    "live_gemini_extraction": "implemented_api_key_required",
    "recommendation_usage": "fixture_context_only",
    "trade_gate_usage": "disabled_for_fixture",
}
PORTFOLIO_FINGERPRINT_DIGITS = 4


def iso_utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def is_suspicious_run_id(run_id: str | None) -> bool:
    lowered = str(run_id or "").lower()
    return any(token in lowered for token in SUSPICIOUS_RUN_TOKENS)


def business_days_after(start: date, end: date) -> int:
    if end <= start:
        return 0
    count = 0
    current = start
    while current < end:
        current = date.fromordinal(current.toordinal() + 1)
        if current.weekday() < 5:
            count += 1
    return count


def resolve_existing(path: str | Path | None) -> Path | None:
    if not path:
        return None
    candidate = Path(path)
    candidates = [candidate] if candidate.is_absolute() else [ROOT / candidate, WORKSPACE_ROOT / candidate, SCENARIO_OUTPUTS / candidate]
    for item in candidates:
        if item.exists():
            return item.resolve()
    return candidates[0].resolve() if candidates else None


def rel_or_abs(path: Path | None) -> str | None:
    if path is None:
        return None
    try:
        return str(path.resolve().relative_to(WORKSPACE_ROOT.resolve())).replace("\\", "/")
    except ValueError:
        return str(path.resolve())


def artifact_exists(path: Path | None) -> bool:
    return bool(path and path.exists())


def parse_float(value) -> float | None:
    try:
        return float(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


def normalized_weight_map(weights: dict[str, float]) -> dict[str, float]:
    values = {str(ticker).strip(): max(0.0, float(weight)) for ticker, weight in weights.items() if str(ticker).strip()}
    total = sum(values.values())
    if total <= 0:
        return {}
    return {ticker: round(weight / total * 100.0, PORTFOLIO_FINGERPRINT_DIGITS) for ticker, weight in sorted(values.items())}


def portfolio_fingerprint(weights: dict[str, float]) -> dict[str, object]:
    normalized = normalized_weight_map(weights)
    canonical = "|".join(f"{ticker}:{weight:.{PORTFOLIO_FINGERPRINT_DIGITS}f}" for ticker, weight in normalized.items())
    return {
        "hash": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
        "ticker_count": len(normalized),
        "total_weight_pct": round(sum(normalized.values()), PORTFOLIO_FINGERPRINT_DIGITS),
        "tickers": list(normalized),
    }


def portfolio_fingerprint_from_input(path: Path | None) -> dict[str, object] | None:
    if not artifact_exists(path):
        return None
    weights: dict[str, float] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            ticker = str(row.get("ticker") or "").strip()
            weight = parse_float(row.get("weight_pct"))
            if ticker and weight is not None:
                weights[ticker] = weights.get(ticker, 0.0) + weight
    if not weights:
        return None
    payload = portfolio_fingerprint(weights)
    payload["path"] = rel_or_abs(path)
    return payload


def parse_json_object(value: str | None) -> dict[str, float]:
    if not value:
        return {}
    try:
        payload = json.loads(value)
    except json.JSONDecodeError:
        return {}
    if not isinstance(payload, dict):
        return {}
    parsed = {}
    for key, raw in payload.items():
        number = parse_float(raw)
        if number is not None:
            parsed[str(key).strip()] = number
    return parsed


def recommendation_base_fingerprint(path: Path | None) -> dict[str, object] | None:
    if not artifact_exists(path):
        return None
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            proposed = parse_json_object(row.get("weights_snapshot"))
            allocation = parse_json_object(row.get("allocation_weights"))
            if not proposed or not allocation:
                continue
            hedge_tickers = set(allocation)
            base = {ticker: weight for ticker, weight in proposed.items() if ticker not in hedge_tickers}
            if not base:
                continue
            payload = portfolio_fingerprint(base)
            payload["source_artifact"] = rel_or_abs(path)
            payload["source_candidate"] = row.get("candidate_ticker") or row.get("candidate_label") or ""
            return payload
    return None


def first_existing_or_last(candidates: list[Path]) -> Path | None:
    if not candidates:
        return None
    for candidate in candidates:
        resolved = resolve_existing(candidate)
        if artifact_exists(resolved):
            return resolved
    return resolve_existing(candidates[-1])


def infer_recommendation_qa_path(args: argparse.Namespace, hedge_run: str) -> Path | None:
    if args.recommendation_status_qa:
        return resolve_existing(args.recommendation_status_qa)
    return first_existing_or_last(
        [
            OUTPUTS / "reports" / f"recommendation_status_qa_post_backtest_{hedge_run}_backtest_gated.md",
            OUTPUTS / "reports" / f"recommendation_status_qa_{hedge_run}_post_backtest.md",
            OUTPUTS / "reports" / f"recommendation_status_qa_{hedge_run}.md",
        ]
    )


def infer_optional_artifact_path(value: str | Path | None, default_path: Path) -> Path | None:
    if value:
        return resolve_existing(value)
    return default_path.resolve() if default_path.exists() else None


def infer_optional_artifact_path_from_candidates(value: str | Path | None, default_paths: list[Path]) -> Path | None:
    if value:
        return resolve_existing(value)
    for default_path in default_paths:
        resolved = resolve_existing(default_path)
        if artifact_exists(resolved):
            return resolved
    return None


def infer_paths(args: argparse.Namespace) -> dict[str, Path | None]:
    scenario_run = args.scenario_run_id
    final_run = args.final_run_id or scenario_run
    hedge_run = args.hedgemate_run_id
    backtest_run = args.backtest_run_id
    return {
        "finalMarketState": resolve_existing(args.final_market_state)
        or (SCENARIO_OUTPUTS / "final" / f"final_market_state_daily_{final_run}.csv").resolve(),
        "scenarioConfidence": resolve_existing(args.scenario_confidence)
        or (SCENARIO_OUTPUTS / "final" / f"scenario_confidence_{final_run}.csv").resolve(),
        "topActiveScenarios": resolve_existing(args.top_active_scenarios)
        or (SCENARIO_OUTPUTS / "final" / f"top_active_scenarios_{final_run}.json").resolve(),
        "scenarioVector": resolve_existing(args.scenario_vector)
        or (SCENARIO_OUTPUTS / "scenario_vectors" / f"current_scenario_vector_{scenario_run}.csv").resolve(),
        "finalScenarioVector": resolve_existing(args.final_scenario_vector)
        or (SCENARIO_OUTPUTS / "scenario_vectors" / f"current_scenario_vector_{final_run}.csv").resolve(),
        "finalMetadata": resolve_existing(args.final_metadata)
        or (SCENARIO_OUTPUTS / "reports" / f"final_market_state_metadata_{final_run}.json").resolve(),
        "eventOverlayMetadata": resolve_existing(args.event_overlay_metadata),
        "features": resolve_existing(args.features)
        or (OUTPUTS / "processed" / f"features_summary_{hedge_run}.csv").resolve(),
        "portfolioInput": resolve_existing(getattr(args, "portfolio_input", None))
        or ((INPUTS / "portfolio_weights.csv").resolve() if (INPUTS / "portfolio_weights.csv").exists() else None),
        "assetScenarioSensitivity": resolve_existing(args.asset_scenario_sensitivity)
        or (OUTPUTS / "processed" / f"asset_scenario_sensitivity_{hedge_run}.csv").resolve(),
        "portfolioVulnerabilityAttribution": infer_optional_artifact_path_from_candidates(
            getattr(args, "portfolio_vulnerability_attribution", None),
            [
                OUTPUTS / "reports" / f"portfolio_vulnerability_attribution_{hedge_run}.csv",
                OUTPUTS / "processed" / f"portfolio_vulnerability_attribution_{hedge_run}.csv",
            ],
        ),
        "portfolioVulnerabilitySummary": infer_optional_artifact_path_from_candidates(
            getattr(args, "portfolio_vulnerability_summary", None),
            [
                OUTPUTS / "reports" / f"portfolio_vulnerability_summary_{hedge_run}.md",
                OUTPUTS / "reports" / f"portfolio_vulnerability_summary_{hedge_run}.json",
            ],
        ),
        "hedgeActionCandidates": infer_optional_artifact_path_from_candidates(
            getattr(args, "hedge_action_candidates", None),
            [
                OUTPUTS / "reports" / f"hedge_action_candidates_{hedge_run}.csv",
                OUTPUTS / "reports" / f"hedge_action_candidates_{hedge_run}.json",
            ],
        ),
        "hedgeActionPlan": infer_optional_artifact_path_from_candidates(
            getattr(args, "hedge_action_plan", None),
            [
                OUTPUTS / "reports" / f"hedge_action_plan_{hedge_run}.csv",
                OUTPUTS / "reports" / f"hedge_action_plan_{hedge_run}.json",
            ],
        ),
        "hedgeActionPlanSummary": infer_optional_artifact_path_from_candidates(
            getattr(args, "hedge_action_plan_summary", None),
            [
                OUTPUTS / "reports" / f"hedge_action_plan_summary_{hedge_run}.md",
                OUTPUTS / "reports" / f"hedge_action_plan_summary_{hedge_run}.json",
            ],
        ),
        "portfolio1to1": resolve_existing(args.portfolio_1to1)
        or (OUTPUTS / "reports" / f"portfolio_1to1_hedge_{hedge_run}.csv").resolve(),
        "portfolioMulti": resolve_existing(args.portfolio_multi)
        or (OUTPUTS / "reports" / f"portfolio_multi_hedge_{hedge_run}.csv").resolve(),
        "recommendationStatusQa": infer_recommendation_qa_path(args, hedge_run),
        "backtestCsv": resolve_existing(args.backtest_csv)
        or (OUTPUTS / "validation" / f"walk_forward_backtest_{backtest_run}.csv").resolve(),
        "backtestSummary": resolve_existing(args.backtest_summary)
        or (OUTPUTS / "reports" / f"walk_forward_backtest_summary_{backtest_run}.md").resolve(),
        "backtestGateSummary": resolve_existing(args.backtest_gate_summary),
        "backtestAttributionCsv": infer_optional_artifact_path(
            getattr(args, "backtest_attribution_csv", None),
            OUTPUTS / "reports" / f"backtest_attribution_{backtest_run}.csv",
        ),
        "backtestAttributionSummary": infer_optional_artifact_path(
            getattr(args, "backtest_attribution_summary", None),
            OUTPUTS / "reports" / f"backtest_attribution_{backtest_run}.md",
        ),
        "formalGateAuditCsv": infer_optional_artifact_path(
            getattr(args, "formal_gate_audit_csv", None),
            OUTPUTS / "reports" / f"formal_gate_audit_{hedge_run}_backtest_gated.csv",
        ),
        "formalGateAuditSummary": infer_optional_artifact_path(
            getattr(args, "formal_gate_audit_summary", None),
            OUTPUTS / "reports" / f"formal_gate_audit_{hedge_run}_backtest_gated.md",
        ),
        "rebalanceModeComparisonCsv": infer_optional_artifact_path(
            getattr(args, "rebalance_mode_comparison_csv", None),
            OUTPUTS / "reports" / f"rebalance_mode_comparison_rebalance-compare-{backtest_run}.csv",
        ),
        "rebalanceModeComparisonSummary": infer_optional_artifact_path(
            getattr(args, "rebalance_mode_comparison_summary", None),
            OUTPUTS / "reports" / f"rebalance_mode_comparison_rebalance-compare-{backtest_run}.md",
        ),
        "rebalanceModeComparisonJson": infer_optional_artifact_path(
            getattr(args, "rebalance_mode_comparison_json", None),
            OUTPUTS / "reports" / f"rebalance_mode_comparison_rebalance-compare-{backtest_run}.json",
        ),
        "finalRunbook": resolve_existing(args.final_runbook)
        or (
            (OUTPUTS / "reports" / f"final_product_runbook_{hedge_run}.md").resolve()
            if (OUTPUTS / "reports" / f"final_product_runbook_{hedge_run}.md").exists()
            else None
        ),
    }


def read_json(path: Path | None) -> dict:
    if not artifact_exists(path):
        return {}
    try:
        with path.open("r", encoding="utf-8") as f:
            payload = json.load(f)
        return payload if isinstance(payload, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def event_overlay_status_from_metadata(path: Path | None) -> dict:
    status = dict(DEFAULT_EVENT_OVERLAY_STATUS)
    metadata = read_json(path)
    if not metadata:
        return status
    provider = str(metadata.get("provider") or "").strip().lower()
    status["metadata_provider"] = provider or "unknown"
    status["metadata_live_research_attached"] = bool(metadata.get("live_research_attached"))
    status["metadata_schema_error_count"] = metadata.get("schema_error_count", 0)
    status["metadata_fatal_schema_error_count"] = metadata.get("fatal_schema_error_count", 0)
    if metadata.get("provider_model"):
        status["provider_model"] = metadata.get("provider_model")
    if provider == "fixture":
        return status
    if provider == "gemini":
        live_attached = bool(metadata.get("live_research_attached"))
        fatal_errors = int(metadata.get("fatal_schema_error_count") or 0)
        status.update(
            {
                "mode": "live_gemini_provider" if live_attached else "gemini_provider_pending",
                "live_gemini_extraction": "attached" if live_attached else "implemented_api_key_required",
                "recommendation_usage": "live_context_review_required" if live_attached else "fixture_context_only",
                "trade_gate_usage": "disabled_until_human_review" if fatal_errors == 0 else "disabled_schema_errors",
            }
        )
    return status


def infer_as_of(args: argparse.Namespace, paths: dict[str, Path | None]) -> str | None:
    if args.scenario_vector_as_of_date:
        return args.scenario_vector_as_of_date
    top_payload = read_json(paths.get("topActiveScenarios"))
    if top_payload.get("date"):
        return str(top_payload["date"])
    metadata = read_json(paths.get("finalMetadata"))
    return metadata.get("date") or metadata.get("as_of_date") or metadata.get("final_market_state_as_of_date")


def classify_freshness(
    scenario_run: str,
    hedge_run: str,
    backtest_run: str,
    as_of_date: str | None,
    paths: dict[str, Path | None],
    reference_date: date | None = None,
    max_stale_days: int = 7,
) -> tuple[str, list[str]]:
    reasons: list[str] = []
    required = [
        "finalMarketState",
        "topActiveScenarios",
        "scenarioVector",
        "features",
        "assetScenarioSensitivity",
        "portfolio1to1",
        "portfolioMulti",
        "backtestCsv",
    ]
    missing = [key for key in required if not artifact_exists(paths.get(key))]
    if missing:
        reasons.append("missing artifacts: " + ", ".join(missing))
    suspicious = [name for name, run_id in [("scenario_run", scenario_run), ("hedgemate_run", hedge_run), ("backtest_run", backtest_run)] if is_suspicious_run_id(run_id)]
    if suspicious:
        reasons.append("suspicious run ids: " + ", ".join(suspicious))
    parsed_as_of = parse_date(as_of_date)
    if parsed_as_of is None:
        reasons.append("missing scenario_vector_as_of_date")
    else:
        today = reference_date or date.today()
        age = business_days_after(parsed_as_of, today)
        if age > max_stale_days:
            reasons.append(f"scenario vector stale: {age} business days old")
    if missing:
        return "INCOMPLETE", reasons
    if reasons:
        return "STALE", reasons
    return "FRESH", []


def build_manifest(args: argparse.Namespace, generated_at_utc: str | None = None, reference_date: date | None = None) -> dict:
    scenario_run = args.scenario_run_id
    final_run = args.final_run_id or scenario_run
    hedge_run = args.hedgemate_run_id
    backtest_run = args.backtest_run_id
    paths = infer_paths(args)
    as_of = infer_as_of(args, paths)
    freshness, reasons = classify_freshness(
        scenario_run,
        hedge_run,
        backtest_run,
        as_of,
        paths,
        reference_date=reference_date,
        max_stale_days=args.max_stale_days,
    )
    portfolio_input_fingerprint = portfolio_fingerprint_from_input(paths.get("portfolioInput"))
    recommendation_portfolio_fingerprint = recommendation_base_fingerprint(paths.get("portfolio1to1"))
    portfolio_mismatch = bool(
        portfolio_input_fingerprint
        and recommendation_portfolio_fingerprint
        and portfolio_input_fingerprint.get("hash") != recommendation_portfolio_fingerprint.get("hash")
    )
    if portfolio_mismatch:
        reasons.append("portfolio input mismatch: active recommendation weights do not match the portfolio input")
        if freshness == "FRESH":
            freshness = "STALE"
    generated = generated_at_utc or iso_utc_now()
    artifacts = {key: rel_or_abs(path) for key, path in paths.items() if path is not None}
    bundle = {
        "scenario_run": scenario_run,
        "final_market_state_run": final_run,
        "hedgemate_run": hedge_run,
        "backtest_run": backtest_run,
        "data_version": args.data_version,
        "scenario_vector_as_of_date": as_of,
        "generated_at_utc": generated,
        "freshness_status": freshness,
        "stale_reasons": reasons,
    }
    if portfolio_input_fingerprint:
        bundle["portfolio_input_fingerprint"] = portfolio_input_fingerprint
    if recommendation_portfolio_fingerprint:
        bundle["recommendation_portfolio_fingerprint"] = recommendation_portfolio_fingerprint
    if portfolio_mismatch:
        bundle["portfolio_input_mismatch"] = True
    return {
        "manifest_version": "hedgemate_active_bundle_v1",
        "generated_at_utc": generated,
        "freshness_status": freshness,
        "stale_reasons": reasons,
        "active_bundle": bundle,
        "active_scenario_run": scenario_run,
        "active_final_run": final_run,
        "active_hedgemate_run": hedge_run,
        "active_backtest_run": backtest_run,
        "data_version": args.data_version,
        "scenario_vector_as_of_date": as_of,
        "portfolio_input_fingerprint": portfolio_input_fingerprint,
        "recommendation_portfolio_fingerprint": recommendation_portfolio_fingerprint,
        "portfolio_input_mismatch": portfolio_mismatch,
        "artifacts": artifacts,
        "event_overlay_status": event_overlay_status_from_metadata(paths.get("eventOverlayMetadata")),
    }


def write_manifest(manifest: dict, output_path: Path = MANIFEST_PATH) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output_path


def write_final_runbook(manifest: dict, output_dir: Path | None = None) -> Path:
    output_dir = output_dir or OUTPUTS / "reports"
    hedge_run = manifest.get("active_hedgemate_run") or manifest.get("active_bundle", {}).get("hedgemate_run") or "unknown"
    bundle = manifest.get("active_bundle", {}) if isinstance(manifest.get("active_bundle"), dict) else {}
    artifacts = manifest.get("artifacts", {}) if isinstance(manifest.get("artifacts"), dict) else {}
    overlay = dict(DEFAULT_EVENT_OVERLAY_STATUS)
    if isinstance(manifest.get("event_overlay_status"), dict):
        overlay.update({key: value for key, value in manifest["event_overlay_status"].items() if value})
    path = output_dir / f"final_product_runbook_{hedge_run}.md"
    lines = [
        "# HedgeMate Final Product Runbook",
        "",
        "## Active Bundle",
        "",
        f"- data_version: {manifest.get('data_version') or bundle.get('data_version')}",
        f"- generated_at_utc: {manifest.get('generated_at_utc') or bundle.get('generated_at_utc')}",
        f"- scenario_run: {bundle.get('scenario_run')}",
        f"- final_market_state_run: {bundle.get('final_market_state_run')}",
        f"- hedgemate_run: {bundle.get('hedgemate_run') or hedge_run}",
        f"- backtest_run: {bundle.get('backtest_run')}",
        f"- freshness_status: {manifest.get('freshness_status')}",
        f"- stale_reasons: {', '.join(manifest.get('stale_reasons') or []) or 'none'}",
        "",
        "## User Workflow",
        "",
        "1. Open the HedgeMate dashboard.",
        "2. Enter assets by Korean name, English name, or ticker. Mixed quantity and KRW amount input is supported.",
        "3. Use price/FX preview before analysis. The preview shows resolved ticker, cached/live mode, price as-of, FX as-of, KRW value, weight, warnings, and row errors.",
        "4. Use market-data refresh only when freshness says stale. If the active bundle is already current for the day, the refresh endpoint returns skipped_latest and avoids the heavy pipeline.",
        "5. Run portfolio analysis after preview passes validation. Recommendations must be read with their recommendation_status, backtest gate, DQ status, and failure/reference reasons.",
        "",
        "## API Surface",
        "",
        "- GET /api/product-dashboard",
        "- GET /api/active-bundle",
        "- GET /api/data-freshness",
        "- POST /api/price-lookup",
        "- POST /api/portfolio/preview",
        "- POST /api/refresh-market-data",
        "- POST /api/run",
        "- GET /api/run-status",
        "",
        "## Evidence And Artifacts",
        "",
    ]
    for key in sorted(artifacts):
        lines.append(f"- {key}: {artifacts[key]}")
    lines.extend(
        [
            "",
            "## Decision Safety Rules",
            "",
            "- WORSENED backtest evidence cannot remain PASS_RECOMMEND.",
            "- INSUFFICIENT_HISTORY is validation-insufficient evidence, not success evidence.",
            "- A combination hedge requires combination-level evidence; component evidence alone cannot upgrade it to a formal recommendation.",
            "- Zero formal recommendations is a valid output when backtest or data evidence is insufficient.",
            "- Cache, fixture, stale, missing-artifact, DQ WARN/FAIL, and API-key-required states must stay visible to the user.",
            "",
            "## Known Non-Automated Items",
            "",
            f"- event_overlay_mode: {overlay.get('mode') or 'unknown'}",
            f"- live_gemini_extraction: {overlay.get('live_gemini_extraction') or 'unknown'}",
            f"- recommendation_usage: {overlay.get('recommendation_usage') or 'unknown'}",
            f"- trade_gate_usage: {overlay.get('trade_gate_usage') or 'unknown'}",
            "- I cannot issue external API keys, connect paid real-time market-data feeds, or configure brokerage credentials without user-provided access.",
            "- HedgeMate is a decision-support dashboard, not an auto-trading or order-routing system.",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def ensure_final_runbook_artifact(manifest: dict) -> Path:
    artifacts = manifest.setdefault("artifacts", {})
    hedge_run = manifest.get("active_hedgemate_run") or manifest.get("active_bundle", {}).get("hedgemate_run") or "unknown"
    default_path = OUTPUTS / "reports" / f"final_product_runbook_{hedge_run}.md"
    existing = resolve_existing(artifacts.get("finalRunbook")) if isinstance(artifacts, dict) else None
    if existing and existing.exists() and existing.resolve() != default_path.resolve():
        return existing
    runbook = write_final_runbook(manifest)
    artifacts["finalRunbook"] = rel_or_abs(runbook)
    return runbook


def sync_scenario_manifest_with_product(
    manifest: dict,
    scenario_manifest_path: Path = SCENARIO_OUTPUTS / "latest_manifest.json",
) -> Path | None:
    existing = read_json(scenario_manifest_path)
    if not isinstance(existing, dict):
        existing = {}

    hedge_run = manifest.get("active_hedgemate_run")
    if not hedge_run:
        return None

    legacy_run = existing.get("active_hedgemate_run")
    if legacy_run and legacy_run != hedge_run:
        existing["legacy_hedgemate_run"] = legacy_run
        existing["legacy_hedgemate_note"] = (
            "Superseded by HedgeMate/outputs/latest_manifest.json active bundle; "
            "do not use this legacy run as product recommendation evidence."
        )

    artifacts = manifest.get("artifacts", {}) if isinstance(manifest.get("artifacts"), dict) else {}
    sensitivity_path = artifacts.get("assetScenarioSensitivity") or f"HedgeMate/outputs/processed/asset_scenario_sensitivity_{hedge_run}.csv"
    summary_name = f"asset_scenario_sensitivity_summary_{hedge_run}.md"
    summary_path = OUTPUTS / "reports" / summary_name
    summary_rel = rel_or_abs(summary_path) if summary_path.exists() else f"HedgeMate/outputs/reports/{summary_name}"
    qa_path = artifacts.get("recommendationStatusQa")
    action_plan_path = artifacts.get("hedgeActionPlan")
    attribution_path = artifacts.get("portfolioVulnerabilityAttribution")

    existing.update(
        {
            "active_hedgemate_run": hedge_run,
            "active_hedgemate_summary": Path(summary_rel).name,
            "active_hedgemate_summary_path": "../" + summary_rel if not str(summary_rel).startswith("../") else summary_rel,
            "active_hedgemate_sensitivity": Path(str(sensitivity_path)).name,
            "active_hedgemate_sensitivity_path": "../" + str(sensitivity_path) if not str(sensitivity_path).startswith("../") else str(sensitivity_path),
            "active_hedgemate_scenario_vector": artifacts.get("scenarioVector"),
            "active_hedgemate_recommendation_status_qa": Path(str(qa_path)).name if qa_path else None,
            "active_hedgemate_recommendation_status_qa_path": "../" + str(qa_path) if qa_path and not str(qa_path).startswith("../") else qa_path,
            "active_hedgemate_action_plan": Path(str(action_plan_path)).name if action_plan_path else None,
            "active_hedgemate_action_plan_path": "../" + str(action_plan_path) if action_plan_path and not str(action_plan_path).startswith("../") else action_plan_path,
            "active_hedgemate_vulnerability_attribution": Path(str(attribution_path)).name if attribution_path else None,
            "active_hedgemate_vulnerability_attribution_path": "../" + str(attribution_path) if attribution_path and not str(attribution_path).startswith("../") else attribution_path,
            "active_hedgemate_product_manifest_path": "../HedgeMate/outputs/latest_manifest.json",
            "active_hedgemate_manifest_basis": "HedgeMate/outputs/latest_manifest.json",
        }
    )

    scenario_manifest_path.parent.mkdir(parents=True, exist_ok=True)
    scenario_manifest_path.write_text(json.dumps(existing, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return scenario_manifest_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build HedgeMate active bundle manifest")
    parser.add_argument("--scenario-run-id", required=True)
    parser.add_argument("--final-run-id")
    parser.add_argument("--hedgemate-run-id", required=True)
    parser.add_argument("--backtest-run-id", required=True)
    parser.add_argument("--data-version", required=True)
    parser.add_argument("--scenario-vector-as-of-date")
    parser.add_argument("--max-stale-days", type=int, default=2)
    parser.add_argument("--scenario-vector")
    parser.add_argument("--final-scenario-vector")
    parser.add_argument("--final-market-state")
    parser.add_argument("--scenario-confidence")
    parser.add_argument("--top-active-scenarios")
    parser.add_argument("--final-metadata")
    parser.add_argument("--event-overlay-metadata")
    parser.add_argument("--features")
    parser.add_argument("--portfolio-input")
    parser.add_argument("--asset-scenario-sensitivity")
    parser.add_argument("--portfolio-vulnerability-attribution")
    parser.add_argument("--portfolio-vulnerability-summary")
    parser.add_argument("--hedge-action-candidates")
    parser.add_argument("--hedge-action-plan")
    parser.add_argument("--hedge-action-plan-summary")
    parser.add_argument("--portfolio-1to1")
    parser.add_argument("--portfolio-multi")
    parser.add_argument("--recommendation-status-qa")
    parser.add_argument("--backtest-csv")
    parser.add_argument("--backtest-summary")
    parser.add_argument("--backtest-gate-summary")
    parser.add_argument("--backtest-attribution-csv")
    parser.add_argument("--backtest-attribution-summary")
    parser.add_argument("--formal-gate-audit-csv")
    parser.add_argument("--formal-gate-audit-summary")
    parser.add_argument("--rebalance-mode-comparison-csv")
    parser.add_argument("--rebalance-mode-comparison-summary")
    parser.add_argument("--rebalance-mode-comparison-json")
    parser.add_argument("--final-runbook")
    parser.add_argument("--output", type=Path, default=MANIFEST_PATH)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    manifest = build_manifest(args)
    ensure_final_runbook_artifact(manifest)
    path = write_manifest(manifest, args.output)
    sync_scenario_manifest_with_product(manifest)
    print(json.dumps({"manifest": str(path), "freshness_status": manifest["freshness_status"], "stale_reasons": manifest["stale_reasons"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
