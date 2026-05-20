import argparse
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from scripts import update_active_bundle
from scripts.apply_backtest_gate import build_backtest_attribution, gate_row, summarize_backtest, write_post_backtest_qa
from scripts.update_active_bundle import build_manifest, sync_scenario_manifest_with_product


class BacktestGateTests(unittest.TestCase):
    def test_worsened_candidate_cannot_remain_pass_recommend(self):
        row = {"candidate_ticker": "GLD", "recommendation_status": "PASS_RECOMMEND", "gate_fail_reasons": ""}
        gated = gate_row(row, {"evaluated_count": 1, "improved_count": 0, "mixed_count": 0, "worsened_count": 1, "insufficient_history_count": 0})

        self.assertEqual(gated["recommendation_status"], "FAIL_GATE")
        self.assertEqual(gated["backtest_gate_status"], "FAIL_BACKTEST")
        self.assertIn("worsened", gated["gate_fail_reasons"])

    def test_insufficient_history_demotes_formal_recommendation(self):
        row = {"candidate_ticker": "GLD", "recommendation_status": "PASS_RECOMMEND", "reference_reason": ""}
        gated = gate_row(row, {"evaluated_count": 0, "improved_count": 0, "mixed_count": 0, "worsened_count": 0, "insufficient_history_count": 2})

        self.assertEqual(gated["recommendation_status"], "REFERENCE_ONLY")
        self.assertEqual(gated["backtest_gate_status"], "VALIDATION_INSUFFICIENT")
        self.assertIn("검증 부족", gated["reference_reason"])

    def test_missing_backtest_demotes_formal_recommendation(self):
        row = {"candidate_ticker": "GLD", "recommendation_status": "PASS_RECOMMEND", "reference_reason": ""}
        gated = gate_row(row, None)

        self.assertEqual(gated["recommendation_status"], "REFERENCE_ONLY")
        self.assertEqual(gated["backtest_gate_status"], "VALIDATION_MISSING")

    def test_summarize_backtest_groups_by_candidate_key_when_available(self):
        summary = summarize_backtest(
            [
                {"candidate_key": "one_to_one|GLD|10", "candidate_label": "GLD", "backtest_status": "EVALUATED", "verdict": "IMPROVED", "turnover": "0.2"},
                {
                    "candidate_key": "one_to_one|GLD|10",
                    "candidate_label": "GLD",
                    "backtest_status": "INSUFFICIENT_HISTORY",
                    "verdict": "INSUFFICIENT_HISTORY",
                },
                {"candidate_key": "one_to_one|GLD|30", "candidate_label": "GLD", "backtest_status": "EVALUATED", "verdict": "WORSENED", "turnover": "0.7"},
            ]
        )

        self.assertEqual(summary["one_to_one|GLD|10"]["evaluated_count"], 1)
        self.assertEqual(summary["one_to_one|GLD|10"]["improved_count"], 1)
        self.assertEqual(summary["one_to_one|GLD|10"]["insufficient_history_count"], 1)
        self.assertEqual(summary["one_to_one|GLD|10"]["target_max_turnover"], "0.2")
        self.assertEqual(summary["one_to_one|GLD|30"]["worsened_count"], 1)

    def test_summarize_backtest_carries_cash_bootstrap_evidence(self):
        summary = summarize_backtest(
            [
                {
                    "candidate_key": "one_to_one|GLD|10",
                    "candidate_label": "GLD",
                    "is_target_scenario": "Y",
                    "backtest_status": "EVALUATED",
                    "verdict": "IMPROVED",
                    "bootstrap_confidence": "ROBUST_IMPROVE",
                    "net_stress_delta_p_improve": "0.97",
                    "cash_bootstrap_confidence": "UNCERTAIN",
                    "cash_net_stress_delta_p_improve": "0.61",
                },
                {
                    "candidate_key": "one_to_one|GLD|10",
                    "candidate_label": "GLD",
                    "is_target_scenario": "Y",
                    "backtest_status": "EVALUATED",
                    "verdict": "IMPROVED",
                    "bootstrap_confidence": "ROBUST_IMPROVE",
                    "net_stress_delta_p_improve": "0.98",
                    "cash_bootstrap_confidence": "ROBUST_IMPROVE",
                    "cash_net_stress_delta_p_improve": "0.96",
                },
            ]
        )

        evidence = summary["one_to_one|GLD|10"]
        self.assertEqual(evidence["target_bootstrap_robust_count"], 2)
        self.assertEqual(evidence["target_cash_bootstrap_count"], 2)
        self.assertEqual(evidence["target_cash_bootstrap_robust_count"], 1)
        self.assertEqual(evidence["target_cash_bootstrap_uncertain_count"], 1)
        self.assertEqual(evidence["target_cash_bootstrap_min_p_improve"], "0.61")

    def test_target_scenario_gate_ignores_non_target_worsening_for_status(self):
        summary = summarize_backtest(
            [
                {
                    "candidate_key": "one_to_one|GLD|10",
                    "candidate_label": "GLD",
                    "expected_scenario_code": "china_trade_fragmentation_shock",
                    "is_target_scenario": "Y",
                    "backtest_status": "EVALUATED",
                    "verdict": "IMPROVED",
                },
                {
                    "candidate_key": "one_to_one|GLD|10",
                    "candidate_label": "GLD",
                    "expected_scenario_code": "usd_strength_krw_weakness",
                    "is_target_scenario": "Y",
                    "backtest_status": "EVALUATED",
                    "verdict": "IMPROVED",
                },
                {
                    "candidate_key": "one_to_one|GLD|10",
                    "candidate_label": "GLD",
                    "expected_scenario_code": "higher_for_longer_long_rate_shock",
                    "is_target_scenario": "N",
                    "backtest_status": "EVALUATED",
                    "verdict": "WORSENED",
                },
            ]
        )

        evidence = summary["one_to_one|GLD|10"]
        gated = gate_row(
            {
                "candidate_ticker": "GLD",
                "recommendation_status": "PASS_RECOMMEND",
                "reference_reason": "",
                "combo_min_adv_60": "200000000000",
            },
            {**evidence, "target_max_turnover": "0.2"},
        )

        self.assertEqual(gated["recommendation_status"], "PASS_RECOMMEND")
        self.assertEqual(gated["backtest_gate_status"], "VALIDATED")
        self.assertEqual(gated["backtest_target_worsened_count"], "0")
        self.assertEqual(gated["backtest_context_worsened_count"], "1")

    def test_thin_target_validation_demotes_formal_recommendation(self):
        gated = gate_row(
            {"candidate_ticker": "USO", "recommendation_status": "PASS_RECOMMEND", "reference_reason": ""},
            {
                "evaluated_count": 1,
                "improved_count": 1,
                "mixed_count": 0,
                "worsened_count": 0,
                "insufficient_history_count": 0,
                "target_evaluated_count": 1,
                "target_improved_count": 1,
                "target_mixed_count": 0,
                "target_worsened_count": 0,
                "target_insufficient_history_count": 0,
            },
        )

        self.assertEqual(gated["recommendation_status"], "REFERENCE_ONLY")
        self.assertEqual(gated["backtest_gate_status"], "VALIDATION_THIN")
        self.assertIn("표본 부족", gated["reference_reason"])

    def test_cash_baseline_lag_demotes_formal_recommendation(self):
        gated = gate_row(
            {"candidate_ticker": "GLD", "recommendation_status": "PASS_RECOMMEND", "reference_reason": ""},
            {
                "evaluated_count": 3,
                "improved_count": 3,
                "mixed_count": 0,
                "worsened_count": 0,
                "insufficient_history_count": 0,
                "target_evaluated_count": 3,
                "target_improved_count": 3,
                "target_mixed_count": 0,
                "target_worsened_count": 0,
                "target_insufficient_history_count": 0,
                "target_beats_cash_count": 1,
                "target_mixed_cash_count": 1,
                "target_lags_cash_count": 1,
            },
        )

        self.assertEqual(gated["recommendation_status"], "REFERENCE_ONLY")
        self.assertEqual(gated["backtest_gate_status"], "REFERENCE_ONLY_CASH_BASELINE")
        self.assertEqual(gated["backtest_target_lags_cash_count"], "1")
        self.assertIn("cash-only de-risking", gated["reference_reason"])
        self.assertIn("cash_baseline_lag", gated["formal_gate_blockers"])

    def test_uncertain_bootstrap_demotes_formal_recommendation(self):
        gated = gate_row(
            {"candidate_ticker": "GLD", "recommendation_status": "PASS_RECOMMEND", "reference_reason": ""},
            {
                "evaluated_count": 3,
                "improved_count": 3,
                "mixed_count": 0,
                "worsened_count": 0,
                "insufficient_history_count": 0,
                "target_evaluated_count": 3,
                "target_improved_count": 3,
                "target_mixed_count": 0,
                "target_worsened_count": 0,
                "target_insufficient_history_count": 0,
                "target_beats_cash_count": 3,
                "target_mixed_cash_count": 0,
                "target_lags_cash_count": 0,
                "target_bootstrap_count": 3,
                "target_bootstrap_robust_count": 2,
                "target_bootstrap_uncertain_count": 1,
                "target_bootstrap_min_p_improve": "0.91",
            },
        )

        self.assertEqual(gated["recommendation_status"], "REFERENCE_ONLY")
        self.assertEqual(gated["backtest_gate_status"], "REFERENCE_ONLY_BOOTSTRAP")
        self.assertEqual(gated["backtest_target_bootstrap_uncertain_count"], "1")
        self.assertIn("bootstrap confidence", gated["reference_reason"])
        self.assertIn("bootstrap_not_robust", gated["formal_gate_blockers"])

    def test_uncertain_cash_bootstrap_demotes_formal_recommendation(self):
        gated = gate_row(
            {"candidate_ticker": "GLD", "recommendation_status": "PASS_RECOMMEND", "reference_reason": ""},
            {
                "evaluated_count": 3,
                "improved_count": 3,
                "mixed_count": 0,
                "worsened_count": 0,
                "insufficient_history_count": 0,
                "target_evaluated_count": 3,
                "target_improved_count": 3,
                "target_mixed_count": 0,
                "target_worsened_count": 0,
                "target_insufficient_history_count": 0,
                "target_beats_cash_count": 3,
                "target_mixed_cash_count": 0,
                "target_lags_cash_count": 0,
                "target_bootstrap_count": 3,
                "target_bootstrap_robust_count": 3,
                "target_bootstrap_uncertain_count": 0,
                "target_cash_bootstrap_count": 3,
                "target_cash_bootstrap_robust_count": 2,
                "target_cash_bootstrap_uncertain_count": 1,
                "target_cash_bootstrap_min_p_improve": "0.64",
            },
        )

        self.assertEqual(gated["recommendation_status"], "REFERENCE_ONLY")
        self.assertEqual(gated["backtest_gate_status"], "REFERENCE_ONLY_CASH_BOOTSTRAP")
        self.assertEqual(gated["backtest_target_cash_bootstrap_uncertain_count"], "1")
        self.assertIn("cash-baseline bootstrap confidence", gated["reference_reason"])
        self.assertIn("cash_bootstrap_not_robust", gated["formal_gate_blockers"])

    def test_low_liquidity_demotes_formal_recommendation(self):
        gated = gate_row(
            {
                "candidate_ticker": "GLD",
                "recommendation_status": "PASS_RECOMMEND",
                "reference_reason": "",
                "combo_min_adv_60": "50000000000",
            },
            {
                "evaluated_count": 3,
                "improved_count": 3,
                "mixed_count": 0,
                "worsened_count": 0,
                "insufficient_history_count": 0,
                "target_evaluated_count": 3,
                "target_improved_count": 3,
                "target_mixed_count": 0,
                "target_worsened_count": 0,
                "target_insufficient_history_count": 0,
                "target_beats_cash_count": 3,
                "target_mixed_cash_count": 0,
                "target_lags_cash_count": 0,
                "target_bootstrap_count": 3,
                "target_bootstrap_robust_count": 3,
                "target_bootstrap_uncertain_count": 0,
            },
        )

        self.assertEqual(gated["recommendation_status"], "REFERENCE_ONLY")
        self.assertEqual(gated["backtest_gate_status"], "REFERENCE_ONLY_LIQUIDITY")
        self.assertIn("ADV", gated["reference_reason"])
        self.assertEqual(gated["liquidity_capacity_status"], "BELOW_FORMAL_ADV_FLOOR_NO_ORDER_SIZE")

    def test_order_size_liquidity_can_pass_below_global_adv_floor(self):
        gated = gate_row(
            {
                "candidate_ticker": "GLD",
                "recommendation_status": "PASS_RECOMMEND",
                "reference_reason": "",
                "combo_min_adv_60": "50000000000",
                "hedge_budget_krw": "1000000",
            },
            {
                "evaluated_count": 3,
                "improved_count": 3,
                "mixed_count": 0,
                "worsened_count": 0,
                "insufficient_history_count": 0,
                "target_evaluated_count": 3,
                "target_improved_count": 3,
                "target_mixed_count": 0,
                "target_worsened_count": 0,
                "target_insufficient_history_count": 0,
                "target_beats_cash_count": 3,
                "target_mixed_cash_count": 0,
                "target_lags_cash_count": 0,
                "target_bootstrap_count": 3,
                "target_bootstrap_robust_count": 3,
                "target_bootstrap_uncertain_count": 0,
            },
        )

        self.assertEqual(gated["recommendation_status"], "PASS_RECOMMEND")
        self.assertEqual(gated["backtest_gate_status"], "VALIDATED")
        self.assertEqual(gated["liquidity_capacity_status"], "ORDER_SIZE_ADV_USAGE_OK")
        self.assertEqual(gated["liquidity_order_notional_krw"], "1000000.0")
        self.assertNotIn("liquidity_below_formal", gated["formal_gate_blockers"])

    def test_order_size_liquidity_blocks_high_adv_usage(self):
        gated = gate_row(
            {
                "candidate_ticker": "GLD",
                "recommendation_status": "PASS_RECOMMEND",
                "reference_reason": "",
                "combo_min_adv_60": "50000000000",
                "hedge_budget_krw": "6000000000",
            },
            {
                "evaluated_count": 3,
                "improved_count": 3,
                "mixed_count": 0,
                "worsened_count": 0,
                "insufficient_history_count": 0,
                "target_evaluated_count": 3,
                "target_improved_count": 3,
                "target_mixed_count": 0,
                "target_worsened_count": 0,
                "target_insufficient_history_count": 0,
                "target_beats_cash_count": 3,
                "target_mixed_cash_count": 0,
                "target_lags_cash_count": 0,
                "target_bootstrap_count": 3,
                "target_bootstrap_robust_count": 3,
                "target_bootstrap_uncertain_count": 0,
            },
        )

        self.assertEqual(gated["recommendation_status"], "REFERENCE_ONLY")
        self.assertEqual(gated["backtest_gate_status"], "REFERENCE_ONLY_LIQUIDITY")
        self.assertEqual(gated["liquidity_capacity_status"], "ORDER_SIZE_ABOVE_ADV_USAGE_LIMIT")
        self.assertEqual(gated["liquidity_adv_usage_pct"], "12.0")
        self.assertIn("liquidity_below_formal", gated["formal_gate_blockers"])

    def test_missing_liquidity_demotes_formal_recommendation(self):
        gated = gate_row(
            {"candidate_ticker": "GLD", "recommendation_status": "PASS_RECOMMEND", "reference_reason": ""},
            {
                "evaluated_count": 3,
                "improved_count": 3,
                "mixed_count": 0,
                "worsened_count": 0,
                "insufficient_history_count": 0,
                "target_evaluated_count": 3,
                "target_improved_count": 3,
                "target_mixed_count": 0,
                "target_worsened_count": 0,
                "target_insufficient_history_count": 0,
                "target_beats_cash_count": 3,
                "target_mixed_cash_count": 0,
                "target_lags_cash_count": 0,
                "target_bootstrap_count": 3,
                "target_bootstrap_robust_count": 3,
                "target_bootstrap_uncertain_count": 0,
            },
        )

        self.assertEqual(gated["recommendation_status"], "REFERENCE_ONLY")
        self.assertEqual(gated["backtest_gate_status"], "REFERENCE_ONLY_LIQUIDITY")
        self.assertIn("liquidity evidence is missing", gated["reference_reason"])

    def test_high_turnover_demotes_formal_recommendation(self):
        gated = gate_row(
            {
                "candidate_ticker": "GLD",
                "recommendation_status": "PASS_RECOMMEND",
                "reference_reason": "",
                "combo_min_adv_60": "200000000000",
            },
            {
                "evaluated_count": 3,
                "improved_count": 3,
                "mixed_count": 0,
                "worsened_count": 0,
                "insufficient_history_count": 0,
                "target_evaluated_count": 3,
                "target_improved_count": 3,
                "target_mixed_count": 0,
                "target_worsened_count": 0,
                "target_insufficient_history_count": 0,
                "target_beats_cash_count": 3,
                "target_mixed_cash_count": 0,
                "target_lags_cash_count": 0,
                "target_bootstrap_count": 3,
                "target_bootstrap_robust_count": 3,
                "target_bootstrap_uncertain_count": 0,
                "target_max_turnover": "0.72",
            },
        )

        self.assertEqual(gated["recommendation_status"], "REFERENCE_ONLY")
        self.assertEqual(gated["backtest_gate_status"], "REFERENCE_ONLY_TURNOVER")
        self.assertEqual(gated["backtest_target_max_turnover"], "0.72")
        self.assertIn("turnover", gated["reference_reason"])

    def test_partial_target_history_demotes_formal_recommendation(self):
        gated = gate_row(
            {"candidate_ticker": "XLU", "recommendation_status": "PASS_RECOMMEND", "reference_reason": ""},
            {
                "evaluated_count": 5,
                "worsened_count": 2,
                "target_evaluated_count": 1,
                "target_improved_count": 1,
                "target_mixed_count": 0,
                "target_worsened_count": 0,
                "target_insufficient_history_count": 2,
                "context_worsened_count": 2,
            },
        )

        self.assertEqual(gated["recommendation_status"], "REFERENCE_ONLY")
        self.assertEqual(gated["backtest_gate_status"], "PARTIAL_VALIDATION")
        self.assertEqual(gated["backtest_target_insufficient_history_count"], "2")

    def test_backtest_attribution_explains_candidate_scenario_metric_failure(self):
        rows = [
            {
                "candidate_label": "GLD",
                "expected_scenario_code": "higher_for_longer_long_rate_shock",
                "case_name": "2022 Global Rate Shock",
                "backtest_status": "EVALUATED",
                "verdict": "WORSENED",
                "cvar_delta": "-0.01",
                "mdd_delta": "-0.12",
                "stress_loss_delta": "-0.18",
                "return_drag": "-0.20",
                "hedge_vs_cash_verdict": "LAGS_CASH",
                "hedge_vs_cash_cvar_delta": "-0.03",
            },
            {
                "candidate_label": "GLD",
                "expected_scenario_code": "higher_for_longer_long_rate_shock",
                "case_name": "Second Case",
                "backtest_status": "EVALUATED",
                "verdict": "IMPROVED",
                "cvar_delta": "0.02",
                "mdd_delta": "0.03",
                "stress_loss_delta": "0.01",
                "return_drag": "0.00",
                "hedge_vs_cash_verdict": "BEATS_CASH",
                "hedge_vs_cash_cvar_delta": "0.01",
            },
        ]

        attribution = build_backtest_attribution(rows)

        self.assertEqual(len(attribution), 1)
        row = attribution[0]
        self.assertEqual(row["candidate_label"], "GLD")
        self.assertEqual(row["expected_scenario_code"], "higher_for_longer_long_rate_shock")
        self.assertEqual(row["evaluated_count"], "2")
        self.assertEqual(row["worsened_count"], "1")
        self.assertEqual(row["worsened_rate"], "0.5")
        self.assertEqual(row["cash_beats_count"], "1")
        self.assertEqual(row["cash_lags_count"], "1")
        self.assertEqual(row["worst_metric"], "return_drag")
        self.assertEqual(row["worst_case_name"], "2022 Global Rate Shock")

    def test_post_backtest_qa_uses_gated_statuses_and_zero_formal_message(self):
        with tempfile.TemporaryDirectory() as tmp:
            qa_path = Path(tmp) / "recommendation_status_qa_post_backtest.md"
            payload = {
                "generated_at_utc": "2026-05-18T00:00:00Z",
                "hedgemate_run_id": "hedgemate-prod",
                "backtest_run_id": "backtest-prod",
                "portfolio_1to1_gated_csv": "portfolio_1to1_gated.csv",
                "portfolio_multi_gated_csv": "portfolio_multi_gated.csv",
            }
            rows = [
                {
                    "candidate_ticker": "GLD",
                    "recommendation_status": "REFERENCE_ONLY",
                    "backtest_gate_status": "VALIDATION_INSUFFICIENT",
                    "backtest_worsened_count": "0",
                    "backtest_insufficient_history_count": "2",
                    "backtest_reason": "historical validation has insufficient history",
                },
                {
                    "candidate_ticker": "TLT",
                    "recommendation_status": "FAIL_GATE",
                    "backtest_gate_status": "FAIL_BACKTEST",
                    "backtest_worsened_count": "1",
                    "backtest_insufficient_history_count": "0",
                    "backtest_reason": "walk-forward backtest worsened risk metrics",
                },
            ]

            attribution_rows = [
                {
                    "candidate_label": "TLT",
                    "expected_scenario_code": "higher_for_longer_long_rate_shock",
                    "evaluated_count": "1",
                    "improved_count": "0",
                    "worsened_count": "1",
                    "insufficient_history_count": "0",
                    "worsened_rate": "1.0",
                    "worst_metric": "MDD",
                    "worst_metric_delta": "-0.12",
                    "worst_case_name": "2022 Global Rate Shock",
                }
            ]

            write_post_backtest_qa(qa_path, payload, rows[:1], rows[1:], attribution_rows)

            text = qa_path.read_text(encoding="utf-8")
            self.assertIn("- PASS_RECOMMEND: 0", text)
            self.assertIn("- REFERENCE_ONLY: 1", text)
            self.assertIn("- FAIL_GATE: 1", text)
            self.assertIn("현재 검증 기준에서 정식 추천 가능한 후보는 없습니다.", text)
            self.assertIn("Backtest Attribution Summary", text)
            self.assertIn("2022 Global Rate Shock", text)
            self.assertIn("WORSENED candidates still marked PASS_RECOMMEND: 0", text)


class ActiveBundleTests(unittest.TestCase):
    def test_manifest_detects_suspicious_deadbeef_run(self):
        args = argparse.Namespace(
            scenario_run_id="v2-scenarios-prod",
            final_run_id="v2-phase6-prod",
            hedgemate_run_id="20260310-deadbeef",
            backtest_run_id="phase10b-prod",
            data_version="20260512",
            scenario_vector_as_of_date="2026-05-11",
            max_stale_days=7,
            scenario_vector=None,
            final_scenario_vector=None,
            final_market_state=None,
            scenario_confidence=None,
            top_active_scenarios=None,
            final_metadata=None,
            event_overlay_metadata=None,
            features=None,
            asset_scenario_sensitivity=None,
            portfolio_1to1=None,
            portfolio_multi=None,
            recommendation_status_qa=None,
            backtest_csv=None,
            backtest_summary=None,
            backtest_gate_summary=None,
            final_runbook=None,
        )

        manifest = build_manifest(args, generated_at_utc="2026-05-18T00:00:00Z", reference_date=date(2026, 5, 18))

        self.assertIn(manifest["freshness_status"], {"INCOMPLETE", "STALE"})
        self.assertTrue(any("suspicious run ids" in reason for reason in manifest["stale_reasons"]))
        self.assertEqual(manifest["active_bundle"]["hedgemate_run"], "20260310-deadbeef")

    def test_manifest_is_fresh_when_required_paths_exist(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            required_paths = {}
            for key in [
                "final_market_state",
                "top_active_scenarios",
                "scenario_vector",
                "features",
                "asset_scenario_sensitivity",
                "portfolio_1to1",
                "portfolio_multi",
                "backtest_csv",
            ]:
                path = root / f"{key}.csv"
                path.write_text("x\n", encoding="utf-8")
                required_paths[key] = str(path)
            top_json = root / "top_active_scenarios.json"
            top_json.write_text('{"date":"2026-05-11"}', encoding="utf-8")
            required_paths["top_active_scenarios"] = str(top_json)

            args = argparse.Namespace(
                scenario_run_id="v2-scenarios-prod",
                final_run_id="v2-phase6-prod",
                hedgemate_run_id="hedgemate-prod",
                backtest_run_id="phase10b-prod",
                data_version="20260512",
                scenario_vector_as_of_date=None,
                max_stale_days=7,
                scenario_vector=required_paths["scenario_vector"],
                final_scenario_vector=None,
                final_market_state=required_paths["final_market_state"],
                scenario_confidence=None,
                top_active_scenarios=required_paths["top_active_scenarios"],
                final_metadata=None,
                event_overlay_metadata=None,
                features=required_paths["features"],
                asset_scenario_sensitivity=required_paths["asset_scenario_sensitivity"],
                portfolio_1to1=required_paths["portfolio_1to1"],
                portfolio_multi=required_paths["portfolio_multi"],
                recommendation_status_qa=None,
                backtest_csv=required_paths["backtest_csv"],
                backtest_summary=None,
                backtest_gate_summary=None,
                final_runbook=None,
            )

            manifest = build_manifest(args, generated_at_utc="2026-05-18T00:00:00Z", reference_date=date(2026, 5, 18))

            self.assertEqual(manifest["freshness_status"], "FRESH")
            self.assertEqual(manifest["scenario_vector_as_of_date"], "2026-05-11")
            self.assertEqual(manifest["event_overlay_status"]["recommendation_usage"], "fixture_context_only")
            self.assertEqual(manifest["event_overlay_status"]["trade_gate_usage"], "disabled_for_fixture")

    def test_manifest_flags_portfolio_input_mismatch_against_recommendation_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            required_paths = {}
            for key in [
                "final_market_state",
                "top_active_scenarios",
                "scenario_vector",
                "features",
                "asset_scenario_sensitivity",
                "portfolio_multi",
                "backtest_csv",
            ]:
                path = root / f"{key}.csv"
                path.write_text("x\n", encoding="utf-8")
                required_paths[key] = str(path)
            top_json = root / "top_active_scenarios.json"
            top_json.write_text('{"date":"2026-05-11"}', encoding="utf-8")
            required_paths["top_active_scenarios"] = str(top_json)
            portfolio_input = root / "portfolio_weights.csv"
            portfolio_input.write_text("ticker,weight_pct\nMSFT,50\nNVDA,50\n", encoding="utf-8")
            portfolio_1to1 = root / "portfolio_1to1.csv"
            portfolio_1to1.write_text(
                "candidate_ticker,allocation_weights,weights_snapshot\n"
                'TLT,"{""TLT"": 10}","{""AAPL"": 45, ""BTC-USD"": 45, ""TLT"": 10}"\n',
                encoding="utf-8",
            )

            args = argparse.Namespace(
                scenario_run_id="v2-scenarios-prod",
                final_run_id="v2-phase6-prod",
                hedgemate_run_id="hedgemate-prod",
                backtest_run_id="phase10b-prod",
                data_version="20260512",
                scenario_vector_as_of_date=None,
                max_stale_days=7,
                scenario_vector=required_paths["scenario_vector"],
                final_scenario_vector=None,
                final_market_state=required_paths["final_market_state"],
                scenario_confidence=None,
                top_active_scenarios=required_paths["top_active_scenarios"],
                final_metadata=None,
                event_overlay_metadata=None,
                features=required_paths["features"],
                portfolio_input=str(portfolio_input),
                asset_scenario_sensitivity=required_paths["asset_scenario_sensitivity"],
                portfolio_1to1=str(portfolio_1to1),
                portfolio_multi=required_paths["portfolio_multi"],
                recommendation_status_qa=None,
                backtest_csv=required_paths["backtest_csv"],
                backtest_summary=None,
                backtest_gate_summary=None,
                final_runbook=None,
            )

            manifest = build_manifest(args, generated_at_utc="2026-05-18T00:00:00Z", reference_date=date(2026, 5, 18))

            self.assertEqual(manifest["freshness_status"], "STALE")
            self.assertTrue(manifest["portfolio_input_mismatch"])
            self.assertIn("portfolio input mismatch", " ".join(manifest["stale_reasons"]))
            self.assertIn("portfolioInput", manifest["artifacts"])
            self.assertNotEqual(
                manifest["portfolio_input_fingerprint"]["hash"],
                manifest["recommendation_portfolio_fingerprint"]["hash"],
            )

    def test_manifest_derives_live_gemini_event_overlay_status_from_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            required_paths = {}
            for key in [
                "final_market_state",
                "top_active_scenarios",
                "scenario_vector",
                "features",
                "asset_scenario_sensitivity",
                "portfolio_1to1",
                "portfolio_multi",
                "backtest_csv",
            ]:
                path = root / f"{key}.csv"
                path.write_text("x\n", encoding="utf-8")
                required_paths[key] = str(path)
            top_json = root / "top_active_scenarios.json"
            top_json.write_text('{"date":"2026-05-11"}', encoding="utf-8")
            required_paths["top_active_scenarios"] = str(top_json)
            metadata = root / "event_overlay_metadata.json"
            metadata.write_text(
                json.dumps(
                    {
                        "provider": "gemini",
                        "provider_model": "gemini-2.5-flash",
                        "live_research_attached": True,
                        "schema_error_count": 0,
                        "fatal_schema_error_count": 0,
                    }
                ),
                encoding="utf-8",
            )

            args = argparse.Namespace(
                scenario_run_id="v2-scenarios-prod",
                final_run_id="v2-phase6-prod",
                hedgemate_run_id="hedgemate-prod",
                backtest_run_id="phase10b-prod",
                data_version="20260512",
                scenario_vector_as_of_date=None,
                max_stale_days=7,
                scenario_vector=required_paths["scenario_vector"],
                final_scenario_vector=None,
                final_market_state=required_paths["final_market_state"],
                scenario_confidence=None,
                top_active_scenarios=required_paths["top_active_scenarios"],
                final_metadata=None,
                event_overlay_metadata=str(metadata),
                features=required_paths["features"],
                portfolio_input=None,
                asset_scenario_sensitivity=required_paths["asset_scenario_sensitivity"],
                portfolio_1to1=required_paths["portfolio_1to1"],
                portfolio_multi=required_paths["portfolio_multi"],
                recommendation_status_qa=None,
                backtest_csv=required_paths["backtest_csv"],
                backtest_summary=None,
                backtest_gate_summary=None,
                final_runbook=None,
            )

            manifest = build_manifest(args, generated_at_utc="2026-05-18T00:00:00Z", reference_date=date(2026, 5, 18))

            status = manifest["event_overlay_status"]
            self.assertEqual(status["mode"], "live_gemini_provider")
            self.assertEqual(status["live_gemini_extraction"], "attached")
            self.assertEqual(status["recommendation_usage"], "live_context_review_required")
            self.assertEqual(status["trade_gate_usage"], "disabled_until_human_review")
            self.assertEqual(status["provider_model"], "gemini-2.5-flash")

    def test_recommendation_qa_path_prefers_post_backtest_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            original_outputs = update_active_bundle.OUTPUTS
            try:
                update_active_bundle.OUTPUTS = Path(tmp) / "outputs"
                reports = update_active_bundle.OUTPUTS / "reports"
                reports.mkdir(parents=True, exist_ok=True)
                pre = reports / "recommendation_status_qa_hedgemate-prod.md"
                post = reports / "recommendation_status_qa_post_backtest_hedgemate-prod_backtest_gated.md"
                pre.write_text("# pre\n", encoding="utf-8")
                post.write_text("# post\n", encoding="utf-8")
                args = argparse.Namespace(recommendation_status_qa=None)

                self.assertEqual(update_active_bundle.infer_recommendation_qa_path(args, "hedgemate-prod"), post.resolve())
            finally:
                update_active_bundle.OUTPUTS = original_outputs

    def test_manifest_includes_backtest_attribution_and_rebalance_artifacts_when_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            original_outputs = update_active_bundle.OUTPUTS
            try:
                update_active_bundle.OUTPUTS = Path(tmp) / "outputs"
                reports = update_active_bundle.OUTPUTS / "reports"
                reports.mkdir(parents=True, exist_ok=True)
                (reports / "backtest_attribution_backtest-prod.csv").write_text("candidate_label\n", encoding="utf-8")
                (reports / "backtest_attribution_backtest-prod.md").write_text("# Attribution\n", encoding="utf-8")
                (reports / "rebalance_mode_comparison_rebalance-compare-backtest-prod.csv").write_text("rebalance_frequency\n", encoding="utf-8")
                (reports / "rebalance_mode_comparison_rebalance-compare-backtest-prod.md").write_text("# Rebalance\n", encoding="utf-8")
                (reports / "rebalance_mode_comparison_rebalance-compare-backtest-prod.json").write_text("{}\n", encoding="utf-8")
                (reports / "portfolio_vulnerability_attribution_hedgemate-prod.csv").write_text("vulnerability_id\n", encoding="utf-8")
                (reports / "portfolio_vulnerability_summary_hedgemate-prod.md").write_text("# Vulnerability\n", encoding="utf-8")
                (reports / "hedge_action_candidates_hedgemate-prod.csv").write_text("action_status\n", encoding="utf-8")
                (reports / "hedge_action_plan_hedgemate-prod.csv").write_text("action_status\n", encoding="utf-8")
                (reports / "hedge_action_plan_summary_hedgemate-prod.md").write_text("# Action Plan\n", encoding="utf-8")
                args = argparse.Namespace(
                    scenario_run_id="v2-scenarios-prod",
                    final_run_id="v2-phase6-prod",
                    hedgemate_run_id="hedgemate-prod",
                    backtest_run_id="backtest-prod",
                    data_version="20260512",
                    scenario_vector_as_of_date="2026-05-11",
                    max_stale_days=7,
                    scenario_vector=None,
                    final_scenario_vector=None,
                    final_market_state=None,
                    scenario_confidence=None,
                    top_active_scenarios=None,
                    final_metadata=None,
                    event_overlay_metadata=None,
                    features=None,
                    asset_scenario_sensitivity=None,
                    portfolio_1to1=None,
                    portfolio_multi=None,
                    recommendation_status_qa=None,
                    backtest_csv=None,
                    backtest_summary=None,
                    backtest_gate_summary=None,
                    backtest_attribution_csv=None,
                    backtest_attribution_summary=None,
                    rebalance_mode_comparison_csv=None,
                    rebalance_mode_comparison_summary=None,
                    rebalance_mode_comparison_json=None,
                    final_runbook=None,
                )

                manifest = build_manifest(args, generated_at_utc="2026-05-18T00:00:00Z", reference_date=date(2026, 5, 18))

                self.assertIn("backtestAttributionCsv", manifest["artifacts"])
                self.assertIn("backtestAttributionSummary", manifest["artifacts"])
                self.assertIn("rebalanceModeComparisonCsv", manifest["artifacts"])
                self.assertIn("rebalanceModeComparisonSummary", manifest["artifacts"])
                self.assertIn("rebalanceModeComparisonJson", manifest["artifacts"])
                self.assertIn("portfolioVulnerabilityAttribution", manifest["artifacts"])
                self.assertIn("portfolioVulnerabilitySummary", manifest["artifacts"])
                self.assertIn("hedgeActionCandidates", manifest["artifacts"])
                self.assertIn("hedgeActionPlan", manifest["artifacts"])
                self.assertIn("hedgeActionPlanSummary", manifest["artifacts"])
                self.assertTrue(manifest["artifacts"]["backtestAttributionCsv"].endswith("backtest_attribution_backtest-prod.csv"))
                self.assertTrue(manifest["artifacts"]["backtestAttributionSummary"].endswith("backtest_attribution_backtest-prod.md"))
                self.assertTrue(manifest["artifacts"]["rebalanceModeComparisonCsv"].endswith("rebalance_mode_comparison_rebalance-compare-backtest-prod.csv"))
                self.assertTrue(manifest["artifacts"]["hedgeActionPlan"].endswith("hedge_action_plan_hedgemate-prod.csv"))
            finally:
                update_active_bundle.OUTPUTS = original_outputs

    def test_final_runbook_artifact_is_generated_when_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            original_outputs = update_active_bundle.OUTPUTS
            try:
                update_active_bundle.OUTPUTS = Path(tmp) / "outputs"
                manifest = {
                    "active_hedgemate_run": "hedgemate-prod",
                    "data_version": "20260519",
                    "generated_at_utc": "2026-05-19T00:00:00Z",
                    "freshness_status": "FRESH",
                    "stale_reasons": [],
                    "active_bundle": {
                        "scenario_run": "scenario-prod",
                        "final_market_state_run": "final-prod",
                        "hedgemate_run": "hedgemate-prod",
                        "backtest_run": "backtest-prod",
                        "data_version": "20260519",
                    },
                    "artifacts": {"features": "HedgeMate/outputs/processed/features_summary_hedgemate-prod.csv"},
                    "event_overlay_status": {
                        "mode": "reviewed_fixture",
                        "live_gemini_extraction": "implemented_api_key_required",
                    },
                }

                runbook = update_active_bundle.ensure_final_runbook_artifact(manifest)

                self.assertTrue(runbook.exists())
                self.assertIn("finalRunbook", manifest["artifacts"])
                text = runbook.read_text(encoding="utf-8")
                self.assertIn("GET /api/data-freshness", text)
                self.assertIn("Known Non-Automated Items", text)
                self.assertIn("implemented_api_key_required", text)
                self.assertIn("fixture_context_only", text)
                self.assertIn("disabled_for_fixture", text)
            finally:
                update_active_bundle.OUTPUTS = original_outputs

    def test_sync_scenario_manifest_replaces_deadbeef_active_hedgemate_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            scenario_manifest = Path(tmp) / "latest_manifest.json"
            scenario_manifest.write_text(
                json.dumps(
                    {
                        "active_final_run": "final-prod",
                        "active_hedgemate_run": "20260310T000000000000-deadbeef",
                        "active_hedgemate_sensitivity_path": "../HedgeMate/outputs/processed/asset_scenario_sensitivity_20260310T000000000000-deadbeef.csv",
                    }
                ),
                encoding="utf-8",
            )
            manifest = {
                "active_hedgemate_run": "hedgemate-prod",
                "artifacts": {
                    "assetScenarioSensitivity": "HedgeMate/outputs/processed/asset_scenario_sensitivity_hedgemate-prod.csv",
                    "recommendationStatusQa": "HedgeMate/outputs/reports/recommendation_status_qa_post_backtest_hedgemate-prod_backtest_gated.md",
                    "scenarioVector": "scenario_research/outputs/scenario_vectors/current_scenario_vector_prod.csv",
                },
            }

            sync_scenario_manifest_with_product(manifest, scenario_manifest)

            payload = json.loads(scenario_manifest.read_text(encoding="utf-8"))
            self.assertEqual(payload["active_hedgemate_run"], "hedgemate-prod")
            self.assertEqual(payload["legacy_hedgemate_run"], "20260310T000000000000-deadbeef")
            self.assertEqual(payload["active_hedgemate_manifest_basis"], "HedgeMate/outputs/latest_manifest.json")
            self.assertIn("post_backtest", payload["active_hedgemate_recommendation_status_qa_path"])


if __name__ == "__main__":
    unittest.main()
