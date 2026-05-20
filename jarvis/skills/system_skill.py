"""System info skill - reports basic info about the host machine."""
from __future__ import annotations

import os
import platform
import socket
from typing import Any, Dict, Optional

from .base import Skill


class SystemInfoSkill(Skill):
    name = "system_info"
    description = "Return basic info about the host system: OS, hostname, Python version, user."
    parameters = []

    def execute(self, **kwargs: Any) -> str:
        user = os.environ.get("USER") or os.environ.get("USERNAME") or "unknown"
        return (
            f"Host: {socket.gethostname()}\n"
            f"OS: {platform.system()} {platform.release()} ({platform.machine()})\n"
            f"Python: {platform.python_version()}\n"
            f"User: {user}"
        )

    def match(self, text: str) -> Optional[Dict[str, Any]]:
        t = text.lower()
        keywords = ("system info", "host info", "machine info", "what os", "which os")
        if any(k in t for k in keywords):
            return {}
        return None
