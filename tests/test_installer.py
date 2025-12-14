"""Tests for the core/installer module."""

from unittest.mock import patch, MagicMock


from lola.targets import get_registry, copy_module_to_local, install_to_assistant
from lola.models import Module, InstallationRegistry


class TestGetRegistry:
    """Tests for get_registry()."""

    def test_returns_registry(self, tmp_path):
        """Returns an InstallationRegistry."""
        with patch("lola.config.INSTALLED_FILE", tmp_path / "installed.yml"):
            registry = get_registry()

        assert isinstance(registry, InstallationRegistry)


class TestCopyModuleToLocal:
    """Tests for copy_module_to_local()."""

    def test_copies_module(self, tmp_path):
        """Copies module to local modules path."""
        # Create source module
        source_dir = tmp_path / "source" / "mymodule"
        source_dir.mkdir(parents=True)
        (source_dir / "SKILL.md").write_text("# My Skill")
        (source_dir / "subdir").mkdir()
        (source_dir / "subdir" / "file.txt").write_text("content")

        module = Module(name="mymodule", path=source_dir)

        local_modules = tmp_path / "local" / ".lola" / "modules"

        result = copy_module_to_local(module, local_modules)

        assert result == local_modules / "mymodule"
        assert result.exists()
        assert (result / "SKILL.md").read_text() == "# My Skill"
        assert (result / "subdir" / "file.txt").read_text() == "content"

    def test_same_path_returns_unchanged(self, tmp_path):
        """Returns same path if source and dest are identical."""
        module_dir = tmp_path / ".lola" / "modules" / "mymodule"
        module_dir.mkdir(parents=True)
        (module_dir / "SKILL.md").write_text("# My Skill")

        module = Module(name="mymodule", path=module_dir)

        local_modules = tmp_path / ".lola" / "modules"

        result = copy_module_to_local(module, local_modules)

        assert result == module_dir

    def test_overwrites_existing(self, tmp_path):
        """Overwrites existing module directory."""
        # Create source module
        source_dir = tmp_path / "source" / "mymodule"
        source_dir.mkdir(parents=True)
        (source_dir / "new.txt").write_text("new content")

        module = Module(name="mymodule", path=source_dir)

        local_modules = tmp_path / "local" / ".lola" / "modules"
        local_modules.mkdir(parents=True)

        # Create existing directory
        existing = local_modules / "mymodule"
        existing.mkdir()
        (existing / "old.txt").write_text("old content")

        result = copy_module_to_local(module, local_modules)

        assert (result / "new.txt").exists()
        assert not (result / "old.txt").exists()

    def test_removes_existing_symlink(self, tmp_path):
        """Removes existing symlink before copying."""
        # Create source module
        source_dir = tmp_path / "source" / "mymodule"
        source_dir.mkdir(parents=True)
        (source_dir / "SKILL.md").write_text("# My Skill")

        module = Module(name="mymodule", path=source_dir)

        local_modules = tmp_path / "local" / ".lola" / "modules"
        local_modules.mkdir(parents=True)

        # Create a symlink
        target = tmp_path / "target"
        target.mkdir()
        symlink = local_modules / "mymodule"
        symlink.symlink_to(target)

        result = copy_module_to_local(module, local_modules)

        assert not result.is_symlink()
        assert result.is_dir()
        assert (result / "SKILL.md").exists()


class TestInstallToAssistant:
    """Tests for install_to_assistant()."""

    def setup_method(self):
        """Set up test fixtures."""
        self.console_mock = MagicMock()

    def create_test_module(self, tmp_path, name="testmod", skills=None, commands=None):
        """Helper to create a test module structure."""
        module_dir = tmp_path / "modules" / name
        module_dir.mkdir(parents=True)

        # Create skill directories (auto-discovered via SKILL.md)
        if skills:
            skills_root = module_dir / "skills"
            skills_root.mkdir()
            for skill in skills:
                skill_dir = skills_root / skill
                skill_dir.mkdir()
                (skill_dir / "SKILL.md").write_text(f"""---
description: {skill} description
---

# {skill}

Content.
""")

        # Create command files (auto-discovered from commands/*.md)
        if commands:
            commands_dir = module_dir / "commands"
            commands_dir.mkdir()
            for cmd in commands:
                (commands_dir / f"{cmd}.md").write_text(f"""---
description: {cmd} command
---

Do {cmd}.
""")

        return Module.from_path(module_dir)

    def test_install_claude_code_project_skills(self, tmp_path):
        """Install skills to claude-code project scope."""
        module = self.create_test_module(tmp_path, skills=["skill1"])

        local_modules = tmp_path / ".lola" / "modules"
        registry = InstallationRegistry(tmp_path / "installed.yml")
        skill_dest = tmp_path / "skills"

        with (
            patch("lola.targets.console", self.console_mock),
            patch(
                "lola.targets.get_assistant_skill_path", return_value=skill_dest
            ),
            patch("lola.targets.get_assistant_command_path", return_value=None),
        ):
            count = install_to_assistant(
                module=module,
                assistant="claude-code",
                scope="project",
                project_path=str(tmp_path),
                local_modules=local_modules,
                registry=registry,
            )

        assert count == 1
        # Check skill was installed
        assert (skill_dest / "testmod-skill1" / "SKILL.md").exists()

    def test_install_claude_code_commands(self, tmp_path):
        """Install commands to claude-code."""
        module = self.create_test_module(tmp_path, commands=["cmd1"])

        local_modules = tmp_path / ".lola" / "modules"
        registry = InstallationRegistry(tmp_path / "installed.yml")
        command_dest = tmp_path / "commands"

        with (
            patch("lola.targets.console", self.console_mock),
            patch("lola.targets.get_assistant_skill_path", return_value=None),
            patch(
                "lola.targets.get_assistant_command_path",
                return_value=command_dest,
            ),
        ):
            count = install_to_assistant(
                module=module,
                assistant="claude-code",
                scope="project",
                project_path=str(tmp_path),
                local_modules=local_modules,
                registry=registry,
            )

        assert count == 1
        # Check command was installed
        assert (command_dest / "testmod-cmd1.md").exists()

    def test_install_records_installation(self, tmp_path):
        """Installation is recorded in registry."""
        module = self.create_test_module(tmp_path, skills=["skill1"], commands=["cmd1"])

        local_modules = tmp_path / ".lola" / "modules"
        registry = InstallationRegistry(tmp_path / "installed.yml")
        skill_dest = tmp_path / "skills"
        command_dest = tmp_path / "commands"

        with (
            patch("lola.targets.console", self.console_mock),
            patch(
                "lola.targets.get_assistant_skill_path", return_value=skill_dest
            ),
            patch(
                "lola.targets.get_assistant_command_path",
                return_value=command_dest,
            ),
        ):
            install_to_assistant(
                module=module,
                assistant="claude-code",
                scope="project",
                project_path=str(tmp_path),
                local_modules=local_modules,
                registry=registry,
            )

        # Check registry
        installations = registry.find("testmod")
        assert len(installations) == 1
        assert installations[0].assistant == "claude-code"
        assert installations[0].scope == "project"
        assert "testmod-skill1" in installations[0].skills
        assert "cmd1" in installations[0].commands

    # Note: test_install_missing_skill_source and test_install_missing_command_source
    # were removed because with auto-discovery, skills and commands are only
    # discovered if they actually exist. There's no manifest to list non-existent items.
