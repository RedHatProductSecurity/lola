"""Tests for converter modules."""

from lola.converters import (
    parse_skill_frontmatter,
    skill_to_claude,
    skill_to_cursor_mdc,
)
from lola.command_converters import (
    parse_command_frontmatter,
    has_positional_args,
    convert_to_gemini_args,
    command_to_gemini,
    get_command_filename,
)


class TestSkillConverters:
    """Tests for skill conversion functions."""

    def test_parse_skill_frontmatter(self):
        """Parse SKILL.md frontmatter."""
        content = """---
name: myskill
description: My skill description
---

# My Skill

Content here.
"""
        metadata, body = parse_skill_frontmatter(content)
        assert metadata["name"] == "myskill"
        assert metadata["description"] == "My skill description"
        assert "# My Skill" in body

    def test_skill_to_claude(self, tmp_path):
        """Convert skill to Claude format (passthrough)."""
        skill_dir = tmp_path / "myskill"
        skill_dir.mkdir()
        skill_content = """---
name: myskill
description: Test skill
---

# My Skill

Do things.
"""
        (skill_dir / "SKILL.md").write_text(skill_content)

        result = skill_to_claude(skill_dir)

        assert result == skill_content

    def test_skill_to_cursor_mdc(self, tmp_path):
        """Convert skill to Cursor MDC format."""
        skill_dir = tmp_path / "myskill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("""---
name: myskill
description: Test skill for cursor
---

# My Skill

Content.
""")

        result = skill_to_cursor_mdc(skill_dir, ".lola/modules/myskill")

        assert result is not None
        assert "description: Test skill for cursor" in result
        assert "globs:" in result
        assert "alwaysApply: false" in result


class TestCommandConverters:
    """Tests for command conversion functions."""

    def test_parse_command_frontmatter(self):
        """Parse command frontmatter."""
        content = """---
description: My command
argument-hint: "<file>"
---

Do the thing.
"""
        metadata, body = parse_command_frontmatter(content)
        assert metadata["description"] == "My command"
        assert metadata["argument-hint"] == "<file>"
        assert "Do the thing." in body

    def test_has_positional_args(self):
        """Detect positional arguments."""
        assert has_positional_args("Use $1 and $2") is True
        assert has_positional_args("Use $ARGUMENTS") is False
        assert has_positional_args("No args here") is False

    def test_convert_to_gemini_args(self):
        """Convert argument placeholders for Gemini."""
        content = "Use $ARGUMENTS for input."
        result = convert_to_gemini_args(content)
        assert "{{args}}" in result
        assert "$ARGUMENTS" not in result

    def test_convert_to_gemini_args_positional(self):
        """Convert content with positional args for Gemini."""
        content = "First arg: $1, second: $2"
        result = convert_to_gemini_args(content)
        assert result.startswith("Arguments: {{args}}")
        assert "$1" in result  # Positional args kept for LLM inference

    def test_command_to_gemini(self, tmp_path):
        """Convert command to Gemini TOML format."""
        cmd_file = tmp_path / "test.md"
        cmd_file.write_text("""---
description: Test command
---

Do something with $ARGUMENTS.
""")

        result = command_to_gemini(cmd_file)

        assert result is not None
        assert 'description = "Test command"' in result
        assert 'prompt = """' in result
        assert "{{args}}" in result

    def test_get_command_filename(self):
        """Get correct filename for each assistant."""
        assert get_command_filename("claude-code", "mod", "cmd") == "mod-cmd.md"
        assert get_command_filename("cursor", "mod", "cmd") == "mod-cmd.md"
        assert get_command_filename("gemini-cli", "mod", "cmd") == "mod-cmd.toml"
