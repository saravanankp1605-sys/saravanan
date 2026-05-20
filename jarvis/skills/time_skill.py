"""Time and date skill."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from .base import Skill


class TimeSkill(Skill):
    name = "get_time"
    description = "Returns the current local date and time."
    parameters = []

    def execute(self, **kwargs: Any) -> str:
        now = datetime.now()
        return f"It is {now.strftime('%A, %B %d %Y at %I:%M %p')}."

    def match(self, text: str) -> Optional[Dict[str, Any]]:
        t = text.lower().strip(" ?.!")
        keywords = (
            "what time", "current time", "the time", "what's the time",
            "what day", "what date", "today's date", "what is the date",
        )
        if any(k in t for k in keywords) or t in {"time", "date"}:
            return {}
        return None
