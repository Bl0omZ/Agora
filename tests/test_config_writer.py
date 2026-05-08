from pathlib import Path

import pytest
import yaml

from src.config_writer import ConfigWriteError, compute_etag, read_yaml_bytes, write_raw_config_atomic
from src.config_writer import _mask_key, to_public_config, update_models
from src.models import AppConfig


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


def test_mask_key_returns_short_preview_only():
    assert _mask_key("sk-a1b2c3d4") == "sk-a1b****c3d4"
    assert _mask_key("12345678") == "12****78"


def test_public_models_include_masked_key_from_environment(monkeypatch):
    monkeypatch.setenv("MODEL_SECRET", "sk-a1b2c3d4")
    config = AppConfig.model_validate({
        "models": [
            {
                "name": "m1",
                "provider": "openai-compatible",
                "base_url": "https://example.test/v1",
                "model_id": "model-1",
                "env_var_name": "MODEL_SECRET",
            }
        ],
        "agents": [
            {
                "name": "Host",
                "description": "host",
                "instructions": "host",
                "model": "m1",
            }
        ],
    })

    public = to_public_config(config)

    assert public.models[0].key_masked == "sk-a1b****c3d4"
    assert "key" not in public.models[0].model_dump()


def test_update_models_writes_key_to_dotenv_without_yaml_leak(monkeypatch, tmp_path: Path):
    dotenv_path = tmp_path / ".env"
    dotenv_path.write_text("KEEP_ME=1\nMODEL_SECRET=old\nMODEL_SECRET=duplicate\n", encoding="utf-8")
    monkeypatch.setattr("src.config_writer.DOTENV_PATH", dotenv_path)
    monkeypatch.delenv("MODEL_SECRET", raising=False)
    raw = _raw_config()

    updated = update_models(raw, [
        {
            "name": "m1",
            "provider": "openai-compatible",
            "base_url": "https://example.test/v1",
            "model_id": "model-1",
            "env_var_name": "MODEL_SECRET",
            "key": "sk-new-secret",
        }
    ])

    assert updated["models"] == [
        {
            "name": "m1",
            "provider": "openai-compatible",
            "base_url": "https://example.test/v1",
            "model_id": "model-1",
            "env_var_name": "MODEL_SECRET",
        }
    ]
    dotenv_text = dotenv_path.read_text(encoding="utf-8")
    assert "KEEP_ME=1" in dotenv_text
    assert dotenv_text.count("MODEL_SECRET=") == 1
    assert "MODEL_SECRET=sk-new-secret" in dotenv_text
    assert "sk-new-secret" not in str(updated)
