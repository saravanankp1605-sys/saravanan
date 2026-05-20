"""Notifications (currently Telegram).

Uses urllib (stdlib only) so it works without extra dependencies. If notifications
are disabled or misconfigured, methods become silent no-ops -- they MUST never
crash the trading loop.

To get a bot token + chat id:
  1. Talk to @BotFather on Telegram, run /newbot, copy the token.
  2. Send any message to your new bot.
  3. Visit https://api.telegram.org/bot<TOKEN>/getUpdates and read the chat id.
"""
from __future__ import annotations

import json
import logging
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Optional

log = logging.getLogger("forex_bot")


@dataclass
class TelegramNotifier:
    bot_token: str = ""
    chat_id: str = ""
    enabled: bool = False
    timeout: float = 5.0

    def _is_configured(self) -> bool:
        return self.enabled and bool(self.bot_token) and bool(self.chat_id)

    def send(self, text: str) -> bool:
        if not self._is_configured():
            return False
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        payload = urllib.parse.urlencode({
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": "Markdown",
            "disable_web_page_preview": "true",
        }).encode("utf-8")
        try:
            req = urllib.request.Request(url, data=payload, method="POST")
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                body = resp.read().decode("utf-8", errors="ignore")
                ok = json.loads(body).get("ok", False) if body else False
                if not ok:
                    log.warning("Telegram send failed: %s", body[:200])
                return bool(ok)
        except Exception as e:  # noqa: BLE001
            log.warning("Telegram notification error: %s", e)
            return False

    # -- friendly helpers -------------------------------------------------

    def trade_opened(self, symbol: str, side: int, volume: float,
                     price: float, sl: float, tp: float, ticket: Optional[int] = None):
        s = "BUY" if side > 0 else "SELL"
        msg = (
            f"*Trade opened* {s} `{symbol}`\n"
            f"Volume: `{volume}`  Price: `{price:.5f}`\n"
            f"SL: `{sl:.5f}`  TP: `{tp:.5f}`"
        )
        if ticket is not None:
            msg += f"\nTicket: `{ticket}`"
        self.send(msg)

    def trade_closed(self, symbol: str, side: int, volume: float,
                     entry: float, exit_price: float, pnl: float,
                     reason: str = ""):
        s = "BUY" if side > 0 else "SELL"
        emoji = "PROFIT" if pnl >= 0 else "LOSS"
        msg = (
            f"*Trade closed* ({emoji}) {s} `{symbol}`\n"
            f"Vol `{volume}`  {entry:.5f} -> {exit_price:.5f}\n"
            f"PnL: `{pnl:+.2f}`"
        )
        if reason:
            msg += f"  ({reason})"
        self.send(msg)

    def info(self, msg: str):
        self.send(msg)


def build_notifier(cfg) -> TelegramNotifier:
    """Build a TelegramNotifier from the BotConfig.notifications.telegram section."""
    tg = cfg.notifications.telegram
    return TelegramNotifier(
        bot_token=tg.bot_token,
        chat_id=tg.chat_id,
        enabled=tg.enabled,
    )
