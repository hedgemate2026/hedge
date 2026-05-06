import csv
import importlib.util
import re
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "serve_dashboard.py"

spec = importlib.util.spec_from_file_location("serve_dashboard", MODULE_PATH)
serve_dashboard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(serve_dashboard)


def write_csv(path, fieldnames, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


class DashboardServerTests(unittest.TestCase):
    def setUp(self):
        serve_dashboard.RUN_JOBS.clear()

    def test_resolve_asset_query_accepts_label_and_ticker(self):
        self.assertEqual(serve_dashboard.resolve_asset_query("Tesla"), "TSLA")
        self.assertEqual(serve_dashboard.resolve_asset_query("tsla"), "TSLA")
        self.assertEqual(serve_dashboard.resolve_asset_query("삼성전자"), "005930.KS")

    def test_find_available_run_ids_sorts_desc(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            (tmp_path / "features_summary_20260305.csv").write_text("ticker\nAAPL\n", encoding="utf-8")
            latest = "20260310T101112123456-deadbeef"
            (tmp_path / f"features_summary_{latest}.csv").write_text("ticker\nAAPL\n", encoding="utf-8")
            self.assertEqual(serve_dashboard.find_available_run_ids(tmp_path), [latest, "20260305"])

    def test_parse_portfolio_rows_converts_amounts_to_weights(self):
        rows, total_amount = serve_dashboard.parse_portfolio_rows(
            [
                {"asset": "Apple", "amountKrw": 6000000},
                {"asset": "삼성전자", "amountKrw": 4000000},
            ]
        )
        self.assertEqual(total_amount, 10000000)
        self.assertEqual(rows[0]["ticker"], "AAPL")
        self.assertAlmostEqual(rows[0]["weight_pct"], 60.0)
        self.assertEqual(rows[1]["ticker"], "005930.KS")
        self.assertAlmostEqual(rows[1]["weight_pct"], 40.0)

    def test_parse_portfolio_rows_rejects_duplicate_assets(self):
        with self.assertRaises(ValueError):
            serve_dashboard.parse_portfolio_rows(
                [
                    {"asset": "Tesla", "amountKrw": 1000000},
                    {"asset": "TSLA", "amountKrw": 2000000},
                ]
            )

    def test_validate_portfolio_weights_allows_concentrated_input_up_to_fifty_percent(self):
        serve_dashboard.validate_portfolio_weights(
            [
                {"ticker": "AAPL", "weight_pct": 50.0},
                {"ticker": "MSFT", "weight_pct": 50.0},
            ]
        )

    def test_validate_portfolio_weights_rejects_weight_over_fifty_percent_by_default(self):
        with self.assertRaises(ValueError):
            serve_dashboard.validate_portfolio_weights(
                [
                    {"ticker": "AAPL", "weight_pct": 60.0},
                    {"ticker": "MSFT", "weight_pct": 40.0},
                ]
            )

    def test_validate_portfolio_weights_can_still_enforce_explicit_cap(self):
        with self.assertRaises(ValueError):
            serve_dashboard.validate_portfolio_weights(
                [
                    {"ticker": "AAPL", "weight_pct": 25.0},
                    {"ticker": "MSFT", "weight_pct": 25.0},
                    {"ticker": "NVDA", "weight_pct": 20.0},
                    {"ticker": "005930.KS", "weight_pct": 20.0},
                    {"ticker": "BTC-USD", "weight_pct": 10.0},
                ],
                max_weight_pct=20.0,
            )

    def test_build_hedge_budget_arg_supports_krw_budget(self):
        self.assertEqual(
            serve_dashboard.build_hedge_budget_arg({"hedgeBudgetKrw": 2000000}, base_amount_krw=10000000),
            "20",
        )

    def test_load_dashboard_data_parses_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            serve_dashboard.ROOT = root
            serve_dashboard.WEB_DIR = root / "web"
            serve_dashboard.OUTPUT_RAW_DIR = root / "outputs" / "raw"
            serve_dashboard.OUTPUT_PROCESSED_DIR = root / "outputs" / "processed"
            serve_dashboard.OUTPUT_REPORT_DIR = root / "outputs" / "reports"
            serve_dashboard.DOC_RESULT_DIR = root / "docs" / "STEP_1" / "04_실행결과"
            run_id = "20260310"

            write_csv(
                serve_dashboard.OUTPUT_PROCESSED_DIR / f"features_summary_{run_id}.csv",
                ["ticker", "asset_class", "mdd_1y_krw", "cvar_95_1y_krw", "sharpe_1y_krw_proxy"],
                [
                    {"ticker": "TSLA", "asset_class": "us_stock", "mdd_1y_krw": -0.71, "cvar_95_1y_krw": -0.08, "sharpe_1y_krw_proxy": 0.23},
                    {"ticker": "IAU", "asset_class": "gold_etf", "mdd_1y_krw": -0.12, "cvar_95_1y_krw": -0.02, "sharpe_1y_krw_proxy": 1.8},
                ],
            )
            write_csv(
                serve_dashboard.OUTPUT_REPORT_DIR / f"dq_result_{run_id}.csv",
                ["ticker", "status"],
                [{"ticker": "TSLA", "status": "WARN"}, {"ticker": "IAU", "status": "PASS"}],
            )
            write_csv(
                serve_dashboard.OUTPUT_PROCESSED_DIR / f"asset_risk_sensitivity_{run_id}.csv",
                ["ticker", "asset_class", "currency", "factor", "factor_label", "direction", "magnitude", "sensitivity_level", "raw_value", "value_basis", "sign_positive_meaning", "sign_negative_meaning", "structural_tags", "evidence_metrics"],
                [
                    {
                        "ticker": "TSLA",
                        "asset_class": "us_stock",
                        "currency": "USD",
                        "factor": "market_beta_sp500",
                        "factor_label": "S&P500 beta",
                        "direction": "positive",
                        "magnitude": 1.2,
                        "sensitivity_level": "high",
                        "raw_value": 1.2,
                        "value_basis": "beta_sp500_1y_krw",
                        "sign_positive_meaning": "SPY와 같은 방향",
                        "sign_negative_meaning": "SPY와 반대 방향",
                        "structural_tags": "usd_exposure",
                        "evidence_metrics": "beta_sp500_1y_krw=1.2",
                    }
                ],
            )
            write_csv(
                serve_dashboard.OUTPUT_REPORT_DIR / f"metric_validation_{run_id}.csv",
                ["metric", "status"],
                [{"metric": "vol_annual", "status": "PASS"}, {"metric": "corr", "status": "FAIL"}],
            )
            write_csv(
                serve_dashboard.OUTPUT_REPORT_DIR / f"hes_components_{run_id}.csv",
                ["ticker", "hedge_bucket", "hes_score", "cvar_95_1y_krw", "sharpe_1y_krw_proxy", "adv_60"],
                [{"ticker": "IAU", "hedge_bucket": "gold", "hes_score": 0.4, "cvar_95_1y_krw": -0.02, "sharpe_1y_krw_proxy": 1.8, "adv_60": 1000}],
            )
            write_csv(
                serve_dashboard.OUTPUT_REPORT_DIR / f"portfolio_compare_{run_id}.csv",
                ["scenario", "vol_annual", "mdd", "cvar_95", "annual_return_krw", "sharpe_krw_proxy", "vol_improve_pct", "mdd_improve_pct", "cvar_improve_pct", "sharpe_improve_pct", "stress_improve", "no_recommendation_reason"],
                [{"scenario": "기존 포트폴리오", "vol_annual": 0.2, "mdd": -0.3, "cvar_95": -0.04, "annual_return_krw": 0.2, "sharpe_krw_proxy": 0.9, "vol_improve_pct": 0, "mdd_improve_pct": 0, "cvar_improve_pct": 0, "sharpe_improve_pct": 0, "stress_improve": 0, "no_recommendation_reason": ""}],
            )
            write_csv(
                serve_dashboard.OUTPUT_REPORT_DIR / f"single_asset_compare_{run_id}.csv",
                ["scenario", "vol_annual", "mdd", "cvar_95", "annual_return_krw", "sharpe_krw_proxy", "vol_improve_pct", "mdd_improve_pct", "cvar_improve_pct", "sharpe_improve_pct", "stress_improve", "no_recommendation_reason"],
                [{"scenario": "기준(TSLA 100%)", "vol_annual": 0.6, "mdd": -0.7, "cvar_95": -0.08, "annual_return_krw": 0.17, "sharpe_krw_proxy": 0.23, "vol_improve_pct": 0, "mdd_improve_pct": 0, "cvar_improve_pct": 0, "sharpe_improve_pct": 0, "stress_improve": 0, "no_recommendation_reason": ""}],
            )
            serve_dashboard.DOC_RESULT_DIR.mkdir(parents=True, exist_ok=True)
            (serve_dashboard.DOC_RESULT_DIR / f"01_실행결과_{run_id}.md").write_text(
                "# Result\n\n- 분석기간: 2021-03-01 ~ 2026-03-10\n- 대상 티커: 70개\n- 수집 성공 티커: 70개\n- 위기구간(stress) 일수: 62일\n- 위기구간 벤치마크: SPY + ^KS200 (20거래일 -8%)\n\n## 6. 다음 액션\n- UI 연결\n",
                encoding="utf-8",
            )
            (serve_dashboard.OUTPUT_REPORT_DIR / f"asset_sensitivity_summary_{run_id}.md").write_text(
                "# Summary\n\n- direction count: positive 1\n",
                encoding="utf-8",
            )
            for rel in [
                serve_dashboard.OUTPUT_RAW_DIR / f"raw_market_daily_{run_id}.csv",
                serve_dashboard.OUTPUT_RAW_DIR / f"raw_fx_daily_{run_id}.csv",
                serve_dashboard.OUTPUT_RAW_DIR / f"raw_benchmark_daily_{run_id}.csv",
            ]:
                rel.parent.mkdir(parents=True, exist_ok=True)
                rel.write_text("stub", encoding="utf-8")

            data = serve_dashboard.load_dashboard_data(run_id)
            self.assertEqual(data["runId"], run_id)
            self.assertEqual(data["singleAssetTicker"], "TSLA")
            self.assertEqual(data["dqSummary"]["pass"], 1)
            self.assertEqual(data["dqSummary"]["warn"], 1)
            self.assertEqual(data["validationSummary"]["fail"], 1)
            self.assertEqual(data["nextActions"], ["UI 연결"])
            self.assertIn("portfolioCompare", data)
            self.assertIn("resultMd", data["artifacts"])
            self.assertIn("assetSensitivity", data["artifacts"])
            self.assertEqual(data["assetSensitivities"][0]["factor"], "market_beta_sp500")
            self.assertEqual(data["assetSensitivities"][0]["displayName"], "Tesla")
            self.assertEqual(data["worstRiskAssets"][0]["displayName"], "Tesla")

    def test_choose_best_detail_prefers_pass_across_result_groups(self):
        best = serve_dashboard.choose_best_detail(
            [{"status": "FAIL", "final_score": 0.9, "candidate_combo": "IAU + GLD", "weights_snapshot": '{"IAU": 10, "GLD": 10}'}],
            [{"status": "PASS", "final_score": 0.4, "candidate_ticker": "IEF", "weights_snapshot": '{"IEF": 20}'}],
        )
        self.assertEqual(best["status"], "PASS")
        self.assertEqual(best["candidate_ticker"], "IEF")

    def test_safe_rel_artifact_allows_outputs_and_blocks_outside_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            serve_dashboard.ROOT = root
            serve_dashboard.WEB_DIR = root / "web"
            serve_dashboard.OUTPUT_RAW_DIR = root / "outputs" / "raw"
            serve_dashboard.OUTPUT_PROCESSED_DIR = root / "outputs" / "processed"
            serve_dashboard.OUTPUT_REPORT_DIR = root / "outputs" / "reports"
            serve_dashboard.DOC_RESULT_DIR = root / "docs" / "STEP_1" / "04_실행결과"
            run_id = "20260310"
            allowed = serve_dashboard.OUTPUT_REPORT_DIR / f"portfolio_compare_{run_id}.csv"
            allowed.parent.mkdir(parents=True, exist_ok=True)
            allowed.write_text("scenario\n기존 포트폴리오\n", encoding="utf-8")

            blocked = root / "secret.txt"
            blocked.write_text("x", encoding="utf-8")

            resolved = serve_dashboard.safe_rel_artifact(f"outputs/reports/portfolio_compare_{run_id}.csv")
            self.assertEqual(resolved, allowed.resolve())
            self.assertIsNone(serve_dashboard.safe_rel_artifact("secret.txt"))

    def test_humanize_scenario_replaces_tickers(self):
        self.assertEqual(
            serve_dashboard.humanize_scenario("제안(다자산) - IAU + GLD + SHY"),
            "제안(다자산) - 금 ETF(IAU) + 금 ETF(GLD) + 단기국채 ETF",
        )
        self.assertEqual(
            serve_dashboard.humanize_scenario("기준(TSLA 100%)"),
            "기준(Tesla 100%)",
        )

    def test_run_pipeline_for_request_builds_single_asset_command(self):
        class Result:
            returncode = 0
            stdout = "FEATURE=outputs/processed/features_summary_20260310.csv\n"
            stderr = ""

        calls = {}

        def fake_runner(cmd, cwd, capture_output, text, check):
            calls["cmd"] = cmd
            calls["cwd"] = cwd
            calls["capture_output"] = capture_output
            calls["text"] = text
            calls["check"] = check
            return Result()

        payload = {"mode": "single_asset", "singleAsset": "tsla", "hedgeBudgets": "10,20", "maxComboSize": 3}
        result = serve_dashboard.run_pipeline_for_request(payload, runner=fake_runner)
        self.assertTrue(result["ok"])
        self.assertEqual(result["runId"], "20260310")
        self.assertIn("--run-id", calls["cmd"])
        self.assertIn("--single-asset", calls["cmd"])
        self.assertIn("TSLA", calls["cmd"])

    def test_run_pipeline_for_request_accepts_single_asset_name_and_krw_budget(self):
        class Result:
            returncode = 0
            stdout = "FEATURE=outputs/processed/features_summary_20260310.csv\n"
            stderr = ""

        calls = {}

        def fake_runner(cmd, cwd, capture_output, text, check):
            calls["cmd"] = cmd
            return Result()

        payload = {"mode": "single_asset", "singleAsset": "Tesla", "baseAmountKrw": 10000000, "hedgeBudgetKrw": 2000000, "maxComboSize": 3}
        serve_dashboard.run_pipeline_for_request(payload, runner=fake_runner)
        self.assertIn("TSLA", calls["cmd"])
        self.assertIn("--base-total-krw", calls["cmd"])
        self.assertIn("--hedge-budgets-krw", calls["cmd"])
        self.assertIn("2000000.0", calls["cmd"])

    def test_run_pipeline_for_request_accepts_structured_portfolio_rows(self):
        class Result:
            returncode = 0
            stdout = "FEATURE=outputs/processed/features_summary_20260310.csv\n"
            stderr = ""

        calls = {}

        def fake_runner(cmd, cwd, capture_output, text, check):
            calls["cmd"] = cmd
            calls["cwd"] = cwd
            return Result()

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            serve_dashboard.ROOT = root
            serve_dashboard.INPUT_DIR = root / "inputs"

            payload = {
                "mode": "portfolio",
                "portfolioRows": [
                    {"asset": "Apple", "amountKrw": 2000000},
                    {"asset": "Microsoft", "amountKrw": 2000000},
                    {"asset": "NVIDIA", "amountKrw": 2000000},
                    {"asset": "삼성전자", "amountKrw": 2000000},
                    {"asset": "비트코인", "amountKrw": 1000000},
                    {"asset": "Tesla", "amountKrw": 1000000},
                ],
                "hedgeBudgetKrw": 1000000,
                "maxComboSize": 2,
            }
            serve_dashboard.run_pipeline_for_request(payload, runner=fake_runner)
            written_files = sorted(serve_dashboard.INPUT_DIR.glob("portfolio_weights_*.csv"))
            self.assertEqual(len(written_files), 1)
            written = written_files[0].read_text(encoding="utf-8")
            self.assertIn("AAPL", written)
            self.assertIn("005930.KS", written)
            self.assertIn("--portfolio-input", calls["cmd"])
            self.assertTrue(any("portfolio_weights_" in str(part) for part in calls["cmd"]))
            self.assertIn("--base-total-krw", calls["cmd"])
            self.assertIn("10000000.0", calls["cmd"])
            self.assertIn("--hedge-budgets-krw", calls["cmd"])

    def test_run_pipeline_for_request_rejects_invalid_structured_portfolio_before_runner(self):
        called = {"runner": False}

        def fake_runner(cmd, cwd, capture_output, text, check):
            called["runner"] = True
            raise AssertionError("runner should not be called")

        payload = {
            "mode": "portfolio",
            "portfolioRows": [
                {"asset": "Apple", "amountKrw": 2500000},
                {"asset": "Apple", "amountKrw": 2500000},
                {"asset": "NVIDIA", "amountKrw": 2000000},
                {"asset": "삼성전자", "amountKrw": 2000000},
                {"asset": "비트코인", "amountKrw": 1000000},
            ],
            "hedgeBudgetKrw": 1000000,
            "maxComboSize": 2,
        }
        with self.assertRaises(ValueError):
            serve_dashboard.run_pipeline_for_request(payload, runner=fake_runner)
        self.assertFalse(called["runner"])

    def test_parse_portfolio_text_requires_ticker_weight_format(self):
        rows = serve_dashboard.parse_portfolio_text("AAPL,20\nMSFT,30")
        self.assertEqual(rows[0]["ticker"], "AAPL")
        self.assertEqual(rows[1]["weight_pct"], 30.0)
        with self.assertRaises(ValueError):
            serve_dashboard.parse_portfolio_text("AAPL 20")

    def test_launch_run_job_completes_and_stores_result(self):
        class Result:
            returncode = 0
            stdout = "FEATURE=outputs/processed/features_summary_20260310.csv\n"
            stderr = ""

        class ImmediateThread:
            def __init__(self, target, args=(), daemon=None):
                self.target = target
                self.args = args
                self.daemon = daemon

            def start(self):
                self.target(*self.args)

        def fake_runner(cmd, cwd, capture_output, text, check):
            return Result()

        payload = {"mode": "single_asset", "singleAsset": "Tesla", "baseAmountKrw": 10000000, "hedgeBudgetKrw": 2000000}
        job = serve_dashboard.launch_run_job(payload, runner=fake_runner, thread_factory=ImmediateThread)

        self.assertEqual(job["status"], "completed")
        self.assertEqual(job["runId"], "20260310")
        self.assertEqual(job["result"]["runId"], "20260310")
        self.assertIsNone(job["error"])

    def test_launch_run_job_rejects_invalid_request_before_creating_job(self):
        with self.assertRaises(ValueError):
            serve_dashboard.launch_run_job(
                {"mode": "single_asset", "singleAsset": "NOT_A_TICKER", "baseAmountKrw": 10000000, "hedgeBudgetKrw": 2000000}
            )
        self.assertEqual(serve_dashboard.RUN_JOBS, {})

    def test_build_run_id_returns_extended_unique_format(self):
        run_id = serve_dashboard.build_run_id()
        self.assertRegex(run_id, r"^\d{8}T\d{12}-[0-9a-f]{8}$")


if __name__ == "__main__":
    unittest.main()
