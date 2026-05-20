import csv
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "hedge_action_engine.py"

spec = importlib.util.spec_from_file_location("hedge_action_engine", MODULE_PATH)
hedge_action_engine = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hedge_action_engine)


class HedgeActionEngineTests(unittest.TestCase):
    def test_attribution_allows_asset_to_be_source_and_offset_by_sleeve(self):
        portfolio = {"XOM": 40.0, "NVDA": 30.0, "GLD": 30.0}
        sensitivity_rows = [
            {
                "ticker": "XOM",
                "asset_name": "Exxon Mobil",
                "asset_class": "us_stock",
                "scenario_code": "stagflation_reinflation_energy_shock",
                "scenario_name_ko": "물가·에너지 재상승장",
                "scenario_beta": -0.4,
                "evidence_quality": "high",
            },
            {
                "ticker": "XOM",
                "asset_name": "Exxon Mobil",
                "asset_class": "us_stock",
                "scenario_code": "geopolitical_escalation_supply_shock",
                "scenario_name_ko": "지정학 확전·공급충격장",
                "scenario_beta": 0.3,
                "evidence_quality": "medium",
            },
            {
                "ticker": "NVDA",
                "asset_name": "NVIDIA",
                "asset_class": "us_stock",
                "scenario_code": "semiconductor_ai_cycle_shock",
                "scenario_name_ko": "AI·반도체 사이클 충격장",
                "scenario_beta": 1.2,
                "evidence_quality": "high",
            },
            {
                "ticker": "GLD",
                "asset_name": "Gold ETF",
                "asset_class": "gold_etf",
                "scenario_code": "stagflation_reinflation_energy_shock",
                "scenario_name_ko": "물가·에너지 재상승장",
                "scenario_beta": -0.5,
                "evidence_quality": "high",
            },
        ]

        rows, summary = hedge_action_engine.build_portfolio_vulnerability_attribution(portfolio, sensitivity_rows)

        xom_roles = {(row["risk_sleeve"], row["source_or_offset"]) for row in rows if row["ticker"] == "XOM"}
        self.assertIn(("inflation_energy_shock", "offset"), xom_roles)
        self.assertIn(("geopolitical_supply_chain", "source"), xom_roles)
        self.assertIn("sleeve_contribution_pct", rows[0])
        self.assertIn("portfolio_contribution_pct", rows[0])
        self.assertIn("contribution_pct_of_sleeve", rows[0])
        self.assertIn("contribution_pct_of_total", rows[0])
        self.assertIn("asset_scenario_beta", rows[0])
        self.assertIn("scenario_activation_weight", rows[0])
        self.assertIn("plain_reason_ko", rows[0])
        self.assertIn("plain_korean_reason", rows[0])
        self.assertIn(rows[0]["ticker"], rows[0]["plain_reason_ko"])
        semiconductor = next(row for row in summary["risk_sleeves"] if row["risk_sleeve"] == "semiconductor_ai_cycle")
        self.assertEqual(semiconductor["source_holdings"][0]["ticker"], "NVDA")

    def test_action_generation_respects_formal_gate_and_no_auto_trim_offsets(self):
        portfolio = {"NVDA": 50.0, "005930.KS": 30.0, "GLD": 20.0}
        sensitivity_rows = [
            {"ticker": "NVDA", "scenario_code": "semiconductor_ai_cycle_shock", "scenario_beta": 1.0},
            {"ticker": "005930.KS", "scenario_code": "semiconductor_ai_cycle_shock", "scenario_beta": 0.8},
            {"ticker": "GLD", "scenario_code": "semiconductor_ai_cycle_shock", "scenario_beta": -0.5},
            {"ticker": "SHY", "scenario_code": "semiconductor_ai_cycle_shock", "scenario_beta": -0.4},
        ]
        _, summary = hedge_action_engine.build_portfolio_vulnerability_attribution(portfolio, sensitivity_rows)
        recommendation_rows = [
            {
                "candidate_ticker": "SHY",
                "candidate_label": "SHY",
                "recommendation_status": "PASS_RECOMMEND",
                "final_score": 0.8,
                "hedge_budget_pct": 10.0,
                "risk_bucket_match": "semiconductor_ai_cycle_shock",
            }
        ]

        actions = hedge_action_engine.build_hedge_action_candidates(
            portfolio,
            summary,
            sensitivity_rows,
            recommendation_rows=recommendation_rows,
        )

        add_action = next(row for row in actions if row["action_type"] == "ADD_HEDGE")
        trim_action = next(row for row in actions if row["action_type"] == "TRIM_AND_HEDGE")
        self.assertEqual(add_action["action_status"], "FORMAL_ACTION")
        self.assertLess(float(add_action["vulnerability_delta"]), 0.0)
        self.assertIn("base_cvar_95", add_action)
        self.assertIn("plain_korean_reason", add_action)
        self.assertIn("source_asset", add_action)
        self.assertIn("hedge_asset", add_action)
        self.assertIn("expected_effect", add_action)
        self.assertIn("status_reason_ko", add_action)
        self.assertIn("rejected_reason_ko", add_action)
        self.assertEqual(trim_action["action_status"], "REVIEW_ACTION")
        self.assertNotIn("GLD", trim_action["source_tickers"].split("|"))

    def test_reference_candidate_stays_review_action(self):
        portfolio = {"NVDA": 50.0, "AAPL": 50.0}
        sensitivity_rows = [
            {"ticker": "NVDA", "scenario_code": "semiconductor_ai_cycle_shock", "scenario_beta": 1.0},
            {"ticker": "SHY", "scenario_code": "semiconductor_ai_cycle_shock", "scenario_beta": -0.4},
        ]
        _, summary = hedge_action_engine.build_portfolio_vulnerability_attribution(portfolio, sensitivity_rows)
        actions = hedge_action_engine.build_hedge_action_candidates(
            portfolio,
            summary,
            sensitivity_rows,
            recommendation_rows=[
                {
                    "candidate_ticker": "SHY",
                    "recommendation_status": "REFERENCE_ONLY",
                    "final_score": 0.9,
                    "hedge_budget_pct": 10.0,
                    "risk_bucket_match": "semiconductor_ai_cycle_shock",
                }
            ],
        )

        self.assertTrue(any(row["action_status"] == "REVIEW_ACTION" for row in actions))
        self.assertFalse(any(row["action_status"] == "FORMAL_ACTION" for row in actions))

    def test_selected_action_plan_diversifies_across_top_vulnerabilities(self):
        summary = {
            "risk_sleeves": [
                {"risk_sleeve": "geopolitical_supply_chain", "risk_sleeve_label_ko": "geopolitical", "net_vulnerability": 0.9},
                {"risk_sleeve": "rate_shock_growth_duration", "risk_sleeve_label_ko": "rates", "net_vulnerability": 0.7},
                {"risk_sleeve": "inflation_energy_shock", "risk_sleeve_label_ko": "inflation", "net_vulnerability": 0.5},
            ]
        }
        rows = []
        for index in range(8):
            rows.append(
                {
                    "action_id": f"geo_{index}",
                    "action_status": "REVIEW_ACTION",
                    "action_type": "TRIM_AND_HEDGE",
                    "risk_sleeve": "geopolitical_supply_chain",
                    "vulnerability_delta": -0.09 - index / 1000,
                    "turnover_pct": 10.0,
                    "source_contribution_pct": 20.0,
                }
            )
        rows.extend(
            [
                {
                    "action_id": "rates_1",
                    "action_status": "REVIEW_ACTION",
                    "action_type": "TRIM_AND_HEDGE",
                    "risk_sleeve": "rate_shock_growth_duration",
                    "vulnerability_delta": -0.02,
                    "turnover_pct": 10.0,
                    "source_contribution_pct": 20.0,
                },
                {
                    "action_id": "inflation_1",
                    "action_status": "REVIEW_ACTION",
                    "action_type": "TRIM_AND_HEDGE",
                    "risk_sleeve": "inflation_energy_shock",
                    "vulnerability_delta": -0.01,
                    "turnover_pct": 10.0,
                    "source_contribution_pct": 20.0,
                },
            ]
        )

        plan = hedge_action_engine.build_hedge_action_plan("unit-run", {"NVDA": 100}, summary, rows)

        selected_sleeves = {row["risk_sleeve"] for row in plan["selected_actions"][:3]}
        self.assertIn("geopolitical_supply_chain", selected_sleeves)
        self.assertIn("rate_shock_growth_duration", selected_sleeves)
        self.assertIn("inflation_energy_shock", selected_sleeves)
        coverage = {row["risk_sleeve"]: row for row in plan["sleeve_selection_coverage"]}
        self.assertEqual(coverage["rate_shock_growth_duration"]["coverage_status"], "SELECTED")
        self.assertEqual(plan["selection_policy"]["diversity_rule"], "select_best_action_per_positive_top_vulnerability_before_global_fill")

    def test_replace_sleeve_absence_reason_is_explicit(self):
        summary = {
            "risk_sleeves": [
                {"risk_sleeve": "geopolitical_supply_chain", "risk_sleeve_label_ko": "geopolitical", "net_vulnerability": 0.9}
            ]
        }
        rows = [
            {
                "action_id": "trim_1",
                "action_status": "REVIEW_ACTION",
                "action_type": "TRIM_AND_HEDGE",
                "risk_sleeve": "geopolitical_supply_chain",
                "vulnerability_delta": -0.05,
                "turnover_pct": 10.0,
                "source_contribution_pct": 20.0,
            }
        ]

        plan = hedge_action_engine.build_hedge_action_plan("unit-run", {"NVDA": 100}, summary, rows)

        replace = plan["replace_sleeve_decision"]
        self.assertEqual(replace["candidate_count"], 0)
        self.assertEqual(replace["selected_count"], 0)
        self.assertEqual(replace["absence_reason_code"], "NO_VALID_REPLACE_SLEEVE_CANDIDATE")
        self.assertIn("REPLACE_SLEEVE 후보가 없습니다", replace["absence_reason_ko"])

    def test_write_action_artifacts_outputs_required_files(self):
        portfolio = {"NVDA": 100.0}
        sensitivity_rows = [
            {"ticker": "NVDA", "scenario_code": "semiconductor_ai_cycle_shock", "scenario_beta": 1.0},
            {"ticker": "SHY", "scenario_code": "semiconductor_ai_cycle_shock", "scenario_beta": -0.4},
        ]
        attribution_rows, summary = hedge_action_engine.build_portfolio_vulnerability_attribution(portfolio, sensitivity_rows)
        actions = hedge_action_engine.build_hedge_action_candidates(
            portfolio,
            summary,
            sensitivity_rows,
            recommendation_rows=[{"candidate_ticker": "SHY", "recommendation_status": "REFERENCE_ONLY", "risk_bucket_match": "semiconductor_ai_cycle_shock"}],
        )
        plan = hedge_action_engine.build_hedge_action_plan("unit-run", portfolio, summary, actions)

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            artifacts = hedge_action_engine.write_action_artifacts(
                "unit-run",
                tmp_path / "processed",
                tmp_path / "reports",
                attribution_rows,
                summary,
                actions,
                plan,
            )

            self.assertTrue(artifacts["portfolio_vulnerability_attribution"].exists())
            self.assertTrue(artifacts["hedge_action_plan"].exists())
            with artifacts["hedge_action_candidates"].open("r", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
            self.assertIn("risk_sleeve", rows[0])
            self.assertIn("base_cvar_95", rows[0])
            self.assertIn("plain_korean_reason", rows[0])
            self.assertIn("expected_effect", rows[0])
            self.assertIn("selection_reason_ko", rows[0])
            self.assertIn("not_selected_reason_ko", rows[0])
            plan_payload = json.loads(artifacts["hedge_action_plan"].read_text(encoding="utf-8"))
            self.assertEqual(plan_payload["policy"]["formal_gate_not_weakened"], True)
            self.assertIn("action_type_coverage", plan_payload)
            self.assertIn("replace_sleeve_decision", plan_payload)
            self.assertIn("Next Validation Needed", artifacts["hedge_action_plan_summary"].read_text(encoding="utf-8"))
            with artifacts["portfolio_vulnerability_attribution"].open("r", encoding="utf-8") as handle:
                attribution_rows = list(csv.DictReader(handle))
            self.assertIn("plain_reason_ko", attribution_rows[0])
            self.assertIn("contribution_pct", attribution_rows[0])


if __name__ == "__main__":
    unittest.main()
