import csv
import importlib.util
import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "run_data_pipeline.py"


spec = importlib.util.spec_from_file_location("run_data_pipeline", MODULE_PATH)
run_data_pipeline = importlib.util.module_from_spec(spec)
spec.loader.exec_module(run_data_pipeline)


def generate_price_rows(start_date, total_days, start_price, return_func, include_weekends=False):
    rows = []
    price = start_price
    obs_idx = 0
    for offset in range(total_days):
        dt = start_date + timedelta(days=offset)
        if not include_weekends and dt.weekday() >= 5:
            continue
        ret = return_func(obs_idx)
        price *= 1.0 + ret
        rows.append(
            {
                "date": dt.isoformat(),
                "open": price,
                "high": price,
                "low": price,
                "close": price,
                "adj_close": price,
                "volume": 1_000_000,
            }
        )
        obs_idx += 1
    return rows


def write_market_raw(path, rows):
    fieldnames = [
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
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def write_fx_raw(path, rows):
    fieldnames = ["date", "ticker", "close", "source", "currency", "ingested_at"]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


class RunDataPipelineTests(unittest.TestCase):
    def test_parse_args_defaults_to_risk_bucket_candidate_mode(self):
        with mock.patch.object(sys, "argv", ["run_data_pipeline.py"]):
            args = run_data_pipeline.parse_args()

        self.assertEqual(args.candidate_mode, "risk-bucket")

    def test_build_krw_price_series_uses_carry_forward_fx(self):
        series = [
            ("2025-01-03", 10.0, 100.0, None, None, None, None),
            ("2025-01-04", 11.0, 100.0, None, None, None, None),
            ("2025-01-05", 12.0, 100.0, None, None, None, None),
        ]
        fx_rate_map = {"2025-01-03": 1300.0}
        krw_prices, adv_series, fx_missing_count = run_data_pipeline.build_krw_price_series(series, "USD", fx_rate_map)
        self.assertEqual(fx_missing_count, 0)
        self.assertEqual(krw_prices[0], ("2025-01-03", 13000.0))
        self.assertEqual(krw_prices[1], ("2025-01-04", 14300.0))
        self.assertEqual(krw_prices[2], ("2025-01-05", 15600.0))
        self.assertEqual(len(adv_series), 3)

    def test_parse_budget_list_dedupes_and_preserves_order(self):
        self.assertEqual(run_data_pipeline.parse_budget_list("10,20,20,30"), [10.0, 20.0, 30.0])

    def test_validate_portfolio_weights_allows_concentrated_input_up_to_fifty_percent(self):
        valid, errors = run_data_pipeline.validate_portfolio_weights(
            {"AAPL": 50.0, "MSFT": 50.0},
            {
                "AAPL": {"ticker": "AAPL"},
                "MSFT": {"ticker": "MSFT"},
            },
        )
        self.assertTrue(valid)
        self.assertEqual(errors, [])

    def test_validate_portfolio_weights_rejects_weight_over_fifty_percent_by_default(self):
        valid, errors = run_data_pipeline.validate_portfolio_weights(
            {"AAPL": 60.0, "MSFT": 40.0},
            {
                "AAPL": {"ticker": "AAPL"},
                "MSFT": {"ticker": "MSFT"},
            },
        )
        self.assertFalse(valid)
        self.assertTrue(any("최대 50.0%" in error for error in errors))

    def test_build_candidate_weights_exact_keeps_leftover_cash(self):
        weights, message, details = run_data_pipeline.build_candidate_weights_exact(
            {"TSLA": 10_000_000.0},
            ("GLD",),
            1_000_000.0,
            {"GLD": 333_333.0},
        )
        self.assertEqual(message, "PASS")
        self.assertEqual(details["share_counts"]["GLD"], 3)
        self.assertAlmostEqual(details["hedge_invested_krw"], 999_999.0)
        self.assertAlmostEqual(details["hedge_cash_left_krw"], 1.0)
        self.assertIn(run_data_pipeline.CASH_TICKER, weights)

    def test_sharpe_from_returns_uses_three_percent_risk_free_rate(self):
        rets = [0.01] * 30 + [-0.002] * 5 + [0.003] * 5
        sharpe = run_data_pipeline.sharpe_from_returns(rets)
        ann_ret = run_data_pipeline.annualized_return_from_returns(rets)
        vol_ann = run_data_pipeline.stdev(rets) * (252 ** 0.5)
        expected = (ann_ret - 0.03) / vol_ann
        self.assertAlmostEqual(sharpe, expected, places=12)

    def test_combo_diversity_ok_rejects_same_bucket_triplet_and_crypto_pair(self):
        universe_map = {
            "IEF": {"ticker": "IEF", "asset_class": "bond_etf", "group_tag": "bond_duration"},
            "TLT": {"ticker": "TLT", "asset_class": "bond_etf", "group_tag": "bond_duration"},
            "SHY": {"ticker": "SHY", "asset_class": "bond_etf", "group_tag": "bond_duration"},
            "BTC-USD": {"ticker": "BTC-USD", "asset_class": "crypto", "group_tag": "large_cap"},
            "ETH-USD": {"ticker": "ETH-USD", "asset_class": "crypto", "group_tag": "large_cap"},
            "GLD": {"ticker": "GLD", "asset_class": "gold_etf", "group_tag": "precious_metal"},
        }
        self.assertFalse(run_data_pipeline.combo_diversity_ok(("IEF", "TLT", "SHY"), universe_map))
        self.assertFalse(run_data_pipeline.combo_diversity_ok(("BTC-USD", "ETH-USD"), universe_map))
        self.assertTrue(run_data_pipeline.combo_diversity_ok(("IEF", "GLD"), universe_map))

    def test_candidate_roles_exclude_conditional_assets_from_default_hedge_mode(self):
        btc_meta = {"ticker": "BTC-USD", "asset_class": "crypto", "is_core_hedge": "Y"}
        shy_meta = {"ticker": "SHY", "asset_class": "bond_etf", "is_core_hedge": "Y"}
        nvda_meta = {"ticker": "NVDA", "asset_class": "us_stock", "is_core_hedge": "N"}

        self.assertEqual(run_data_pipeline.candidate_role(btc_meta), "conditional_candidate")
        self.assertFalse(run_data_pipeline.is_hedge_candidate(btc_meta))
        self.assertTrue(run_data_pipeline.is_hedge_candidate(btc_meta, candidate_mode="all"))
        self.assertEqual(run_data_pipeline.candidate_role(shy_meta), "hedge_candidate")
        self.assertTrue(run_data_pipeline.is_hedge_candidate(shy_meta))
        self.assertEqual(run_data_pipeline.candidate_role(nvda_meta), "conditional_candidate")
        self.assertFalse(run_data_pipeline.is_hedge_candidate(nvda_meta))

    def test_build_asset_sensitivity_rows_records_direction_magnitude_and_tags(self):
        feature_rows = [
            {
                "ticker": "TSLA",
                "asset_class": "us_stock",
                "currency": "USD",
                "beta_sp500_1y_krw": 1.2,
                "downside_beta_sp500_1y_krw": 1.1,
                "corr_sp500_60d_krw": 0.55,
                "corr_kospi200_60d_krw": -0.25,
                "avg_stress_ret_krw": -0.002,
            }
        ]
        universe_map = {
            "TSLA": {
                "ticker": "TSLA",
                "asset_class": "us_stock",
                "group_tag": "large_cap",
                "currency": "USD",
            }
        }

        rows = run_data_pipeline.build_asset_sensitivity_rows(feature_rows, universe_map)
        self.assertEqual(len(rows), len(run_data_pipeline.SENSITIVITY_FACTOR_SPECS))
        market_beta = next(row for row in rows if row["factor"] == "market_beta_sp500")
        kospi_corr = next(row for row in rows if row["factor"] == "corr_kospi200_60d")
        stress = next(row for row in rows if row["factor"] == "stress_response")

        self.assertEqual(market_beta["direction"], "positive")
        self.assertEqual(market_beta["sensitivity_level"], "high")
        self.assertAlmostEqual(market_beta["magnitude"], 1.2)
        self.assertIn("usd_exposure", market_beta["structural_tags"])
        self.assertEqual(kospi_corr["direction"], "negative")
        self.assertEqual(stress["direction"], "negative")
        self.assertAlmostEqual(stress["magnitude"], 0.002)

    def test_evaluate_recommendations_returns_reason_when_candidate_pool_empty(self):
        base_weights_pct = {"TSLA": 100.0}
        ticker_ret_map = {
            "TSLA": {
                "2025-01-01": 0.01,
                "2025-01-02": 0.01,
                "2025-01-03": -0.02,
                "2025-01-06": 0.01,
                "2025-01-07": 0.0,
            },
            "SPY": {
                "2025-01-01": 0.005,
                "2025-01-02": 0.004,
                "2025-01-03": -0.01,
                "2025-01-06": 0.003,
                "2025-01-07": 0.001,
            },
        }
        old_min_obs = dict(run_data_pipeline.MIN_OBS_POLICY)
        try:
            run_data_pipeline.MIN_OBS_POLICY.update(
                {
                    "vol_annual": 2,
                    "mdd_1y": 2,
                    "tail_1y": 2,
                    "beta_overlap": 2,
                    "downside_overlap": 1,
                    "corr_overlap": 2,
                    "adv_60": 1,
                    "portfolio_common_dates": 2,
                }
            )
            result = run_data_pipeline.evaluate_recommendations(
                label_prefix="기준(TSLA 100%)",
                base_weights_pct=base_weights_pct,
                ticker_ret_map=ticker_ret_map,
                spy_ret_map=ticker_ret_map["SPY"],
                stress_dates={"2025-01-03"},
                candidate_pool=[],
                feature_map={},
                dq_map={},
                universe_map={"TSLA": {"ticker": "TSLA", "asset_class": "us_stock", "group_tag": "large_cap"}},
                hedge_budgets_pct=[10.0],
                max_combo_size=2,
                exempt_tickers={"TSLA"},
            )
            self.assertEqual(result["no_recommendation_reason"], "추천 후보군이 비어 있습니다.")
            self.assertEqual(len(result["compare_rows"]), 1)
            self.assertEqual(result["compare_rows"][0]["no_recommendation_reason"], "추천 후보군이 비어 있습니다.")
        finally:
            run_data_pipeline.MIN_OBS_POLICY.clear()
            run_data_pipeline.MIN_OBS_POLICY.update(old_min_obs)

    def test_evaluate_recommendations_returns_fallback_candidate_when_gate_fails(self):
        old_min_obs = dict(run_data_pipeline.MIN_OBS_POLICY)
        try:
            run_data_pipeline.MIN_OBS_POLICY.update(
                {
                    "vol_annual": 2,
                    "mdd_1y": 2,
                    "tail_1y": 2,
                    "beta_overlap": 2,
                    "downside_overlap": 1,
                    "corr_overlap": 2,
                    "adv_60": 1,
                    "portfolio_common_dates": 2,
                }
            )
            ticker_ret_map = {
                "TSLA": {
                    "2025-01-01": 0.01,
                    "2025-01-02": -0.03,
                    "2025-01-03": 0.01,
                    "2025-01-06": -0.03,
                    "2025-01-07": 0.01,
                },
                "BAD": {
                    "2025-01-01": 0.01,
                    "2025-01-02": -0.03,
                    "2025-01-03": 0.01,
                    "2025-01-06": -0.03,
                    "2025-01-07": 0.01,
                },
                "SPY": {
                    "2025-01-01": 0.005,
                    "2025-01-02": -0.01,
                    "2025-01-03": 0.004,
                    "2025-01-06": -0.008,
                    "2025-01-07": 0.003,
                },
            }
            result = run_data_pipeline.evaluate_recommendations(
                label_prefix="기준(TSLA 100%)",
                base_weights_pct={"TSLA": 100.0},
                ticker_ret_map=ticker_ret_map,
                spy_ret_map=ticker_ret_map["SPY"],
                stress_dates={"2025-01-02", "2025-01-06"},
                candidate_pool=[{"ticker": "BAD"}],
                feature_map={"BAD": {"adv_60": 1000.0}},
                dq_map={"BAD": {"status": "PASS"}},
                universe_map={
                    "TSLA": {"ticker": "TSLA", "asset_class": "us_stock", "group_tag": "large_cap"},
                    "BAD": {"ticker": "BAD", "asset_class": "bond_etf", "group_tag": "bond_duration"},
                },
                hedge_budgets_pct=[10.0],
                max_combo_size=1,
                exempt_tickers={"TSLA"},
            )
            self.assertEqual(
                result["no_recommendation_reason"],
                "Gate 통과 후보가 없어 참고안을 표시합니다. 리스크 관리가 어렵습니다.",
            )
            self.assertEqual(len(result["compare_rows"]), 2)
            self.assertTrue(result["compare_rows"][1]["scenario"].startswith("참고안"))
        finally:
            run_data_pipeline.MIN_OBS_POLICY.clear()
            run_data_pipeline.MIN_OBS_POLICY.update(old_min_obs)

    def test_evaluate_recommendations_exact_budget_records_cash_leftover(self):
        old_min_obs = dict(run_data_pipeline.MIN_OBS_POLICY)
        try:
            run_data_pipeline.MIN_OBS_POLICY.update(
                {
                    "vol_annual": 2,
                    "mdd_1y": 2,
                    "tail_1y": 2,
                    "beta_overlap": 2,
                    "downside_overlap": 1,
                    "corr_overlap": 2,
                    "adv_60": 1,
                    "portfolio_common_dates": 2,
                }
            )
            ticker_ret_map = {
                "TSLA": {"2025-01-01": 0.01, "2025-01-02": -0.02, "2025-01-03": 0.015, "2025-01-06": -0.01},
                "IEF": {"2025-01-01": -0.002, "2025-01-02": 0.003, "2025-01-03": 0.004, "2025-01-06": 0.002},
                "SPY": {"2025-01-01": 0.005, "2025-01-02": -0.01, "2025-01-03": 0.004, "2025-01-06": -0.002},
            }
            result = run_data_pipeline.evaluate_recommendations(
                label_prefix="기준(TSLA 100%)",
                base_weights_pct={"TSLA": 100.0},
                ticker_ret_map=ticker_ret_map,
                spy_ret_map=ticker_ret_map["SPY"],
                stress_dates={"2025-01-02"},
                candidate_pool=[{"ticker": "IEF"}],
                feature_map={"IEF": {"adv_60": 1000.0}},
                dq_map={"IEF": {"status": "PASS"}},
                universe_map={
                    "TSLA": {"ticker": "TSLA", "asset_class": "us_stock", "group_tag": "large_cap"},
                    "IEF": {"ticker": "IEF", "asset_class": "bond_etf", "group_tag": "bond_duration"},
                },
                hedge_budgets_pct=[],
                hedge_budgets_krw=[1_000_000.0],
                base_total_krw=10_000_000.0,
                latest_price_map={"IEF": 333_333.0},
                max_combo_size=1,
                exempt_tickers={"TSLA"},
            )
            row = result["single_rows"][0]
            self.assertEqual(row["hedge_budget_krw"], 1_000_000.0)
            self.assertAlmostEqual(row["hedge_cash_left_krw"], 1.0)
            self.assertIn(run_data_pipeline.CASH_TICKER, row["weights_snapshot"])
        finally:
            run_data_pipeline.MIN_OBS_POLICY.clear()
            run_data_pipeline.MIN_OBS_POLICY.update(old_min_obs)

    def test_normalize_rows_for_final_score_keeps_zero_score_as_zero(self):
        rows = [
            {
                "candidate_label": "worst",
                "status": "PASS",
                "cvar_improve_pct": 0.0,
                "mdd_improve_pct": 0.0,
                "stress_improve": 0.0,
                "exposure_improve": 0.0,
                "sharpe_improve": 0.0,
                "combo_min_adv_60": 100.0,
            },
            {
                "candidate_label": "best",
                "status": "PASS",
                "cvar_improve_pct": 10.0,
                "mdd_improve_pct": 10.0,
                "stress_improve": 10.0,
                "exposure_improve": 10.0,
                "sharpe_improve": 10.0,
                "combo_min_adv_60": 200.0,
            },
        ]

        run_data_pipeline.normalize_rows_for_final_score(rows)

        self.assertEqual(rows[0]["final_score"], 0.0)
        self.assertEqual(rows[1]["final_score"], 1.0)

    def test_load_scenario_vector_missing_falls_back_without_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            context = run_data_pipeline.load_scenario_vector(Path(tmp) / "missing.csv")
        self.assertEqual(context["rows"], [])
        self.assertEqual(context["active_rows"], [])
        self.assertIn("fallback", context["summary_ko"])

    def test_load_scenario_vector_auto_selects_max_as_of_date_not_filename(self):
        with tempfile.TemporaryDirectory() as tmp:
            scenario_dir = Path(tmp)
            fieldnames = ["as_of_date", "scenario_code", "scenario_name", "display_state", "score", "confidence", "coverage", "lens"]
            old_path = scenario_dir / "current_scenario_vector_phasef-20260507-smoke.csv"
            new_path = scenario_dir / "current_scenario_vector_latest-20260512-refresh.csv"
            for path, as_of_date, score in [(old_path, "2026-04-14", 80), (new_path, "2026-05-11", 72)]:
                with path.open("w", encoding="utf-8", newline="") as f:
                    writer = csv.DictWriter(f, fieldnames=fieldnames)
                    writer.writeheader()
                    writer.writerow(
                        {
                            "as_of_date": as_of_date,
                            "scenario_code": "soft_landing_goldilocks",
                            "scenario_name": "Soft Landing",
                            "display_state": "ACTIVE",
                            "score": score,
                            "confidence": 80,
                            "coverage": 1.0,
                            "lens": "us_global",
                        }
                    )

            with mock.patch.object(run_data_pipeline, "SCENARIO_VECTOR_DIR", scenario_dir):
                context = run_data_pipeline.load_scenario_vector()

        self.assertEqual(Path(context["path"]).name, new_path.name)
        self.assertEqual(context["as_of_date"], "2026-05-11")
        self.assertEqual(context["selected_by"], "max_as_of_date")
        self.assertEqual(context["candidate_count"], 2)

    def test_load_scenario_vector_explicit_path_overrides_auto_selection(self):
        with tempfile.TemporaryDirectory() as tmp:
            scenario_dir = Path(tmp)
            explicit_path = scenario_dir / "manual.csv"
            with explicit_path.open("w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(
                    f,
                    fieldnames=["as_of_date", "scenario_code", "scenario_name", "display_state", "score", "confidence", "coverage", "lens"],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "as_of_date": "2026-04-14",
                        "scenario_code": "soft_landing_goldilocks",
                        "scenario_name": "Soft Landing",
                        "display_state": "ACTIVE",
                        "score": 70,
                        "confidence": 70,
                        "coverage": 1.0,
                        "lens": "us_global",
                    }
                )

            with mock.patch.object(run_data_pipeline, "SCENARIO_VECTOR_DIR", scenario_dir):
                context = run_data_pipeline.load_scenario_vector(explicit_path)

        self.assertEqual(Path(context["path"]).name, explicit_path.name)
        self.assertEqual(context["selected_by"], "explicit_path")

    def test_scenario_adjustment_penalizes_adverse_vulnerability_increase(self):
        scenario_context = {
            "rows": [
                {
                    "scenario_code": "acute_global_stress_liquidity_crunch",
                    "scenario_name": "Acute Global Stress / Liquidity Crunch",
                    "scenario_name_ko": "급성 리스크오프/유동성 경색장",
                    "display_state": "ACTIVE",
                    "score": 80.0,
                    "confidence": 80.0,
                    "coverage": 1.0,
                    "lens": "us_global",
                }
            ],
        }
        scenario_context["active_rows"] = list(scenario_context["rows"])
        feature_map = {
            "TSLA": {"ticker": "TSLA", "asset_class": "us_stock", "beta_sp500_1y_krw": 1.2, "corr_sp500_60d_krw": 0.7, "avg_stress_ret_krw": -0.02},
            "IEF": {"ticker": "IEF", "asset_class": "bond_etf", "beta_sp500_1y_krw": -0.3, "corr_sp500_60d_krw": -0.4, "avg_stress_ret_krw": 0.004},
        }
        universe_map = {
            "TSLA": {"ticker": "TSLA", "asset_class": "us_stock", "group_tag": "large_cap", "currency": "USD"},
            "IEF": {"ticker": "IEF", "asset_class": "bond_etf", "group_tag": "bond_duration", "currency": "USD"},
        }
        row = run_data_pipeline.scenario_adjustment_row(
            {"TSLA": 1.0},
            {"TSLA": 0.8, "IEF": 0.2},
            feature_map,
            universe_map,
            scenario_context,
            ["IEF"],
        )
        self.assertGreater(row["scenario_vulnerability_reduction"], 0)
        self.assertEqual(row["recommended_role"], "scenario_vulnerability_reducer")

    def test_adverse_scenario_sensitive_candidate_cannot_be_pass_recommend(self):
        scenario_context = {
            "rows": [
                {
                    "scenario_code": "acute_global_stress_liquidity_crunch",
                    "scenario_name": "Acute Global Stress / Liquidity Crunch",
                    "scenario_name_ko": "급성 리스크오프/유동성 경색장",
                    "display_state": "ACTIVE",
                    "score": 85.0,
                    "confidence": 85.0,
                    "coverage": 1.0,
                    "lens": "us_global",
                }
            ],
        }
        scenario_context["active_rows"] = list(scenario_context["rows"])
        feature_map = {
            "IEF": {"ticker": "IEF", "asset_class": "bond_etf", "beta_sp500_1y_krw": -0.3, "corr_sp500_60d_krw": -0.4, "avg_stress_ret_krw": 0.004},
            "BTC-USD": {"ticker": "BTC-USD", "asset_class": "crypto", "beta_sp500_1y_krw": 1.4, "corr_sp500_60d_krw": 0.6, "avg_stress_ret_krw": -0.05},
        }
        universe_map = {
            "IEF": {"ticker": "IEF", "asset_class": "bond_etf", "group_tag": "bond_duration", "currency": "USD"},
            "BTC-USD": {"ticker": "BTC-USD", "asset_class": "crypto", "group_tag": "large_cap", "currency": "USD"},
        }
        row = {
            "status": "PASS",
            "message": "PASS",
            **run_data_pipeline.scenario_adjustment_row(
                {"IEF": 1.0},
                {"IEF": 0.9, "BTC-USD": 0.1},
                feature_map,
                universe_map,
                scenario_context,
                ["BTC-USD"],
            ),
        }
        run_data_pipeline.apply_recommendation_status(row, ["BTC-USD"], {"BTC-USD": {"status": "PASS"}})

        self.assertEqual(row["recommended_role"], "adverse_scenario_sensitive")
        self.assertEqual(row["recommendation_status"], "FAIL_GATE")
        self.assertEqual(row["status"], "FAIL")
        self.assertIn("active adverse scenario", row["gate_fail_reasons"])

    def test_expected_calendar_rows_excludes_us_market_holiday(self):
        start = datetime(2025, 1, 1).date()
        end = datetime(2025, 1, 3).date()
        self.assertEqual(run_data_pipeline.expected_calendar_rows("US", start, end), 2)

    def test_expected_calendar_rows_excludes_krx_holiday(self):
        start = datetime(2025, 1, 27).date()
        end = datetime(2025, 1, 31).date()
        self.assertEqual(run_data_pipeline.expected_calendar_rows("KR", start, end), 1)

    def test_classify_data_quality_splits_non_blocking_calendar_warn(self):
        dq = run_data_pipeline.classify_data_quality(
            miss_rate=0.0,
            coverage_calendar=0.95,
            invalid_price=0,
            duplicate_count=0,
            outlier_count=0,
            fx_missing_count=0,
            total_rows=100,
        )
        self.assertEqual(dq["status"], "WARN")
        self.assertFalse(dq["dq_blocking"])
        self.assertIn("calendar_coverage_warn", dq["dq_reason_codes"])

    def test_non_blocking_dq_warn_does_not_force_reference_only(self):
        row = {
            "status": "PASS",
            "message": "PASS",
            "candidate_role": "hedge_candidate",
            "recommended_role": "scenario_vulnerability_reducer",
        }
        dq_map = {"GLD": {"status": "WARN", "dq_blocking": False, "dq_reason_codes": "calendar_coverage_warn"}}

        run_data_pipeline.apply_recommendation_status(row, ["GLD"], dq_map)

        self.assertEqual(row["recommendation_status"], "PASS_RECOMMEND")
        self.assertIn("DQ WARN non-blocking - GLD", row["dq_warning_reasons"])
        self.assertEqual(row["recommendation_confidence_score"], 0.9)

    def test_blocking_dq_warn_forces_reference_only(self):
        row = {
            "status": "PASS",
            "message": "PASS",
            "candidate_role": "hedge_candidate",
            "recommended_role": "scenario_vulnerability_reducer",
        }
        dq_map = {"GLD": {"status": "FAIL", "dq_blocking": True, "dq_reason_codes": "invalid_price"}}

        run_data_pipeline.apply_recommendation_status(row, ["GLD"], dq_map)

        self.assertEqual(row["recommendation_status"], "REFERENCE_ONLY")
        self.assertIn("DQ BLOCKING - GLD", row["reference_reason"])
        self.assertEqual(row["recommendation_confidence_score"], 0.0)

    def test_asset_scenario_sensitivity_v3_fields_and_evidence_quality(self):
        scenario_context = {
            "rows": [
                {
                    "scenario_code": "acute_global_stress_liquidity_crunch",
                    "scenario_name": "Acute Global Stress / Liquidity Crunch",
                    "scenario_name_ko": "급성 리스크오프/유동성 경색장",
                    "display_state": "ACTIVE",
                    "score": 80.0,
                    "confidence": 80.0,
                    "coverage": 1.0,
                    "lens": "us_global",
                    "as_of_date": "2026-05-07",
                }
            ],
        }
        feature_rows = [
            {
                "ticker": "TSLA",
                "asset_class": "us_stock",
                "beta_sp500_1y_krw": 1.2,
                "downside_beta_sp500_1y_krw": 1.1,
                "corr_sp500_60d_krw": 0.7,
                "corr_kospi200_60d_krw": 0.2,
                "avg_stress_ret_krw": -0.02,
                "sp500_overlap_count": 150,
                "stress_observation_count": 80,
            }
        ]
        universe_map = {
            "TSLA": {"ticker": "TSLA", "asset_class": "us_stock", "group_tag": "large_cap", "currency": "USD"}
        }

        rows = run_data_pipeline.build_asset_scenario_sensitivity_rows(feature_rows, universe_map, scenario_context)

        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["sensitivity_version"], "v3")
        self.assertEqual(row["method"], "rolling_beta")
        self.assertEqual(row["evidence_quality"], "high")
        self.assertEqual(row["direct_metric_count"], 3)
        self.assertEqual(row["sample_count_actual"], 150)
        self.assertEqual(row["source_quality"], "market")
        self.assertEqual(row["beta_stability"], "pass")
        self.assertEqual(row["gate_eligible"], "Y")
        self.assertGreater(row["scenario_context_weight"], 0)
        self.assertGreater(row["scenario_trade_gate_weight"], 0)
        self.assertEqual(row["gate_reason"], "trade-gated adverse scenario with medium/high evidence")
        self.assertIn("scenario_return_beta", row)
        self.assertIn("scenario_downside_beta", row)

    def test_scenario_specific_beta_required_for_high_evidence_on_new_scenario(self):
        scenario_row = {
            "scenario_code": "semiconductor_ai_cycle_shock",
            "scenario_name": "Semiconductor / AI Cycle Shock",
            "scenario_name_ko": "AI·반도체 사이클 충격장",
            "display_state": "ACTIVE",
            "score": 82.0,
            "confidence": 85.0,
            "coverage": 1.0,
            "lens": "korea_semiconductor",
            "as_of_date": "2026-05-07",
        }
        generic_feature = {
            "ticker": "TSLA",
            "asset_class": "us_stock",
            "beta_sp500_1y_krw": 1.4,
            "corr_sp500_60d_krw": 0.8,
            "avg_stress_ret_krw": -0.01,
        }
        direct_feature = {
            **generic_feature,
            "ticker": "NVDA",
            "beta_soxx_1y_krw": 1.6,
            "downside_beta_soxx_1y_krw": 1.8,
            "corr_soxx_60d_krw": 0.9,
            "soxx_overlap_count": 150,
        }

        generic = run_data_pipeline.estimate_asset_scenario_sensitivity(
            generic_feature,
            {"ticker": "TSLA", "asset_class": "us_stock", "currency": "USD"},
            scenario_row,
        )
        direct = run_data_pipeline.estimate_asset_scenario_sensitivity(
            direct_feature,
            {"ticker": "NVDA", "asset_class": "us_stock", "group_tag": "semiconductor", "currency": "USD"},
            scenario_row,
        )

        self.assertNotEqual(generic["evidence_quality"], "high")
        self.assertEqual(direct["method"], "rolling_beta")
        self.assertEqual(direct["evidence_quality"], "high")
        self.assertEqual(direct["scenario_return_beta"], 1.6)
        self.assertEqual(direct["scenario_downside_beta"], 1.8)

    def test_seed_source_quality_caps_high_evidence(self):
        scenario_row = {
            "scenario_code": "korea_domestic_financial_stress",
            "display_state": "ACTIVE",
            "score": 82.0,
            "confidence": 90.0,
            "coverage": 1.0,
            "source_quality": "seed",
            "as_of_date": "2026-05-07",
        }
        feature = {
            "ticker": "EWY",
            "asset_class": "us_stock",
            "beta_ks200_1y_krw": 1.1,
            "downside_beta_ks200_1y_krw": 1.0,
            "beta_usdkrw_1y": 0.5,
            "beta_kr_financial_basket_1y_krw": 0.8,
            "corr_kospi200_60d_krw": 0.7,
            "ks200_overlap_count": 180,
            "usdkrw_overlap_count": 180,
            "kr_financial_overlap_count": 180,
        }

        estimate = run_data_pipeline.estimate_asset_scenario_sensitivity(
            feature,
            {"ticker": "EWY", "asset_class": "us_stock", "currency": "USD"},
            scenario_row,
        )

        self.assertEqual(estimate["source_quality"], "seed")
        self.assertEqual(estimate["event_or_seed_dependent"], "Y")
        self.assertEqual(estimate["beta_stability"], "pass")
        self.assertEqual(estimate["evidence_quality"], "medium")
        self.assertEqual(estimate["gate_eligible"], "N")
        self.assertEqual(estimate["scenario_trade_gate_weight"], 0.0)
        self.assertIn("source_quality=seed", estimate["gate_reason"])

    def test_watch_and_manual_scenarios_are_context_not_trade_gate(self):
        watch_row = {
            "scenario_code": "acute_global_stress_liquidity_crunch",
            "display_state": "WATCH",
            "score": 58.0,
            "confidence": 80.0,
            "coverage": 1.0,
            "source_quality": "market",
        }
        manual_row = {
            "scenario_code": "geopolitical_escalation_supply_shock",
            "display_state": "ACTIVE",
            "score": 75.0,
            "confidence": 80.0,
            "coverage": 1.0,
            "source_quality": "manual",
        }
        stress_row = {
            "scenario_code": "usd_strength_krw_weakness",
            "display_state": "STRESS",
            "score": 70.0,
            "confidence": 70.0,
            "coverage": 0.95,
            "source_quality": "market",
        }

        self.assertGreater(run_data_pipeline.scenario_activation_weight(watch_row), 0)
        self.assertEqual(run_data_pipeline.scenario_trade_gate_weight(watch_row), 0.0)
        self.assertIn("WATCH", run_data_pipeline.scenario_trade_gate_reason(watch_row))
        self.assertGreater(run_data_pipeline.scenario_activation_weight(manual_row), 0)
        self.assertEqual(run_data_pipeline.scenario_trade_gate_weight(manual_row), 0.0)
        self.assertIn("source_quality=manual", run_data_pipeline.scenario_trade_gate_reason(manual_row))
        self.assertGreater(run_data_pipeline.scenario_trade_gate_weight(stress_row), 0)
        active_codes = run_data_pipeline.active_scenario_codes({"rows": [watch_row, manual_row, stress_row]})
        self.assertEqual(active_codes, {"usd_strength_krw_weakness"})

    def test_raw_off_scenario_has_zero_activation_even_if_display_provisional(self):
        row = {
            "scenario_code": "korea_domestic_financial_stress",
            "raw_state": "OFF",
            "display_state": "PROVISIONAL",
            "score": 80.0,
            "confidence": 80.0,
            "coverage": 1.0,
        }

        self.assertEqual(run_data_pipeline.scenario_activation_weight(row), 0.0)
        self.assertNotIn(
            "korea_domestic_financial_stress",
            run_data_pipeline.active_scenario_codes({"rows": [row]}),
        )

    def test_asset_scenario_sensitivity_matrix_expands_to_ten_scenarios(self):
        scenario_codes = [
            "soft_landing_goldilocks",
            "slowdown_recession_deflation_risk",
            "higher_for_longer_long_rate_shock",
            "stagflation_reinflation_energy_shock",
            "usd_strength_krw_weakness",
            "acute_global_stress_liquidity_crunch",
            "china_trade_fragmentation_shock",
            "semiconductor_ai_cycle_shock",
            "korea_domestic_financial_stress",
            "geopolitical_escalation_supply_shock",
        ]
        scenario_context = {
            "rows": [
                {
                    "scenario_code": code,
                    "scenario_name": code,
                    "scenario_name_ko": code,
                    "display_state": "ACTIVE",
                    "score": 80.0,
                    "confidence": 80.0,
                    "coverage": 1.0,
                    "lens": "test",
                }
                for code in scenario_codes
            ]
        }
        feature_rows = [
            {
                "ticker": f"T{idx:02d}",
                "asset_class": "us_stock",
                "beta_sp500_1y_krw": 1.0,
                "downside_beta_sp500_1y_krw": 1.0,
                "corr_sp500_60d_krw": 0.7,
            }
            for idx in range(70)
        ]
        universe_map = {
            row["ticker"]: {"ticker": row["ticker"], "asset_class": "us_stock", "currency": "USD"}
            for row in feature_rows
        }

        rows = run_data_pipeline.build_asset_scenario_sensitivity_rows(feature_rows, universe_map, scenario_context)

        self.assertEqual(len(rows), 700)
        self.assertEqual({row["scenario_code"] for row in rows}, set(scenario_codes))

    def test_asset_scenario_visualization_includes_all_scenarios_and_badges(self):
        scenario_codes = [
            "soft_landing_goldilocks",
            "slowdown_recession_deflation_risk",
            "higher_for_longer_long_rate_shock",
            "stagflation_reinflation_energy_shock",
            "usd_strength_krw_weakness",
            "acute_global_stress_liquidity_crunch",
            "china_trade_fragmentation_shock",
            "semiconductor_ai_cycle_shock",
            "korea_domestic_financial_stress",
            "geopolitical_escalation_supply_shock",
        ]
        scenario_context = {
            "rows": [
                {
                    "scenario_code": code,
                    "scenario_name": code,
                    "scenario_name_ko": code,
                    "display_state": "ACTIVE" if idx in (2, 5) else "REFERENCE",
                    "score": 80.0 if idx in (2, 5) else 20.0,
                    "confidence": 80.0,
                    "coverage": 1.0,
                    "lens": "test",
                }
                for idx, code in enumerate(scenario_codes)
            ],
        }
        scenario_context["active_rows"] = [
            row for row in scenario_context["rows"] if row["display_state"] == "ACTIVE"
        ]
        rows = []
        for ticker, asset_class, beta_sign in [("TSLA", "us_stock", 1.0), ("IEF", "bond_etf", -1.0)]:
            for idx, code in enumerate(scenario_codes):
                rows.append(
                    {
                        "ticker": ticker,
                        "asset_class": asset_class,
                        "scenario_code": code,
                        "scenario_name": code,
                        "scenario_name_ko": code,
                        "lens": "test",
                        "scenario_beta": beta_sign * (idx + 1) / 10.0,
                        "method": "rolling_beta",
                        "evidence_quality": "high" if idx < 3 else "medium",
                        "gate_eligible": "Y" if idx == 5 else "N",
                    }
                )

        with tempfile.TemporaryDirectory() as tmp:
            html_path = Path(tmp) / "visual.html"
            run_data_pipeline.write_asset_scenario_sensitivity_visualization(
                html_path,
                "test-run",
                "test-data",
                scenario_context,
                rows,
            )
            html = html_path.read_text(encoding="utf-8")

        for code in scenario_codes:
            self.assertIn(code, html)
        self.assertIn("All scenario heatmap", html)
        self.assertIn("ACTIVE", html)
        self.assertIn("ADVERSE", html)
        self.assertIn("Total scenarios", html)

    def test_scenario_adjustment_returns_vulnerability_fields_without_vector(self):
        row = run_data_pipeline.scenario_adjustment_row(
            {"TSLA": 1.0},
            {"TSLA": 0.9, "IEF": 0.1},
            {},
            {
                "TSLA": {"ticker": "TSLA", "asset_class": "us_stock"},
                "IEF": {"ticker": "IEF", "asset_class": "bond_etf"},
            },
            {"rows": [], "summary_ko": "시나리오 벡터 없음"},
            ["IEF"],
        )

        for field in [
            "base_scenario_vulnerability",
            "proposed_scenario_vulnerability",
            "base_gate_vulnerability",
            "proposed_gate_vulnerability",
            "scenario_vulnerability_delta",
            "gate_vulnerability_delta",
        ]:
            self.assertIn(field, row)
            self.assertIsNone(row[field])

    def test_recommendation_status_qa_report_counts_statuses(self):
        portfolio_result = {
            "errors": [],
            "single_rows": [
                {
                    "candidate_ticker": "TLT",
                    "status": "PASS",
                    "recommendation_status": "PASS_RECOMMEND",
                    "candidate_role": "hedge_candidate",
                    "candidate_bucket": "bond",
                    "final_score": 0.9,
                    "cvar_improve_pct": 12.0,
                    "mdd_improve_pct": 8.0,
                    "stress_improve": 0.01,
                    "scenario_vulnerability_reduction": 0.2,
                    "annual_return_improve_pct": -2.0,
                    "sharpe_improve_pct": 1.0,
                    "dq_penalty": 0.0,
                    "scenario_vulnerability_delta": -0.1,
                    "gate_vulnerability_delta": -0.1,
                },
                {
                    "candidate_ticker": "BTC-USD",
                    "status": "FAIL",
                    "recommendation_status": "FAIL_GATE",
                    "candidate_role": "conditional_candidate",
                    "gate_fail_reasons": "active adverse scenario",
                    "scenario_vulnerability_delta": 0.2,
                    "gate_vulnerability_delta": 0.2,
                },
                {
                    "candidate_ticker": "GLD",
                    "status": "PASS",
                    "recommendation_status": "REFERENCE_ONLY",
                    "candidate_role": "hedge_candidate",
                    "reference_reason": "DQ WARN: coverage warning",
                },
            ],
            "multi_rows": [],
        }
        with tempfile.TemporaryDirectory() as tmp:
            qa_path = Path(tmp) / "recommendation_status_qa.md"
            run_data_pipeline.write_recommendation_status_qa(
                qa_path,
                "qa-run",
                portfolio_result,
                None,
                {"errors": [], "single_rows": [], "multi_rows": []},
            )
            text = qa_path.read_text(encoding="utf-8")

        self.assertIn("FAIL_GATE 1", text)
        self.assertIn("REFERENCE_ONLY 1", text)
        self.assertIn("PASS_RECOMMEND 1", text)
        self.assertIn("INSUFFICIENT_DATA 0", text)
        self.assertIn("HedgeMate Pre-Backtest Candidate QA", text)
        self.assertIn("formal_recommendation_gate: post_backtest_required", text)
        self.assertIn("Status Bucket Summary (Pre-Backtest Candidate Labels)", text)
        self.assertIn("| INSUFFICIENT_DATA | - | - | - | - | no rows in this run |", text)
        self.assertIn("DQ WARN affected rows: 1", text)
        self.assertIn("active adverse scenario", text)
        self.assertIn("Top Pre-Backtest PASS Candidate Audit", text)
        self.assertIn("Representative Pre-Backtest PASS Candidates by Bucket", text)
        self.assertIn("return drag", text)
        self.assertIn("TLT", text)

    def test_grid_allocations_include_non_equal_weights_for_multi_combo(self):
        allocations = run_data_pipeline.generate_grid_allocations(("TLT", "GLD"), 0.10)
        allocation_weights = [row["allocation_weights"] for row in allocations]

        self.assertTrue(any(weights["TLT"] != weights["GLD"] for weights in allocation_weights))
        self.assertTrue(all(row["allocation_method"] == "grid_scenario_risk" for row in allocations))

    def test_input_aware_prefilter_changes_ranking_by_base_asset(self):
        feature_rows = [
            {"ticker": "TSLA", "asset_class": "us_stock", "beta_sp500_1y_krw": 1.5, "downside_beta_sp500_1y_krw": 1.6, "corr_sp500_60d_krw": 0.8, "corr_kospi200_60d_krw": 0.2, "avg_stress_ret_krw": -0.04, "cvar_95_1y_krw": -0.07, "sharpe_1y_krw_proxy": 0.1, "adv_60": 100.0},
            {"ticker": "005930.KS", "asset_class": "kr_stock", "beta_sp500_1y_krw": 0.8, "downside_beta_sp500_1y_krw": 0.9, "corr_sp500_60d_krw": 0.5, "corr_kospi200_60d_krw": 0.9, "avg_stress_ret_krw": -0.03, "cvar_95_1y_krw": -0.05, "sharpe_1y_krw_proxy": 0.1, "adv_60": 100.0},
            {"ticker": "USO", "asset_class": "commodity_etf", "beta_sp500_1y_krw": 0.6, "downside_beta_sp500_1y_krw": 0.8, "corr_sp500_60d_krw": 0.4, "corr_kospi200_60d_krw": 0.1, "avg_stress_ret_krw": -0.02, "cvar_95_1y_krw": -0.09, "sharpe_1y_krw_proxy": 0.05, "adv_60": 100.0},
            {"ticker": "TLT", "asset_class": "bond_etf", "beta_sp500_1y_krw": -0.4, "downside_beta_sp500_1y_krw": -0.2, "corr_sp500_60d_krw": -0.5, "corr_kospi200_60d_krw": -0.2, "avg_stress_ret_krw": 0.01, "cvar_95_1y_krw": -0.01, "sharpe_1y_krw_proxy": 0.3, "adv_60": 100.0},
            {"ticker": "GLD", "asset_class": "gold_etf", "beta_sp500_1y_krw": 0.0, "downside_beta_sp500_1y_krw": 0.1, "corr_sp500_60d_krw": 0.0, "corr_kospi200_60d_krw": 0.0, "avg_stress_ret_krw": 0.005, "cvar_95_1y_krw": -0.015, "sharpe_1y_krw_proxy": 0.25, "adv_60": 100.0},
            {"ticker": "XLP", "asset_class": "etf", "beta_sp500_1y_krw": 0.2, "downside_beta_sp500_1y_krw": 0.2, "corr_sp500_60d_krw": 0.2, "corr_kospi200_60d_krw": 0.1, "avg_stress_ret_krw": 0.0, "cvar_95_1y_krw": -0.02, "sharpe_1y_krw_proxy": 0.2, "adv_60": 100.0},
        ]
        universe_map = {
            "TSLA": {"ticker": "TSLA", "asset_class": "us_stock", "group_tag": "large_cap", "currency": "USD", "region": "US", "is_core_hedge": "N"},
            "005930.KS": {"ticker": "005930.KS", "asset_class": "kr_stock", "group_tag": "large_cap", "currency": "KRW", "region": "KR", "is_core_hedge": "N"},
            "USO": {"ticker": "USO", "asset_class": "commodity_etf", "group_tag": "oil", "currency": "USD", "region": "US", "is_core_hedge": "Y"},
            "TLT": {"ticker": "TLT", "asset_class": "bond_etf", "group_tag": "bond_duration", "currency": "USD", "region": "US", "is_core_hedge": "Y"},
            "GLD": {"ticker": "GLD", "asset_class": "gold_etf", "group_tag": "precious_metal", "currency": "USD", "region": "US", "is_core_hedge": "Y"},
            "XLP": {"ticker": "XLP", "asset_class": "etf", "group_tag": "defensive_sector", "currency": "USD", "region": "US", "is_core_hedge": "Y"},
        }
        dq_rows = [{"ticker": row["ticker"], "status": "PASS"} for row in feature_rows]
        scenario_context = {
            "rows": [
                {
                    "scenario_code": "acute_global_stress_liquidity_crunch",
                    "scenario_name": "stress",
                    "scenario_name_ko": "stress",
                    "display_state": "ACTIVE",
                    "score": 80.0,
                    "confidence": 80.0,
                    "coverage": 1.0,
                }
            ],
        }
        scenario_context["active_rows"] = list(scenario_context["rows"])

        tsla_order = tuple(row["ticker"] for row in run_data_pipeline.build_input_aware_candidate_prefilter_rows({"TSLA": 100.0}, feature_rows, dq_rows, universe_map, scenario_context)[:4])
        samsung_order = tuple(row["ticker"] for row in run_data_pipeline.build_input_aware_candidate_prefilter_rows({"005930.KS": 100.0}, feature_rows, dq_rows, universe_map, scenario_context)[:4])
        uso_order = tuple(row["ticker"] for row in run_data_pipeline.build_input_aware_candidate_prefilter_rows({"USO": 100.0}, feature_rows, dq_rows, universe_map, scenario_context)[:4])

        self.assertNotEqual(tsla_order, samsung_order)
        self.assertNotEqual(tsla_order, uso_order)

    def test_build_candidate_prefilter_rows_keeps_candidates_with_missing_metrics(self):
        rows = run_data_pipeline.build_candidate_prefilter_rows(
            feature_rows=[
                {
                    "ticker": "GLD",
                    "asset_class": "gold_etf",
                    "cvar_95_1y_krw": None,
                    "corr_sp500_60d_krw": None,
                    "avg_stress_ret_krw": None,
                    "sharpe_1y_krw_proxy": None,
                    "adv_60": None,
                }
            ],
            dq_rows=[{"ticker": "GLD", "status": "WARN"}],
            universe_map={"GLD": {"ticker": "GLD", "asset_class": "gold_etf", "group_tag": "precious_metal"}},
        )

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["ticker"], "GLD")
        self.assertIn("hes_score", rows[0])

    def test_risk_bucket_mode_adds_scenario_specific_conditional_candidates(self):
        feature_rows = [
            {
                "ticker": "GLD",
                "asset_class": "gold_etf",
                "cvar_95_1y_krw": -0.05,
                "corr_sp500_60d_krw": -0.2,
                "avg_stress_ret_krw": 0.01,
                "sharpe_1y_krw_proxy": 0.6,
                "adv_60": 100.0,
            },
            {
                "ticker": "ITA",
                "asset_class": "etf",
                "cvar_95_1y_krw": -0.06,
                "corr_sp500_60d_krw": 0.1,
                "avg_stress_ret_krw": 0.0,
                "sharpe_1y_krw_proxy": 0.4,
                "adv_60": 80.0,
            },
        ]
        dq_rows = [{"ticker": "GLD", "status": "PASS"}, {"ticker": "ITA", "status": "PASS"}]
        universe_map = {
            "GLD": {"ticker": "GLD", "asset_class": "gold_etf", "group_tag": "precious_metal", "is_core_hedge": "Y"},
            "ITA": {"ticker": "ITA", "asset_class": "etf", "group_tag": "defense_sector", "candidate_role": "diagnostic_only"},
        }
        scenario_context = {
            "rows": [
                {
                    "scenario_code": "acute_global_stress_liquidity_crunch",
                    "display_state": "ACTIVE",
                    "score": 80.0,
                    "confidence": 80.0,
                    "coverage": 1.0,
                }
            ]
        }
        scenario_context["active_rows"] = list(scenario_context["rows"])

        hedge_only = run_data_pipeline.build_candidate_prefilter_rows(feature_rows, dq_rows, universe_map)
        risk_bucket = run_data_pipeline.build_candidate_prefilter_rows(
            feature_rows,
            dq_rows,
            universe_map,
            candidate_mode="risk-bucket",
            scenario_context=scenario_context,
        )

        self.assertEqual({row["ticker"] for row in hedge_only}, {"GLD"})
        self.assertEqual({row["ticker"] for row in risk_bucket}, {"GLD", "ITA"})
        gld_row = next(row for row in risk_bucket if row["ticker"] == "GLD")
        ita_row = next(row for row in risk_bucket if row["ticker"] == "ITA")
        self.assertIn("acute_global_stress_liquidity_crunch", gld_row["risk_bucket_match"])
        self.assertIn("acute_global_stress_liquidity_crunch", ita_row["risk_bucket_match"])

        watch_context = {
            "rows": [
                {
                    "scenario_code": "acute_global_stress_liquidity_crunch",
                    "display_state": "WATCH",
                    "score": 80.0,
                    "confidence": 80.0,
                    "coverage": 1.0,
                }
            ]
        }
        watch_context["active_rows"] = list(watch_context["rows"])
        watch_bucket = run_data_pipeline.build_candidate_prefilter_rows(
            feature_rows,
            dq_rows,
            universe_map,
            candidate_mode="risk-bucket",
            scenario_context=watch_context,
        )
        self.assertEqual({row["ticker"] for row in watch_bucket}, {"GLD"})

    def test_evaluate_gate_soft_return_drag_marks_reference_reason(self):
        base_metrics = {
            "cvar_95_krw": -0.10,
            "mdd_krw": -0.20,
            "stress_avg_ret_krw": -0.03,
            "corr_sp500_krw": 0.60,
            "beta_sp500_krw": 1.00,
            "sharpe_krw_proxy": 1.00,
            "annual_return_krw": 0.20,
            "downside_beta_sp500_krw": 1.00,
            "corr_kospi200_krw": 0.20,
        }
        proposed_metrics = {
            "cvar_95_krw": -0.09,
            "mdd_krw": -0.19,
            "stress_avg_ret_krw": -0.02,
            "corr_sp500_krw": 0.50,
            "beta_sp500_krw": 0.90,
            "sharpe_krw_proxy": 0.98,
            "annual_return_krw": 0.185,
            "downside_beta_sp500_krw": 0.90,
            "corr_kospi200_krw": 0.15,
        }
        result = run_data_pipeline.evaluate_gate(
            base_metrics,
            proposed_metrics,
            ["GLD"],
            {"GLD": {"adv_60": 100.0}},
            {"GLD": {"status": "PASS"}},
        )

        self.assertEqual(result["status"], "PASS")
        self.assertIn("annual return drag soft warning", result["reference_reason"])

    def test_main_generates_single_asset_outputs_from_cached_data(self):
        fixed_now = datetime(2026, 3, 10, 0, 0, 0, tzinfo=timezone.utc)
        run_id = "20260310T000000000000-deadbeef"
        data_version = "20260310"
        start_date = datetime(2025, 1, 1).date()
        ingested_at = fixed_now.isoformat()

        universe_rows = [
            ["TSLA", "us_stock", "US", "large_cap", "USD", "SP500", "N"],
            ["AAPL", "us_stock", "US", "large_cap", "USD", "SP500", "N"],
            ["MSFT", "us_stock", "US", "large_cap", "USD", "SP500", "N"],
            ["NVDA", "us_stock", "US", "large_cap", "USD", "SP500", "N"],
            ["005930.KS", "kr_stock", "KR", "large_cap", "KRW", "KOSPI200", "N"],
            ["SPY", "etf", "US", "equity_index", "USD", "SP500", "N"],
            ["IEF", "bond_etf", "US", "bond_duration", "USD", "US_TREASURY", "Y"],
            ["SHY", "bond_etf", "US", "bond_short", "USD", "US_TREASURY", "Y"],
            ["GLD", "gold_etf", "US", "precious_metal", "USD", "GOLD", "Y"],
            ["XLP", "etf", "US", "defensive_sector", "USD", "SP500_SECTOR", "Y"],
            ["BTC-USD", "crypto", "CRYPTO", "large_cap", "USD", "CRYPTO_MARKET", "Y"],
            ["ETH-USD", "crypto", "CRYPTO", "large_cap", "USD", "CRYPTO_MARKET", "Y"],
        ]

        def spy_ret(i):
            if 12 <= i < 20:
                return -0.02
            if i % 7 == 0:
                return 0.004
            return 0.001

        def tsla_ret(i):
            return 1.8 * spy_ret(i) + (0.008 if i % 9 == 0 else -0.002)

        def aapl_ret(i):
            return 1.1 * spy_ret(i) + 0.0008

        def msft_ret(i):
            return 1.0 * spy_ret(i) + 0.0007

        def nvda_ret(i):
            return 1.5 * spy_ret(i) + 0.0015

        def samsung_ret(i):
            return 0.7 * spy_ret(i) + 0.0005

        def ief_ret(i):
            if 12 <= i < 20:
                return 0.018
            return 0.0012

        def shy_ret(i):
            if 12 <= i < 20:
                return 0.008
            return 0.0005

        def gld_ret(i):
            if 12 <= i < 20:
                return 0.014
            return 0.0009

        def xlp_ret(i):
            return 0.35 * spy_ret(i) + 0.0006

        def btc_ret(i):
            if i % 10 == 0:
                return 0.03
            if i % 6 == 0:
                return -0.02
            return 1.2 * spy_ret(i) + 0.002

        def eth_ret(i):
            if i % 11 == 0:
                return 0.035
            if i % 5 == 0:
                return -0.025
            return 1.4 * spy_ret(i) + 0.002

        market_defs = {
            "TSLA": ("us_stock", "USD", generate_price_rows(start_date, 75, 100.0, tsla_ret)),
            "AAPL": ("us_stock", "USD", generate_price_rows(start_date, 75, 120.0, aapl_ret)),
            "MSFT": ("us_stock", "USD", generate_price_rows(start_date, 75, 130.0, msft_ret)),
            "NVDA": ("us_stock", "USD", generate_price_rows(start_date, 75, 90.0, nvda_ret)),
            "005930.KS": ("kr_stock", "KRW", generate_price_rows(start_date, 75, 70_000.0, samsung_ret)),
            "SPY": ("etf", "USD", generate_price_rows(start_date, 75, 400.0, spy_ret)),
            "IEF": ("bond_etf", "USD", generate_price_rows(start_date, 75, 100.0, ief_ret)),
            "SHY": ("bond_etf", "USD", generate_price_rows(start_date, 75, 90.0, shy_ret)),
            "GLD": ("gold_etf", "USD", generate_price_rows(start_date, 75, 180.0, gld_ret)),
            "XLP": ("etf", "USD", generate_price_rows(start_date, 75, 70.0, xlp_ret)),
            "BTC-USD": ("crypto", "USD", generate_price_rows(start_date, 75, 30_000.0, btc_ret, include_weekends=True)),
            "ETH-USD": ("crypto", "USD", generate_price_rows(start_date, 75, 2_000.0, eth_ret, include_weekends=True)),
        }

        ks200_rows = generate_price_rows(start_date, 75, 300.0, lambda i: 0.9 * spy_ret(i) + 0.0003)
        fx_rows = []
        for offset in range(75):
            dt = start_date + timedelta(days=offset)
            if dt.weekday() >= 5:
                continue
            fx_rows.append(
                {
                    "date": dt.isoformat(),
                    "ticker": run_data_pipeline.FX_TICKER,
                    "close": 1300.0 + (offset % 5),
                    "source": "yahoo",
                    "currency": "KRW",
                    "ingested_at": ingested_at,
                }
            )

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            docs_root = tmp_path / "docs" / "STEP_1"
            output_raw = tmp_path / "outputs" / "raw"
            output_processed = tmp_path / "outputs" / "processed"
            output_reports = tmp_path / "outputs" / "reports"
            doc_result_dir = docs_root / "04_실행결과"
            meta_path = docs_root / "01_개요" / "03_자산유니버스_메타_v1.csv"
            meta_path.parent.mkdir(parents=True, exist_ok=True)
            doc_result_dir.mkdir(parents=True, exist_ok=True)
            output_raw.mkdir(parents=True, exist_ok=True)

            with meta_path.open("w", encoding="utf-8", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["ticker", "asset_class", "region", "group_tag", "currency", "benchmark_group", "is_core_hedge"])
                writer.writerows(universe_rows)

            market_raw_rows = []
            for ticker, (asset_class, currency, rows) in market_defs.items():
                for row in rows:
                    market_raw_rows.append(
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
            write_market_raw(output_raw / f"raw_market_daily_{data_version}.csv", sorted(market_raw_rows, key=lambda x: (x["ticker"], x["date"])))
            write_fx_raw(output_raw / f"raw_fx_daily_{data_version}.csv", fx_rows)

            old_min_obs = dict(run_data_pipeline.MIN_OBS_POLICY)
            try:
                run_data_pipeline.UNIVERSE_META = meta_path
                run_data_pipeline.OUTPUT_RAW_DIR = output_raw
                run_data_pipeline.OUTPUT_PROCESSED_DIR = output_processed
                run_data_pipeline.OUTPUT_REPORT_DIR = output_reports
                run_data_pipeline.DOC_RESULT_DIR = doc_result_dir
                run_data_pipeline.MIN_OBS_POLICY.update(
                    {
                        "vol_annual": 5,
                        "mdd_1y": 5,
                        "tail_1y": 10,
                        "beta_overlap": 10,
                        "downside_overlap": 5,
                        "corr_overlap": 5,
                        "adv_60": 5,
                        "portfolio_common_dates": 10,
                    }
                )

                portfolio_path = tmp_path / "inputs" / "portfolio_weights.csv"
                portfolio_path.parent.mkdir(parents=True, exist_ok=True)
                with portfolio_path.open("w", encoding="utf-8", newline="") as f:
                    writer = csv.writer(f)
                    writer.writerow(["ticker", "weight_pct"])
                    writer.writerow(["TSLA", 20])
                    writer.writerow(["AAPL", 20])
                    writer.writerow(["MSFT", 20])
                    writer.writerow(["NVDA", 20])
                    writer.writerow(["005930.KS", 20])

                def fake_load_portfolio_input(_universe_map, _input_path=None):
                    return portfolio_path, {"TSLA": 20.0, "AAPL": 20.0, "MSFT": 20.0, "NVDA": 20.0, "005930.KS": 20.0}

                def fake_fetch_yahoo_chart(ticker, period1, period2, retries=5):
                    del period1, period2, retries
                    if ticker == "^KS200":
                        return ks200_rows
                    if ticker == "^KS11":
                        return []
                    raise AssertionError(f"Unexpected fetch for ticker={ticker}")

                with mock.patch.object(run_data_pipeline, "now_utc", return_value=fixed_now), \
                     mock.patch.object(run_data_pipeline, "load_portfolio_input", side_effect=fake_load_portfolio_input), \
                     mock.patch.object(run_data_pipeline, "fetch_yahoo_chart", side_effect=fake_fetch_yahoo_chart):
                    run_data_pipeline.main(["--single-asset", "TSLA", "--hedge-budgets", "10,20", "--max-combo-size", "3", "--run-id", run_id])

                feature_csv = output_processed / f"features_summary_{run_id}.csv"
                self.assertTrue(feature_csv.exists())
                with feature_csv.open(encoding="utf-8", newline="") as f:
                    reader = csv.DictReader(f)
                    rows = list(reader)
                self.assertIn("annual_return_1y_krw", reader.fieldnames)
                self.assertIn("sharpe_1y_krw_proxy", reader.fieldnames)
                tsla_row = next(row for row in rows if row["ticker"] == "TSLA")
                self.assertNotEqual(tsla_row["sharpe_1y_krw_proxy"], "")

                sensitivity_csv = output_processed / f"asset_risk_sensitivity_{run_id}.csv"
                self.assertTrue(sensitivity_csv.exists())
                with sensitivity_csv.open(encoding="utf-8", newline="") as f:
                    reader = csv.DictReader(f)
                    sensitivity_rows = list(reader)
                self.assertIn("direction", reader.fieldnames)
                self.assertIn("magnitude", reader.fieldnames)
                self.assertIn("sensitivity_level", reader.fieldnames)
                self.assertTrue(any(row["ticker"] == "TSLA" and row["factor"] == "market_beta_sp500" for row in sensitivity_rows))

                sensitivity_md = output_reports / f"asset_sensitivity_summary_{run_id}.md"
                self.assertTrue(sensitivity_md.exists())
                summary_text = sensitivity_md.read_text(encoding="utf-8")
                self.assertIn("현재 run에서 사용한 정량 민감도 축", summary_text)
                self.assertIn("direction", summary_text)

                scenario_sensitivity_csv = output_processed / f"asset_scenario_sensitivity_{run_id}.csv"
                self.assertTrue(scenario_sensitivity_csv.exists())
                with scenario_sensitivity_csv.open(encoding="utf-8", newline="") as f:
                    reader = csv.DictReader(f)
                    self.assertIn("scenario_beta", reader.fieldnames)
                    self.assertIn("recommended_role", reader.fieldnames)

                single_compare = output_reports / f"single_asset_compare_{run_id}.csv"
                self.assertTrue(single_compare.exists())
                with single_compare.open(encoding="utf-8", newline="") as f:
                    reader = csv.DictReader(f)
                    compare_rows = list(reader)
                self.assertGreaterEqual(len(compare_rows), 2)
                self.assertIn("sharpe_krw_proxy", reader.fieldnames)
                self.assertIn("no_recommendation_reason", reader.fieldnames)

                single_1to1 = output_reports / f"single_asset_hedge_1to1_{run_id}.csv"
                with single_1to1.open(encoding="utf-8", newline="") as f:
                    reader = csv.DictReader(f)
                    self.assertIn("scenario_reason_ko", reader.fieldnames)
                    self.assertIn("recommended_role", reader.fieldnames)
                    self.assertIn("candidate_role", reader.fieldnames)
                    self.assertIn("candidate_role_reason_ko", reader.fieldnames)

                single_multi = output_reports / f"single_asset_hedge_multi_{run_id}.csv"
                self.assertTrue(single_multi.exists())
                with single_multi.open(encoding="utf-8", newline="") as f:
                    reader = csv.DictReader(f)
                    multi_rows = list(reader)
                self.assertIn("candidate_role", reader.fieldnames)
                self.assertIn("candidate_role_reason_ko", reader.fieldnames)
                self.assertTrue(any(row["combo_size"] == "2" for row in multi_rows))
                self.assertTrue(any(row["status"] == "PASS" for row in multi_rows))

                portfolio_compare = output_reports / f"portfolio_compare_{run_id}.csv"
                self.assertTrue(portfolio_compare.exists())
                with portfolio_compare.open(encoding="utf-8", newline="") as f:
                    reader = csv.DictReader(f)
                    portfolio_rows = list(reader)
                self.assertGreaterEqual(len(portfolio_rows), 2)

                benchmark_raw = output_raw / f"raw_benchmark_daily_{data_version}.csv"
                self.assertTrue(benchmark_raw.exists())
            finally:
                run_data_pipeline.MIN_OBS_POLICY.clear()
                run_data_pipeline.MIN_OBS_POLICY.update(old_min_obs)

    def test_main_falls_back_to_latest_cached_snapshot_when_today_cache_missing(self):
        fixed_now = datetime(2026, 3, 18, 0, 0, 0, tzinfo=timezone.utc)
        run_id = "offline-fallback"
        cached_version = "20260311"
        start_date = datetime(2025, 1, 1, tzinfo=timezone.utc).date()
        ingested_at = "2026-03-11T00:00:00+00:00"

        def stock_ret(obs_idx):
            if obs_idx % 17 == 0:
                return -0.02
            if obs_idx % 7 == 0:
                return 0.012
            return 0.004

        def hedge_ret(obs_idx):
            if obs_idx % 17 == 0:
                return 0.004
            if obs_idx % 7 == 0:
                return 0.001
            return 0.0006

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            docs_root = tmp_path / "docs" / "STEP_1"
            output_raw = tmp_path / "outputs" / "raw"
            output_processed = tmp_path / "outputs" / "processed"
            output_reports = tmp_path / "outputs" / "reports"
            doc_result_dir = docs_root / "04_실행결과"
            meta_path = docs_root / "01_개요" / "03_자산유니버스_메타_v1.csv"
            meta_path.parent.mkdir(parents=True, exist_ok=True)
            doc_result_dir.mkdir(parents=True, exist_ok=True)
            output_raw.mkdir(parents=True, exist_ok=True)

            tickers = [
                ("TSLA", "us_stock", "US", "USD"),
                ("AAPL", "us_stock", "US", "USD"),
                ("MSFT", "us_stock", "US", "USD"),
                ("NVDA", "us_stock", "US", "USD"),
                ("005930.KS", "kr_stock", "KR", "KRW"),
                ("SPY", "etf", "US", "USD"),
                ("GLD", "gold_etf", "US", "USD"),
                ("IEF", "bond_etf", "US", "USD"),
                ("SHY", "bond_etf", "US", "USD"),
            ]

            with meta_path.open("w", encoding="utf-8", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["ticker", "asset_class", "region", "group_tag", "currency", "benchmark_group", "is_core_hedge"])
                for ticker, asset_class, region, currency in tickers:
                    writer.writerow([ticker, asset_class, region, "", currency, "", "Y" if ticker in {"GLD", "IEF", "SHY"} else "N"])

            market_raw_rows = []
            for ticker, asset_class, _, currency in tickers:
                rows = generate_price_rows(
                    start_date,
                    total_days=120,
                    start_price=100.0,
                    return_func=hedge_ret if ticker in {"GLD", "IEF", "SHY"} else stock_ret,
                )
                for row in rows:
                    market_raw_rows.append(
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
            write_market_raw(output_raw / f"raw_market_daily_{cached_version}.csv", sorted(market_raw_rows, key=lambda x: (x["ticker"], x["date"])))

            fx_rows = []
            for row in generate_price_rows(start_date, total_days=120, start_price=1300.0, return_func=lambda idx: 0.0001):
                fx_rows.append(
                    {
                        "date": row["date"],
                        "ticker": run_data_pipeline.FX_TICKER,
                        "close": row["adj_close"],
                        "source": "yahoo",
                        "currency": "KRW",
                        "ingested_at": ingested_at,
                    }
                )
            write_fx_raw(output_raw / f"raw_fx_daily_{cached_version}.csv", fx_rows)

            ks200_rows = generate_price_rows(start_date, total_days=120, start_price=300.0, return_func=lambda idx: -0.012 if idx % 17 == 0 else 0.002)
            with (output_raw / f"raw_benchmark_daily_{cached_version}.csv").open("w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=["date", "ticker", "adj_close", "source", "currency", "ingested_at"])
                writer.writeheader()
                for row in [
                    {
                        "date": row["date"],
                        "ticker": "^KS200",
                        "adj_close": row["adj_close"],
                        "source": "yahoo",
                        "currency": "KRW",
                        "ingested_at": ingested_at,
                    }
                    for row in ks200_rows
                ]:
                    writer.writerow(row)

            old_min_obs = dict(run_data_pipeline.MIN_OBS_POLICY)
            try:
                run_data_pipeline.UNIVERSE_META = meta_path
                run_data_pipeline.OUTPUT_RAW_DIR = output_raw
                run_data_pipeline.OUTPUT_PROCESSED_DIR = output_processed
                run_data_pipeline.OUTPUT_REPORT_DIR = output_reports
                run_data_pipeline.DOC_RESULT_DIR = doc_result_dir
                run_data_pipeline.MIN_OBS_POLICY.update(
                    {
                        "vol_annual": 5,
                        "mdd_1y": 5,
                        "tail_1y": 10,
                        "beta_overlap": 10,
                        "downside_overlap": 5,
                        "corr_overlap": 5,
                        "adv_60": 5,
                        "portfolio_common_dates": 10,
                    }
                )

                portfolio_path = tmp_path / "inputs" / "portfolio_weights.csv"
                portfolio_path.parent.mkdir(parents=True, exist_ok=True)
                with portfolio_path.open("w", encoding="utf-8", newline="") as f:
                    writer = csv.writer(f)
                    writer.writerow(["ticker", "weight_pct"])
                    writer.writerow(["TSLA", 20])
                    writer.writerow(["AAPL", 20])
                    writer.writerow(["MSFT", 20])
                    writer.writerow(["NVDA", 20])
                    writer.writerow(["005930.KS", 20])

                def fake_load_portfolio_input(_universe_map, _input_path=None):
                    return portfolio_path, {"TSLA": 20.0, "AAPL": 20.0, "MSFT": 20.0, "NVDA": 20.0, "005930.KS": 20.0}

                with mock.patch.object(run_data_pipeline, "now_utc", return_value=fixed_now), \
                     mock.patch.object(run_data_pipeline, "load_portfolio_input", side_effect=fake_load_portfolio_input), \
                     mock.patch.object(run_data_pipeline, "fetch_yahoo_chart", side_effect=AssertionError("network fetch should not be used when cached snapshot exists")):
                    run_data_pipeline.main(["--single-asset", "TSLA", "--run-id", run_id])

                feature_csv = output_processed / f"features_summary_{run_id}.csv"
                self.assertTrue(feature_csv.exists())
                with feature_csv.open(encoding="utf-8", newline="") as f:
                    reader = csv.DictReader(f)
                    rows = list(reader)
                self.assertTrue(rows)
                self.assertTrue(all(row["data_version"] == cached_version for row in rows))
            finally:
                run_data_pipeline.MIN_OBS_POLICY.clear()
                run_data_pipeline.MIN_OBS_POLICY.update(old_min_obs)

    def test_build_run_id_returns_extended_unique_format(self):
        fixed_now = datetime(2026, 3, 10, 0, 0, 0, tzinfo=timezone.utc)
        with mock.patch.object(run_data_pipeline, "now_utc", return_value=fixed_now), \
             mock.patch("uuid.uuid4") as mock_uuid:
            mock_uuid.return_value.hex = "deadbeefcafebabe1234"
            self.assertEqual(run_data_pipeline.build_run_id(), "20260310T000000000000-deadbeef")

    def test_update_latest_manifest_preserves_product_active_bundle(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            scenario_manifest = root / "scenario_research" / "outputs" / "latest_manifest.json"
            product_manifest = root / "HedgeMate" / "outputs" / "latest_manifest.json"
            product_manifest.parent.mkdir(parents=True, exist_ok=True)
            product_manifest.write_text(
                json.dumps(
                    {
                        "active_hedgemate_run": "hedgemate-prod",
                        "active_bundle": {"hedgemate_run": "hedgemate-prod"},
                        "artifacts": {
                            "assetScenarioSensitivity": "HedgeMate/outputs/processed/asset_scenario_sensitivity_hedgemate-prod.csv",
                            "scenarioVector": "scenario_research/outputs/scenario_vectors/current_scenario_vector_prod.csv",
                            "recommendationStatusQa": "HedgeMate/outputs/reports/recommendation_status_qa_post_backtest_hedgemate-prod_backtest_gated.md",
                        },
                    }
                ),
                encoding="utf-8",
            )
            original_product_manifest = run_data_pipeline.PRODUCT_MANIFEST_PATH
            try:
                run_data_pipeline.PRODUCT_MANIFEST_PATH = product_manifest
                run_data_pipeline.update_latest_manifest(
                    {
                        "active_hedgemate_run": "20260310T000000000000-deadbeef",
                        "active_hedgemate_sensitivity_path": "../HedgeMate/outputs/processed/asset_scenario_sensitivity_20260310T000000000000-deadbeef.csv",
                    },
                    path=scenario_manifest,
                )
            finally:
                run_data_pipeline.PRODUCT_MANIFEST_PATH = original_product_manifest

            payload = json.loads(scenario_manifest.read_text(encoding="utf-8"))
            self.assertEqual(payload["active_hedgemate_run"], "hedgemate-prod")
            self.assertEqual(payload["legacy_hedgemate_run"], "20260310T000000000000-deadbeef")
            self.assertEqual(payload["active_hedgemate_manifest_basis"], "HedgeMate/outputs/latest_manifest.json")
            self.assertIn("post_backtest", payload["active_hedgemate_recommendation_status_qa_path"])

    def test_resolve_fetch_start_dt_defaults_to_gfc_coverage(self):
        fixed_now = datetime(2026, 5, 19, 0, 0, 0, tzinfo=timezone.utc)

        start_dt = run_data_pipeline.resolve_fetch_start_dt(fixed_now)

        self.assertEqual(start_dt.date().isoformat(), "2007-01-01")

    def test_parse_args_exposes_force_raw_refresh(self):
        args = run_data_pipeline.parse_args(["--force-refresh-raw", "--history-start-date", "2008-01-01"])

        self.assertTrue(args.force_refresh_raw)
        self.assertEqual(args.history_start_date, "2008-01-01")


if __name__ == "__main__":
    unittest.main()
