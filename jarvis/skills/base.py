"""Base classes for JARVIS skills.

A skill is a small, self-contained capability the assistant can invoke.
Every skill must:

  * declare a unique `name` and human-readable `description`
  * declare its `parameters` (so the LLM can call it as a tool)
  * implement `execute(**kwargs) -> str`
  * optionally implement `match(text)` so the offline EchoBrain can route to it
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class SkillParameter:
    name: str
    type: str  # "string" | "integer" | "number" | "boolean"
    description: str
    required: bool = True
    enum: Optional[List[str]] = None


class Skill(ABC):
    """Subclass and set `name`, `description`, `parameters`, then implement `execute`."""

    name: str = ""
    description: str = ""
    parameters: List[SkillParameter] = []

    @abstractmethod
    def execute(self, **kwargs: Any) -> str:
        """Run the skill and return a human-readable result string."""

    # ---- LLM tool schema ------------------------------------------------
    def to_openai_tool(self) -> Dict[str, Any]:
        """Return the OpenAI function-calling tool schema for this skill."""
        properties: Dict[str, Any] = {}
        required: List[str] = []
        for p in self.parameters:
            spec: Dict[str, Any] = {"type": p.type, "description": p.description}
            if p.enum:
                spec["enum"] = p.enum
            properties[p.name] = spec
            if p.required:
                required.append(p.name)
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            },
        }

    # ---- offline keyword routing ---------------------------------------
    def match(self, text: str) -> Optional[Dict[str, Any]]:
        """Return kwargs dict if this skill should handle the text, else None.

        The offline EchoBrain uses this to decide which skill to invoke when
        no LLM is available. Override per skill.
        """
        return None
