"""Settings loaded from the .env file (copy .env.example to .env)."""
import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()


def _list(name: str, default: str) -> list[str]:
    return [s.strip() for s in os.getenv(name, default).split(",") if s.strip()]


@dataclass
class Settings:
    symbols: list[str] = field(default_factory=lambda: _list("SYMBOLS", "EURUSD"))
    timeframe: str = os.getenv("TIMEFRAME", "H1")
    risk_pct: float = float(os.getenv("RISK_PCT", "0.5"))
    max_daily_loss_pct: float = float(os.getenv("MAX_DAILY_LOSS_PCT", "3"))
    trade_hours_utc: tuple[int, int] = tuple(int(h) for h in os.getenv("TRADE_HOURS_UTC", "7-20").split("-"))
    magic: int = int(os.getenv("MAGIC", "770077"))
    dry_run: bool = os.getenv("DRY_RUN", "true").lower() == "true"
    telegram_token: str = os.getenv("TELEGRAM_TOKEN", "")
    telegram_chat_id: str = os.getenv("TELEGRAM_CHAT_ID", "")
    mt5_path: str = os.getenv("MT5_PATH", "")  # optional: path to terminal64.exe
