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
    fast_period: int = 20
    slow_period: int = 50


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
class BotConfig:
    mt5: MT5Config = field(default_factory=MT5Config)
    trading: TradingConfig = field(default_factory=TradingConfig)
    strategy: StrategyConfig = field(default_factory=StrategyConfig)
    risk: RiskConfig = field(default_factory=RiskConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BotConfig":
        return cls(
            mt5=MT5Config(**(data.get("mt5") or {})),
            trading=TradingConfig(**(data.get("trading") or {})),
            strategy=StrategyConfig(**(data.get("strategy") or {})),
            risk=RiskConfig(**(data.get("risk") or {})),
            logging=LoggingConfig(**(data.get("logging") or {})),
        )

    @classmethod
    def load(cls, path: str | Path = "config.yaml") -> "BotConfig":
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return cls.from_dict(data)
