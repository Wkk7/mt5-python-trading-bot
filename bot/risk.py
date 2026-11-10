"""Position sizing and account protection."""
import math


def lot_size(balance: float, risk_pct: float, sl_distance: float,
             tick_size: float, tick_value: float,
             vol_min: float, vol_max: float, vol_step: float) -> float:
    """Lots so that hitting the stop loss loses `risk_pct` % of `balance`.

    tick_value is the account-currency value of one tick for 1.0 lot,
    exactly as MetaTrader 5 reports it in symbol_info().
    """
    if sl_distance <= 0 or tick_size <= 0 or tick_value <= 0:
        return 0.0
    money_at_risk = balance * risk_pct / 100.0
    loss_per_lot = sl_distance / tick_size * tick_value
    raw = money_at_risk / loss_per_lot
    lots = math.floor(raw / vol_step) * vol_step          # never round UP the risk
    if lots < vol_min:
        return 0.0                                        # too small: skip the trade
    return round(min(lots, vol_max), 8)


class DailyLossGuard:
    """Stops new trades after the account loses `max_daily_loss_pct` in one day."""

    def __init__(self, max_daily_loss_pct: float):
        self.max_daily_loss_pct = max_daily_loss_pct
        self.day = None
        self.start_equity = None

    def allows_trading(self, today, equity: float) -> bool:
        if self.day != today:
            self.day, self.start_equity = today, equity
        drawdown_pct = (self.start_equity - equity) / self.start_equity * 100
        return drawdown_pct < self.max_daily_loss_pct
