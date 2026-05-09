"""Launch the Agora web server."""

import copy
import logging
import os
from typing import Any

import uvicorn
from uvicorn.config import LOGGING_CONFIG


def _log_level_name() -> str:
    level = os.getenv("AGORA_LOG_LEVEL", "INFO").upper()
    return level if level in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"} else "INFO"


def _build_log_config() -> dict[str, Any]:
    level = _log_level_name()
    config = copy.deepcopy(LOGGING_CONFIG)
    config["disable_existing_loggers"] = False
    config["formatters"]["default"]["fmt"] = "%(asctime)s %(levelprefix)s [%(name)s] %(message)s"
    config["formatters"]["access"]["fmt"] = (
        '%(asctime)s %(levelprefix)s [%(name)s] %(client_addr)s - "%(request_line)s" %(status_code)s'
    )
    config["loggers"]["src"] = {
        "handlers": ["default"],
        "level": level,
        "propagate": False,
    }
    config["loggers"]["watchfiles"] = {
        "handlers": ["default"],
        "level": "WARNING",
        "propagate": False,
    }
    return config


def main() -> None:
    level = _log_level_name()
    logging.basicConfig(
        level=getattr(logging, level),
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        force=True,
    )
    logging.getLogger("src").setLevel(level)
    logging.getLogger(__name__).info("agora web starting log_level=%s", level)

    uvicorn.run(
        "src.web_server:app",
        host="0.0.0.0",
        port=8001,
        reload=True,
        reload_dirs=["src"],
        log_level=level.lower(),
        log_config=_build_log_config(),
    )
