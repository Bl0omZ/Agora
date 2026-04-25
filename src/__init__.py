"""Agent Discussion backend package."""

from __future__ import annotations

import logging
import os

_LEVEL = os.getenv("AGENT_DISCUSSION_LOG_LEVEL", "INFO").upper()
logging.getLogger(__name__).setLevel(
    _LEVEL if _LEVEL in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"} else "INFO"
)
