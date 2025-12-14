"""Tests for the core/generator module."""

from lola.targets import (
    get_skill_description,
    generate_claude_skill,
    generate_claude_command,
    generate_gemini_command,
    update_gemini_md,
    remove_gemini_skills,
    GEMINI_START_MARKER,
    GEMINI_END_MARKER,
)


class TestGetSkillDescription:
    """Tests for get_skill_description()"""

    def test_with_description(self, tmp_path):
        """Get description from SKILL.md with frontmatter."""
        skill_dir = tmp_path / "myskill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("""---
name: myskill
description: This is my skill description
---

# My Skill

Content here.
""")
        desc = get_skill_description(skill_dir)
        assert desc == "This is my skill description"

    def test_without_skill_file(self, tmp_path):
        """Get description when SKILL.md doesn't exist."""
        skill_dir = tmp_path / "myskill"
        skill_dir.mkdir()
        desc = get_skill_description(skill_dir)
        assert desc == ""

    def test_without_description(self, tmp_path):
        """Get description when frontmatter has no description."""
        skill_dir = tmp_path / "myskill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("""---
name: myskill
---

Content.
""")
        desc = get_skill_description(skill_dir)
        assert desc == ""


class TestGenerateClaudeSkill:
    """Tests for generate_claude_skill()"""

    def test_generates_skill_md(self, tmp_path):
        """Generate SKILL.md in destination."""
        source = tmp_path / "source" / "myskill"
        source.mkdir(parents=True)
        (source / "SKILL.md").write_text("# My Skill\n\nContent.")

        dest = tmp_path / "dest" / "myskill"

        result = generate_claude_skill(source, dest)

        assert result is True
        assert dest.exists()
        assert (dest / "SKILL.md").exists()
        assert "My Skill" in (dest / "SKILL.md").read_text()

    def test_copies_supporting_files(self, tmp_path):
        """Copy supporting files alongside SKILL.md."""
        source = tmp_path / "source" / "myskill"
        source.mkdir(parents=True)
        (source / "SKILL.md").write_text("# My Skill")
        (source / "helper.py").write_text("# Helper script")
        (source / "scripts").mkdir()
        (source / "scripts" / "run.sh").write_text("#!/bin/bash")

        dest = tmp_path / "dest" / "myskill"

        result = generate_claude_skill(source, dest)

        assert result is True
        assert (dest / "helper.py").exists()
        assert (dest / "scripts" / "run.sh").exists()

    def test_source_not_exists(self, tmp_path):
        """Return False when source doesn't exist."""
        source = tmp_path / "nonexistent"
        dest = tmp_path / "dest"

        result = generate_claude_skill(source, dest)

        assert result is False


class TestGenerateCommands:
    """Tests for command generation functions."""

    def test_generate_claude_command(self, tmp_path):
        """Generate Claude command file."""
        source = tmp_path / "commands" / "test.md"
        source.parent.mkdir(parents=True)
        source.write_text("""---
description: Test command
---

Do something.
""")
        dest_dir = tmp_path / "dest"

        result = generate_claude_command(source, dest_dir, "test", "mymodule")

        assert result is True
        assert (dest_dir / "mymodule-test.md").exists()

    def test_generate_gemini_command(self, tmp_path):
        """Generate Gemini TOML command file."""
        source = tmp_path / "commands" / "test.md"
        source.parent.mkdir(parents=True)
        source.write_text("""---
description: Test command
---

Do something with $ARGUMENTS.
""")
        dest_dir = tmp_path / "dest"

        result = generate_gemini_command(source, dest_dir, "test", "mymodule")

        assert result is True
        toml_file = dest_dir / "mymodule-test.toml"
        assert toml_file.exists()
        content = toml_file.read_text()
        assert 'description = "Test command"' in content
        assert 'prompt = """' in content

    def test_command_source_not_exists(self, tmp_path):
        """Return False when command source doesn't exist."""
        source = tmp_path / "nonexistent.md"
        dest_dir = tmp_path / "dest"

        result = generate_claude_command(source, dest_dir, "test", "mymodule")

        assert result is False


class TestGeminiMdHelpers:
    """Tests for Gemini MD update/remove functions."""

    def test_update_gemini_md_new_file(self, tmp_path):
        """Create new GEMINI.md with skills."""
        gemini_file = tmp_path / "GEMINI.md"
        skills = [
            ("skill1", "Description 1", tmp_path / "skill1"),
            ("skill2", "Description 2", tmp_path / "skill2"),
        ]

        result = update_gemini_md(gemini_file, "mymodule", skills, str(tmp_path))

        assert result is True
        assert gemini_file.exists()
        content = gemini_file.read_text()
        assert GEMINI_START_MARKER in content
        assert GEMINI_END_MARKER in content
        assert "### mymodule" in content
        assert "skill1" in content
        assert "Description 1" in content

    def test_update_gemini_md_existing_file(self, tmp_path):
        """Update existing GEMINI.md with new module."""
        gemini_file = tmp_path / "GEMINI.md"
        gemini_file.write_text(f"""# Project Info

Some existing content.

{GEMINI_START_MARKER}
### existing-module

#### existingskill
**When to use:** Existing skill
**Instructions:** Read `path/SKILL.md` for detailed guidance.

{GEMINI_END_MARKER}
""")
        skills = [("newskill", "New description", tmp_path / "newskill")]

        result = update_gemini_md(gemini_file, "newmodule", skills, str(tmp_path))

        assert result is True
        content = gemini_file.read_text()
        # Existing content preserved
        assert "Some existing content." in content
        assert "### existing-module" in content
        # New module added
        assert "### newmodule" in content
        assert "newskill" in content

    def test_remove_gemini_skills(self, tmp_path):
        """Remove skills from GEMINI.md."""
        gemini_file = tmp_path / "GEMINI.md"
        gemini_file.write_text(f"""{GEMINI_START_MARKER}
### module1

#### skill1
Content for skill1.

### module2

#### skill2
Content for skill2.

{GEMINI_END_MARKER}
""")

        result = remove_gemini_skills(gemini_file, "module1")

        assert result is True
        content = gemini_file.read_text()
        assert "### module1" not in content
        assert "### module2" in content
        assert "skill2" in content

    def test_remove_gemini_skills_no_file(self, tmp_path):
        """Remove from nonexistent file returns True."""
        gemini_file = tmp_path / "nonexistent.md"

        result = remove_gemini_skills(gemini_file, "anymodule")

        assert result is True
