import re
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
CONFIG_DIR = ROOT_DIR / "src" / "config"
ENV_EXAMPLE_PATH = ROOT_DIR / ".env.example"


def test_public_configs_do_not_contain_internal_endpoints_or_literal_keys():
    blocked_fragments = [
        "4dU00PyHvtU2BTeGn9aPHAA07wxChzJ2",
    ]
    for path in CONFIG_DIR.glob("*.yaml"):
        text = path.read_text(encoding="utf-8")
        for fragment in blocked_fragments:
            assert fragment not in text, f"{path} contains blocked fragment {fragment}"


def test_public_configs_use_env_placeholders_for_api_keys():
    for path in CONFIG_DIR.glob("*.yaml"):
        text = path.read_text(encoding="utf-8")
        literal_key_lines = [
            line.strip()
            for line in text.splitlines()
            if line.strip().startswith("api_key:") and "${" not in line
        ]
        assert literal_key_lines == [], f"{path} has literal api_key lines: {literal_key_lines}"


def test_env_example_documents_public_config_placeholders():
    documented_keys = {
        line.split("=", 1)[0].strip()
        for line in ENV_EXAMPLE_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#") and "=" in line
    }
    referenced_keys: set[str] = set()
    for path in CONFIG_DIR.glob("*.yaml"):
        text = path.read_text(encoding="utf-8")
        referenced_keys.update(re.findall(r"\$\{(\w+)(?::-[^}]*)?\}", text))

    missing_keys = sorted(referenced_keys - documented_keys)
    assert missing_keys == [], f".env.example misses referenced config keys: {missing_keys}"
