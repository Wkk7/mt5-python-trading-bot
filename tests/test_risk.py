import unittest
from datetime import date

from bot.risk import DailyLossGuard, lot_size


class LotSizeTest(unittest.TestCase):
    def test_eurusd_one_percent(self):
        # 10,000 balance, 1% risk = 100. SL 20 pips = 0.0020. 1 lot = 10 per pip -> 200 per lot -> 0.5 lots
        lots = lot_size(10_000, 1.0, 0.0020, tick_size=0.00001, tick_value=1.0,
                        vol_min=0.01, vol_max=100, vol_step=0.01)
        self.assertAlmostEqual(lots, 0.5)

    def test_never_rounds_risk_up(self):
        lots = lot_size(10_000, 1.0, 0.0030, 0.00001, 1.0, 0.01, 100, 0.01)  # exact = 0.3333
        self.assertAlmostEqual(lots, 0.33)

    def test_too_small_returns_zero(self):
        self.assertEqual(lot_size(100, 0.1, 0.0050, 0.00001, 1.0, 0.01, 100, 0.01), 0.0)

    def test_capped_at_max_volume(self):
        self.assertEqual(lot_size(10_000_000, 5, 0.0010, 0.00001, 1.0, 0.01, 50, 0.01), 50)


class DailyLossGuardTest(unittest.TestCase):
    def test_blocks_after_limit_and_resets_next_day(self):
        g = DailyLossGuard(3)
        self.assertTrue(g.allows_trading(date(2026, 1, 5), 10_000))
        self.assertTrue(g.allows_trading(date(2026, 1, 5), 9_750))
        self.assertFalse(g.allows_trading(date(2026, 1, 5), 9_690))
        self.assertTrue(g.allows_trading(date(2026, 1, 6), 9_690))


if __name__ == "__main__":
    unittest.main()
