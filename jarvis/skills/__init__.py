"""Skill registry."""
from __future__ import annotations

from typing import List

from .base import Skill, SkillParameter
from .system_skill import SystemInfoSkill
from .time_skill import TimeSkill
from .trading_skill import RunBacktestSkill, ShowTradingConfigSkill
from .web_skill import WebSearchSkill


def default_skills() -> List[Skill]:
    """Return the list of skills JARVIS comes with out of the box."""
    return [
        TimeSkill(),
        WebSearchSkill(),
        SystemInfoSkill(),
        ShowTradingConfigSkill(),
        RunBacktestSkill(),
    ]


__all__ = [
    "Skill",
    "SkillParameter",
    "TimeSkill",
    "WebSearchSkill",
    "SystemInfoSkill",
    "ShowTradingConfigSkill",
    "RunBacktestSkill",
    "default_skills",
]
