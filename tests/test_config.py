import json

from app.config import Config


def test_defaults_without_user_file(tmp_path):
    config = Config(tmp_path / "config.json")
    assert config.get("persona", "character_name") == "Rey"
    assert config.get("persona", "cefr_level") == "B1"
    assert config.get("voice") == "Kore"
    assert config.path.exists() is False


def test_save_and_reload(tmp_path):
    path = tmp_path / "config.json"
    config = Config(path)
    config.set("Alvin", "persona", "user_name")
    config.set(2, "persona", "spice_level")
    config.save()

    assert path.exists()
    raw = json.loads(path.read_text(encoding="utf-8"))
    assert raw["persona"]["user_name"] == "Alvin"

    reloaded = Config(path)
    assert reloaded.get("persona", "user_name") == "Alvin"
    assert reloaded.get("persona", "spice_level") == 2
    # nilai yang tidak diubah tetap dari default
    assert reloaded.get("voice") == "Kore"


def test_api_key_from_environment(tmp_path, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "  test-key  ")
    config = Config(tmp_path / "config.json")
    assert config.api_key == "  test-key  "
    assert config.has_api_key is True


def test_missing_key_is_empty(tmp_path, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    config = Config(tmp_path / "config.json")
    config.set("", "gemini_api_key")
    assert config.has_api_key is False


def test_get_returns_default_for_missing_path(tmp_path):
    config = Config(tmp_path / "config.json")
    assert config.get("tidak", "ada", default="fallback") == "fallback"
