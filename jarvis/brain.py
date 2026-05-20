"""The "brain" of JARVIS - decides how to respond and which skills to invoke.

Two implementations are provided:

  * EchoBrain   - offline, no API key required. Routes to skills via keyword
                  matching (skill.match(text)). Falls back to a help message.
  * OpenAIBrain - uses OpenAI chat completions with tool/function calling.
                  Skills are exposed as tools; the model decides when to call them.

Both share the same `respond(user_input) -> str` interface.
"""
from __future__ import annotations

import json
import os
from typing import List

from .skills.base import Skill


SYSTEM_PROMPT = (
    "You are JARVIS, a concise, helpful, slightly witty AI assistant. "
    "You have access to tools that fetch information or operate the user's "
    "trading bot. Use them when they would help. When you don't need a tool, "
    "answer naturally. Keep replies short unless detail is requested."
)


class Brain:
    """Base class. Subclasses implement `respond`."""

    def __init__(self, skills: List[Skill]) -> None:
        self.skills = {s.name: s for s in skills}

    def respond(self, user_input: str) -> str:  # pragma: no cover - abstract
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Offline brain
# ---------------------------------------------------------------------------

_GREETINGS = {"hi", "hello", "hey", "hey jarvis", "yo", "hi jarvis"}
_IDENTITY = {"who are you", "what are you", "your name"}
_HELP = {"help", "what can you do", "commands", "skills"}


class EchoBrain(Brain):
    """Offline brain: keyword routing to skills, plus a few canned replies."""

    def respond(self, user_input: str) -> str:
        text = user_input.strip()
        if not text:
            return ""
        low = text.lower().strip(" ?.!")

        if low in _GREETINGS:
            return "Hello. How can I help?"
        if any(low.startswith(k) or low == k for k in _IDENTITY):
            return "I am JARVIS, your modular AI assistant."
        if low in _HELP:
            return self._help_text()

        # Keyword route to a skill
        for skill in self.skills.values():
            args = skill.match(text)
            if args is not None:
                try:
                    return skill.execute(**args)
                except Exception as e:  # noqa: BLE001
                    return f"Skill '{skill.name}' failed: {e}"

        return (
            "I'm running in offline mode (no LLM). Try one of these:\n"
            + self._help_text()
        )

    def _help_text(self) -> str:
        lines = ["Available skills:"]
        for s in self.skills.values():
            lines.append(f"  - {s.name}: {s.description}")
        lines.append("")
        lines.append("Examples:")
        lines.append("  what time is it?")
        lines.append("  search for python decorators")
        lines.append("  system info")
        lines.append("  show trading config")
        lines.append("  run a backtest")
        lines.append("Set OPENAI_API_KEY for full conversation.")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# OpenAI brain
# ---------------------------------------------------------------------------

class OpenAIBrain(Brain):
    """LLM-powered brain using OpenAI chat completions with tool calling."""

    def __init__(self, skills: List[Skill], model: str = "gpt-4o-mini") -> None:
        super().__init__(skills)
        try:
            from openai import OpenAI  # type: ignore
        except ImportError as e:
            raise RuntimeError(
                "openai package not installed. Install with: pip install openai"
            ) from e

        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError(
                "OPENAI_API_KEY environment variable is not set. "
                "Either set it, or use --brain echo for offline mode."
            )

        self.model = os.environ.get("OPENAI_MODEL", model)
        self._client = OpenAI(api_key=api_key)
        self._tools = [s.to_openai_tool() for s in self.skills.values()]
        self.history: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]

    def respond(self, user_input: str) -> str:
        self.history.append({"role": "user", "content": user_input})

        # Up to N tool-call rounds, then bail out.
        for _ in range(5):
            resp = self._client.chat.completions.create(
                model=self.model,
                messages=self.history,
                tools=self._tools,
                tool_choice="auto",
            )
            msg = resp.choices[0].message

            # Persist assistant turn (including any tool calls)
            self.history.append(_assistant_msg_to_dict(msg))

            if not msg.tool_calls:
                return msg.content or ""

            # Execute each requested tool and feed results back
            for call in msg.tool_calls:
                fname = call.function.name
                try:
                    fargs = json.loads(call.function.arguments or "{}")
                except json.JSONDecodeError:
                    fargs = {}

                skill = self.skills.get(fname)
                if skill is None:
                    result = f"Unknown skill: {fname}"
                else:
                    try:
                        result = skill.execute(**fargs)
                    except Exception as e:  # noqa: BLE001
                        result = f"Skill '{fname}' raised {type(e).__name__}: {e}"

                self.history.append({
                    "role": "tool",
                    "tool_call_id": call.id,
                    "content": str(result),
                })

        return "I got stuck in a tool-call loop. Try rephrasing your request."


def _assistant_msg_to_dict(msg) -> dict:
    """Serialize an OpenAI ChatCompletionMessage into the format we need to send back."""
    out: dict = {"role": "assistant", "content": msg.content}
    if msg.tool_calls:
        out["tool_calls"] = [
            {
                "id": tc.id,
                "type": "function",
                "function": {
                    "name": tc.function.name,
                    "arguments": tc.function.arguments,
                },
            }
            for tc in msg.tool_calls
        ]
    return out


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def build_brain(name: str, skills: List[Skill]) -> Brain:
    """Build a brain by name. 'auto' picks openai if OPENAI_API_KEY is set, else echo."""
    n = (name or "auto").lower()
    if n == "auto":
        n = "openai" if os.environ.get("OPENAI_API_KEY") else "echo"
    if n == "openai":
        return OpenAIBrain(skills)
    if n == "echo":
        return EchoBrain(skills)
    raise ValueError(f"Unknown brain: {name}. Choose: auto | openai | echo")
