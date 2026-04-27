import json
import time
import pytest
from pathlib import Path
from unittest.mock import patch


@pytest.fixture
def config_file(tmp_path):
    data = {
        "gemini": {
            "script": {"api_key": "sk-script", "model": "gemini-2.5-flash"},
            "media":  {"api_key": "sk-media",  "model": "gemini-2.0-flash-exp"},
            "music":  {"api_key": "sk-music",  "model": "lyria-3-clip-preview"},
        },
        "elevenlabs": {"api_key": "el-key", "voice_id_en": "en-id", "voice_id_vi": "vi-id", "model": "eleven_multilingual_v2"},
        "suno":       {"api_key": "suno-key", "model": "V4_5"},
        "pexels":     {"api_key": "pexels-key"},
    }
    p = tmp_path / "api_keys.json"
    p.write_text(json.dumps(data))
    return p


def _reset_cache():
    import config.api_config as m
    m._cache = {}
    m._cache_time = 0.0


def test_get_config_reads_file(config_file):
    _reset_cache()
    with patch("config.api_config._CONFIG_PATH", config_file):
        from config.api_config import get_config
        cfg = get_config()
    assert cfg["gemini"]["script"]["api_key"] == "sk-script"
    assert cfg["pexels"]["api_key"] == "pexels-key"


def test_get_config_caches(config_file):
    _reset_cache()
    with patch("config.api_config._CONFIG_PATH", config_file):
        from config.api_config import get_config
        cfg1 = get_config()
        # mutate file — should not affect cached result within TTL
        config_file.write_text(json.dumps({"gemini": {}}))
        cfg2 = get_config()
    assert cfg1 is cfg2


def test_get_config_missing_file(tmp_path):
    _reset_cache()
    with patch("config.api_config._CONFIG_PATH", tmp_path / "missing.json"):
        from config.api_config import get_config
        cfg = get_config()
    assert cfg["gemini"]["script"]["api_key"] == ""
    assert cfg["pexels"]["api_key"] == ""


def test_save_config_writes_and_busts_cache(config_file):
    _reset_cache()
    with patch("config.api_config._CONFIG_PATH", config_file):
        from config.api_config import get_config, save_config
        get_config()  # prime cache
        new = {"gemini": {"script": {"api_key": "new-key", "model": "m"}}}
        save_config(new)
        cfg = get_config()
    assert cfg["gemini"]["script"]["api_key"] == "new-key"
    written = json.loads(config_file.read_text())
    assert written["gemini"]["script"]["api_key"] == "new-key"
