from app.config import Config
from app.core.persona import build_system_instruction, greeting_prompt


def _config(tmp_path) -> Config:
    return Config(path=tmp_path / "config.json")


def test_prompt_has_identity_and_level(tmp_path):
    config = _config(tmp_path)
    config.set("Alvin", "persona", "user_name")
    config.set("B2", "persona", "cefr_level")

    prompt = build_system_instruction(config, "free_talk")

    assert "You are Rey" in prompt
    assert "Alvin" in prompt
    assert "B2" in prompt
    assert "free_talk" in prompt


def test_tools_are_disabled_by_default(tmp_path):
    prompt = build_system_instruction(_config(tmp_path), "free_talk")
    assert "not connected in this build" in prompt
    assert "save_mistake" not in prompt


def test_tools_can_be_enabled(tmp_path):
    prompt = build_system_instruction(_config(tmp_path), "free_talk", tools_enabled=True)
    assert "save_mistake" in prompt
    assert "not connected in this build" not in prompt


def test_roleplay_gets_scenario_block(tmp_path):
    prompt = build_system_instruction(_config(tmp_path), "roleplay")
    assert "Invent a simple everyday scene" in prompt
    assert "No roleplay scenario is selected" not in prompt


def test_empty_user_name_falls_back(tmp_path):
    prompt = build_system_instruction(_config(tmp_path), "drill")
    assert "to the user through a voice chat app" in prompt


def test_greeting_mentions_name_once(tmp_path):
    assert "Rey" not in greeting_prompt()
    assert "Alvin" in greeting_prompt("Alvin")
    assert "one simple" in greeting_prompt()
