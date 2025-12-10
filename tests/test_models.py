"""Tests for the models module."""

from pathlib import Path

import pytest
import yaml

from lola.models import (
    Skill,
    Command,
    Module,
    Installation,
    InstallationRegistry,
    validate_skill_frontmatter,
    validate_command_frontmatter,
)


class TestSkill:
    """Tests for Skill dataclass."""

    def test_from_path_with_skill_file(self, tmp_path):
        """Load skill from directory with SKILL.md."""
        skill_dir = tmp_path / "myskill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("""---
name: myskill
description: A test skill
---

Content.
""")
        skill = Skill.from_path(skill_dir)
        assert skill.name == "myskill"
        assert skill.path == skill_dir
        assert skill.description == "A test skill"

    def test_from_path_without_skill_file(self, tmp_path):
        """Load skill from directory without SKILL.md."""
        skill_dir = tmp_path / "myskill"
        skill_dir.mkdir()

        skill = Skill.from_path(skill_dir)
        assert skill.name == "myskill"
        assert skill.description is None


class TestCommand:
    """Tests for Command dataclass."""

    def test_from_path_with_frontmatter(self, tmp_path):
        """Load command from file with frontmatter."""
        cmd_file = tmp_path / "test.md"
        cmd_file.write_text("""---
description: Test command
argument-hint: "<file>"
---

Do something.
""")
        cmd = Command.from_path(cmd_file)
        assert cmd.name == "test"
        assert cmd.description == "Test command"
        assert cmd.argument_hint == "<file>"

    def test_from_path_without_file(self, tmp_path):
        """Load command when file doesn't exist."""
        cmd_file = tmp_path / "nonexistent.md"

        cmd = Command.from_path(cmd_file)
        assert cmd.name == "nonexistent"
        assert cmd.description is None
        assert cmd.argument_hint is None


class TestModule:
    """Tests for Module dataclass."""

    def test_from_path_valid_module(self, tmp_path):
        """Load valid module from path."""
        module_dir = tmp_path / "mymodule"
        module_dir.mkdir()
        lola_dir = module_dir / ".lola"
        lola_dir.mkdir()

        manifest = {
            'type': 'lola/module',
            'version': '1.0.0',
            'description': 'Test module',
            'skills': ['skill1', 'skill2'],
            'commands': ['cmd1'],
        }
        (lola_dir / "module.yml").write_text(yaml.dump(manifest))

        module = Module.from_path(module_dir)
        assert module is not None
        assert module.name == "mymodule"
        assert module.version == "1.0.0"
        assert module.description == "Test module"
        assert module.skills == ['skill1', 'skill2']
        assert module.commands == ['cmd1']

    def test_from_path_no_manifest(self, tmp_path):
        """Return None when no manifest exists."""
        module_dir = tmp_path / "mymodule"
        module_dir.mkdir()

        module = Module.from_path(module_dir)
        assert module is None

    def test_from_path_wrong_type(self, tmp_path):
        """Return None when manifest has wrong type."""
        module_dir = tmp_path / "mymodule"
        module_dir.mkdir()
        lola_dir = module_dir / ".lola"
        lola_dir.mkdir()

        manifest = {'type': 'wrong/type', 'version': '1.0.0'}
        (lola_dir / "module.yml").write_text(yaml.dump(manifest))

        module = Module.from_path(module_dir)
        assert module is None

    def test_get_skill_paths(self, tmp_path):
        """Get full paths to skills."""
        module = Module(
            name="test",
            path=tmp_path,
            skills=['skill1', 'skill2']
        )
        paths = module.get_skill_paths()
        assert len(paths) == 2
        assert paths[0] == tmp_path / "skill1"
        assert paths[1] == tmp_path / "skill2"

    def test_get_command_paths(self, tmp_path):
        """Get full paths to commands."""
        module = Module(
            name="test",
            path=tmp_path,
            commands=['cmd1', 'cmd2']
        )
        paths = module.get_command_paths()
        assert len(paths) == 2
        assert paths[0] == tmp_path / "commands" / "cmd1.md"
        assert paths[1] == tmp_path / "commands" / "cmd2.md"

    def test_validate_valid_module(self, tmp_path):
        """Validate a correctly structured module."""
        module_dir = tmp_path / "mymodule"
        module_dir.mkdir()
        lola_dir = module_dir / ".lola"
        lola_dir.mkdir()

        manifest = {
            'type': 'lola/module',
            'version': '1.0.0',
            'skills': ['skill1'],
            'commands': ['cmd1'],
        }
        (lola_dir / "module.yml").write_text(yaml.dump(manifest))

        # Create skill
        skill_dir = module_dir / "skill1"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("""---
description: A skill
---

Content.
""")

        # Create command
        cmd_dir = module_dir / "commands"
        cmd_dir.mkdir()
        (cmd_dir / "cmd1.md").write_text("""---
description: A command
---

Content.
""")

        module = Module.from_path(module_dir)
        is_valid, errors = module.validate()
        assert is_valid is True
        assert errors == []

    def test_validate_missing_skill(self, tmp_path):
        """Validate module with missing skill directory."""
        module_dir = tmp_path / "mymodule"
        module_dir.mkdir()
        lola_dir = module_dir / ".lola"
        lola_dir.mkdir()

        manifest = {
            'type': 'lola/module',
            'version': '1.0.0',
            'skills': ['nonexistent'],
        }
        (lola_dir / "module.yml").write_text(yaml.dump(manifest))

        module = Module.from_path(module_dir)
        is_valid, errors = module.validate()
        assert is_valid is False
        assert any('not found' in e for e in errors)

    def test_validate_missing_skill_md(self, tmp_path):
        """Validate module with skill directory but no SKILL.md."""
        module_dir = tmp_path / "mymodule"
        module_dir.mkdir()
        lola_dir = module_dir / ".lola"
        lola_dir.mkdir()

        manifest = {
            'type': 'lola/module',
            'version': '1.0.0',
            'skills': ['skill1'],
        }
        (lola_dir / "module.yml").write_text(yaml.dump(manifest))

        skill_dir = module_dir / "skill1"
        skill_dir.mkdir()
        # No SKILL.md file

        module = Module.from_path(module_dir)
        is_valid, errors = module.validate()
        assert is_valid is False
        assert any('SKILL.md' in e for e in errors)


class TestValidateSkillFrontmatter:
    """Tests for validate_skill_frontmatter()."""

    def test_valid_frontmatter(self, tmp_path):
        """Validate valid SKILL.md."""
        skill_file = tmp_path / "SKILL.md"
        skill_file.write_text("""---
name: myskill
description: My skill description
---

Content.
""")
        errors = validate_skill_frontmatter(skill_file)
        assert errors == []

    def test_missing_frontmatter(self, tmp_path):
        """Validate file without frontmatter."""
        skill_file = tmp_path / "SKILL.md"
        skill_file.write_text("# Just content")

        errors = validate_skill_frontmatter(skill_file)
        assert len(errors) == 1
        assert 'Missing YAML frontmatter' in errors[0]

    def test_unclosed_frontmatter(self, tmp_path):
        """Validate file with unclosed frontmatter."""
        skill_file = tmp_path / "SKILL.md"
        skill_file.write_text("""---
description: test
Content without closing.
""")
        errors = validate_skill_frontmatter(skill_file)
        assert len(errors) == 1
        assert 'Unclosed' in errors[0]

    def test_missing_description(self, tmp_path):
        """Validate file without description field."""
        skill_file = tmp_path / "SKILL.md"
        skill_file.write_text("""---
name: myskill
---

Content.
""")
        errors = validate_skill_frontmatter(skill_file)
        assert len(errors) == 1
        assert 'description' in errors[0].lower()


class TestInstallation:
    """Tests for Installation dataclass."""

    def test_to_dict(self):
        """Convert installation to dictionary."""
        inst = Installation(
            module_name="mymodule",
            assistant="claude-code",
            scope="user",
            skills=["skill1"],
            commands=["cmd1"],
        )
        d = inst.to_dict()
        assert d['module'] == "mymodule"
        assert d['assistant'] == "claude-code"
        assert d['scope'] == "user"
        assert d['skills'] == ["skill1"]
        assert d['commands'] == ["cmd1"]
        assert 'project_path' not in d

    def test_to_dict_with_project_path(self):
        """Convert installation with project path to dictionary."""
        inst = Installation(
            module_name="mymodule",
            assistant="cursor",
            scope="project",
            project_path="/path/to/project",
            skills=["skill1"],
        )
        d = inst.to_dict()
        assert d['project_path'] == "/path/to/project"

    def test_from_dict(self):
        """Create installation from dictionary."""
        d = {
            'module': 'mymodule',
            'assistant': 'claude-code',
            'scope': 'user',
            'skills': ['skill1', 'skill2'],
            'commands': ['cmd1'],
        }
        inst = Installation.from_dict(d)
        assert inst.module_name == "mymodule"
        assert inst.assistant == "claude-code"
        assert inst.scope == "user"
        assert inst.skills == ['skill1', 'skill2']
        assert inst.commands == ['cmd1']


class TestInstallationRegistry:
    """Tests for InstallationRegistry."""

    def test_empty_registry(self, tmp_path):
        """Create registry when file doesn't exist."""
        registry_path = tmp_path / "installed.yml"
        registry = InstallationRegistry(registry_path)
        assert registry.all() == []

    def test_add_installation(self, tmp_path):
        """Add installation to registry."""
        registry_path = tmp_path / "installed.yml"
        registry = InstallationRegistry(registry_path)

        inst = Installation(
            module_name="mymodule",
            assistant="claude-code",
            scope="user",
            skills=["skill1"],
        )
        registry.add(inst)

        assert len(registry.all()) == 1
        assert registry_path.exists()

    def test_add_replaces_existing(self, tmp_path):
        """Adding installation with same key replaces existing."""
        registry_path = tmp_path / "installed.yml"
        registry = InstallationRegistry(registry_path)

        inst1 = Installation(
            module_name="mymodule",
            assistant="claude-code",
            scope="user",
            skills=["skill1"],
        )
        registry.add(inst1)

        inst2 = Installation(
            module_name="mymodule",
            assistant="claude-code",
            scope="user",
            skills=["skill1", "skill2"],
        )
        registry.add(inst2)

        all_inst = registry.all()
        assert len(all_inst) == 1
        assert all_inst[0].skills == ["skill1", "skill2"]

    def test_find_by_module(self, tmp_path):
        """Find installations by module name."""
        registry_path = tmp_path / "installed.yml"
        registry = InstallationRegistry(registry_path)

        registry.add(Installation("mod1", "claude-code", "user"))
        registry.add(Installation("mod1", "cursor", "project", "/path"))
        registry.add(Installation("mod2", "claude-code", "user"))

        found = registry.find("mod1")
        assert len(found) == 2

    def test_remove_all_by_module(self, tmp_path):
        """Remove all installations of a module."""
        registry_path = tmp_path / "installed.yml"
        registry = InstallationRegistry(registry_path)

        registry.add(Installation("mod1", "claude-code", "user"))
        registry.add(Installation("mod1", "cursor", "user"))
        registry.add(Installation("mod2", "claude-code", "user"))

        removed = registry.remove("mod1")
        assert len(removed) == 2
        assert len(registry.all()) == 1

    def test_remove_specific_installation(self, tmp_path):
        """Remove specific installation by all criteria."""
        registry_path = tmp_path / "installed.yml"
        registry = InstallationRegistry(registry_path)

        registry.add(Installation("mod1", "claude-code", "user"))
        registry.add(Installation("mod1", "cursor", "user"))

        removed = registry.remove("mod1", assistant="claude-code", scope="user")
        assert len(removed) == 1
        assert len(registry.all()) == 1
        assert registry.all()[0].assistant == "cursor"

    def test_load_existing_registry(self, tmp_path):
        """Load registry from existing file."""
        registry_path = tmp_path / "installed.yml"
        data = {
            'version': '1.0',
            'installations': [
                {'module': 'mod1', 'assistant': 'claude-code', 'scope': 'user', 'skills': ['s1']},
                {'module': 'mod2', 'assistant': 'cursor', 'scope': 'project', 'project_path': '/p', 'skills': []},
            ]
        }
        registry_path.write_text(yaml.dump(data))

        registry = InstallationRegistry(registry_path)
        assert len(registry.all()) == 2
