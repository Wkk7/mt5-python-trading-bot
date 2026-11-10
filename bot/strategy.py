"""Example strategy: EMA trend filter + RSI pullback entries, ATR-based stops.

This is a DEMO strategy that shows how the framework works. Replace the logic in
`generate_signal` with your own rules - everything else (risk, orders, alerts,
backtest) keeps working.
"""
from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class StrategyParams:
    ema_fast: int = 50
    ema_slow: int = 200
    rsi_period: int = 14
    rsi_buy_below: float = 35.0
    rsi_sell_above: float = 65.0
    atr_period: int = 14
    sl_atr: float = 1.5
    tp_atr: float = 3.0


@dataclass
class Signal:
    side: str          # "buy" or "sell"
    sl_distance: float  # price distance from entry to stop loss
    tp_distance: float  # price distance from entry to take profit
    reason: str


def add_indicators(df: pd.DataFrame, p: StrategyParams) -> pd.DataFrame:
    out = df.copy()
    out["ema_fast"] = out["close"].ewm(span=p.ema_fast, adjust=False).mean()
    out["ema_slow"] = out["close"].ewm(span=p.ema_slow, adjust=False).mean()

    delta = out["close"].diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / p.rsi_period, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / p.rsi_period, adjust=False).mean()
    rs = gain / loss.replace(0, np.nan)
    out["rsi"] = 100 - 100 / (1 + rs)

    prev_close = out["close"].shift()
    tr = pd.concat(
        [out["high"] - out["low"], (out["high"] - prev_close).abs(), (out["low"] - prev_close).abs()],
        axis=1,
    ).max(axis=1)
    out["atr"] = tr.ewm(alpha=1 / p.atr_period, adjust=False).mean()
    return out


def signal_sides(ind: pd.DataFrame, p: StrategyParams) -> pd.Series:
    """Vectorised rules: +1 = buy, -1 = sell, 0 = nothing (one value per candle).

    The live bot and the backtest both use this function, so they always agree.
    """
    uptrend = (ind["close"] > ind["ema_slow"]) & (ind["ema_fast"] > ind["ema_slow"])
    downtrend = (ind["close"] < ind["ema_slow"]) & (ind["ema_fast"] < ind["ema_slow"])
    side = pd.Series(0, index=ind.index)
    side[uptrend & (ind["rsi"] < p.rsi_buy_below)] = 1
    side[downtrend & (ind["rsi"] > p.rsi_sell_above)] = -1
    side.iloc[: p.ema_slow] = 0  # warm-up period
    return side


def generate_signal(df: pd.DataFrame, p: StrategyParams) -> Signal | None:
    """Look at the last CLOSED candle and return a Signal or None."""
    if len(df) < p.ema_slow + 5:
        return None
    ind = add_indicators(df, p)
    row, side = ind.iloc[-1], signal_sides(ind, p).iloc[-1]
    if side == 0 or np.isnan(row["atr"]):
        return None
    sl, tp = float(p.sl_atr * row["atr"]), float(p.tp_atr * row["atr"])
    name = "buy" if side == 1 else "sell"
    trend = "uptrend" if side == 1 else "downtrend"
    return Signal(name, sl, tp, f"{trend} + RSI {row['rsi']:.1f} pullback")
