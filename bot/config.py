"""Configuration loader."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict

import yaml


@dataclass
class MT5Config:
    login: int = 0
    password: str = ""
    server: str = ""
    path: str = ""


@dataclass
class TradingConfig:
    symbol: str = "EURUSD"
    timeframe: str = "M15"
    lot_size: float = 0.01
    magic_number: int = 234000
    deviation: int = 20


@dataclass
class StrategyConfig:
    name: str = "ma_crossover"
    # Generic params dict; specific strategies pick what they need.
    params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RiskConfig:
    dynamic_sizing: bool = True
    risk_per_trade: float = 0.01
    stop_loss_pips: int = 30
    take_profit_pips: int = 60
    max_open_positions: int = 1


@dataclass
class LoggingConfig:
    level: str = "INFO"
    file: str = "logs/bot.log"


@dataclass
class TelegramConfig:
    enabled: bool = False
    bot_token: str = ""
    chat_id: str = ""


@dataclass
class NotificationsConfig:
    telegram: TelegramConfig = field(default_factory=TelegramConfig)


@dataclass
class DataConfig:
    source: str = "synthetic"          # synthetic | csv | yfinance | mt5
    csv_path: str = ""
    yfinance_symbol: str = "EURUSD=X"
    start_date: str = ""
    end_date: str = ""
    interval: str = "15m"              # for yfinance (minutes/hours/days)


@dataclass
class BotConfig:
    mt5: MT5Config = field(default_factory=MT5Config)
    trading: TradingConfig = field(default_factory=TradingConfig)
    strategy: StrategyConfig = field(default_factory=StrategyConfig)
    risk: RiskConfig = field(default_factory=RiskConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    notifications: NotificationsConfig = field(default_factory=NotificationsConfig)
    data: DataConfig = field(default_factory=DataConfig)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BotConfig":
        # Strategy params: everything in the strategy section other than `name`.
        strat_raw = dict(data.get("strategy") or {})
        strat_name = strat_raw.pop("name", "ma_crossover")
        # Allow either nested `params:` or flat keys.
        strat_params = strat_raw.pop("params", None) or strat_raw

        notif_raw = data.get("notifications") or {}
        tg = TelegramConfig(**(notif_raw.get("telegram") or {}))

        return cls(
            mt5=MT5Config(**(data.get("mt5") or {})),
            trading=TradingConfig(**(data.get("trading") or {})),
            strategy=StrategyConfig(name=strat_name, params=strat_params),
            risk=RiskConfig(**(data.get("risk") or {})),
            logging=LoggingConfig(**(data.get("logging") or {})),
            notifications=NotificationsConfig(telegram=tg),
            data=DataConfig(**(data.get("data") or {})),
        )

    @classmethod
    def load(cls, path: str | Path = "config.yaml") -> "BotConfig":
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return cls.from_dict(data)
