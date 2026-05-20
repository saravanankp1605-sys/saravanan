"""JARVIS - a modular AI assistant.

Public API:
    Assistant         - main orchestrator (REPL loop)
    build_brain(name) - factory for the LLM "brain"
    default_skills()  - returns the built-in skill set
    VoiceIO           - optional speech I/O
"""
from __future__ import annotations

__version__ = "0.1.0"

from .assistant import Assistant
from .brain import build_brain
from .skills import default_skills
from .voice import VoiceIO

__all__ = ["Assistant", "build_brain", "default_skills", "VoiceIO"]
