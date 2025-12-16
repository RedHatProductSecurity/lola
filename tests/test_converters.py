"""Tests for converter modules."""

from lola.frontmatter import parse as parse_frontmatter, has_positional_args
from lola.targets import (
    TARGETS,
    get_target,
    _convert_to_gemini_args,
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
        metadata, body = parse_frontmatter(content)
        assert metadata["name"] == "myskill"
        assert metadata["description"] == "My skill description"
        assert "# My Skill" in body

    def test_claude_skill_generation(self, tmp_path):
        """Generate skill for Claude Code."""
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

        target = get_target("claude-code")
        dest = tmp_path / "dest"
        success = target.generate_skill(skill_dir, dest, "test-myskill")

        assert success
        assert (dest / "test-myskill" / "SKILL.md").exists()
        result = (dest / "test-myskill" / "SKILL.md").read_text()
        assert result == skill_content

    def test_cursor_skill_generation(self, tmp_path):
        """Generate skill for Cursor (MDC format)."""
        skill_dir = tmp_path / "myskill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("""---
name: myskill
description: Test skill for cursor
---

# My Skill

Content.
""")

        target = get_target("cursor")
        dest = tmp_path / "dest"
        success = target.generate_skill(skill_dir, dest, "test-myskill", str(tmp_path))

        assert success
        mdc_file = dest / "test-myskill.mdc"
        assert mdc_file.exists()
        result = mdc_file.read_text()
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
        metadata, body = parse_frontmatter(content)
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
        result = _convert_to_gemini_args(content)
        assert "{{args}}" in result
        assert "$ARGUMENTS" not in result

    def test_convert_to_gemini_args_positional(self):
        """Convert content with positional args for Gemini."""
        content = "First arg: $1, second: $2"
        result = _convert_to_gemini_args(content)
        assert result.startswith("Arguments: {{args}}")
        assert "$1" in result  # Positional args kept for LLM inference

    def test_gemini_command_generation(self, tmp_path):
        """Generate command for Gemini (TOML format)."""
        cmd_file = tmp_path / "test.md"
        cmd_file.write_text("""---
description: Test command
---

Do something with $ARGUMENTS.
""")

        target = get_target("gemini-cli")
        dest = tmp_path / "dest"
        success = target.generate_command(cmd_file, dest, "test", "mymodule")

        assert success
        toml_file = dest / "mymodule-test.toml"
        assert toml_file.exists()
        result = toml_file.read_text()
        assert 'description = "Test command"' in result
        assert 'prompt = """' in result
        assert "{{args}}" in result

    def test_get_command_filename(self):
        """Get correct filename for each assistant."""
        claude = get_target("claude-code")
        cursor = get_target("cursor")
        gemini = get_target("gemini-cli")

        assert claude.get_command_filename("mod", "cmd") == "mod-cmd.md"
        assert cursor.get_command_filename("mod", "cmd") == "mod-cmd.md"
        assert gemini.get_command_filename("mod", "cmd") == "mod-cmd.toml"
