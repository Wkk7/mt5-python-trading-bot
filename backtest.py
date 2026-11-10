"""Honest backtest of the strategy: spread + commission included, no look-ahead.

    python backtest.py                                  # sample data in data/
    python backtest.py --csv my_data.csv --risk 1
    python backtest.py --mt5 EURUSD --bars 20000        # download from your MT5 terminal

Rules of the simulation
- signal on a CLOSED candle -> entry at the NEXT candle open (+ half spread)
- if stop loss and take profit are both touched in the same candle, the LOSS is counted
- one position at a time, fixed % risk per trade
"""
import argparse
from dataclasses import dataclass

import matplotlib
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from bot.strategy import StrategyParams, add_indicators, signal_sides  # noqa: E402


@dataclass
class Costs:
    spread: float = 0.00008        # price units (0.8 pips on EURUSD)
    commission_r: float = 0.00007  # round-trip commission expressed in price units


def load_csv(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    df["time"] = pd.to_datetime(df.iloc[:, 0], utc=True)
    return df.set_index("time")[["open", "high", "low", "close"]].astype(float).sort_index()


def load_mt5(symbol: str, bars: int, timeframe: str) -> pd.DataFrame:
    from bot.broker import Broker  # imported here so the backtest works without MT5
    broker = Broker(magic=0)
    try:
        return broker.candles(symbol, timeframe, bars)
    finally:
        broker.shutdown()


def run(df: pd.DataFrame, p: StrategyParams, costs: Costs, risk_pct: float) -> pd.DataFrame:
    ind = add_indicators(df, p)
    sides = signal_sides(ind, p).to_numpy()
    o, h, l, atr = ind["open"].to_numpy(), ind["high"].to_numpy(), ind["low"].to_numpy(), ind["atr"].to_numpy()
    times = ind.index
    trades, i, n = [], 0, len(ind)
    while i < n - 1:
        side = sides[i]
        if side == 0:
            i += 1
            continue
        entry_i = i + 1
        entry = o[entry_i] + side * costs.spread / 2
        sl_d, tp_d = p.sl_atr * atr[i], p.tp_atr * atr[i]
        sl, tp = entry - side * sl_d, entry + side * tp_d
        exit_price, j = None, entry_i
        while j < n:
            hit_sl = l[j] <= sl if side == 1 else h[j] >= sl
            hit_tp = h[j] >= tp if side == 1 else l[j] <= tp
            if hit_sl:
                exit_price = sl
                break
            if hit_tp:
                exit_price = tp
                break
            j += 1
        if exit_price is None:
            break  # trade still open at the end of the data
        exit_price -= side * costs.spread / 2
        pnl_price = side * (exit_price - entry) - costs.commission_r
        trades.append({"entry_time": times[entry_i], "exit_time": times[j], "side": "buy" if side == 1 else "sell",
                       "r": pnl_price / sl_d})
        i = j + 1
    t = pd.DataFrame(trades)
    if t.empty:
        return t
    t["pct"] = t["r"] * risk_pct
    t["equity"] = 100 * (1 + t["pct"] / 100).cumprod()
    t["drawdown"] = t["equity"] / t["equity"].cummax() - 1
    return t


def report(t: pd.DataFrame) -> dict:
    wins, losses = t[t["r"] > 0], t[t["r"] <= 0]
    return {
        "trades": len(t),
        "win_rate_%": round(100 * len(wins) / len(t), 1),
        "avg_R": round(t["r"].mean(), 3),
        "profit_factor": round(wins["r"].sum() / -losses["r"].sum(), 2) if len(losses) else float("inf"),
        "total_return_%": round(t["equity"].iloc[-1] - 100, 2),
        "max_drawdown_%": round(100 * t["drawdown"].min(), 2),
    }


def plot(t: pd.DataFrame, stats: dict, title: str, out: str) -> None:
    red, bg, fg = "#e81e2d", "#141416", "#eaeaea"
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12.8, 7.2), dpi=100, sharex=True,
                                   gridspec_kw={"height_ratios": [3, 1]}, facecolor=bg)
    for ax in (ax1, ax2):
        ax.set_facecolor(bg)
        ax.tick_params(colors=fg)
        for s in ax.spines.values():
            s.set_color("#333")
        ax.grid(color="#2a2a2e", linewidth=0.6)
    ax1.plot(t["exit_time"], t["equity"], color=red, linewidth=2)
    ax1.set_title(title, color=fg, fontsize=16, loc="left", pad=12)
    ax1.set_ylabel("Equity (start = 100)", color=fg)
    ax2.fill_between(t["exit_time"], 100 * t["drawdown"], 0, color=red, alpha=0.35)
    ax2.set_ylabel("Drawdown %", color=fg)
    text = "   ".join(f"{k.replace('_', ' ')}: {v}" for k, v in stats.items())
    fig.text(0.01, 0.01, text, color=fg, fontsize=11)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    fig.savefig(out, facecolor=bg)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--csv", default="data/EURUSD_H1.csv")
    ap.add_argument("--mt5", help="symbol to download from MetaTrader 5 instead of a CSV")
    ap.add_argument("--bars", type=int, default=20000)
    ap.add_argument("--timeframe", default="H1")
    ap.add_argument("--risk", type=float, default=0.5, help="risk per trade in %%")
    ap.add_argument("--spread", type=float, default=Costs.spread)
    ap.add_argument("--chart", default="backtest.png")
    a = ap.parse_args()

    df = load_mt5(a.mt5, a.bars, a.timeframe) if a.mt5 else load_csv(a.csv)
    trades = run(df, StrategyParams(), Costs(spread=a.spread), a.risk)
    if trades.empty:
        print("No trades.")
        return
    stats = report(trades)
    for k, v in stats.items():
        print(f"{k:>16}: {v}")
    print("\nResult by year (%):")
    print(trades.groupby(trades["exit_time"].dt.year)["pct"].sum().round(2).to_string())
    name = a.mt5 or a.csv.split("/")[-1].replace(".csv", "")
    plot(trades, stats, f"Backtest {name}  |  {df.index[0]:%Y-%m} to {df.index[-1]:%Y-%m}  |  costs included", a.chart)
    trades.to_csv("trades.csv", index=False)
    print(f"\nChart saved to {a.chart}, trade list saved to trades.csv")


if __name__ == "__main__":
    main()
