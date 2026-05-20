import csv
import importlib.util
import json
import os
import re
import tempfile
import threading
import unittest
import urllib.request
from datetime import date
from pathlib import Path
from unittest import mock


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
    def _last_js_function_body(self, source, name):
        marker = f"function {name}("
        start = source.rfind(marker)
        self.assertNotEqual(start, -1, f"{name} function not found")
        paren = source.index("(", start)
        paren_depth = 0
        signature_end = None
        for idx in range(paren, len(source)):
            char = source[idx]
            if char == "(":
                paren_depth += 1
            elif char == ")":
                paren_depth -= 1
                if paren_depth == 0:
                    signature_end = idx
                    break
        self.assertIsNotNone(signature_end, f"{name} function signature was not closed")
        brace = source.index("{", signature_end)
        depth = 0
        for idx in range(brace, len(source)):
            char = source[idx]
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    return source[brace + 1 : idx]
        self.fail(f"{name} function body was not closed")

    def setUp(self):
        serve_dashboard.RUN_JOBS.clear()
        serve_dashboard.ROOT = ROOT
        serve_dashboard.INPUT_DIR = ROOT / "inputs"
        serve_dashboard.WEB_DIR = ROOT / "web"
        serve_dashboard.OUTPUT_RAW_DIR = ROOT / "outputs" / "raw"
        serve_dashboard.OUTPUT_PROCESSED_DIR = ROOT / "outputs" / "processed"
        serve_dashboard.OUTPUT_REPORT_DIR = ROOT / "outputs" / "reports"
        serve_dashboard.OUTPUT_VALIDATION_DIR = ROOT / "outputs" / "validation"
        serve_dashboard.DOC_RESULT_DIR = ROOT / "docs" / "STEP_1" / "04_실행결과"
        serve_dashboard.SCENARIO_RESEARCH_ROOT = ROOT.parent / "scenario_research"
        serve_dashboard.SCENARIO_OUTPUT_DIR = serve_dashboard.SCENARIO_RESEARCH_ROOT / "outputs"
        serve_dashboard.SCENARIO_FINAL_DIR = serve_dashboard.SCENARIO_OUTPUT_DIR / "final"
        serve_dashboard.SCENARIO_PROCESSED_DIR = serve_dashboard.SCENARIO_OUTPUT_DIR / "processed"
        serve_dashboard.SCENARIO_REPORT_DIR = serve_dashboard.SCENARIO_OUTPUT_DIR / "reports"
        serve_dashboard.SCENARIO_VECTOR_DIR = serve_dashboard.SCENARIO_OUTPUT_DIR / "scenario_vectors"
        serve_dashboard.SCENARIO_NOWCAST_DIR = serve_dashboard.SCENARIO_OUTPUT_DIR / "nowcast_vectors"
        serve_dashboard.SCENARIO_EVENT_DIR = serve_dashboard.SCENARIO_OUTPUT_DIR / "events"
        serve_dashboard.SCENARIO_VALIDATION_DIR = serve_dashboard.SCENARIO_OUTPUT_DIR / "validation"

    def test_resolve_asset_query_accepts_label_and_ticker(self):
        self.assertEqual(serve_dashboard.resolve_asset_query("Tesla"), "TSLA")
        self.assertEqual(serve_dashboard.resolve_asset_query("tes"), "TSLA")
        self.assertEqual(serve_dashboard.resolve_asset_query("tsla"), "TSLA")
        self.assertEqual(serve_dashboard.resolve_asset_query("삼성전자"), "005930.KS")
        self.assertEqual(serve_dashboard.resolve_asset_query("금ETF"), "GLD")

    def test_asset_options_include_aliases_and_user_friendly_labels(self):
        assets = {row["ticker"]: row for row in serve_dashboard.asset_options()}
        self.assertEqual(assets["TSLA"]["displayLabel"], "Tesla (TSLA)")
        self.assertEqual(assets["SHY"]["displayLabel"], "단기 미국국채 ETF (SHY)")
        self.assertIn("테슬라", assets["TSLA"]["aliases"])
        self.assertIn("금", assets["GLD"]["aliases"])
        self.assertEqual(assets["005930.KS"]["assetClass"], "국내주식")

    def test_find_available_run_ids_sorts_desc(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            (tmp_path / "features_summary_20260305.csv").write_text("ticker\nAAPL\n", encoding="utf-8")
            latest = "20260310T101112123456-deadbeef"
            (tmp_path / f"features_summary_{latest}.csv").write_text("ticker\nAAPL\n", encoding="utf-8")
            self.assertEqual(serve_dashboard.find_available_run_ids(tmp_path), [latest, "20260305"])

    def test_find_available_run_ids_prefers_active_bundle_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            serve_dashboard.ROOT = root
            serve_dashboard.OUTPUT_PROCESSED_DIR = root / "outputs" / "processed"
            serve_dashboard.OUTPUT_PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
            (serve_dashboard.OUTPUT_PROCESSED_DIR / "features_summary_20260310.csv").write_text("ticker\nTSLA\n", encoding="utf-8")
            (serve_dashboard.OUTPUT_PROCESSED_DIR / "features_summary_hedgemate-prod.csv").write_text("ticker\nGLD\n", encoding="utf-8")
            (root / "outputs").mkdir(parents=True, exist_ok=True)
            (root / "outputs" / "latest_manifest.json").write_text(
                '{"active_bundle":{"hedgemate_run":"hedgemate-prod"},"active_hedgemate_run":"hedgemate-prod"}',
                encoding="utf-8",
            )

            self.assertEqual(serve_dashboard.find_available_run_ids(serve_dashboard.OUTPUT_PROCESSED_DIR), ["hedgemate-prod", "20260310"])

    def test_find_scenario_run_ids_sorts_by_recent_file_first(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            older = tmp_path / "final_market_state_daily_phase-z.csv"
            newer = tmp_path / "final_market_state_daily_phase-a.csv"
            older.write_text("date\n2026-01-01\n", encoding="utf-8")
            newer.write_text("date\n2026-01-02\n", encoding="utf-8")
            os.utime(older, (1000, 1000))
            os.utime(newer, (2000, 2000))
            self.assertEqual(serve_dashboard.find_scenario_run_ids(tmp_path), ["phase-a", "phase-z"])

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

    def test_lookup_price_uses_cached_market_and_fx_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            serve_dashboard.OUTPUT_RAW_DIR = root / "outputs" / "raw"
            write_csv(
                serve_dashboard.OUTPUT_RAW_DIR / "raw_market_daily_20260518.csv",
                ["date", "ticker", "asset_class", "source", "close", "adj_close", "currency", "ingested_at"],
                [{"date": "2026-05-18", "ticker": "AAPL", "asset_class": "us_stock", "source": "cache", "close": "100", "adj_close": "100", "currency": "USD", "ingested_at": "2026-05-18T00:00:00Z"}],
            )
            write_csv(
                serve_dashboard.OUTPUT_RAW_DIR / "raw_fx_daily_20260518.csv",
                ["date", "ticker", "close", "source", "currency", "ingested_at"],
                [{"date": "2026-05-18", "ticker": "KRW=X", "close": "1300", "source": "cache", "currency": "KRW", "ingested_at": "2026-05-18T00:00:00Z"}],
            )

            result = serve_dashboard.lookup_price("Apple", quantity=2, data_version="20260518")

            self.assertEqual(result["resolvedTicker"], "AAPL")
            self.assertEqual(result["displayLabel"], "Apple (AAPL)")
            self.assertEqual(result["latestPrice"], 100.0)
            self.assertEqual(result["unitPriceKrw"], 130000.0)
            self.assertEqual(result["fxRate"], 1300.0)
            self.assertEqual(result["marketValueKrw"], 260000.0)
            self.assertEqual(result["valuationBasis"], "quantity")
            self.assertEqual(result["dataMode"], "cache")

    def test_enrich_execution_plan_uses_combo_share_counts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            serve_dashboard.ROOT = root
            serve_dashboard.OUTPUT_RAW_DIR = root / "outputs" / "raw"
            serve_dashboard._MARKET_PRICE_CACHE.clear()
            serve_dashboard._FX_PRICE_CACHE.clear()
            (root / "outputs").mkdir(parents=True, exist_ok=True)
            (root / "outputs" / "latest_manifest.json").write_text(json.dumps({"data_version": "20260518"}), encoding="utf-8")
            write_csv(
                serve_dashboard.OUTPUT_RAW_DIR / "raw_market_daily_20260518.csv",
                ["date", "ticker", "asset_class", "source", "close", "adj_close", "currency", "ingested_at"],
                [
                    {"date": "2026-05-18", "ticker": "GLD", "asset_class": "gold_etf", "source": "cache", "close": "400", "adj_close": "400", "currency": "USD", "ingested_at": "2026-05-18T00:00:00Z"},
                    {"date": "2026-05-18", "ticker": "IAU", "asset_class": "gold_etf", "source": "cache", "close": "80", "adj_close": "80", "currency": "USD", "ingested_at": "2026-05-18T00:00:00Z"},
                ],
            )
            write_csv(
                serve_dashboard.OUTPUT_RAW_DIR / "raw_fx_daily_20260518.csv",
                ["date", "ticker", "close", "source", "currency", "ingested_at"],
                [{"date": "2026-05-18", "ticker": "KRW=X", "close": "1300", "source": "cache", "currency": "KRW", "ingested_at": "2026-05-18T00:00:00Z"}],
            )
            row = {
                "candidate_combo": "GLD + IAU",
                "hedge_share_counts": json.dumps({"GLD": 2, "IAU": 5}),
                "hedge_cash_left_krw": 12345.0,
            }

            enriched = serve_dashboard.enrich_execution_plan(row)

            self.assertEqual(len(enriched["executionPlan"]), 2)
            self.assertEqual(enriched["executionPlan"][0]["wholeShareQuantity"], 2)
            self.assertEqual(enriched["executionPlan"][0]["estimatedUsedKrw"], 1040000.0)
            self.assertIn("후보 전체 예상 잔액", enriched["executionNote"])

    def test_portfolio_preview_accepts_mixed_quantity_and_krw_amounts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            serve_dashboard.OUTPUT_RAW_DIR = root / "outputs" / "raw"
            write_csv(
                serve_dashboard.OUTPUT_RAW_DIR / "raw_market_daily_20260518.csv",
                ["date", "ticker", "asset_class", "source", "close", "adj_close", "currency", "ingested_at"],
                [
                    {"date": "2026-05-18", "ticker": "AAPL", "asset_class": "us_stock", "source": "cache", "close": "100", "adj_close": "100", "currency": "USD", "ingested_at": "2026-05-18T00:00:00Z"},
                    {"date": "2026-05-18", "ticker": "005930.KS", "asset_class": "kr_stock", "source": "cache", "close": "70000", "adj_close": "70000", "currency": "KRW", "ingested_at": "2026-05-18T00:00:00Z"},
                ],
            )
            write_csv(
                serve_dashboard.OUTPUT_RAW_DIR / "raw_fx_daily_20260518.csv",
                ["date", "ticker", "close", "source", "currency", "ingested_at"],
                [{"date": "2026-05-18", "ticker": "KRW=X", "close": "1300", "source": "cache", "currency": "KRW", "ingested_at": "2026-05-18T00:00:00Z"}],
            )

            preview = serve_dashboard.preview_portfolio(
                {
                    "dataVersion": "20260518",
                    "portfolioRows": [
                        {"asset": "Apple", "quantity": 2},
                        {"asset": "005930.KS", "amountKrw": 260000},
                    ],
                }
            )

            self.assertTrue(preview["canRunAnalysis"])
            self.assertAlmostEqual(preview["totalMarketValueKrw"], 520000.0)
            self.assertEqual(preview["analysisRows"][0]["ticker"], "AAPL")
            self.assertAlmostEqual(preview["analysisRows"][0]["weight_pct"], 50.0)
            self.assertEqual(preview["analysisRows"][1]["ticker"], "005930.KS")
            self.assertAlmostEqual(preview["analysisRows"][1]["weight_pct"], 50.0)

    def test_portfolio_preview_blocks_analysis_when_weight_cap_would_fail_execution(self):
        preview = serve_dashboard.preview_portfolio(
            {
                "portfolioRows": [
                    {"asset": "AAPL", "amountKrw": 8000000},
                    {"asset": "MSFT", "amountKrw": 2000000},
                ],
            }
        )

        self.assertFalse(preview["canRunAnalysis"])
        self.assertFalse(preview["ok"])
        self.assertIn("AAPL", " ".join(preview["errors"]))

    def test_data_freshness_reports_skip_when_manifest_is_current_and_complete(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            serve_dashboard.ROOT = root
            (root / "outputs" / "reports").mkdir(parents=True, exist_ok=True)
            artifact = root / "outputs" / "reports" / "x.csv"
            artifact.write_text("x\n", encoding="utf-8")
            (root / "outputs" / "latest_manifest.json").write_text(
                '{"freshness_status":"FRESH","data_version":"20260519","artifacts":{"x":"outputs/reports/x.csv"},"active_bundle":{"data_version":"20260519","freshness_status":"FRESH"}}',
                encoding="utf-8",
            )

            freshness = serve_dashboard.load_data_freshness(reference_date=date(2026, 5, 19))

            self.assertEqual(freshness["status"], "current")
            self.assertFalse(freshness["needsRefresh"])
            self.assertTrue(freshness["skipHeavyRefresh"])

    def test_data_freshness_flags_portfolio_input_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            serve_dashboard.ROOT = root
            serve_dashboard.INPUT_DIR = root / "inputs"
            serve_dashboard.INPUT_DIR.mkdir(parents=True, exist_ok=True)
            (root / "outputs" / "reports").mkdir(parents=True, exist_ok=True)
            artifact = root / "outputs" / "reports" / "x.csv"
            artifact.write_text("x\n", encoding="utf-8")
            old_portfolio = root / "old_portfolio.csv"
            old_portfolio.write_text("ticker,weight_pct\nAAPL,50\nMSFT,50\n", encoding="utf-8")
            current_portfolio = serve_dashboard.INPUT_DIR / "portfolio_weights.csv"
            current_portfolio.write_text("ticker,weight_pct\nMSFT,50\nNVDA,50\n", encoding="utf-8")
            old_fingerprint = serve_dashboard.current_portfolio_fingerprint(old_portfolio)
            (root / "outputs" / "latest_manifest.json").write_text(
                json.dumps(
                    {
                        "freshness_status": "FRESH",
                        "data_version": "20260519",
                        "portfolio_input_fingerprint": old_fingerprint,
                        "artifacts": {"x": "outputs/reports/x.csv"},
                        "active_bundle": {
                            "data_version": "20260519",
                            "freshness_status": "FRESH",
                            "portfolio_input_fingerprint": old_fingerprint,
                        },
                    }
                ),
                encoding="utf-8",
            )

            freshness = serve_dashboard.load_data_freshness(reference_date=date(2026, 5, 19))

            self.assertEqual(freshness["status"], "stale")
            self.assertTrue(freshness["portfolioInputMismatch"])
            self.assertFalse(freshness["skipHeavyRefresh"])
            self.assertIn("portfolio input mismatch", " ".join(freshness["reasons"]))

    def test_data_freshness_flags_stale_scenario_snapshot_version_even_when_price_data_is_today(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            serve_dashboard.ROOT = root
            serve_dashboard.SCENARIO_REPORT_DIR = root.parent / "scenario_research" / "outputs" / "reports"
            serve_dashboard.SCENARIO_REPORT_DIR.mkdir(parents=True, exist_ok=True)
            (root / "outputs" / "reports").mkdir(parents=True, exist_ok=True)
            artifact = root / "outputs" / "reports" / "x.csv"
            artifact.write_text("x\n", encoding="utf-8")
            (serve_dashboard.SCENARIO_REPORT_DIR / "scenario_snapshot_metadata_scenario-old.json").write_text(
                json.dumps({"data_version": "20260519", "scenario_vector_as_of_date": "2026-05-18"}),
                encoding="utf-8",
            )
            (root / "outputs" / "latest_manifest.json").write_text(
                json.dumps(
                    {
                        "freshness_status": "FRESH",
                        "data_version": "20260520",
                        "artifacts": {"x": "outputs/reports/x.csv"},
                        "active_bundle": {
                            "scenario_run": "scenario-old",
                            "data_version": "20260520",
                            "scenario_vector_as_of_date": "2026-05-18",
                            "freshness_status": "FRESH",
                        },
                    }
                ),
                encoding="utf-8",
            )

            freshness = serve_dashboard.load_data_freshness(reference_date=date(2026, 5, 20))

            self.assertEqual(freshness["status"], "stale")
            self.assertTrue(freshness["needsRefresh"])
            self.assertFalse(freshness["skipHeavyRefresh"])
            self.assertEqual(freshness["scenarioVectorLagDays"], 2)
            self.assertEqual(freshness["scenarioDataVersion"], "20260519")
            self.assertIn("scenario data_version", " ".join(freshness["reasons"]))

    def test_data_freshness_allows_lagged_scenario_as_of_when_snapshot_version_matches(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            serve_dashboard.ROOT = root
            serve_dashboard.SCENARIO_REPORT_DIR = root.parent / "scenario_research" / "outputs" / "reports"
            serve_dashboard.SCENARIO_REPORT_DIR.mkdir(parents=True, exist_ok=True)
            (root / "outputs" / "reports").mkdir(parents=True, exist_ok=True)
            artifact = root / "outputs" / "reports" / "x.csv"
            artifact.write_text("x\n", encoding="utf-8")
            (serve_dashboard.SCENARIO_REPORT_DIR / "scenario_snapshot_metadata_scenario-current.json").write_text(
                json.dumps({"data_version": "20260520", "scenario_vector_as_of_date": "2026-05-18"}),
                encoding="utf-8",
            )
            (root / "outputs" / "latest_manifest.json").write_text(
                json.dumps(
                    {
                        "freshness_status": "FRESH",
                        "data_version": "20260520",
                        "artifacts": {"x": "outputs/reports/x.csv"},
                        "active_bundle": {
                            "scenario_run": "scenario-current",
                            "data_version": "20260520",
                            "scenario_vector_as_of_date": "2026-05-18",
                            "freshness_status": "FRESH",
                        },
                    }
                ),
                encoding="utf-8",
            )

            freshness = serve_dashboard.load_data_freshness(reference_date=date(2026, 5, 20))

            self.assertEqual(freshness["status"], "current")
            self.assertFalse(freshness["needsRefresh"])
            self.assertTrue(freshness["skipHeavyRefresh"])
            self.assertEqual(freshness["scenarioVectorLagDays"], 2)
            self.assertEqual(freshness["scenarioDataVersion"], "20260520")

    def test_data_freshness_flags_historical_stress_price_gap(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            serve_dashboard.ROOT = root
            validation_dir = root / "outputs" / "validation"
            validation_dir.mkdir(parents=True, exist_ok=True)
            backtest_csv = validation_dir / "walk_forward_backtest_gap.csv"
            write_csv(
                backtest_csv,
                ["case_id", "case_name", "backtest_status", "price_window_status"],
                [
                    {
                        "case_id": "gfc",
                        "case_name": "GFC",
                        "backtest_status": "INSUFFICIENT_HISTORY",
                        "price_window_status": "OUT_OF_PRICE_RANGE",
                    }
                ],
            )
            (root / "outputs" / "latest_manifest.json").write_text(
                json.dumps(
                    {
                        "freshness_status": "FRESH",
                        "data_version": "20260519",
                        "artifacts": {"backtestCsv": "outputs/validation/walk_forward_backtest_gap.csv"},
                        "active_bundle": {"data_version": "20260519", "freshness_status": "FRESH"},
                    }
                ),
                encoding="utf-8",
            )

            freshness = serve_dashboard.load_data_freshness(reference_date=date(2026, 5, 19))

            self.assertEqual(freshness["status"], "stale")
            self.assertTrue(freshness["needsRefresh"])
            self.assertFalse(freshness["skipHeavyRefresh"])
            self.assertEqual(freshness["backtestPriceGapSummary"]["outOfPriceRangeRows"], 1)
            self.assertIn("historical stress price coverage gap", " ".join(freshness["reasons"]))

    def test_refresh_market_data_job_uses_responsive_combo_size_and_cache_by_default(self):
        class Result:
            returncode = 0
            stdout = "REFRESHED\n"
            stderr = ""

        calls = {}

        def fake_runner(cmd, cwd, capture_output, text, check):
            calls["cmd"] = cmd
            calls["cwd"] = cwd
            return Result()

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "HedgeMate"
            serve_dashboard.ROOT = root
            job_id = "refresh-job"
            serve_dashboard.RUN_JOBS[job_id] = {"jobId": job_id, "status": "running"}

            serve_dashboard._run_refresh_market_data_job(
                job_id,
                {"dataVersion": "20260520", "runStamp": "smoke"},
                fake_runner,
            )

        self.assertIn("refresh_product_bundle.py", " ".join(calls["cmd"]))
        self.assertEqual(calls["cmd"][calls["cmd"].index("--max-combo-size") + 1], "2")
        self.assertNotIn("--force-refresh-raw", calls["cmd"])
        self.assertEqual(serve_dashboard.RUN_JOBS[job_id]["status"], "completed")

    def test_refresh_market_data_job_can_force_raw_refresh_explicitly(self):
        class Result:
            returncode = 0
            stdout = "REFRESHED\n"
            stderr = ""

        calls = {}

        def fake_runner(cmd, cwd, capture_output, text, check):
            calls["cmd"] = cmd
            return Result()

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "HedgeMate"
            serve_dashboard.ROOT = root
            job_id = "refresh-force-job"
            serve_dashboard.RUN_JOBS[job_id] = {"jobId": job_id, "status": "running"}

            serve_dashboard._run_refresh_market_data_job(
                job_id,
                {"dataVersion": "20260520", "runStamp": "smoke", "maxComboSize": 3, "forceRefreshRaw": True},
                fake_runner,
            )

        self.assertEqual(calls["cmd"][calls["cmd"].index("--max-combo-size") + 1], "3")
        self.assertIn("--force-refresh-raw", calls["cmd"])

    def test_refresh_market_data_job_forwards_portfolio_amount_context(self):
        class Result:
            returncode = 0
            stdout = "REFRESHED\n"
            stderr = ""

        calls = {}

        def fake_runner(cmd, cwd, capture_output, text, check):
            calls["cmd"] = cmd
            return Result()

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "HedgeMate"
            serve_dashboard.ROOT = root
            serve_dashboard.INPUT_DIR = root / "inputs"
            job_id = "refresh-portfolio-job"
            serve_dashboard.RUN_JOBS[job_id] = {"jobId": job_id, "status": "running"}

            serve_dashboard._run_refresh_market_data_job(
                job_id,
                {
                    "dataVersion": "20260520",
                    "runStamp": "smoke",
                    "portfolioRows": [
                        {"asset": "AAPL", "amountKrw": 4000000},
                        {"asset": "MSFT", "amountKrw": 3000000},
                        {"asset": "NVDA", "amountKrw": 3000000},
                    ],
                    "hedgeBudgetKrw": 1000000,
                },
                fake_runner,
            )

        self.assertIn("--portfolio-input", calls["cmd"])
        self.assertIn("--base-total-krw", calls["cmd"])
        self.assertEqual(calls["cmd"][calls["cmd"].index("--base-total-krw") + 1], "10000000.0")
        self.assertIn("--hedge-budgets-krw", calls["cmd"])
        self.assertEqual(calls["cmd"][calls["cmd"].index("--hedge-budgets-krw") + 1], "1000000.0")
        self.assertEqual(serve_dashboard.RUN_JOBS[job_id]["status"], "completed")
        context = serve_dashboard.RUN_JOBS[job_id]["result"]["portfolioContext"]
        self.assertTrue(context["requested"])
        self.assertTrue(context["applied"])
        self.assertEqual(context["reason"], "portfolio_context_applied")
        self.assertEqual(context["totalMarketValueKrw"], 10000000.0)
        self.assertEqual(context["hedgeBudgetKrw"], 1000000.0)

    def test_refresh_market_data_job_skips_invalid_portfolio_context_without_failing_refresh(self):
        class Result:
            returncode = 0
            stdout = "REFRESHED\n"
            stderr = ""

        calls = {}

        def fake_runner(cmd, cwd, capture_output, text, check):
            calls["cmd"] = cmd
            return Result()

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "HedgeMate"
            serve_dashboard.ROOT = root
            serve_dashboard.INPUT_DIR = root / "inputs"
            job_id = "refresh-invalid-portfolio-job"
            serve_dashboard.RUN_JOBS[job_id] = {"jobId": job_id, "status": "running"}

            serve_dashboard._run_refresh_market_data_job(
                job_id,
                {
                    "dataVersion": "20260520",
                    "runStamp": "smoke",
                    "portfolioRows": [
                        {"asset": "AAPL", "amountKrw": 8000000},
                        {"asset": "MSFT", "amountKrw": 2000000},
                    ],
                    "hedgeBudgetKrw": 1000000,
                },
                fake_runner,
            )

        self.assertNotIn("--portfolio-input", calls["cmd"])
        self.assertNotIn("--base-total-krw", calls["cmd"])
        self.assertEqual(serve_dashboard.RUN_JOBS[job_id]["status"], "completed")
        context = serve_dashboard.RUN_JOBS[job_id]["result"]["portfolioContext"]
        self.assertTrue(context["requested"])
        self.assertFalse(context["applied"])
        self.assertIn("portfolio_context_omitted_preview_error", context["reason"])

    def test_launch_refresh_does_not_skip_when_portfolio_context_is_present(self):
        class Result:
            returncode = 0
            stdout = "REFRESHED\n"
            stderr = ""

        class ImmediateThread:
            def __init__(self, target, args=(), kwargs=None, daemon=None):
                self.target = target
                self.args = args
                self.kwargs = kwargs or {}

            def start(self):
                self.target(*self.args, **self.kwargs)

        calls = {}

        def fake_runner(cmd, cwd, capture_output, text, check):
            calls["cmd"] = cmd
            return Result()

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "HedgeMate"
            serve_dashboard.ROOT = root
            serve_dashboard.INPUT_DIR = root / "inputs"
            with mock.patch.object(
                serve_dashboard,
                "load_data_freshness",
                return_value={"status": "current", "skipHeavyRefresh": True},
            ):
                job = serve_dashboard.launch_refresh_market_data_job(
                    {
                        "portfolioRows": [
                            {"asset": "AAPL", "amountKrw": 4000000},
                            {"asset": "MSFT", "amountKrw": 3000000},
                            {"asset": "NVDA", "amountKrw": 3000000},
                        ],
                        "hedgeBudgetKrw": 1000000,
                    },
                    runner=fake_runner,
                    thread_factory=ImmediateThread,
                )

        self.assertEqual(job["status"], "completed")
        self.assertIn("--base-total-krw", calls["cmd"])
        self.assertIn("--hedge-budgets-krw", calls["cmd"])
        self.assertTrue(job["result"]["portfolioContext"]["applied"])

    def test_active_dashboard_does_not_fallback_to_raw_recommendations_when_gated_artifact_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            serve_dashboard.ROOT = root
            serve_dashboard.OUTPUT_RAW_DIR = root / "outputs" / "raw"
            serve_dashboard.OUTPUT_PROCESSED_DIR = root / "outputs" / "processed"
            serve_dashboard.OUTPUT_REPORT_DIR = root / "outputs" / "reports"
            serve_dashboard.OUTPUT_VALIDATION_DIR = root / "outputs" / "validation"
            serve_dashboard.DOC_RESULT_DIR = root / "docs" / "STEP_1" / "04_실행결과"
            run_id = "hedgemate-prod"
            write_csv(
                serve_dashboard.OUTPUT_PROCESSED_DIR / f"features_summary_{run_id}.csv",
                ["ticker", "mdd_1y_krw"],
                [{"ticker": "GLD", "mdd_1y_krw": "-0.1"}],
            )
            write_csv(serve_dashboard.OUTPUT_PROCESSED_DIR / f"asset_risk_sensitivity_{run_id}.csv", ["ticker"], [])
            write_csv(serve_dashboard.OUTPUT_REPORT_DIR / f"dq_result_{run_id}.csv", ["ticker", "status"], [])
            write_csv(serve_dashboard.OUTPUT_REPORT_DIR / f"hes_components_{run_id}.csv", ["ticker"], [])
            write_csv(serve_dashboard.OUTPUT_REPORT_DIR / f"portfolio_compare_{run_id}.csv", ["scenario"], [])
            write_csv(serve_dashboard.OUTPUT_REPORT_DIR / f"single_asset_compare_{run_id}.csv", ["scenario"], [])
            write_csv(
                serve_dashboard.OUTPUT_REPORT_DIR / f"portfolio_multi_hedge_{run_id}.csv",
                ["candidate_combo", "recommendation_status"],
                [{"candidate_combo": "GLD + IEF", "recommendation_status": "PASS_RECOMMEND"}],
            )
            write_csv(
                serve_dashboard.OUTPUT_REPORT_DIR / f"portfolio_1to1_hedge_{run_id}.csv",
                ["candidate_ticker", "recommendation_status"],
                [{"candidate_ticker": "GLD", "recommendation_status": "PASS_RECOMMEND"}],
            )
            (serve_dashboard.DOC_RESULT_DIR).mkdir(parents=True, exist_ok=True)
            (serve_dashboard.DOC_RESULT_DIR / f"01_실행결과_{run_id}.md").write_text("# Result\n", encoding="utf-8")
            (serve_dashboard.DOC_RESULT_DIR / f"02_분석리포트_초안_{run_id}.md").write_text("# Draft\n", encoding="utf-8")
            (serve_dashboard.DOC_RESULT_DIR / f"03_결과검토_{run_id}.md").write_text("# Review\n", encoding="utf-8")
            (root / "outputs").mkdir(parents=True, exist_ok=True)
            (root / "outputs" / "latest_manifest.json").write_text(
                json.dumps(
                    {
                        "active_bundle": {"hedgemate_run": run_id},
                        "active_hedgemate_run": run_id,
                        "artifacts": {
                            "portfolioMulti": f"outputs/reports/portfolio_multi_hedge_{run_id}_backtest_gated.csv",
                            "portfolio1to1": f"outputs/reports/portfolio_1to1_hedge_{run_id}_backtest_gated.csv",
                        },
                    }
                ),
                encoding="utf-8",
            )

            data = serve_dashboard.load_dashboard_data(run_id)

            self.assertEqual(data["portfolioMulti"], [])
            self.assertEqual(data["portfolioOneToOne"], [])
            self.assertIn("missing active gated recommendation artifact", data["meta"]["recommendationArtifactWarnings"][0])
            self.assertFalse(data["meta"]["usesActiveGatedRecommendations"])

    def test_fallback_product_manifest_does_not_leak_raw_recommendations(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            serve_dashboard.ROOT = root
            serve_dashboard.OUTPUT_PROCESSED_DIR = root / "outputs" / "processed"
            serve_dashboard.OUTPUT_REPORT_DIR = root / "outputs" / "reports"
            serve_dashboard.DOC_RESULT_DIR = root / "docs"
            run_id = "hedgemate-fallback"
            write_csv(
                serve_dashboard.OUTPUT_PROCESSED_DIR / f"features_summary_{run_id}.csv",
                ["ticker", "mdd_1y_krw"],
                [{"ticker": "GLD", "mdd_1y_krw": "-0.1"}],
            )
            write_csv(serve_dashboard.OUTPUT_PROCESSED_DIR / f"asset_risk_sensitivity_{run_id}.csv", ["ticker"], [])
            write_csv(serve_dashboard.OUTPUT_REPORT_DIR / f"dq_result_{run_id}.csv", ["ticker", "status"], [])
            write_csv(serve_dashboard.OUTPUT_REPORT_DIR / f"hes_components_{run_id}.csv", ["ticker"], [])
            write_csv(serve_dashboard.OUTPUT_REPORT_DIR / f"portfolio_compare_{run_id}.csv", ["scenario"], [])
            write_csv(serve_dashboard.OUTPUT_REPORT_DIR / f"single_asset_compare_{run_id}.csv", ["scenario"], [])
            write_csv(
                serve_dashboard.OUTPUT_REPORT_DIR / f"portfolio_multi_hedge_{run_id}.csv",
                ["candidate_combo", "recommendation_status"],
                [{"candidate_combo": "GLD + IEF", "recommendation_status": "PASS_RECOMMEND"}],
            )
            write_csv(
                serve_dashboard.OUTPUT_REPORT_DIR / f"portfolio_1to1_hedge_{run_id}.csv",
                ["candidate_ticker", "recommendation_status"],
                [{"candidate_ticker": "GLD", "recommendation_status": "PASS_RECOMMEND"}],
            )
            fallback_manifest = {
                "manifest_version": "hedgemate_active_bundle_fallback_v1",
                "freshness_status": "INCOMPLETE",
                "active_bundle": {"hedgemate_run": run_id},
            }

            data = serve_dashboard.load_dashboard_data(run_id, product_manifest=fallback_manifest)

            self.assertEqual(data["portfolioMulti"], [])
            self.assertEqual(data["portfolioOneToOne"], [])
            self.assertIn("missing active gated recommendation artifact", data["meta"]["recommendationArtifactWarnings"][0])
            self.assertIsNone(data["artifacts"]["portfolioMulti"])
            self.assertIsNone(data["artifacts"]["portfolio1to1"])

    def test_backtest_payload_exposes_attribution_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            serve_dashboard.ROOT = root
            serve_dashboard.OUTPUT_VALIDATION_DIR = root / "outputs" / "validation"
            serve_dashboard.OUTPUT_REPORT_DIR = root / "outputs" / "reports"
            backtest_csv = serve_dashboard.OUTPUT_VALIDATION_DIR / "walk_forward_backtest_backtest-prod.csv"
            write_csv(
                backtest_csv,
                [
                    "case_id",
                    "case_name",
                    "expected_scenario_code",
                    "candidate_label",
                    "is_target_scenario",
                    "backtest_status",
                    "verdict",
                    "evaluation_day_count",
                    "price_coverage_ratio",
                    "price_window_status",
                    "price_blocking_tickers",
                    "pre_inception_tickers",
                    "missing_price_tickers",
                    "hedge_vs_cash_verdict",
                    "implementation_cost",
                    "recurring_rebalance_cost",
                    "total_path_cost",
                    "transaction_cost_bps",
                    "slippage_bps",
                    "bootstrap_confidence",
                    "net_stress_delta_p_improve",
                    "cash_bootstrap_confidence",
                    "cash_net_stress_delta_p_improve",
                ],
                [
                    {
                        "case_id": "rate_2022",
                        "case_name": "2022 Rate Shock",
                        "expected_scenario_code": "higher_for_longer_long_rate_shock",
                        "candidate_label": "GLD",
                        "is_target_scenario": "Y",
                        "backtest_status": "EVALUATED",
                        "verdict": "WORSENED",
                        "evaluation_day_count": "55",
                        "price_coverage_ratio": "1.0",
                        "price_window_status": "PRICE_WINDOW_AVAILABLE",
                        "hedge_vs_cash_verdict": "LAGS_CASH",
                        "implementation_cost": "0.00096",
                        "recurring_rebalance_cost": "0.00012",
                        "total_path_cost": "0.00108",
                        "transaction_cost_bps": "10.0",
                        "slippage_bps": "5.0",
                        "bootstrap_confidence": "UNCERTAIN",
                        "net_stress_delta_p_improve": "0.62",
                        "cash_bootstrap_confidence": "UNCERTAIN",
                        "cash_net_stress_delta_p_improve": "0.37",
                    },
                    {
                        "case_id": "gfc",
                        "case_name": "GFC",
                        "expected_scenario_code": "acute_global_stress_liquidity_crunch",
                        "candidate_label": "GLD",
                        "is_target_scenario": "N",
                        "backtest_status": "INSUFFICIENT_HISTORY",
                        "verdict": "INSUFFICIENT_HISTORY",
                        "evaluation_day_count": "",
                        "price_coverage_ratio": "",
                        "price_window_status": "NO_COMMON_PRICE_DATES",
                        "price_blocking_tickers": "BTC-USD|NVDA",
                        "pre_inception_tickers": "BTC-USD",
                        "missing_price_tickers": "",
                        "hedge_vs_cash_verdict": "",
                    },
                ],
            )
            attr_csv = serve_dashboard.OUTPUT_REPORT_DIR / "backtest_attribution_backtest-prod.csv"
            attr_md = serve_dashboard.OUTPUT_REPORT_DIR / "backtest_attribution_backtest-prod.md"
            formal_csv = serve_dashboard.OUTPUT_REPORT_DIR / "formal_gate_audit_hedgemate-prod_backtest_gated.csv"
            formal_md = serve_dashboard.OUTPUT_REPORT_DIR / "formal_gate_audit_hedgemate-prod_backtest_gated.md"
            attr_csv.parent.mkdir(parents=True, exist_ok=True)
            attr_csv.write_text("candidate_label\nGLD\n", encoding="utf-8")
            attr_md.write_text("# Attribution\n", encoding="utf-8")
            write_csv(
                formal_csv,
                [
                    "candidate_name",
                    "recommendation_status",
                    "formal_gate_blockers",
                    "target_lags_cash_count",
                    "target_avg_cash_net_stress_delta",
                    "target_min_cash_net_stress_delta",
                    "target_avg_cash_net_mdd_delta",
                    "target_avg_cash_net_cvar_delta",
                    "target_bootstrap_count",
                    "target_bootstrap_robust_count",
                    "target_bootstrap_min_p_improve",
                    "target_bootstrap_avg_p_improve",
                    "target_cash_bootstrap_count",
                    "target_cash_bootstrap_robust_count",
                    "target_cash_bootstrap_min_p_improve",
                    "target_cash_bootstrap_avg_p_improve",
                ],
                [
                    {
                        "candidate_name": "GLD",
                        "recommendation_status": "REFERENCE_ONLY",
                        "formal_gate_blockers": "cash_baseline_lag|bootstrap_not_robust|cash_bootstrap_not_robust",
                        "target_lags_cash_count": "2",
                        "target_avg_cash_net_stress_delta": "-0.012",
                        "target_min_cash_net_stress_delta": "-0.016",
                        "target_avg_cash_net_mdd_delta": "-0.02",
                        "target_avg_cash_net_cvar_delta": "-0.003",
                        "target_bootstrap_count": "2",
                        "target_bootstrap_robust_count": "0",
                        "target_bootstrap_min_p_improve": "0.41",
                        "target_bootstrap_avg_p_improve": "0.48",
                        "target_cash_bootstrap_count": "2",
                        "target_cash_bootstrap_robust_count": "0",
                        "target_cash_bootstrap_min_p_improve": "0.37",
                        "target_cash_bootstrap_avg_p_improve": "0.39",
                    }
                ],
            )
            formal_md.write_text("# Formal Gate Audit\n", encoding="utf-8")
            manifest = {
                "artifacts": {
                    "backtestCsv": str(backtest_csv),
                    "backtestAttributionCsv": str(attr_csv),
                    "backtestAttributionSummary": str(attr_md),
                    "formalGateAuditCsv": str(formal_csv),
                    "formalGateAuditSummary": str(formal_md),
                }
            }

            payload = serve_dashboard.load_backtest_payload(manifest)

            self.assertEqual(payload["rowCount"], 2)
            self.assertEqual(payload["verdictCounts"]["WORSENED"], 1)
            self.assertTrue(payload["attributionCsvArtifact"].endswith("backtest_attribution_backtest-prod.csv"))
            self.assertTrue(payload["attributionSummaryArtifact"].endswith("backtest_attribution_backtest-prod.md"))
            self.assertTrue(payload["formalGateAuditCsvArtifact"].endswith("formal_gate_audit_hedgemate-prod_backtest_gated.csv"))
            self.assertTrue(payload["formalGateAuditSummaryArtifact"].endswith("formal_gate_audit_hedgemate-prod_backtest_gated.md"))
            self.assertEqual(payload["formalGateAuditSummary"]["blockerCounts"]["cash_baseline_lag"], 1)
            self.assertEqual(payload["formalGateAuditSummary"]["blockerCounts"]["bootstrap_not_robust"], 1)
            self.assertEqual(payload["formalGateAuditSummary"]["blockerCounts"]["cash_bootstrap_not_robust"], 1)
            self.assertEqual(payload["formalGateAuditSummary"]["cashBaselineAudit"]["lagCandidateRows"], 1)
            self.assertEqual(payload["formalGateAuditSummary"]["cashBaselineAudit"]["targetLagStressRows"], 2)
            self.assertEqual(payload["formalGateAuditSummary"]["cashBaselineAudit"]["avgCashNetStressDelta"]["avg"], -0.012)
            self.assertEqual(payload["formalGateAuditSummary"]["bootstrapAudit"]["notRobustCandidateRows"], 1)
            self.assertEqual(payload["formalGateAuditSummary"]["bootstrapAudit"]["targetBootstrapRows"], 2)
            self.assertEqual(payload["formalGateAuditSummary"]["bootstrapAudit"]["targetBootstrapRobustRows"], 0)
            self.assertEqual(payload["formalGateAuditSummary"]["bootstrapAudit"]["targetCashBootstrapRows"], 2)
            self.assertEqual(payload["formalGateAuditSummary"]["bootstrapAudit"]["targetCashBootstrapRobustRows"], 0)
            self.assertEqual(payload["formalGateAuditSummary"]["bootstrapAudit"]["pImprove"]["min"], 0.41)
            self.assertEqual(payload["formalGateAuditSummary"]["bootstrapAudit"]["cashPImprove"]["min"], 0.37)
            self.assertEqual(payload["coverageSummary"]["qualityLevel"], "LOW")
            self.assertEqual(payload["coverageSummary"]["evaluatedCaseCount"], 1)
            self.assertEqual(payload["coverageSummary"]["shortEvaluationRows"], 1)
            self.assertEqual(payload["coverageSummary"]["shortEvaluationCaseCount"], 1)
            self.assertEqual(payload["coverageSummary"]["shortEvaluationCaseNames"], ["2022 Rate Shock"])
            self.assertEqual(payload["coverageSummary"]["insufficientCaseNames"], ["GFC"])
            self.assertEqual(payload["coverageSummary"]["noCommonPriceCaseNames"], ["GFC"])
            self.assertEqual(payload["coverageSummary"]["priceWindowStatusCounts"]["NO_COMMON_PRICE_DATES"], 1)
            self.assertEqual(payload["coverageSummary"]["priceCoverageBlockerType"], "PRE_INCEPTION_ONLY")
            self.assertEqual(payload["coverageSummary"]["preInceptionBlockedRows"], 1)
            self.assertEqual(payload["coverageSummary"]["preInceptionBlockedCaseCount"], 1)
            self.assertEqual(payload["coverageSummary"]["missingPriceBlockedRows"], 0)
            self.assertEqual(payload["coverageSummary"]["missingPriceBlockedCaseCount"], 0)
            self.assertEqual(payload["coverageSummary"]["priceBlockingTickerCounts"]["BTC-USD"], 1)
            self.assertEqual(payload["coverageSummary"]["preInceptionTickerCounts"]["BTC-USD"], 1)
            self.assertEqual(payload["coverageSummary"]["cashBaselineVerdictCounts"]["LAGS_CASH"], 1)
            self.assertEqual(payload["coverageSummary"]["cashLagRows"], 1)
            self.assertEqual(payload["coverageSummary"]["implementationCost"]["avg"], 0.00096)
            self.assertEqual(payload["coverageSummary"]["recurringRebalanceCost"]["avg"], 0.00012)
            self.assertEqual(payload["coverageSummary"]["totalPathCost"]["avg"], 0.00108)
            self.assertEqual(payload["coverageSummary"]["transactionCostBps"]["avg"], 10.0)
            self.assertEqual(payload["coverageSummary"]["slippageBps"]["avg"], 5.0)
            self.assertEqual(payload["coverageSummary"]["bootstrapConfidenceCounts"]["UNCERTAIN"], 1)
            self.assertEqual(payload["coverageSummary"]["cashBootstrapConfidenceCounts"]["UNCERTAIN"], 1)
            self.assertEqual(payload["coverageSummary"]["targetBootstrapRows"], 1)
            self.assertEqual(payload["coverageSummary"]["targetBootstrapRobustRows"], 0)
            self.assertEqual(payload["coverageSummary"]["targetBootstrapPImprove"]["avg"], 0.62)
            self.assertEqual(payload["coverageSummary"]["targetCashBootstrapRows"], 1)
            self.assertEqual(payload["coverageSummary"]["targetCashBootstrapRobustRows"], 0)
            self.assertEqual(payload["coverageSummary"]["targetCashBootstrapPImprove"]["avg"], 0.37)
            self.assertIn("bootstrap", " ".join(payload["coverageSummary"]["warnings"]))
            self.assertIn("가장 짧은 평가 구간", " ".join(payload["coverageSummary"]["warnings"]))
            self.assertIn("2022 Rate Shock", " ".join(payload["coverageSummary"]["warnings"]))
            self.assertIn("공통 가격일이 없어", " ".join(payload["coverageSummary"]["warnings"]))
            self.assertIn("상장 전 stress window", " ".join(payload["coverageSummary"]["warnings"]))
            self.assertIn("Pre-inception price history", " ".join(payload["coverageSummary"]["warnings"]))
            self.assertIn("현금화 기준보다 약한", " ".join(payload["coverageSummary"]["warnings"]))

    def test_recommendation_decision_blocks_when_no_formal_recommendation(self):
        hedge = {
            "portfolioOneToOne": [
                {"candidate_ticker": "GLD", "recommendation_status": "REFERENCE_ONLY"},
                {"candidate_ticker": "EWY", "recommendation_status": "FAIL_GATE"},
            ],
            "portfolioMulti": [],
        }
        backtest = {
            "coverageSummary": {
                "rowCount": 207,
                "evaluatedCaseCount": 7,
                "cashLagRows": 108,
                "insufficientCaseCount": 1,
                "noCommonPriceCaseCount": 1,
            },
            "formalGateAuditSummary": {
                "cashBaselineAudit": {
                    "lagCandidateRows": 4,
                    "targetLagStressRows": 8,
                    "avgCashNetStressDelta": {"avg": -0.01},
                    "topRows": [{"candidate_name": "GLD + SHY", "target_avg_cash_net_stress_delta": "-0.014"}],
                },
                "bootstrapAudit": {
                    "notRobustCandidateRows": 4,
                    "targetBootstrapRows": 8,
                    "targetBootstrapRobustRows": 0,
                    "pImprove": {"min": 0.37},
                    "topRows": [{"candidate_name": "GLD + SHY", "target_bootstrap_min_p_improve": "0.37"}],
                },
            },
        }

        decision = serve_dashboard.build_recommendation_decision(hedge, backtest, {"status": "current"})

        self.assertFalse(decision["canExecuteRecommendations"])
        self.assertEqual(decision["state"], "NO_FORMAL_RECOMMENDATION")
        self.assertEqual(decision["formalRecommendationCount"], 0)
        self.assertEqual(decision["referenceOnlyCount"], 1)
        self.assertEqual(decision["failGateCount"], 1)
        self.assertIn("실행 추천", decision["title"])
        joined_reasons = " ".join(decision["primaryReasons"])
        self.assertIn("정식 추천 후보가 없습니다", joined_reasons)
        self.assertIn("현금", joined_reasons)
        self.assertEqual(decision["cashBaselineAudit"]["lagCandidateRows"], 4)
        self.assertEqual(decision["bootstrapAudit"]["notRobustCandidateRows"], 4)

    def test_event_overlay_status_preserves_false_and_zero_metadata(self):
        status = serve_dashboard.normalized_event_overlay_status(
            {
                "metadata_provider": "fixture",
                "metadata_live_research_attached": False,
                "metadata_schema_error_count": 0,
                "metadata_fatal_schema_error_count": 0,
            }
        )

        self.assertFalse(status["metadata_live_research_attached"])
        self.assertEqual(status["metadata_schema_error_count"], 0)
        self.assertEqual(status["metadata_fatal_schema_error_count"], 0)

    def test_recommendation_decision_uses_single_asset_gated_rows_without_double_counting(self):
        hedge = {
            "singleAssetTicker": "TSLA",
            "portfolioOneToOne": [
                {"candidate_ticker": "GLD", "recommendation_status": "REFERENCE_ONLY", "backtest_gate_status": "REFERENCE_ONLY_CASH_BASELINE"},
                {"candidate_ticker": "EWY", "recommendation_status": "FAIL_GATE", "backtest_gate_status": "REFERENCE_ONLY_CASH_BASELINE"},
            ],
            "singleAssetOneToOne": [
                {"candidate_ticker": "GLD", "recommendation_status": "REFERENCE_ONLY", "backtest_gate_status": "REFERENCE_ONLY_CASH_BASELINE"},
            ],
            "singleAssetMulti": [
                {"candidate_combo": "GLD + TLT", "recommendation_status": "REFERENCE_ONLY", "backtest_gate_status": "REFERENCE_ONLY_CASH_BASELINE"},
            ],
        }
        backtest = {
            "coverageSummary": {
                "rowCount": 20,
                "evaluatedCaseCount": 8,
                "cashLagRows": 1,
                "insufficientCaseCount": 0,
                "noCommonPriceCaseCount": 0,
            }
        }

        decision = serve_dashboard.build_recommendation_decision(hedge, backtest, {"status": "current"})

        self.assertEqual(decision["candidateCount"], 2)
        self.assertEqual(decision["referenceOnlyCount"], 2)
        self.assertEqual(decision["failGateCount"], 0)

    def test_recommendation_decision_blocks_stale_data_even_with_formal_candidate(self):
        hedge = {"portfolioOneToOne": [{"candidate_ticker": "GLD", "recommendation_status": "PASS_RECOMMEND"}]}
        backtest = {
            "coverageSummary": {
                "rowCount": 20,
                "qualityLevel": "HIGH",
                "evaluatedCaseCount": 8,
                "cashLagRows": 0,
                "insufficientCaseCount": 0,
                "noCommonPriceCaseCount": 0,
            }
        }

        decision = serve_dashboard.build_recommendation_decision(
            hedge,
            backtest,
            {"status": "stale", "reasons": ["scenario data_version mismatch"]},
        )

        self.assertFalse(decision["canExecuteRecommendations"])
        self.assertEqual(decision["state"], "BLOCKED_STALE_DATA")
        self.assertEqual(decision["formalRecommendationCount"], 1)
        self.assertIn("stale_data", decision["blockers"])

    def test_recommendation_decision_allows_current_formal_candidate(self):
        hedge = {"portfolioOneToOne": [{"candidate_ticker": "GLD", "recommendation_status": "PASS_RECOMMEND"}]}
        backtest = {
            "coverageSummary": {
                "rowCount": 20,
                "qualityLevel": "HIGH",
                "evaluatedCaseCount": 8,
                "cashLagRows": 0,
                "insufficientCaseCount": 0,
                "noCommonPriceCaseCount": 0,
            }
        }

        decision = serve_dashboard.build_recommendation_decision(
            hedge,
            backtest,
            {"status": "current"},
            {"trade_gate_usage": "enabled"},
        )

        self.assertTrue(decision["canExecuteRecommendations"])
        self.assertEqual(decision["state"], "FORMAL_RECOMMENDATION_AVAILABLE")
        self.assertEqual(decision["formalRecommendationCount"], 1)

    def test_recommendation_decision_blocks_non_high_validation_quality(self):
        hedge = {"portfolioOneToOne": [{"candidate_ticker": "GLD", "recommendation_status": "PASS_RECOMMEND"}]}
        backtest = {
            "coverageSummary": {
                "rowCount": 20,
                "qualityLevel": "MEDIUM",
                "evaluatedCaseCount": 8,
                "cashLagRows": 0,
                "insufficientCaseCount": 0,
                "noCommonPriceCaseCount": 0,
            }
        }

        decision = serve_dashboard.build_recommendation_decision(
            hedge,
            backtest,
            {"status": "current"},
            {"trade_gate_usage": "enabled"},
        )

        self.assertFalse(decision["canExecuteRecommendations"])
        self.assertEqual(decision["state"], "BLOCKED_VALIDATION")
        self.assertIn("validation_quality_not_high", decision["blockers"])

    def test_recommendation_decision_blocks_fixture_event_overlay_trade_gate(self):
        hedge = {"portfolioOneToOne": [{"candidate_ticker": "GLD", "recommendation_status": "PASS_RECOMMEND"}]}
        backtest = {
            "coverageSummary": {
                "rowCount": 20,
                "qualityLevel": "HIGH",
                "evaluatedCaseCount": 8,
                "cashLagRows": 0,
                "insufficientCaseCount": 0,
                "noCommonPriceCaseCount": 0,
            }
        }

        decision = serve_dashboard.build_recommendation_decision(
            hedge,
            backtest,
            {"status": "current"},
            {"trade_gate_usage": "disabled_for_fixture", "recommendation_usage": "fixture_context_only"},
        )

        self.assertFalse(decision["canExecuteRecommendations"])
        self.assertEqual(decision["state"], "BLOCKED_VALIDATION")
        self.assertIn("event_overlay_not_trade_safe", decision["blockers"])

    def test_action_plan_decision_keeps_review_actions_non_executable(self):
        decision = serve_dashboard.build_action_plan_decision(
            [{"action_status": "REVIEW_ACTION", "action_type": "trim", "holding_ticker": "QQQ"}],
            {"canExecuteRecommendations": True, "blockers": []},
        )

        self.assertEqual(decision["formalActionCount"], 0)
        self.assertEqual(decision["reviewActionCount"], 1)
        self.assertFalse(decision["canExecuteAction"])
        self.assertIn("no_formal_action", decision["blockers"])
        self.assertEqual(decision["countBasis"], "hedgeActionPlan_selected_actions_only")
        self.assertEqual(decision["countedRowSet"], "hedgeActionPlan")
        self.assertEqual(decision["countedRowScope"], "SELECTED_ACTIONS_ONLY")
        self.assertEqual(decision["selectedActionCount"], 1)
        self.assertIn("취약성을 낮추는 REVIEW_ACTION", decision["whyNoFormalRecommendationKo"])
        self.assertTrue(decision["formalActionUpgradeRequirements"])

    def test_action_plan_decision_requires_existing_formal_gate(self):
        decision = serve_dashboard.build_action_plan_decision(
            [{"action_status": "FORMAL_ACTION", "action_type": "add", "candidate_ticker": "GLD"}],
            {
                "canExecuteRecommendations": False,
                "blockers": ["validation_quality_not_high", "event_overlay_not_trade_safe"],
            },
        )

        self.assertEqual(decision["formalActionCount"], 1)
        self.assertFalse(decision["canExecuteAction"])
        self.assertIn("validation_quality_not_high", decision["blockers"])
        self.assertIn("event_overlay_not_trade_safe", decision["blockers"])

    def test_action_plan_payload_falls_back_when_artifacts_missing(self):
        payload = serve_dashboard.load_action_plan_payload(
            {"artifacts": {}},
            {"canExecuteRecommendations": True, "blockers": []},
        )

        self.assertEqual(payload["portfolioVulnerabilityAttribution"], [])
        self.assertEqual(payload["hedgeActionCandidates"], [])
        self.assertEqual(payload["hedgeActionPlan"], [])
        self.assertEqual(payload["hedgeActionPlanScope"], "SELECTED_ACTIONS_ONLY")
        self.assertEqual(payload["hedgeActionCandidatesScope"], "FULL_EVALUATED_ACTION_CANDIDATES")
        self.assertTrue(payload["actionPayloadShape"]["hedgeActionPlan"]["countedByActionPlanDecision"])
        self.assertFalse(payload["actionPayloadShape"]["hedgeActionCandidates"]["countedByActionPlanDecision"])
        self.assertEqual(payload["portfolioVulnerabilitySummary"]["text"], "")
        self.assertFalse(payload["actionPlanDecision"]["canExecuteAction"])
        self.assertIn("no_action_plan", payload["actionPlanDecision"]["blockers"])
        self.assertTrue(
            any("missing action artifact: hedgeActionPlan" in warning for warning in payload["actionArtifactWarnings"])
        )

    def test_action_plan_payload_reads_artifacts_without_promoting_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            attribution = root / "portfolio_vulnerability_attribution.csv"
            candidates = root / "hedge_action_candidates.csv"
            plan = root / "hedge_action_plan.csv"
            vulnerability_summary = root / "portfolio_vulnerability_summary.md"
            action_summary = root / "hedge_action_plan_summary.md"
            write_csv(
                attribution,
                ["vulnerability_id", "holding_ticker", "risk_contribution"],
                [{"vulnerability_id": "duration", "holding_ticker": "TLT", "risk_contribution": "0.42"}],
            )
            write_csv(
                candidates,
                ["vulnerability_id", "candidate_ticker", "action_status"],
                [{"vulnerability_id": "duration", "candidate_ticker": "SHY", "action_status": "REVIEW_ACTION"}],
            )
            write_csv(
                plan,
                ["vulnerability_id", "holding_ticker", "action_type", "action_status"],
                [{"vulnerability_id": "duration", "holding_ticker": "TLT", "action_type": "trim", "action_status": "REVIEW_ACTION"}],
            )
            vulnerability_summary.write_text("# Vulnerability\n", encoding="utf-8")
            action_summary.write_text("# Action Plan\n", encoding="utf-8")
            manifest = {
                "artifacts": {
                    "portfolioVulnerabilityAttribution": str(attribution),
                    "portfolioVulnerabilitySummary": str(vulnerability_summary),
                    "hedgeActionCandidates": str(candidates),
                    "hedgeActionPlan": str(plan),
                    "hedgeActionPlanSummary": str(action_summary),
                }
            }

            payload = serve_dashboard.load_action_plan_payload(
                manifest,
                {"canExecuteRecommendations": True, "blockers": []},
            )

            self.assertEqual(payload["portfolioVulnerabilityAttribution"][0]["holding_ticker"], "TLT")
            self.assertIn("source_asset", payload["portfolioVulnerabilityAttribution"][0])
            self.assertEqual(payload["hedgeActionCandidates"][0]["candidate_ticker"], "SHY")
            self.assertIn("hedge_asset", payload["hedgeActionCandidates"][0])
            self.assertEqual(payload["hedgeActionPlan"][0]["action_type"], "trim")
            self.assertIn("expected_effect", payload["hedgeActionPlan"][0])
            self.assertIn("Vulnerability", payload["portfolioVulnerabilitySummary"]["text"])
            self.assertEqual(payload["actionPlanDecision"]["reviewActionCount"], 1)
            self.assertEqual(payload["actionPlanDecision"]["selectedActionCount"], 1)
            self.assertEqual(payload["actionPlanDecision"]["countedRowSet"], "hedgeActionPlan")
            self.assertFalse(payload["actionPlanDecision"]["canExecuteAction"])

    def test_action_plan_payload_reads_selected_actions_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = root / "hedge_action_plan.json"
            plan.write_text(
                json.dumps(
                    {
                        "status_counts": {"REVIEW_ACTION": 1},
                        "selection_policy": {
                            "scope": "SELECTED_ACTIONS_ONLY",
                            "diversity_rule": "select_best_action_per_positive_top_vulnerability_before_global_fill",
                        },
                        "replace_sleeve_decision": {
                            "candidate_count": 0,
                            "selected_count": 0,
                            "present_in_candidates": False,
                            "present_in_selected": False,
                            "absence_reason_code": "NO_VALID_REPLACE_SLEEVE_CANDIDATE",
                            "absence_reason_ko": "REPLACE_SLEEVE 후보가 없습니다.",
                        },
                        "sleeve_selection_coverage": [
                            {
                                "risk_sleeve": "rate_shock_growth_duration",
                                "selected_action_count": 1,
                                "coverage_status": "SELECTED",
                            }
                        ],
                        "rows": [
                            {
                                "action_id": "raw_row_should_not_define_plan",
                                "action_status": "FORMAL_ACTION",
                            }
                        ],
                        "selected_actions": [
                            {
                                "action_id": "action_001",
                                "action_status": "REVIEW_ACTION",
                                "candidate_tickers": "GLD",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            payload = serve_dashboard.load_action_plan_payload(
                {"artifacts": {"hedgeActionPlan": str(plan)}},
                {"canExecuteRecommendations": True, "blockers": []},
            )

            self.assertEqual(payload["hedgeActionPlan"][0]["action_id"], "action_001")
            self.assertEqual(len(payload["hedgeActionPlan"]), 1)
            self.assertEqual(payload["actionPlanDecision"]["formalActionCount"], 0)
            self.assertEqual(payload["actionPlanDecision"]["reviewActionCount"], 1)
            self.assertEqual(
                payload["actionPlanDecision"]["selectionPolicy"]["diversity_rule"],
                "select_best_action_per_positive_top_vulnerability_before_global_fill",
            )
            self.assertEqual(
                payload["actionPlanDecision"]["replaceSleeveDecision"]["absenceReasonCode"],
                "NO_VALID_REPLACE_SLEEVE_CANDIDATE",
            )
            self.assertIn("REPLACE_SLEEVE 후보가 없습니다", payload["actionPlanDecision"]["replaceSleeveDecision"]["absenceReasonKo"])
            self.assertEqual(payload["actionPlanDecision"]["sleeveSelectionCoverage"][0]["coverage_status"], "SELECTED")
            self.assertFalse(payload["actionPlanDecision"]["canExecuteAction"])

    def test_action_plan_decision_excludes_candidate_rows_from_counts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            candidates = root / "hedge_action_candidates.json"
            candidates.write_text(
                json.dumps(
                    {
                        "action_candidates": [
                            {"action_id": "candidate_001", "action_status": "REVIEW_ACTION"},
                            {"action_id": "candidate_002", "action_status": "FORMAL_ACTION"},
                        ]
                    }
                ),
                encoding="utf-8",
            )

            payload = serve_dashboard.load_action_plan_payload(
                {"artifacts": {"hedgeActionCandidates": str(candidates)}},
                {"canExecuteRecommendations": True, "blockers": []},
            )

            self.assertEqual(len(payload["hedgeActionCandidates"]), 2)
            self.assertEqual(payload["hedgeActionPlan"], [])
            self.assertEqual(payload["actionPlanDecision"]["formalActionCount"], 0)
            self.assertEqual(payload["actionPlanDecision"]["reviewActionCount"], 0)
            self.assertEqual(payload["actionPlanDecision"]["selectedActionCount"], 0)
            self.assertEqual(payload["actionPlanDecision"]["countBasis"], "hedgeActionPlan_selected_actions_only")

    def test_product_dashboard_exposes_action_payload_alongside_recommendations(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = root / "hedge_action_plan.csv"
            write_csv(
                plan,
                ["vulnerability_id", "holding_ticker", "action_type", "action_status"],
                [{"vulnerability_id": "growth_beta", "holding_ticker": "QQQ", "action_type": "trim", "action_status": "REVIEW_ACTION"}],
            )
            manifest = {
                "freshness_status": "FRESH",
                "active_bundle": {"hedgemate_run": "hedge-prod", "final_market_state_run": "scenario-prod"},
                "event_overlay_status": {"trade_gate_usage": "enabled"},
                "artifacts": {"hedgeActionPlan": str(plan)},
            }
            hedge = {
                "portfolioOneToOne": [{"candidate_ticker": "GLD", "recommendation_status": "PASS_RECOMMEND"}],
                "portfolioMulti": [],
            }
            backtest = {
                "coverageSummary": {
                    "rowCount": 20,
                    "qualityLevel": "HIGH",
                    "evaluatedCaseCount": 8,
                    "cashLagRows": 0,
                    "insufficientCaseCount": 0,
                    "noCommonPriceCaseCount": 0,
                },
                "formalGateAuditSummary": {},
            }
            with mock.patch.object(serve_dashboard, "read_product_manifest", return_value=manifest), mock.patch.object(
                serve_dashboard, "load_dashboard_data", return_value=hedge
            ), mock.patch.object(serve_dashboard, "load_scenario_dashboard_data", return_value={"runId": "scenario-prod"}), mock.patch.object(
                serve_dashboard, "load_data_freshness", return_value={"status": "current"}
            ), mock.patch.object(
                serve_dashboard, "load_backtest_payload", return_value=backtest
            ):
                data = serve_dashboard.load_product_dashboard_data()

            self.assertEqual(data["hedge"]["portfolioOneToOne"][0]["candidate_ticker"], "GLD")
            self.assertEqual(data["hedgeActionPlanScope"], "SELECTED_ACTIONS_ONLY")
            self.assertEqual(data["actionPayloadShape"]["actionPlanDecision"]["countBasis"], "hedgeActionPlan_selected_actions_only")
            self.assertEqual(data["hedgeActionPlan"][0]["action_status"], "REVIEW_ACTION")
            self.assertEqual(data["recommendationDecision"]["formalRecommendationCount"], 1)
            self.assertEqual(data["actionPlanDecision"]["reviewActionCount"], 1)
            self.assertFalse(data["actionPlanDecision"]["canExecuteAction"])

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

    def test_choose_best_detail_prefers_reference_over_fail_gate(self):
        best = serve_dashboard.choose_best_detail(
            [
                {
                    "status": "PASS",
                    "recommendation_status": "FAIL_GATE",
                    "final_score": 0.95,
                    "candidate_combo": "GLD + IAU",
                    "weights_snapshot": '{"GLD": 10, "IAU": 10}',
                }
            ],
            [
                {
                    "status": "WARN",
                    "recommendation_status": "REFERENCE_ONLY",
                    "final_score": 0.50,
                    "candidate_ticker": "SHY",
                    "weights_snapshot": '{"SHY": 20}',
                }
            ],
        )

        self.assertEqual(best["recommendation_status"], "REFERENCE_ONLY")
        self.assertEqual(best["candidate_ticker"], "SHY")

    def test_safe_rel_artifact_allows_outputs_and_blocks_outside_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            serve_dashboard.ROOT = root
            serve_dashboard.WEB_DIR = root / "web"
            serve_dashboard.OUTPUT_RAW_DIR = root / "outputs" / "raw"
            serve_dashboard.OUTPUT_PROCESSED_DIR = root / "outputs" / "processed"
            serve_dashboard.OUTPUT_REPORT_DIR = root / "outputs" / "reports"
            serve_dashboard.DOC_RESULT_DIR = root / "docs" / "STEP_1" / "04_실행결과"
            serve_dashboard.SCENARIO_RESEARCH_ROOT = root.parent / "scenario_research"
            serve_dashboard.SCENARIO_OUTPUT_DIR = serve_dashboard.SCENARIO_RESEARCH_ROOT / "outputs"
            run_id = "20260310"
            allowed = serve_dashboard.OUTPUT_REPORT_DIR / f"portfolio_compare_{run_id}.csv"
            allowed.parent.mkdir(parents=True, exist_ok=True)
            allowed.write_text("scenario\n기존 포트폴리오\n", encoding="utf-8")

            scenario_allowed = serve_dashboard.SCENARIO_OUTPUT_DIR / "reports" / "final_market_state_summary_test.md"
            scenario_allowed.parent.mkdir(parents=True, exist_ok=True)
            scenario_allowed.write_text("# Summary\n", encoding="utf-8")

            blocked = root / "secret.txt"
            blocked.write_text("x", encoding="utf-8")

            resolved = serve_dashboard.safe_rel_artifact(f"outputs/reports/portfolio_compare_{run_id}.csv")
            self.assertEqual(resolved, allowed.resolve())
            scenario_resolved = serve_dashboard.safe_rel_artifact("scenario_research/outputs/reports/final_market_state_summary_test.md")
            self.assertEqual(scenario_resolved, scenario_allowed.resolve())
            self.assertIsNone(serve_dashboard.safe_rel_artifact("secret.txt"))

    def test_load_scenario_dashboard_data_parses_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            root = workspace / "HedgeMate"
            scenario_root = workspace / "scenario_research"
            serve_dashboard.ROOT = root
            serve_dashboard.WEB_DIR = root / "web"
            serve_dashboard.SCENARIO_RESEARCH_ROOT = scenario_root
            serve_dashboard.SCENARIO_OUTPUT_DIR = scenario_root / "outputs"
            serve_dashboard.SCENARIO_FINAL_DIR = serve_dashboard.SCENARIO_OUTPUT_DIR / "final"
            serve_dashboard.SCENARIO_PROCESSED_DIR = serve_dashboard.SCENARIO_OUTPUT_DIR / "processed"
            serve_dashboard.SCENARIO_REPORT_DIR = serve_dashboard.SCENARIO_OUTPUT_DIR / "reports"
            serve_dashboard.SCENARIO_VECTOR_DIR = serve_dashboard.SCENARIO_OUTPUT_DIR / "scenario_vectors"
            serve_dashboard.SCENARIO_NOWCAST_DIR = serve_dashboard.SCENARIO_OUTPUT_DIR / "nowcast_vectors"
            serve_dashboard.SCENARIO_EVENT_DIR = serve_dashboard.SCENARIO_OUTPUT_DIR / "events"
            serve_dashboard.SCENARIO_VALIDATION_DIR = serve_dashboard.SCENARIO_OUTPUT_DIR / "validation"
            run_id = "phase6-test"

            write_csv(
                serve_dashboard.SCENARIO_FINAL_DIR / f"final_market_state_daily_{run_id}.csv",
                ["date", "scenario_code", "scenario_name", "scenario_name_ko", "lens", "final_score", "final_confidence", "final_display_state", "event_count", "overlay_applied"],
                [
                    {"date": "2026-05-06", "scenario_code": "soft_landing", "scenario_name": "Soft Landing", "scenario_name_ko": "우호적 위험선호장", "lens": "us_global", "final_score": 72.5, "final_confidence": 73.2, "final_display_state": "ACTIVE", "event_count": 2, "overlay_applied": "Y"},
                    {"date": "2026-05-06", "scenario_code": "rate_shock", "scenario_name": "Rate Shock", "scenario_name_ko": "금리 부담장", "lens": "us_global", "final_score": 48.9, "final_confidence": 62.5, "final_display_state": "WATCH", "event_count": 0, "overlay_applied": "N"},
                ],
            )
            write_csv(
                serve_dashboard.SCENARIO_FINAL_DIR / f"scenario_confidence_{run_id}.csv",
                ["date", "scenario_code", "final_confidence"],
                [{"date": "2026-05-06", "scenario_code": "soft_landing", "final_confidence": 73.2}],
            )
            (serve_dashboard.SCENARIO_FINAL_DIR / f"top_active_scenarios_{run_id}.json").write_text(
                '{"date":"2026-05-06","merge_engine_version":"phase6","top_active_scenarios":[{"scenario_code":"soft_landing","scenario_name":"Soft Landing","scenario_name_ko":"우호적 위험선호장","final_score":72.5,"final_confidence":73.2,"final_display_state":"ACTIVE","lens":"us_global"}]}',
                encoding="utf-8",
            )
            (serve_dashboard.SCENARIO_REPORT_DIR / f"final_market_state_metadata_{run_id}.json").parent.mkdir(parents=True, exist_ok=True)
            (serve_dashboard.SCENARIO_REPORT_DIR / f"final_market_state_metadata_{run_id}.json").write_text(
                '{"pipeline_phase":"phase6_final_merge","final_row_count":2,"overlay_row_count":1}',
                encoding="utf-8",
            )
            (serve_dashboard.SCENARIO_REPORT_DIR / f"final_market_state_summary_{run_id}.md").write_text(
                "# Summary\n\n- 기준일: `2026-05-06`\n- top_active_count: 1\n",
                encoding="utf-8",
            )
            (serve_dashboard.SCENARIO_VECTOR_DIR / "current_scenario_vector_latest.json").parent.mkdir(parents=True, exist_ok=True)
            (serve_dashboard.SCENARIO_VECTOR_DIR / "current_scenario_vector_latest.json").write_text(
                '[{"scenario_code":"soft_landing","scenario_name_ko":"우호적 위험선호장","score":75.1,"display_state":"STRONG","confidence":73.0,"lens":"us_global"}]',
                encoding="utf-8",
            )
            (serve_dashboard.SCENARIO_NOWCAST_DIR / "current_intraday_nowcast_latest.json").parent.mkdir(parents=True, exist_ok=True)
            (serve_dashboard.SCENARIO_NOWCAST_DIR / "current_intraday_nowcast_latest.json").write_text(
                '[{"nowcast_code":"kr_risk_on","nowcast_name_ko":"한국장 위험선호","score":91.0,"status":"RISK_ON","confidence":97.0,"lens":"korea_market"}]',
                encoding="utf-8",
            )
            write_csv(
                serve_dashboard.SCENARIO_VALIDATION_DIR / "historical_validation_cases_latest.csv",
                ["case_id", "status"],
                [{"case_id": "global_rate_shock_2022", "status": "OK"}],
            )
            (serve_dashboard.SCENARIO_REPORT_DIR / "historical_validation_metadata_latest.json").write_text(
                '{"case_count":1,"ok_case_count":1,"insufficient_history_case_count":0}',
                encoding="utf-8",
            )

            data = serve_dashboard.load_scenario_dashboard_data(run_id)
            self.assertEqual(data["runId"], run_id)
            self.assertEqual(data["asOfDate"], serve_dashboard.display_reference_date())
            self.assertEqual(data["dataAsOfDate"], "2026-05-06")
            self.assertEqual(data["topActiveScenarios"][0]["scenario_code"], "soft_landing")
            self.assertEqual(data["topMarketRows"][0]["scenario_code"], "soft_landing")
            self.assertEqual(data["stateCounts"], [{"state": "ACTIVE", "count": 1}, {"state": "WATCH", "count": 1}])
            self.assertEqual(data["scenarioVectorLeaders"][0]["score"], 75.1)
            self.assertEqual(data["nowcastLeaders"][0]["status"], "RISK_ON")
            self.assertIn("finalMarketState", data["artifacts"])

    def test_scenario_dashboard_prefers_latest_manifest_active_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            root = workspace / "HedgeMate"
            scenario_root = workspace / "scenario_research"
            serve_dashboard.ROOT = root
            serve_dashboard.SCENARIO_RESEARCH_ROOT = scenario_root
            serve_dashboard.SCENARIO_OUTPUT_DIR = scenario_root / "outputs"
            serve_dashboard.SCENARIO_FINAL_DIR = serve_dashboard.SCENARIO_OUTPUT_DIR / "final"
            serve_dashboard.SCENARIO_PROCESSED_DIR = serve_dashboard.SCENARIO_OUTPUT_DIR / "processed"
            serve_dashboard.SCENARIO_REPORT_DIR = serve_dashboard.SCENARIO_OUTPUT_DIR / "reports"
            serve_dashboard.SCENARIO_VECTOR_DIR = serve_dashboard.SCENARIO_OUTPUT_DIR / "scenario_vectors"
            serve_dashboard.SCENARIO_NOWCAST_DIR = serve_dashboard.SCENARIO_OUTPUT_DIR / "nowcast_vectors"
            serve_dashboard.SCENARIO_EVENT_DIR = serve_dashboard.SCENARIO_OUTPUT_DIR / "events"
            serve_dashboard.SCENARIO_VALIDATION_DIR = serve_dashboard.SCENARIO_OUTPUT_DIR / "validation"

            for run_id, score in [("latest-20260512-refresh", 40.0), ("v2-phase6-prod", 88.0)]:
                write_csv(
                    serve_dashboard.SCENARIO_FINAL_DIR / f"final_market_state_daily_{run_id}.csv",
                    ["date", "scenario_code", "scenario_name", "scenario_name_ko", "lens", "final_score", "final_confidence", "final_display_state", "event_count", "overlay_applied"],
                    [{"date": "2026-05-12", "scenario_code": "soft_landing_goldilocks", "scenario_name": "Soft Landing", "scenario_name_ko": "Soft", "lens": "us_global", "final_score": score, "final_confidence": 70.0, "final_display_state": "STRONG", "event_count": 0, "overlay_applied": "N"}],
                )
                write_csv(
                    serve_dashboard.SCENARIO_FINAL_DIR / f"scenario_confidence_{run_id}.csv",
                    ["date", "scenario_code", "final_confidence"],
                    [{"date": "2026-05-12", "scenario_code": "soft_landing_goldilocks", "final_confidence": 70.0}],
                )
                (serve_dashboard.SCENARIO_FINAL_DIR / f"top_active_scenarios_{run_id}.json").write_text(
                    '{"date":"2026-05-12","top_active_scenarios":[{"scenario_code":"soft_landing_goldilocks","final_score":88.0}]}',
                    encoding="utf-8",
                )
                (serve_dashboard.SCENARIO_REPORT_DIR / f"final_market_state_metadata_{run_id}.json").parent.mkdir(parents=True, exist_ok=True)
                (serve_dashboard.SCENARIO_REPORT_DIR / f"final_market_state_metadata_{run_id}.json").write_text(
                    '{"pipeline_phase":"phase6_final_merge","final_row_count":1}',
                    encoding="utf-8",
                )
                (serve_dashboard.SCENARIO_REPORT_DIR / f"final_market_state_summary_{run_id}.md").write_text("# Summary\n", encoding="utf-8")

            (serve_dashboard.SCENARIO_VECTOR_DIR / "current_scenario_vector_v2-scenarios-prod.json").parent.mkdir(parents=True, exist_ok=True)
            (serve_dashboard.SCENARIO_VECTOR_DIR / "current_scenario_vector_v2-scenarios-prod.json").write_text(
                '[{"scenario_code":"soft_landing_goldilocks","score":88.0,"display_state":"STRONG","confidence":70.0,"lens":"us_global"}]',
                encoding="utf-8",
            )
            (serve_dashboard.SCENARIO_OUTPUT_DIR / "latest_manifest.json").write_text(
                '{"active_final_run":"v2-phase6-prod","active_scenario_vector_json_path":"scenario_vectors/current_scenario_vector_v2-scenarios-prod.json","scenario_count":10}',
                encoding="utf-8",
            )

            data = serve_dashboard.load_scenario_dashboard_data()

            self.assertEqual(data["runId"], "v2-phase6-prod")
            self.assertEqual(data["scenarioVectorLeaders"][0]["score"], 88.0)

    def test_humanize_scenario_replaces_tickers(self):
        self.assertEqual(
            serve_dashboard.humanize_scenario("제안(다자산) - IAU + GLD + SHY"),
            "제안(다자산) - 금 ETF (IAU) + 금 ETF (GLD) + 단기 미국국채 ETF (SHY)",
        )
        self.assertEqual(
            serve_dashboard.humanize_scenario("기준(TSLA 100%)"),
            "기준(Tesla (TSLA) 100%)",
        )

    def test_logic_map_static_assets_are_whitelisted(self):
        source = MODULE_PATH.read_text(encoding="utf-8")

        self.assertIn('"/unified.js"', source)
        self.assertIn('"/logic.html"', source)
        self.assertIn('"/logic.js"', source)
        self.assertTrue((ROOT / "web" / "unified.js").exists())
        self.assertTrue((ROOT / "web" / "logic.html").exists())
        self.assertTrue((ROOT / "web" / "logic.js").exists())

    def test_unified_dashboard_main_views_use_action_payloads(self):
        source = (ROOT / "web" / "unified.js").read_text(encoding="utf-8")

        dashboard_body = self._last_js_function_body(source, "renderDashboard")
        self.assertIn("const best = pickBestAction();", dashboard_body)
        self.assertIn("renderVulnerabilityAnalysis();", dashboard_body)
        self.assertIn("renderVulnerabilityContributors();", dashboard_body)
        self.assertIn("renderActionRecommendations(actionDecision);", dashboard_body)

        self.assertIn("payload?.hedgeActionPlan", self._last_js_function_body(source, "selectedActionRows"))
        self.assertIn("payload?.hedgeActionCandidates", self._last_js_function_body(source, "actionCandidateRows"))
        self.assertIn(
            "payload?.portfolioVulnerabilitySummary",
            self._last_js_function_body(source, "vulnerabilitySummaryData"),
        )
        self.assertIn(
            "payload?.portfolioVulnerabilityAttribution",
            self._last_js_function_body(source, "vulnerabilityAttributionRows"),
        )

        action_body = self._last_js_function_body(source, "renderActionRecommendations")
        self.assertIn("selectedActionRows()", action_body)
        self.assertIn("actionCandidateRows()", action_body)
        self.assertNotIn("allCandidateRows", action_body)
        self.assertNotIn("renderCandidateActionGroup", action_body)
        self.assertNotIn("getTopCausativeAsset", action_body)
        self.assertNotIn("portfolioOneToOne", action_body)
        self.assertNotIn("portfolioMulti", action_body)

        action_card_body = self._last_js_function_body(source, "actionPlanCard")
        self.assertIn("changedWeightRows(row)", action_card_body)
        changed_weights_body = self._last_js_function_body(source, "changedWeightRows")
        self.assertIn("before_weights_json", changed_weights_body)
        self.assertIn("after_weights_json", changed_weights_body)
        self.assertNotIn("addVulnerability", action_card_body)
        self.assertNotIn("trimVulnerability", action_card_body)
        self.assertNotIn("replaceVulnerability", action_card_body)
        self.assertNotIn("const allRows = allCandidateRows(hedge);", source)
        self.assertNotIn("addVulnerability", source)
        self.assertNotIn("trimVulnerability", source)
        self.assertNotIn("replaceVulnerability", source)

        vulnerability_body = self._last_js_function_body(source, "renderVulnerabilityAnalysis")
        self.assertIn("vulnerabilitySleeves()", vulnerability_body)
        self.assertNotIn("scenarioSensitivities", vulnerability_body)
        self.assertNotIn("topActiveScenarios", vulnerability_body)
        self.assertNotIn("basePortfolioWeights", vulnerability_body)

        contributor_body = self._last_js_function_body(source, "renderVulnerabilityContributors")
        self.assertIn("vulnerabilityAttributionRows()", contributor_body)
        self.assertNotIn("scenarioSensitivities", contributor_body)
        self.assertNotIn("basePortfolioWeights", contributor_body)

    def test_auto_preview_invalidates_pending_responses_on_input_change(self):
        source = (ROOT / "web" / "unified.js").read_text(encoding="utf-8")
        schedule_match = re.search(r"function scheduleAutoPreview\(\) \{(?P<body>.*?)\n\}", source, re.S)
        self.assertIsNotNone(schedule_match)
        schedule_body = schedule_match.group("body")

        request_bump = schedule_body.index("previewRequestId += 1;")
        preview_reset = schedule_body.index("portfolioPreview = null;")
        row_collect = schedule_body.index("const rows = collectPortfolioRows();")
        self.assertLess(request_bump, preview_reset)
        self.assertLess(preview_reset, row_collect)

        preview_match = re.search(r"async function previewPortfolio\(\) \{(?P<body>.*?)\n\}", source, re.S)
        self.assertIsNotNone(preview_match)
        preview_body = preview_match.group("body")
        post_call = preview_body.index('await postJson("/api/portfolio/preview"')
        stale_guard = preview_body.index("if (requestId !== previewRequestId) return;")
        render_call = preview_body.index("renderPortfolioPreview(portfolioPreview);")
        self.assertLess(post_call, stale_guard)
        self.assertLess(stale_guard, render_call)

    def test_api_status_returns_operational_summary(self):
        server = serve_dashboard.ThreadingHTTPServer(("127.0.0.1", 0), serve_dashboard.DashboardHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base_url = f"http://127.0.0.1:{server.server_address[1]}"

        try:
            with mock.patch.object(
                serve_dashboard,
                "load_service_status",
                return_value={
                    "ok": True,
                    "service": "HedgeMate dashboard",
                    "activeHedgemateRun": "hedgemate-test",
                    "freshnessStatus": "FRESH",
                    "recommendationState": "NO_FORMAL_RECOMMENDATION",
                    "canExecuteRecommendations": False,
                    "blockers": ["no_formal_recommendation"],
                },
            ):
                with urllib.request.urlopen(f"{base_url}/api/status", timeout=5) as response:
                    self.assertEqual(response.status, 200)
                    payload = json.loads(response.read().decode("utf-8"))
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["service"], "HedgeMate dashboard")
            self.assertEqual(payload["activeHedgemateRun"], "hedgemate-test")
            self.assertEqual(payload["recommendationState"], "NO_FORMAL_RECOMMENDATION")
            self.assertEqual(payload["blockers"], ["no_formal_recommendation"])
        finally:
            server.shutdown()
            thread.join(timeout=5)
            server.server_close()

    def test_unified_dashboard_static_routes_return_200(self):
        server = serve_dashboard.ThreadingHTTPServer(("127.0.0.1", 0), serve_dashboard.DashboardHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base_url = f"http://127.0.0.1:{server.server_address[1]}"

        try:
            expectations = {
                "/": "통합 대시보드",
                "/unified.js": "SCENARIO_LABELS",
                "/scenario.html": "scenario.js",
                "/logic.html": "logic.js",
            }
            for route, marker in expectations.items():
                with urllib.request.urlopen(f"{base_url}{route}", timeout=5) as response:
                    self.assertEqual(response.status, 200)
                    body = response.read().decode("utf-8")
                    self.assertIn(marker, body)
            with urllib.request.urlopen(f"{base_url}/favicon.ico", timeout=5) as response:
                self.assertEqual(response.status, 204)
        finally:
            server.shutdown()
            thread.join(timeout=5)
            server.server_close()

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
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            serve_dashboard.ROOT = root
            serve_dashboard.INPUT_DIR = root / "inputs"
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
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            serve_dashboard.ROOT = root
            serve_dashboard.INPUT_DIR = root / "inputs"
            serve_dashboard.run_pipeline_for_request(payload, runner=fake_runner)
        self.assertIn("TSLA", calls["cmd"])
        self.assertIn("--base-total-krw", calls["cmd"])
        self.assertIn("--hedge-budgets-krw", calls["cmd"])
        self.assertIn("2000000.0", calls["cmd"])

    def test_run_pipeline_for_request_can_force_raw_refresh(self):
        class Result:
            returncode = 0
            stdout = "FEATURE=outputs/processed/features_summary_20260310.csv\n"
            stderr = ""

        calls = {}

        def fake_runner(cmd, cwd, capture_output, text, check):
            calls["cmd"] = cmd
            return Result()

        payload = {"mode": "single_asset", "singleAsset": "Tesla", "forceRefreshRaw": True}
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            serve_dashboard.ROOT = root
            serve_dashboard.INPUT_DIR = root / "inputs"
            serve_dashboard.run_pipeline_for_request(payload, runner=fake_runner)

        self.assertIn("--force-refresh-raw", calls["cmd"])

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

    def test_single_row_portfolio_runs_single_asset_analysis(self):
        class Result:
            returncode = 0
            stdout = "FEATURE=outputs/processed/features_summary_20260310.csv\n"
            stderr = ""

        calls = {}

        def fake_runner(cmd, cwd, capture_output, text, check):
            calls["cmd"] = cmd
            return Result()

        payload = {
            "mode": "portfolio",
            "portfolioRows": [{"asset": "Apple", "amountKrw": 2000000}],
            "hedgeBudgetKrw": 500000,
            "maxComboSize": 2,
        }

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            serve_dashboard.ROOT = root
            serve_dashboard.INPUT_DIR = root / "inputs"
            serve_dashboard.run_pipeline_for_request(payload, runner=fake_runner)
            written_files = sorted(serve_dashboard.INPUT_DIR.glob("portfolio_weights_*.csv"))
            self.assertEqual(len(written_files), 1)
            self.assertIn("AAPL,100.0", written_files[0].read_text(encoding="utf-8"))

        self.assertIn("--single-asset", calls["cmd"])
        self.assertIn("AAPL", calls["cmd"])
        self.assertIn("--base-total-krw", calls["cmd"])
        self.assertIn("2000000.0", calls["cmd"])
        self.assertIn("--hedge-budgets-krw", calls["cmd"])
        self.assertNotIn("--portfolio-input", calls["cmd"])

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
        self.assertEqual(job["stage"], "completed")
        self.assertEqual(job["runId"], "20260310")
        self.assertEqual(job["result"]["runId"], "20260310")
        self.assertIsNone(job["error"])

    def test_run_pipeline_for_request_reports_stage_transitions(self):
        class Result:
            returncode = 0
            stdout = "FEATURE=outputs/processed/features_summary_20260310.csv\n"
            stderr = ""

        stages = []

        def fake_runner(cmd, cwd, capture_output, text, check):
            return Result()

        result = serve_dashboard.run_pipeline_for_request(
            {"_prepared_request": True, "runId": "no-artifacts", "cmd": ["python", "fake"]},
            runner=fake_runner,
            status_callback=stages.append,
        )

        self.assertEqual(result["runId"], "20260310")
        self.assertEqual(stages, ["running HedgeMate analysis", "completed"])

    def test_run_pipeline_for_request_updates_active_bundle_when_artifacts_exist(self):
        class Result:
            returncode = 0
            stdout = "FEATURE=outputs/processed/features_summary_hedge-user.csv\n"
            stderr = ""

        calls = []
        stages = []

        def fake_runner(cmd, cwd, capture_output, text, check):
            calls.append(cmd)
            return Result()

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "HedgeMate"
            workspace = root.parent
            scenario = workspace / "scenario_research"
            serve_dashboard.ROOT = root
            serve_dashboard.OUTPUT_PROCESSED_DIR = root / "outputs" / "processed"
            serve_dashboard.OUTPUT_REPORT_DIR = root / "outputs" / "reports"
            serve_dashboard.OUTPUT_VALIDATION_DIR = root / "outputs" / "validation"
            serve_dashboard.SCENARIO_RESEARCH_ROOT = scenario
            serve_dashboard.SCENARIO_OUTPUT_DIR = scenario / "outputs"
            serve_dashboard.SCENARIO_FINAL_DIR = serve_dashboard.SCENARIO_OUTPUT_DIR / "final"
            serve_dashboard.SCENARIO_REPORT_DIR = serve_dashboard.SCENARIO_OUTPUT_DIR / "reports"
            serve_dashboard.SCENARIO_VECTOR_DIR = serve_dashboard.SCENARIO_OUTPUT_DIR / "scenario_vectors"

            for path in [
                serve_dashboard.OUTPUT_PROCESSED_DIR / "features_summary_hedge-user.csv",
                serve_dashboard.OUTPUT_PROCESSED_DIR / "asset_scenario_sensitivity_hedge-user.csv",
                serve_dashboard.OUTPUT_REPORT_DIR / "portfolio_1to1_hedge_hedge-user.csv",
                serve_dashboard.OUTPUT_REPORT_DIR / "portfolio_multi_hedge_hedge-user.csv",
                serve_dashboard.SCENARIO_VECTOR_DIR / "current_scenario_vector_scenario-active.csv",
                serve_dashboard.SCENARIO_VECTOR_DIR / "current_scenario_vector_final-active.csv",
                serve_dashboard.SCENARIO_FINAL_DIR / "final_market_state_daily_final-active.csv",
                serve_dashboard.SCENARIO_FINAL_DIR / "scenario_confidence_final-active.csv",
                serve_dashboard.SCENARIO_FINAL_DIR / "top_active_scenarios_final-active.json",
                serve_dashboard.SCENARIO_REPORT_DIR / "final_market_state_metadata_final-active.json",
            ]:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("{}" if path.suffix == ".json" else "x\n", encoding="utf-8")
            (root / "outputs" / "latest_manifest.json").write_text(
                json.dumps(
                    {
                        "active_bundle": {
                            "scenario_run": "scenario-active",
                            "final_market_state_run": "final-active",
                            "data_version": "20260519",
                            "scenario_vector_as_of_date": "2026-05-18",
                        },
                        "artifacts": {
                            "scenarioVector": "scenario_research/outputs/scenario_vectors/current_scenario_vector_scenario-active.csv",
                            "finalScenarioVector": "scenario_research/outputs/scenario_vectors/current_scenario_vector_final-active.csv",
                            "finalMarketState": "scenario_research/outputs/final/final_market_state_daily_final-active.csv",
                            "scenarioConfidence": "scenario_research/outputs/final/scenario_confidence_final-active.csv",
                            "topActiveScenarios": "scenario_research/outputs/final/top_active_scenarios_final-active.json",
                            "finalMetadata": "scenario_research/outputs/reports/final_market_state_metadata_final-active.json",
                        },
                    }
                ),
                encoding="utf-8",
            )
            backtest_portfolio = root / "inputs" / "portfolio_weights_user.csv"
            backtest_portfolio.parent.mkdir(parents=True, exist_ok=True)
            backtest_portfolio.write_text("ticker,weight_pct\nAAPL,100\n", encoding="utf-8")

            result = serve_dashboard.run_pipeline_for_request(
                {
                    "_prepared_request": True,
                    "runId": "hedge-user",
                    "cmd": ["python", "fake"],
                    "dataVersion": "20260520",
                    "backtestPortfolioInputPath": str(backtest_portfolio),
                },
                runner=fake_runner,
                status_callback=stages.append,
            )

        self.assertTrue(result["productBundleUpdated"])
        self.assertEqual(result["backtestRunId"], "backtest-hedge-user")
        self.assertEqual(
            stages,
            [
                "running HedgeMate analysis",
                "running scenario backtest",
                "applying backtest gate",
                "updating active dashboard bundle",
                "completed",
            ],
        )
        self.assertEqual(len(calls), 4)
        self.assertIn("run_scenario_backtest.py", " ".join(calls[1]))
        self.assertIn("--portfolio-input", calls[1])
        self.assertIn(str(backtest_portfolio), calls[1])
        self.assertEqual(calls[1][calls[1].index("--data-version") + 1], "20260520")
        self.assertIn("apply_backtest_gate.py", " ".join(calls[2]))
        self.assertIn("update_active_bundle.py", " ".join(calls[3]))
        self.assertEqual(calls[3][calls[3].index("--data-version") + 1], "20260520")
        self.assertIn("--portfolio-input", calls[3])
        self.assertEqual(calls[3][calls[3].index("--portfolio-input") + 1], str(backtest_portfolio))
        self.assertIn("--portfolio-1to1", calls[3])
        self.assertIn("portfolio_1to1_hedge_hedge-user_backtest_gated.csv", " ".join(calls[3]))

    def test_single_asset_product_update_uses_single_asset_recommendation_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "HedgeMate"
            workspace = root.parent
            scenario = workspace / "scenario_research"
            serve_dashboard.ROOT = root
            serve_dashboard.OUTPUT_PROCESSED_DIR = root / "outputs" / "processed"
            serve_dashboard.OUTPUT_REPORT_DIR = root / "outputs" / "reports"
            serve_dashboard.OUTPUT_VALIDATION_DIR = root / "outputs" / "validation"
            serve_dashboard.SCENARIO_RESEARCH_ROOT = scenario
            serve_dashboard.SCENARIO_OUTPUT_DIR = scenario / "outputs"
            serve_dashboard.SCENARIO_FINAL_DIR = serve_dashboard.SCENARIO_OUTPUT_DIR / "final"
            serve_dashboard.SCENARIO_REPORT_DIR = serve_dashboard.SCENARIO_OUTPUT_DIR / "reports"
            serve_dashboard.SCENARIO_VECTOR_DIR = serve_dashboard.SCENARIO_OUTPUT_DIR / "scenario_vectors"
            for path in [
                serve_dashboard.OUTPUT_REPORT_DIR / "single_asset_hedge_1to1_hedge-user.csv",
                serve_dashboard.OUTPUT_REPORT_DIR / "single_asset_hedge_multi_hedge-user.csv",
                serve_dashboard.SCENARIO_VECTOR_DIR / "current_scenario_vector_scenario-active.csv",
                serve_dashboard.SCENARIO_VECTOR_DIR / "current_scenario_vector_final-active.csv",
                serve_dashboard.SCENARIO_FINAL_DIR / "final_market_state_daily_final-active.csv",
                serve_dashboard.SCENARIO_FINAL_DIR / "scenario_confidence_final-active.csv",
                serve_dashboard.SCENARIO_FINAL_DIR / "top_active_scenarios_final-active.json",
                serve_dashboard.SCENARIO_REPORT_DIR / "final_market_state_metadata_final-active.json",
            ]:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("{}" if path.suffix == ".json" else "x\n", encoding="utf-8")
            (root / "outputs" / "latest_manifest.json").write_text(
                json.dumps(
                    {
                        "active_bundle": {
                            "scenario_run": "scenario-active",
                            "final_market_state_run": "final-active",
                            "data_version": "20260519",
                        },
                        "artifacts": {},
                    }
                ),
                encoding="utf-8",
            )

            commands, _ = serve_dashboard.build_product_update_commands("hedge-user", recommendation_scope="single_asset")

        self.assertIn("--recommendation-scope", commands[0])
        self.assertIn("single_asset", commands[0])
        self.assertIn("single_asset_hedge_1to1_hedge-user.csv", " ".join(commands[1]))
        self.assertIn("single_asset_hedge_1to1_hedge-user_backtest_gated.csv", " ".join(commands[1]))
        self.assertIn("single_asset_hedge_1to1_hedge-user_backtest_gated.csv", " ".join(commands[2]))

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
