#!/usr/bin/env python3
"""Refresh API-free scenario, hedge, backtest, gate, and active bundle outputs."""

from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = ROOT.parent


def run_step(cmd: list[str]) -> None:
    print("RUN", " ".join(cmd), flush=True)
    completed = subprocess.run(cmd, cwd=str(WORKSPACE_ROOT), text=True, check=False)
    if completed.returncode != 0:
        raise SystemExit(completed.returncode)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    today = datetime.now().strftime("%Y%m%d")
    parser = argparse.ArgumentParser(description="Refresh HedgeMate product active bundle without API-key services")
    parser.add_argument("--data-version", default=today)
    parser.add_argument("--run-stamp", default=today)
    parser.add_argument("--portfolio-input", default=r"HedgeMate\inputs\portfolio_weights.csv")
    parser.add_argument("--hedge-budgets", default=None, help="Hedge budget percentages to pass to HedgeMate (for example 10,20,30).")
    parser.add_argument("--base-total-krw", type=float, default=None, help="Portfolio total market value in KRW for order-size-aware liquidity checks.")
    parser.add_argument("--hedge-budgets-krw", default=None, help="Hedge budget KRW amounts to pass to HedgeMate (for example 1000000,2000000).")
    parser.add_argument("--event-input", default=r"scenario_research\inputs\event_overlay_sample_combined_20260514.csv")
    parser.add_argument("--historical-validation-run-id", default="phase10a-wave5-20260514")
    parser.add_argument("--max-combo-size", type=int, default=2, help="Maximum hedge combo size for product refresh. Default keeps refresh responsive.")
    parser.add_argument("--force-refresh-raw", action="store_true", help="Force HedgeMate raw market refresh instead of reusing same data_version cache.")
    args = parser.parse_args(argv)
    if args.base_total_krw is not None and args.base_total_krw <= 0:
        parser.error("--base-total-krw must be greater than zero.")
    if args.hedge_budgets_krw and args.base_total_krw is None:
        parser.error("--base-total-krw is required when --hedge-budgets-krw is set.")
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    scenario_run = f"scenario-refresh-{args.run_stamp}"
    overlay_run = f"event-refresh-{args.run_stamp}"
    final_run = f"final-refresh-{args.run_stamp}"
    hedge_run = f"hedgemate-refresh-{args.run_stamp}"
    backtest_run = f"backtest-refresh-{args.run_stamp}"

    python = sys.executable
    run_step([python, r"scenario_research\scripts\run_event_overlay_pipeline.py", "--input", args.event_input, "--run-id", overlay_run])
    run_step([python, r"scenario_research\scripts\run_market_state_pipeline.py", "--run-id", scenario_run, "--data-version", args.data_version, "--skip-shared-cache"])
    run_step([python, r"scenario_research\scripts\run_final_market_state_pipeline.py", "--run-id", final_run, "--scenario-run-id", scenario_run, "--overlay-run-id", overlay_run])
    hedge_cmd = [
        python,
        r"HedgeMate\scripts\run_data_pipeline.py",
        "--run-id",
        hedge_run,
        "--data-version",
        args.data_version,
        "--candidate-mode",
        "risk-bucket",
        "--max-combo-size",
        str(max(1, min(args.max_combo_size, 4))),
        "--portfolio-input",
        args.portfolio_input,
        "--scenario-vector",
        fr"scenario_research\outputs\scenario_vectors\current_scenario_vector_{final_run}.csv",
    ]
    if args.hedge_budgets:
        hedge_cmd.extend(["--hedge-budgets", args.hedge_budgets])
    if args.hedge_budgets_krw:
        hedge_cmd.extend(["--base-total-krw", str(args.base_total_krw), "--hedge-budgets-krw", args.hedge_budgets_krw])
    if args.force_refresh_raw:
        hedge_cmd.append("--force-refresh-raw")
    run_step(hedge_cmd)
    run_step([
        python,
        r"HedgeMate\scripts\run_scenario_backtest.py",
        "--run-id",
        backtest_run,
        "--historical-validation-run-id",
        args.historical_validation_run_id,
        "--hedgemate-run-id",
        hedge_run,
        "--data-version",
        args.data_version,
    ])
    run_step([python, r"HedgeMate\scripts\apply_backtest_gate.py", "--hedgemate-run-id", hedge_run, "--backtest-run-id", backtest_run])
    run_step([
        python,
        r"HedgeMate\scripts\update_active_bundle.py",
        "--scenario-run-id",
        scenario_run,
        "--final-run-id",
        final_run,
        "--hedgemate-run-id",
        hedge_run,
        "--backtest-run-id",
        backtest_run,
        "--data-version",
        args.data_version,
        "--portfolio-input",
        args.portfolio_input,
        "--scenario-vector",
        fr"scenario_research\outputs\scenario_vectors\current_scenario_vector_{scenario_run}.csv",
        "--final-scenario-vector",
        fr"scenario_research\outputs\scenario_vectors\current_scenario_vector_{final_run}.csv",
        "--event-overlay-metadata",
        fr"scenario_research\outputs\reports\event_overlay_metadata_{overlay_run}.json",
        "--portfolio-1to1",
        fr"HedgeMate\outputs\reports\portfolio_1to1_hedge_{hedge_run}_backtest_gated.csv",
        "--portfolio-multi",
        fr"HedgeMate\outputs\reports\portfolio_multi_hedge_{hedge_run}_backtest_gated.csv",
        "--backtest-gate-summary",
        fr"HedgeMate\outputs\reports\backtest_gate_summary_{hedge_run}_backtest_gated.md",
    ])
    print(f"REFRESHED scenario={scenario_run} final={final_run} hedge={hedge_run} backtest={backtest_run}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
