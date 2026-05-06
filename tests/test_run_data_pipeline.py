import csv
import importlib.util
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
            return -0.6 * spy_ret(i) + 0.0015

        def gld_ret(i):
            return -0.25 * spy_ret(i) + 0.0008

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

                single_compare = output_reports / f"single_asset_compare_{run_id}.csv"
                self.assertTrue(single_compare.exists())
                with single_compare.open(encoding="utf-8", newline="") as f:
                    reader = csv.DictReader(f)
                    compare_rows = list(reader)
                self.assertGreaterEqual(len(compare_rows), 2)
                self.assertIn("sharpe_krw_proxy", reader.fieldnames)
                self.assertIn("no_recommendation_reason", reader.fieldnames)

                single_multi = output_reports / f"single_asset_hedge_multi_{run_id}.csv"
                self.assertTrue(single_multi.exists())
                with single_multi.open(encoding="utf-8", newline="") as f:
                    reader = csv.DictReader(f)
                    multi_rows = list(reader)
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


if __name__ == "__main__":
    unittest.main()
