from pathlib import Path

SKILL = Path(__file__).parents[1] / "skills" / "mathfmt"


def test_skill_layout_and_metadata() -> None:
    skill_text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    agent_text = (SKILL / "agents" / "openai.yaml").read_text(encoding="utf-8")
    reference = SKILL / "references" / "paper-notation.md"

    assert skill_text.startswith("---\nname: mathfmt\ndescription: ")
    assert "[TODO" not in skill_text
    assert "display_name: \"MathFmt\"" in agent_text
    assert "$mathfmt" in agent_text
    assert reference.is_file()
