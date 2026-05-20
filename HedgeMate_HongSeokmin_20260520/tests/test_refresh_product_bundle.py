import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "refresh_product_bundle.py"

spec = importlib.util.spec_from_file_location("refresh_product_bundle", MODULE_PATH)
refresh_product_bundle = importlib.util.module_from_spec(spec)
spec.loader.exec_module(refresh_product_bundle)


class RefreshProductBundleTests(unittest.TestCase):
    def test_refresh_forwards_portfolio_and_krw_budget_to_hedgemate_pipeline(self):
        calls = []
        original_run_step = refresh_product_bundle.run_step
        refresh_product_bundle.run_step = lambda cmd: calls.append(cmd)
        try:
            rc = refresh_product_bundle.main(
                [
                    "--data-version",
                    "20260520",
                    "--run-stamp",
                    "smoke",
                    "--portfolio-input",
                    r"HedgeMate\inputs\portfolio_weights_smoke.csv",
                    "--base-total-krw",
                    "10000000",
                    "--hedge-budgets-krw",
                    "1000000",
                    "--max-combo-size",
                    "3",
                ]
            )
        finally:
            refresh_product_bundle.run_step = original_run_step

        self.assertEqual(rc, 0)
        hedge_cmd = next(cmd for cmd in calls if any("run_data_pipeline.py" in part for part in cmd))
        self.assertIn("--portfolio-input", hedge_cmd)
        self.assertEqual(hedge_cmd[hedge_cmd.index("--portfolio-input") + 1], r"HedgeMate\inputs\portfolio_weights_smoke.csv")
        self.assertIn("--base-total-krw", hedge_cmd)
        self.assertEqual(hedge_cmd[hedge_cmd.index("--base-total-krw") + 1], "10000000.0")
        self.assertIn("--hedge-budgets-krw", hedge_cmd)
        self.assertEqual(hedge_cmd[hedge_cmd.index("--hedge-budgets-krw") + 1], "1000000")
        update_cmd = next(cmd for cmd in calls if any("update_active_bundle.py" in part for part in cmd))
        self.assertEqual(update_cmd[update_cmd.index("--portfolio-input") + 1], r"HedgeMate\inputs\portfolio_weights_smoke.csv")

    def test_refresh_rejects_krw_budget_without_base_total(self):
        with self.assertRaises(SystemExit):
            refresh_product_bundle.parse_args(["--hedge-budgets-krw", "1000000"])


if __name__ == "__main__":
    unittest.main()
