from pathlib import Path

import pytest
import yaml

from src.config_writer import ConfigWriteError, compute_etag, read_yaml_bytes, write_raw_config_atomic


def _raw_config() -> dict:
    return {
        "models": [],
        "manager_service_index": 0,
        "agents": [
            {
                "name": "Host",
                "description": "主持人",
                "instructions": "host",
                "model": "host-model",
                "api_key": "${OPENAI_API_KEY:-}",
            },
            {
                "name": "Architect",
                "description": "架构师",
                "instructions": "arch",
                "model": "arch-model",
                "api_key": "${OPENAI_API_KEY:-}",
            },
            {
                "name": "Pragmatist",
                "description": "落地派",
                "instructions": "pm",
                "model": "pm-model",
                "api_key": "${OPENAI_API_KEY:-}",
            },
            {
                "name": "Challenger",
                "description": "挑战者",
                "instructions": "risk",
                "model": "risk-model",
                "api_key": "${OPENAI_API_KEY:-}",
            },
        ],
        "default_preset": "default",
        "presets": {
            "default": {
                "label": "默认",
                "description": "默认讨论组",
                "agents": ["Architect", "Pragmatist", "Challenger"],
            }
        },
    }


def test_write_raw_config_atomic_updates_file_and_etag(tmp_path: Path):
    path = tmp_path / "agents.yaml"
    raw = _raw_config()
    path.write_text(yaml.safe_dump(raw, allow_unicode=True, sort_keys=False), encoding="utf-8")

    raw["discussion"] = {"enabled": True, "max_rounds": 4}
    etag = write_raw_config_atomic(path, raw)

    assert etag == compute_etag(read_yaml_bytes(path))
    assert yaml.safe_load(path.read_text(encoding="utf-8"))["discussion"]["max_rounds"] == 4


def test_write_raw_config_atomic_keeps_original_on_schema_failure(tmp_path: Path):
    path = tmp_path / "agents.yaml"
    original = _raw_config()
    path.write_text(yaml.safe_dump(original, allow_unicode=True, sort_keys=False), encoding="utf-8")
    before = path.read_text(encoding="utf-8")

    broken = dict(original)
    broken["agents"] = [{"name": "Host"}]
    with pytest.raises(ConfigWriteError):
        write_raw_config_atomic(path, broken)

    assert path.read_text(encoding="utf-8") == before
