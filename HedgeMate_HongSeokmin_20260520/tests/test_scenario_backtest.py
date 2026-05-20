import unittest
import tempfile
from datetime import date, timedelta
from pathlib import Path

import scripts.compare_rebalance_modes as compare_rebalance_modes
from scripts.run_scenario_backtest import (
    cvar_95,
    evaluate_case_candidate,
    max_drawdown_from_returns,
    portfolio_daily_returns,
    portfolio_path_result,
    portfolio_path_returns,
    return_maps_from_prices,
    resolve_recommendation_rows,
    select_representative_candidates,
)


class ScenarioBacktestTest(unittest.TestCase):
    def test_selects_pass_recommend_candidates_first(self):
        rows = [
            {"candidate_ticker": "A", "recommendation_status": "REFERENCE_ONLY", "final_score": "0.9", "weights_snapshot": '{"A": 10}'},
            {"candidate_ticker": "B", "recommendation_status": "PASS_RECOMMEND", "final_score": "0.8", "weights_snapshot": '{"B": 10}'},
        ]

        selected = select_representative_candidates(rows, limit=1)

        self.assertEqual(selected[0]["candidate_ticker"], "B")

    def test_zero_candidate_limit_keeps_each_allocation_row(self):
        rows = [
            {
                "candidate_ticker": "GLD",
                "recommendation_status": "PASS_RECOMMEND",
                "final_score": "0.8",
                "hedge_weight_pct": "10",
                "weights_snapshot": '{"BASE": 90, "GLD": 10}',
            },
            {
                "candidate_ticker": "GLD",
                "recommendation_status": "PASS_RECOMMEND",
                "final_score": "0.9",
                "hedge_weight_pct": "30",
                "weights_snapshot": '{"BASE": 70, "GLD": 30}',
            },
        ]

        selected = select_representative_candidates(rows, limit=0)

        self.assertEqual(len(selected), 2)

    def test_single_asset_scope_reads_single_asset_recommendation_files(self):
        import scripts.run_scenario_backtest as backtest

        original_dir = backtest.OUTPUT_REPORT_DIR
        try:
            with tempfile.TemporaryDirectory() as tmp:
                backtest.OUTPUT_REPORT_DIR = Path(tmp)
                (backtest.OUTPUT_REPORT_DIR / "portfolio_1to1_hedge_run.csv").write_text(
                    "candidate_ticker,recommendation_status,weights_snapshot\nTLT,PASS_RECOMMEND,\"{\"\"TLT\"\": 20}\"\n",
                    encoding="utf-8",
                )
                (backtest.OUTPUT_REPORT_DIR / "single_asset_hedge_1to1_run.csv").write_text(
                    "candidate_ticker,recommendation_status,weights_snapshot\nGLD,PASS_RECOMMEND,\"{\"\"GLD\"\": 20}\"\n",
                    encoding="utf-8",
                )

                rows = resolve_recommendation_rows("run", "single_asset")
        finally:
            backtest.OUTPUT_REPORT_DIR = original_dir
        self.assertEqual([row["candidate_ticker"] for row in rows], ["GLD"])

    def test_portfolio_returns_treat_cash_as_zero_return_weight(self):
        returns = {"BASE": {"2024-01-02": 0.10, "2024-01-03": -0.10}}

        rows = portfolio_daily_returns({"BASE": 0.5, "__CASH__": 0.5}, returns, "2024-01-02", "2024-01-03")

        self.assertEqual([date_str for date_str, _ in rows], ["2024-01-02", "2024-01-03"])
        self.assertAlmostEqual(rows[0][1], 0.05)
        self.assertAlmostEqual(rows[1][1], -0.05)

    def test_formation_only_path_uses_buy_and_hold_weights(self):
        returns = {"BASE": {"2024-01-02": 0.10, "2024-01-03": -0.10}}

        formation_rows = portfolio_path_returns(
            {"BASE": 0.5, "__CASH__": 0.5},
            returns,
            "2024-01-02",
            "2024-01-03",
            rebalance_frequency="formation_only",
        )
        daily_rows = portfolio_path_returns(
            {"BASE": 0.5, "__CASH__": 0.5},
            returns,
            "2024-01-02",
            "2024-01-03",
            rebalance_frequency="daily",
        )

        self.assertAlmostEqual(formation_rows[0][1], 0.05)
        self.assertLess(formation_rows[1][1], daily_rows[1][1])
        self.assertAlmostEqual(formation_rows[1][1], -0.05238095238)
        self.assertAlmostEqual(daily_rows[1][1], -0.05)

    def test_monthly_rebalance_path_deducts_recurring_cost(self):
        returns = {
            "BASE": {
                "2024-01-31": 0.20,
                "2024-02-01": 0.10,
                "2024-02-02": 0.00,
            }
        }
        weights = {"BASE": 0.5, "__CASH__": 0.5}

        gross_rows, gross_cost = portfolio_path_result(
            weights,
            returns,
            "2024-01-31",
            "2024-02-02",
            rebalance_frequency="monthly",
            transaction_cost_bps=0,
            slippage_bps=0,
        )
        net_rows, recurring_cost = portfolio_path_result(
            weights,
            returns,
            "2024-01-31",
            "2024-02-02",
            rebalance_frequency="monthly",
            transaction_cost_bps=100,
            slippage_bps=0,
        )

        self.assertEqual(gross_cost, 0.0)
        self.assertGreater(recurring_cost, 0.0)
        self.assertEqual([date_str for date_str, _ in gross_rows], [date_str for date_str, _ in net_rows])
        self.assertLess(dict(net_rows)["2024-02-01"], dict(gross_rows)["2024-02-01"])

    def test_marks_insufficient_history_without_evaluating_as_success(self):
        row = evaluate_case_candidate(
            {"case_id": "gfc", "case_name": "GFC", "expected_scenario_code": "acute", "detection_status": "INSUFFICIENT_HISTORY", "data_sufficiency": "INSUFFICIENT_HISTORY"},
            {"candidate_ticker": "GLD", "recommendation_status": "PASS_RECOMMEND", "weights_snapshot": '{"GLD": 10}'},
            {"SPY": 1.0},
            {},
        )

        self.assertEqual(row["backtest_status"], "INSUFFICIENT_HISTORY")
        self.assertEqual(row["verdict"], "INSUFFICIENT_HISTORY")
        self.assertEqual(row["price_window_status"], "EVENT_WINDOW_MISSING")
        self.assertIn("GLD", row["missing_price_tickers"])
        self.assertIn("SPY", row["price_blocking_tickers"])

    def test_insufficient_history_explains_out_of_price_range_window(self):
        prices = {
            "BASE": [("2021-05-10", 100.0), ("2021-05-11", 101.0), ("2021-05-12", 102.0)],
            "HEDGE": [("2021-05-10", 50.0), ("2021-05-11", 50.5), ("2021-05-12", 51.0)],
        }
        row = evaluate_case_candidate(
            {
                "case_id": "covid",
                "case_name": "COVID",
                "expected_scenario_code": "acute",
                "detection_status": "INSUFFICIENT_HISTORY",
                "data_sufficiency": "INSUFFICIENT_HISTORY",
                "start_date": "2020-02-19",
                "end_date": "2020-04-15",
            },
            {
                "candidate_ticker": "HEDGE",
                "recommendation_status": "PASS_RECOMMEND",
                "weights_snapshot": '{"BASE": 90, "HEDGE": 10}',
            },
            {"BASE": 1.0},
            return_maps_from_prices(prices),
        )

        self.assertEqual(row["backtest_status"], "INSUFFICIENT_HISTORY")
        self.assertEqual(row["price_window_status"], "OUT_OF_PRICE_RANGE")
        self.assertEqual(row["first_price_date"], "2021-05-11")
        self.assertEqual(row["last_price_date"], "2021-05-12")
        self.assertIn("outside cached return history", row["notes"])

    def test_insufficient_history_explains_pre_inception_blocker(self):
        prices = {
            "BASE": [("2021-01-01", 100.0), ("2021-01-02", 101.0), ("2021-01-03", 102.0)],
            "HEDGE": [("2020-01-01", 50.0), ("2020-01-02", 50.5), ("2020-01-03", 51.0)],
        }
        row = evaluate_case_candidate(
            {
                "case_id": "gfc",
                "case_name": "GFC",
                "expected_scenario_code": "acute",
                "detection_status": "INSUFFICIENT_HISTORY",
                "data_sufficiency": "INSUFFICIENT_HISTORY",
                "start_date": "2020-01-02",
                "end_date": "2020-01-03",
            },
            {
                "candidate_ticker": "HEDGE",
                "recommendation_status": "PASS_RECOMMEND",
                "weights_snapshot": '{"BASE": 50, "HEDGE": 50}',
            },
            {"BASE": 1.0},
            return_maps_from_prices(prices),
        )

        self.assertEqual(row["backtest_status"], "INSUFFICIENT_HISTORY")
        self.assertEqual(row["price_window_status"], "NO_COMMON_PRICE_DATES")
        self.assertIn("BASE", row["price_blocking_tickers"])
        self.assertIn("BASE", row["pre_inception_tickers"])
        self.assertIn("Pre-inception tickers: BASE", row["notes"])

    def test_insufficient_scenario_history_still_evaluates_when_prices_cover_event(self):
        dates = [(date(2020, 2, 1) + timedelta(days=day)).isoformat() for day in range(100)]
        prices = {
            "BASE": [(date_str, 100.0 + index) for index, date_str in enumerate(dates)],
            "HEDGE": [(date_str, 100.0 + index * 0.2) for index, date_str in enumerate(dates)],
        }

        row = evaluate_case_candidate(
            {
                "case_id": "covid",
                "case_name": "COVID",
                "expected_scenario_code": "acute",
                "detection_status": "INSUFFICIENT_HISTORY",
                "data_sufficiency": "INSUFFICIENT_HISTORY",
                "start_date": dates[1],
                "end_date": dates[-1],
            },
            {
                "candidate_ticker": "HEDGE",
                "recommendation_status": "PASS_RECOMMEND",
                "weights_snapshot": '{"BASE": 80, "HEDGE": 20}',
            },
            {"BASE": 1.0},
            return_maps_from_prices(prices),
        )

        self.assertEqual(row["backtest_status"], "EVALUATED")
        self.assertEqual(row["price_window_status"], "PRICE_WINDOW_AVAILABLE")
        self.assertIn(row["verdict"], {"IMPROVED", "MIXED", "WORSENED"})
        self.assertIn("directly from cached event-window prices", row["notes"])

    def test_evaluates_case_candidate_with_cached_returns(self):
        prices = {
            "BASE": [(f"2024-01-{day:02d}", 100.0 + day) for day in range(1, 32)]
            + [(f"2024-02-{day:02d}", 131.0 + day) for day in range(1, 30)]
            + [(f"2024-03-{day:02d}", 160.0 + day) for day in range(1, 32)],
            "HEDGE": [(f"2024-01-{day:02d}", 100.0 + day * 0.5) for day in range(1, 32)]
            + [(f"2024-02-{day:02d}", 115.5 + day * 0.5) for day in range(1, 30)]
            + [(f"2024-03-{day:02d}", 130.0 + day * 0.5) for day in range(1, 32)],
        }
        return_maps = return_maps_from_prices(prices)
        row = evaluate_case_candidate(
            {
                "case_id": "case",
                "case_name": "Case",
                "expected_scenario_code": "scenario",
                "detection_status": "DETECTED",
                "data_sufficiency": "SUFFICIENT",
                "active_date": "2024-01-02",
                "start_date": "2024-01-01",
                "end_date": "2024-03-31",
            },
            {"candidate_ticker": "HEDGE", "recommendation_status": "PASS_RECOMMEND", "weights_snapshot": '{"BASE": 90, "HEDGE": 10}'},
            {"BASE": 1.0},
            return_maps,
        )

        self.assertEqual(row["backtest_status"], "EVALUATED")
        self.assertGreaterEqual(row["evaluation_day_count"], 60)
        self.assertIn(row["verdict"], {"IMPROVED", "MIXED", "WORSENED"})
        self.assertIn(row["hedge_vs_cash_verdict"], {"BEATS_CASH", "MIXED_CASH", "LAGS_CASH"})

    def test_applies_transaction_cost_and_slippage_to_net_metrics(self):
        dates = [(date(2024, 1, 1) + timedelta(days=day)).isoformat() for day in range(90)]
        prices = {
            "BASE": [(date_str, 100.0 + index) for index, date_str in enumerate(dates)],
            "HEDGE": [(date_str, 100.0 + index * 0.8) for index, date_str in enumerate(dates)],
        }

        row = evaluate_case_candidate(
            {
                "case_id": "case",
                "case_name": "Case",
                "expected_scenario_code": "scenario",
                "detection_status": "DETECTED",
                "data_sufficiency": "SUFFICIENT",
                "active_date": dates[1],
                "start_date": dates[0],
                "end_date": dates[-1],
            },
            {"candidate_ticker": "HEDGE", "recommendation_status": "PASS_RECOMMEND", "weights_snapshot": '{"BASE": 90, "HEDGE": 10}'},
            {"BASE": 1.0},
            return_maps_from_prices(prices),
            transaction_cost_bps=20,
            slippage_bps=5,
        )

        self.assertEqual(row["backtest_status"], "EVALUATED")
        self.assertAlmostEqual(row["turnover"], 0.1)
        self.assertAlmostEqual(row["total_cost_bps"], 25.0)
        self.assertAlmostEqual(row["implementation_cost"], 0.00025)
        self.assertLess(row["proposed_net_annual_return"], row["proposed_annual_return"])
        self.assertLess(row["cost_adjusted_return_drag"], row["return_drag"])
        self.assertIn("Cost-adjusted", row["notes"])

    def test_monthly_rebalance_cost_flows_into_net_metrics(self):
        dates = [(date(2024, 1, 1) + timedelta(days=day)).isoformat() for day in range(90)]
        prices = {
            "BASE": [(date_str, 100.0 + index) for index, date_str in enumerate(dates)],
            "HEDGE": [(date_str, 100.0 + index * 1.2) for index, date_str in enumerate(dates)],
        }

        row = evaluate_case_candidate(
            {
                "case_id": "case",
                "case_name": "Case",
                "expected_scenario_code": "scenario",
                "detection_status": "DETECTED",
                "data_sufficiency": "SUFFICIENT",
                "active_date": dates[1],
                "start_date": dates[0],
                "end_date": dates[-1],
            },
            {"candidate_ticker": "HEDGE", "recommendation_status": "PASS_RECOMMEND", "weights_snapshot": '{"BASE": 50, "HEDGE": 50}'},
            {"BASE": 1.0},
            return_maps_from_prices(prices),
            transaction_cost_bps=100,
            slippage_bps=0,
            rebalance_frequency="monthly",
        )

        self.assertEqual(row["backtest_status"], "EVALUATED")
        self.assertGreater(row["recurring_rebalance_cost"], 0.0)
        self.assertGreater(row["total_path_cost"], row["implementation_cost"])
        self.assertLess(row["proposed_net_annual_return"], row["proposed_annual_return"])

    def test_bootstrap_confidence_fields_are_deterministic(self):
        dates = [(date(2024, 1, 1) + timedelta(days=day)).isoformat() for day in range(90)]
        prices = {
            "BASE": [(date_str, 100.0 + index * 0.1) for index, date_str in enumerate(dates)],
            "HEDGE": [(date_str, 100.0 + index * 1.0) for index, date_str in enumerate(dates)],
        }
        case = {
            "case_id": "case",
            "case_name": "Case",
            "expected_scenario_code": "scenario",
            "detection_status": "DETECTED",
            "data_sufficiency": "SUFFICIENT",
            "active_date": dates[1],
            "start_date": dates[0],
            "end_date": dates[-1],
        }
        candidate = {"candidate_ticker": "HEDGE", "recommendation_status": "PASS_RECOMMEND", "weights_snapshot": '{"BASE": 90, "HEDGE": 10}'}
        return_maps = return_maps_from_prices(prices)

        row1 = evaluate_case_candidate(case, candidate, {"BASE": 1.0}, return_maps, bootstrap_iterations=50)
        row2 = evaluate_case_candidate(case, candidate, {"BASE": 1.0}, return_maps, bootstrap_iterations=50)

        self.assertEqual(row1["bootstrap_iterations"], 50)
        self.assertEqual(row1["bootstrap_seed"], row2["bootstrap_seed"])
        self.assertEqual(row1["net_stress_delta_ci_low"], row2["net_stress_delta_ci_low"])
        self.assertIn(row1["bootstrap_confidence"], {"ROBUST_IMPROVE", "ROBUST_WORSE", "UNCERTAIN"})
        self.assertNotEqual(row1["net_stress_delta_p_improve"], "")
        self.assertEqual(row1["cash_bootstrap_iterations"], 50)
        self.assertEqual(row1["cash_bootstrap_seed"], row2["cash_bootstrap_seed"])
        self.assertNotEqual(row1["cash_bootstrap_seed"], row1["bootstrap_seed"])
        self.assertEqual(row1["cash_net_stress_delta_ci_low"], row2["cash_net_stress_delta_ci_low"])
        self.assertIn(row1["cash_bootstrap_confidence"], {"ROBUST_IMPROVE", "ROBUST_WORSE", "UNCERTAIN"})
        self.assertNotEqual(row1["cash_net_stress_delta_p_improve"], "")

    def test_short_event_window_uses_coverage_based_minimum(self):
        dates = [(date(2024, 1, 1) + timedelta(days=day)).isoformat() for day in range(57)]
        prices = {
            "BASE": [(date_str, 100.0 + index) for index, date_str in enumerate(dates)],
            "HEDGE": [(date_str, 100.0 + index * 0.5) for index, date_str in enumerate(dates)],
        }
        row = evaluate_case_candidate(
            {
                "case_id": "short_event",
                "case_name": "Short Event",
                "expected_scenario_code": "scenario",
                "detection_status": "DETECTED",
                "data_sufficiency": "SUFFICIENT",
                "active_date": dates[1],
                "start_date": dates[0],
                "end_date": dates[-1],
            },
            {"candidate_ticker": "HEDGE", "recommendation_status": "PASS_RECOMMEND", "weights_snapshot": '{"BASE": 90, "HEDGE": 10}'},
            {"BASE": 1.0},
            return_maps_from_prices(prices),
        )

        self.assertEqual(row["backtest_status"], "EVALUATED")
        self.assertLess(row["evaluation_day_count"], 60)

    def test_metric_helpers(self):
        self.assertLess(cvar_95([-0.10, -0.05, 0.01, 0.02]), 0)
        self.assertLessEqual(max_drawdown_from_returns([0.1, -0.2, 0.05]), 0)

    def test_rebalance_mode_comparison_summarizes_recurring_costs(self):
        dates = [(date(2024, 1, 1) + timedelta(days=day)).isoformat() for day in range(90)]
        cases = [
            {
                "case_id": "case",
                "case_name": "Case",
                "expected_scenario_code": "scenario",
                "detection_status": "DETECTED",
                "data_sufficiency": "SUFFICIENT",
                "active_date": dates[1],
                "start_date": dates[0],
                "end_date": dates[-1],
            }
        ]
        candidates = [
            {
                "candidate_ticker": "HEDGE",
                "recommendation_status": "PASS_RECOMMEND",
                "weights_snapshot": '{"BASE": 50, "HEDGE": 50}',
                "risk_bucket_match": "scenario",
            }
        ]
        prices = {
            "BASE": [(date_str, 100.0 + index) for index, date_str in enumerate(dates)],
            "HEDGE": [(date_str, 100.0 + index * 1.2) for index, date_str in enumerate(dates)],
        }

        formation_rows = compare_rebalance_modes.evaluate_mode(
            "formation_only",
            cases,
            candidates,
            {"BASE": 1.0},
            return_maps_from_prices(prices),
            transaction_cost_bps=100,
            slippage_bps=0,
            bootstrap_iterations=10,
            bootstrap_ci_level=0.95,
        )
        monthly_rows = compare_rebalance_modes.evaluate_mode(
            "monthly",
            cases,
            candidates,
            {"BASE": 1.0},
            return_maps_from_prices(prices),
            transaction_cost_bps=100,
            slippage_bps=0,
            bootstrap_iterations=10,
            bootstrap_ci_level=0.95,
        )

        formation = compare_rebalance_modes.mode_summary("formation_only", formation_rows)
        monthly = compare_rebalance_modes.mode_summary("monthly", monthly_rows)

        self.assertEqual(formation["avg_recurring_rebalance_cost"], 0.0)
        self.assertGreater(monthly["avg_recurring_rebalance_cost"], 0.0)
        self.assertGreater(monthly["avg_total_path_cost"], formation["avg_total_path_cost"])


if __name__ == "__main__":
    unittest.main()
