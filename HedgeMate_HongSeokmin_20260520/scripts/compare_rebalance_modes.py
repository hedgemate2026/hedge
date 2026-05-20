#!/usr/bin/env python3
"""Compare HedgeMate backtest results across supported rebalance modes."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path

try:
    from . import run_scenario_backtest as backtest
except ImportError:  # pragma: no cover - used when executed as a script path.
    import run_scenario_backtest as backtest


REPORT_DIR = backtest.OUTPUT_REPORT_DIR
RAW_DIR = backtest.RAW_DIR
DEFAULT_MODES = ("formation_only", "monthly", "daily")

COMPARE_FIELDS = [
    "rebalance_frequency",
    "row_count",
    "evaluated_rows",
    "insufficient_history_rows",
    "improved_rows",
    "mixed_rows",
    "worsened_rows",
    "cash_beats_rows",
    "cash_mixed_rows",
    "cash_lags_rows",
    "target_evaluated_rows",
    "target_bootstrap_rows",
    "target_bootstrap_robust_rows",
    "target_bootstrap_uncertain_rows",
    "target_bootstrap_worse_rows",
    "avg_implementation_cost",
    "avg_recurring_rebalance_cost",
    "avg_total_path_cost",
    "avg_cost_adjusted_return_drag",
    "recommendation_bias",
]


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=COMPARE_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def numeric_values(rows: list[dict[str, object]], key: str) -> list[float]:
    values = []
    for row in rows:
        value = backtest.parse_float(row.get(key))
        if value is not None:
            values.append(value)
    return values


def average(rows: list[dict[str, object]], key: str) -> float:
    values = numeric_values(rows, key)
    return round(sum(values) / len(values), 8) if values else 0.0


def mode_summary(mode: str, rows: list[dict[str, object]]) -> dict[str, object]:
    evaluated = [row for row in rows if row.get("backtest_status") == "EVALUATED"]
    target_evaluated = [
        row
        for row in evaluated
        if str(row.get("is_target_scenario") or "").upper() in {"Y", "TRUE", "1"}
    ]
    verdicts = Counter(str(row.get("verdict") or "") for row in rows)
    cash = Counter(str(row.get("hedge_vs_cash_verdict") or "") for row in evaluated)
    bootstrap = Counter(str(row.get("bootstrap_confidence") or "") for row in target_evaluated)
    improved = verdicts.get("IMPROVED", 0)
    worsened = verdicts.get("WORSENED", 0)
    if improved > worsened:
        bias = "more_improved_than_worsened"
    elif worsened > improved:
        bias = "more_worsened_than_improved"
    else:
        bias = "balanced"
    return {
        "rebalance_frequency": mode,
        "row_count": len(rows),
        "evaluated_rows": len(evaluated),
        "insufficient_history_rows": verdicts.get("INSUFFICIENT_HISTORY", 0),
        "improved_rows": improved,
        "mixed_rows": verdicts.get("MIXED", 0),
        "worsened_rows": worsened,
        "cash_beats_rows": cash.get("BEATS_CASH", 0),
        "cash_mixed_rows": cash.get("MIXED_CASH", 0),
        "cash_lags_rows": cash.get("LAGS_CASH", 0),
        "target_evaluated_rows": len(target_evaluated),
        "target_bootstrap_rows": sum(
            count for key, count in bootstrap.items() if key not in {"", "INSUFFICIENT_SAMPLE"}
        ),
        "target_bootstrap_robust_rows": bootstrap.get("ROBUST_IMPROVE", 0),
        "target_bootstrap_uncertain_rows": bootstrap.get("UNCERTAIN", 0),
        "target_bootstrap_worse_rows": bootstrap.get("ROBUST_WORSE", 0),
        "avg_implementation_cost": average(evaluated, "implementation_cost"),
        "avg_recurring_rebalance_cost": average(evaluated, "recurring_rebalance_cost"),
        "avg_total_path_cost": average(evaluated, "total_path_cost"),
        "avg_cost_adjusted_return_drag": average(evaluated, "cost_adjusted_return_drag"),
        "recommendation_bias": bias,
    }


def evaluate_mode(
    mode: str,
    cases: list[dict[str, str]],
    candidates: list[dict[str, str]],
    base_weights: dict[str, float],
    return_maps: dict[str, dict[str, float]],
    transaction_cost_bps: float,
    slippage_bps: float,
    bootstrap_iterations: int,
    bootstrap_ci_level: float,
) -> list[dict[str, object]]:
    rows = []
    for case in cases:
        if (case.get("detection_status") or case.get("validation_status")) == "INSUFFICIENT_HISTORY":
            for candidate in candidates or [{}]:
                rows.append(
                    backtest.evaluate_case_candidate(
                        case,
                        candidate,
                        base_weights,
                        return_maps,
                        transaction_cost_bps=transaction_cost_bps,
                        slippage_bps=slippage_bps,
                        rebalance_frequency=mode,
                        bootstrap_iterations=bootstrap_iterations,
                        bootstrap_ci_level=bootstrap_ci_level,
                    )
                )
            continue
        for candidate in candidates:
            rows.append(
                backtest.evaluate_case_candidate(
                    case,
                    candidate,
                    base_weights,
                    return_maps,
                    transaction_cost_bps=transaction_cost_bps,
                    slippage_bps=slippage_bps,
                    rebalance_frequency=mode,
                    bootstrap_iterations=bootstrap_iterations,
                    bootstrap_ci_level=bootstrap_ci_level,
                )
            )
    return rows


def render_markdown(run_id: str, summaries: list[dict[str, object]]) -> str:
    lines = [
        "# HedgeMate Rebalance Mode Comparison",
        "",
        f"- run_id: `{run_id}`",
        f"- engine_version: `{backtest.BACKTEST_ENGINE_VERSION}`",
        "- modes: `formation_only`, `monthly`, `daily`",
        "- scope: API-free cached market prices and reviewed HedgeMate recommendation artifacts",
        "",
        "| mode | evaluated | improved | worsened | cash_lags | robust/target_bootstrap | avg_recurring_cost | avg_total_path_cost | bias |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in summaries:
        lines.append(
            "| {mode} | {evaluated} | {improved} | {worsened} | {cash_lags} | {robust}/{bootstrap} | {recurring} | {total_cost} | {bias} |".format(
                mode=row["rebalance_frequency"],
                evaluated=row["evaluated_rows"],
                improved=row["improved_rows"],
                worsened=row["worsened_rows"],
                cash_lags=row["cash_lags_rows"],
                robust=row["target_bootstrap_robust_rows"],
                bootstrap=row["target_bootstrap_rows"],
                recurring=row["avg_recurring_rebalance_cost"],
                total_cost=row["avg_total_path_cost"],
                bias=row["recommendation_bias"],
            )
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "- This report is comparison evidence only; it does not update the active product bundle.",
            "- A mode should not become the product default until cash baseline, bootstrap, validation quality, liquidity, and turnover gates remain acceptable under that mode.",
        ]
    )
    return "\n".join(lines) + "\n"


def build_comparison(args: argparse.Namespace) -> dict[str, object]:
    cases = backtest.load_csv(backtest.resolve_historical_validation_path(args.historical_validation_run_id))
    recommendation_rows = backtest.resolve_recommendation_rows(args.hedgemate_run_id, args.recommendation_scope)
    candidates = backtest.select_representative_candidates(recommendation_rows, limit=args.candidate_limit)
    base_weights = backtest.pct_weights_from_rows(backtest.load_csv(args.portfolio_input))
    raw_market_path = RAW_DIR / f"raw_market_daily_{args.data_version}.csv"
    return_maps = backtest.return_maps_from_prices(backtest.load_price_maps(raw_market_path))

    summaries = []
    for mode in args.modes:
        rows = evaluate_mode(
            mode,
            cases,
            candidates,
            base_weights,
            return_maps,
            args.transaction_cost_bps,
            args.slippage_bps,
            args.bootstrap_iterations,
            args.bootstrap_ci_level,
        )
        summaries.append(mode_summary(mode, rows))

    csv_path = REPORT_DIR / f"rebalance_mode_comparison_{args.run_id}.csv"
    md_path = REPORT_DIR / f"rebalance_mode_comparison_{args.run_id}.md"
    json_path = REPORT_DIR / f"rebalance_mode_comparison_{args.run_id}.json"
    write_csv(csv_path, summaries)
    md_path.write_text(render_markdown(args.run_id, summaries), encoding="utf-8")
    payload = {
        "run_id": args.run_id,
        "engine_version": backtest.BACKTEST_ENGINE_VERSION,
        "modes": list(args.modes),
        "transaction_cost_bps": args.transaction_cost_bps,
        "slippage_bps": args.slippage_bps,
        "bootstrap_iterations": args.bootstrap_iterations,
        "bootstrap_ci_level": args.bootstrap_ci_level,
        "csv_path": str(csv_path),
        "summary_md_path": str(md_path),
        "summaries": summaries,
    }
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"csv": csv_path, "summary_md": md_path, "json": json_path, "summaries": summaries}


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare HedgeMate backtest rebalance modes.")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--historical-validation-run-id", required=True)
    parser.add_argument("--hedgemate-run-id", required=True)
    parser.add_argument("--data-version", default="20260520")
    parser.add_argument("--portfolio-input", type=Path, default=backtest.DEFAULT_PORTFOLIO_INPUT)
    parser.add_argument("--candidate-limit", type=int, default=0)
    parser.add_argument("--recommendation-scope", choices=["portfolio", "single_asset"], default="portfolio")
    parser.add_argument("--transaction-cost-bps", type=float, default=backtest.DEFAULT_TRANSACTION_COST_BPS)
    parser.add_argument("--slippage-bps", type=float, default=backtest.DEFAULT_SLIPPAGE_BPS)
    parser.add_argument("--bootstrap-iterations", type=int, default=backtest.DEFAULT_BOOTSTRAP_ITERATIONS)
    parser.add_argument("--bootstrap-ci-level", type=float, default=backtest.DEFAULT_BOOTSTRAP_CI_LEVEL)
    parser.add_argument("--modes", nargs="+", choices=DEFAULT_MODES, default=list(DEFAULT_MODES))
    return parser.parse_args(argv)


def main(argv=None) -> int:
    result = build_comparison(parse_args(argv))
    print(f"REBALANCE_COMPARISON_CSV={result['csv']}")
    print(f"REBALANCE_COMPARISON_SUMMARY={result['summary_md']}")
    print(f"REBALANCE_COMPARISON_JSON={result['json']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
