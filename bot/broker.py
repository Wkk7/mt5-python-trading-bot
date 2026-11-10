"""Thin wrapper around the official MetaTrader5 Python package."""
import logging

import MetaTrader5 as mt5
import pandas as pd

log = logging.getLogger(__name__)

TIMEFRAMES = {
    "M5": mt5.TIMEFRAME_M5, "M15": mt5.TIMEFRAME_M15, "M30": mt5.TIMEFRAME_M30,
    "H1": mt5.TIMEFRAME_H1, "H4": mt5.TIMEFRAME_H4, "D1": mt5.TIMEFRAME_D1,
}


class Broker:
    def __init__(self, magic: int, path: str = ""):
        self.magic = magic
        ok = mt5.initialize(path) if path else mt5.initialize()
        if not ok:
            raise RuntimeError(f"MT5 initialize failed: {mt5.last_error()}")
        acc = mt5.account_info()
        log.info("Connected to %s, account %s (%s)", acc.server, acc.login, acc.currency)

    def candles(self, symbol: str, timeframe: str, count: int = 500) -> pd.DataFrame:
        mt5.symbol_select(symbol, True)
        rates = mt5.copy_rates_from_pos(symbol, TIMEFRAMES[timeframe], 1, count)  # 1 = skip the open candle
        if rates is None or len(rates) == 0:
            raise RuntimeError(f"No data for {symbol}: {mt5.last_error()}")
        df = pd.DataFrame(rates)
        df["time"] = pd.to_datetime(df["time"], unit="s", utc=True)
        return df.set_index("time")[["open", "high", "low", "close", "tick_volume"]]

    def account(self):
        return mt5.account_info()

    def symbol(self, symbol: str):
        return mt5.symbol_info(symbol)

    def open_positions(self, symbol: str) -> list:
        return [p for p in (mt5.positions_get(symbol=symbol) or []) if p.magic == self.magic]

    def market_order(self, symbol: str, side: str, lots: float, sl_distance: float, tp_distance: float, comment: str = "bot"):
        tick = mt5.symbol_info_tick(symbol)
        info = mt5.symbol_info(symbol)
        price = tick.ask if side == "buy" else tick.bid
        sign = 1 if side == "buy" else -1
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": lots,
            "type": mt5.ORDER_TYPE_BUY if side == "buy" else mt5.ORDER_TYPE_SELL,
            "price": price,
            "sl": round(price - sign * sl_distance, info.digits),
            "tp": round(price + sign * tp_distance, info.digits),
            "deviation": 20,
            "magic": self.magic,
            "comment": comment[:31],
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        result = mt5.order_send(request)
        if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
            raise RuntimeError(f"Order rejected: {getattr(result, 'retcode', None)} {getattr(result, 'comment', mt5.last_error())}")
        return result

    def shutdown(self):
        mt5.shutdown()
