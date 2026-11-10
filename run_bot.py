"""Live loop: checks every symbol once per closed candle and trades the signals.

    python run_bot.py

DRY_RUN=true (default) only logs what the bot WOULD do. Test on a demo account first.
"""
import logging
import time
from datetime import datetime, timezone

from bot.broker import Broker
from bot.config import Settings
from bot.notifier import Telegram
from bot.risk import DailyLossGuard, lot_size
from bot.strategy import StrategyParams, generate_signal

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("bot")


def in_trading_hours(now: datetime, hours: tuple[int, int]) -> bool:
    start, end = hours
    return start <= now.hour < end


def run_once(broker: Broker, cfg: Settings, params: StrategyParams, guard: DailyLossGuard, tg: Telegram) -> None:
    now = datetime.now(timezone.utc)
    acc = broker.account()
    if not guard.allows_trading(now.date(), acc.equity):
        log.info("Daily loss limit reached - no new trades today")
        return
    if not in_trading_hours(now, cfg.trade_hours_utc):
        return

    for symbol in cfg.symbols:
        if broker.open_positions(symbol):
            continue  # one position per symbol
        signal = generate_signal(broker.candles(symbol, cfg.timeframe), params)
        if signal is None:
            continue
        info = broker.symbol(symbol)
        lots = lot_size(acc.balance, cfg.risk_pct, signal.sl_distance,
                        info.trade_tick_size, info.trade_tick_value,
                        info.volume_min, info.volume_max, info.volume_step)
        if lots == 0:
            log.info("%s: signal skipped, position would be below minimum lot", symbol)
            continue

        text = f"{'[DRY RUN] ' if cfg.dry_run else ''}{signal.side.upper()} {symbol} {lots} lots - {signal.reason}"
        log.info(text)
        if not cfg.dry_run:
            try:
                broker.market_order(symbol, signal.side, lots, signal.sl_distance, signal.tp_distance)
            except RuntimeError as exc:
                text = f"Order failed on {symbol}: {exc}"
                log.error(text)
        tg.send(text)


def main() -> None:
    cfg, params = Settings(), StrategyParams()
    broker = Broker(cfg.magic, cfg.mt5_path)
    guard, tg = DailyLossGuard(cfg.max_daily_loss_pct), Telegram(cfg.telegram_token, cfg.telegram_chat_id)
    tg.send(f"Bot started on {', '.join(cfg.symbols)} {cfg.timeframe} (dry run: {cfg.dry_run})")
    last_minute = None
    try:
        while True:
            minute = datetime.now(timezone.utc).strftime("%Y%m%d%H%M")
            if minute != last_minute:  # evaluate once per minute; signals use closed candles only
                last_minute = minute
                try:
                    run_once(broker, cfg, params, guard, tg)
                except Exception as exc:  # keep running, but tell the owner
                    log.exception("Loop error")
                    tg.send(f"Bot error: {exc}")
            time.sleep(5)
    except KeyboardInterrupt:
        log.info("Stopped by user")
    finally:
        broker.shutdown()


if __name__ == "__main__":
    main()
