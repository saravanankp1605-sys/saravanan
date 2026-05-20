"""Web search skill - uses the DuckDuckGo Instant Answer API (no key required)."""
from __future__ import annotations

import json
import urllib.parse
import urllib.request
from typing import Any, Dict, Optional

from .base import Skill, SkillParameter


_TRIGGERS = (
    "search for ", "search ", "look up ", "lookup ",
    "what is ", "what's ", "who is ", "who's ", "tell me about ",
)


class WebSearchSkill(Skill):
    name = "web_search"
    description = (
        "Search the web (DuckDuckGo) for a topic and return a brief summary. "
        "Use for current events, definitions, or anything you don't know."
    )
    parameters = [
        SkillParameter("query", "string", "What to search for", required=True),
    ]

    def execute(self, **kwargs: Any) -> str:
        query = (kwargs.get("query") or "").strip()
        if not query:
            return "I need something to search for."

        url = (
            "https://api.duckduckgo.com/?q="
            + urllib.parse.quote(query)
            + "&format=json&no_redirect=1&no_html=1"
        )
        req = urllib.request.Request(url, headers={"User-Agent": "jarvis-assistant/0.1"})
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                data = json.loads(r.read().decode("utf-8", errors="replace"))
        except Exception as e:
            return f"Sorry, I couldn't reach the web: {e}"

        abstract = data.get("AbstractText") or data.get("Answer")
        if abstract:
            source = data.get("AbstractSource") or "DuckDuckGo"
            return f"{abstract} (source: {source})"

        related = data.get("RelatedTopics") or []
        for entry in related:
            if isinstance(entry, dict) and entry.get("Text"):
                return entry["Text"]

        definition = data.get("Definition")
        if definition:
            return definition

        return f"I couldn't find a quick summary for '{query}'."

    def match(self, text: str) -> Optional[Dict[str, Any]]:
        low = text.lower().strip()
        for trigger in _TRIGGERS:
            if low.startswith(trigger):
                query = text[len(trigger):].strip().rstrip("?.!")
                if query:
                    return {"query": query}
        return None
