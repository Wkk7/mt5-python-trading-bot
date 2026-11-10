"""Telegram alerts (optional). Create a bot with @BotFather and put the token in .env."""
import logging

import requests

log = logging.getLogger(__name__)


class Telegram:
    def __init__(self, token: str, chat_id: str):
        self.enabled = bool(token and chat_id)
        self.url = f"https://api.telegram.org/bot{token}/sendMessage"
        self.chat_id = chat_id

    def send(self, text: str) -> None:
        if not self.enabled:
            return
        try:
            requests.post(self.url, data={"chat_id": self.chat_id, "text": text}, timeout=10)
        except requests.RequestException as exc:  # alerts must never crash the bot
            log.warning("Telegram alert failed: %s", exc)
