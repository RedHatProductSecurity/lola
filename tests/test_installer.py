"""Tests for the core/installer module."""

from pathlib import Path
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

        module = Module(name="mymodule", path=source_dir, content_path=source_dir)

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

        module = Module(name="mymodule", path=module_dir, content_path=module_dir)

        local_modules = tmp_path / ".lola" / "modules"

        result = copy_module_to_local(module, local_modules)

        assert result == module_dir

    def test_overwrites_existing(self, tmp_path):
        """Overwrites existing module directory."""
        # Create source module
        source_dir = tmp_path / "source" / "mymodule"
        source_dir.mkdir(parents=True)
        (source_dir / "new.txt").write_text("new content")

        module = Module(name="mymodule", path=source_dir, content_path=source_dir)

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

        module = Module(name="mymodule", path=source_dir, content_path=source_dir)

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

        # Create mock target
        mock_target = MagicMock()
        mock_target.name = "claude-code"
        mock_target.supports_agents = True
        mock_target.uses_managed_section = False  # Not a managed section target
        mock_target.get_skill_path.return_value = skill_dest
        mock_target.get_command_path.return_value = None
        mock_target.get_agent_path.return_value = None
        mock_target.generate_skill.return_value = True
        mock_target.generate_command.return_value = True
        mock_target.generate_agent.return_value = True

        with (
            patch("lola.targets.console", self.console_mock),
            patch("lola.targets.get_target", return_value=mock_target),
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
        # Check generate_skill was called
        mock_target.generate_skill.assert_called_once()

    def test_install_claude_code_commands(self, tmp_path):
        """Install commands to claude-code."""
        module = self.create_test_module(tmp_path, commands=["cmd1"])

        local_modules = tmp_path / ".lola" / "modules"
        registry = InstallationRegistry(tmp_path / "installed.yml")
        command_dest = tmp_path / "commands"

        # Create mock target
        mock_target = MagicMock()
        mock_target.name = "claude-code"
        mock_target.supports_agents = True
        mock_target.uses_managed_section = False  # Not a managed section target
        mock_target.get_skill_path.return_value = None
        mock_target.get_command_path.return_value = command_dest
        mock_target.get_agent_path.return_value = None
        mock_target.generate_skill.return_value = True
        mock_target.generate_command.return_value = True
        mock_target.generate_agent.return_value = True

        with (
            patch("lola.targets.console", self.console_mock),
            patch("lola.targets.get_target", return_value=mock_target),
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
        # Check generate_command was called
        mock_target.generate_command.assert_called_once()

    def test_install_records_installation(self, tmp_path):
        """Installation is recorded in registry."""
        module = self.create_test_module(tmp_path, skills=["skill1"], commands=["cmd1"])

        local_modules = tmp_path / ".lola" / "modules"
        registry = InstallationRegistry(tmp_path / "installed.yml")
        skill_dest = tmp_path / "skills"
        command_dest = tmp_path / "commands"

        # Create mock target
        mock_target = MagicMock()
        mock_target.name = "claude-code"
        mock_target.supports_agents = True
        mock_target.uses_managed_section = False  # Not a managed section target
        mock_target.get_skill_path.return_value = skill_dest
        mock_target.get_command_path.return_value = command_dest
        mock_target.get_agent_path.return_value = None
        mock_target.generate_skill.return_value = True
        mock_target.generate_command.return_value = True
        mock_target.generate_agent.return_value = True

        with (
            patch("lola.targets.console", self.console_mock),
            patch("lola.targets.get_target", return_value=mock_target),
        ):
            install_to_assistant(
                module=module,
                assistant="claude-code",
                scope="project",
                project_path=str(tmp_path),
                local_modules=local_modules,
                registry=registry,
            )

        # Check registry (skill names are now unprefixed)
        installations = registry.find("testmod")
        assert len(installations) == 1
        assert installations[0].assistant == "claude-code"
        assert installations[0].scope == "project"
        assert "skill1" in installations[0].skills
        assert "cmd1" in installations[0].commands

    # Note: test_install_missing_skill_source and test_install_missing_command_source
    # were removed because with auto-discovery, skills and commands are only
    # discovered if they actually exist. There's no manifest to list non-existent items.


class TestGenerationIsIdempotent:
    """Tests for _generation_is_idempotent() and idempotent re-installs."""

    def test_returns_true_when_identical(self, tmp_path):
        from lola.targets.install import _generation_is_idempotent

        real = tmp_path / "dest"
        (real / "sub").mkdir(parents=True)
        (real / "sub" / "f.txt").write_text("same")

        def generate(d):
            (d / "sub").mkdir(parents=True)
            (d / "sub" / "f.txt").write_text("same")
            return True

        assert _generation_is_idempotent(generate, real) is True

    def test_returns_false_when_content_differs(self, tmp_path):
        from lola.targets.install import _generation_is_idempotent

        real = tmp_path / "dest"
        real.mkdir()
        (real / "f.txt").write_text("old")

        def generate(d):
            (d / "f.txt").write_text("new")
            return True

        assert _generation_is_idempotent(generate, real) is False

    def test_returns_false_when_file_missing(self, tmp_path):
        from lola.targets.install import _generation_is_idempotent

        real = tmp_path / "dest"
        real.mkdir()

        def generate(d):
            (d / "f.txt").write_text("data")
            return True

        assert _generation_is_idempotent(generate, real) is False

    def test_returns_false_when_generate_fails(self, tmp_path):
        from lola.targets.install import _generation_is_idempotent

        real = tmp_path / "dest"
        real.mkdir()
        assert _generation_is_idempotent(lambda d: False, real) is False

    def test_copilot_variants_share_project_skill(self, tmp_path):
        """Installing the same skill to copilot-cli then copilot-vscode at
        project scope must not fail on the shared .github/ files."""
        from lola.targets.install import _install_skills
        from lola.targets.copilot import CopilotCliTarget, CopilotVSCodeTarget

        module_dir = tmp_path / "modules" / "testmod"
        skill_dir = module_dir / "skills" / "skill1"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(
            "---\ndescription: skill1 description\n---\n\n# skill1\n\nContent.\n"
        )
        module = Module.from_path(module_dir)
        assert module is not None

        cli = CopilotCliTarget()
        vscode = CopilotVSCodeTarget()

        installed_cli, failed_cli = _install_skills(
            cli, module, module_dir, str(tmp_path), scope="project"
        )
        assert installed_cli == ["skill1"]
        assert failed_cli == []

        # Second target writes byte-identical .github/ files: idempotent no-op.
        installed_vscode, failed_vscode = _install_skills(
            vscode, module, module_dir, str(tmp_path), scope="project"
        )
        assert installed_vscode == ["skill1"]
        assert failed_vscode == []

    def test_returns_false_when_destination_is_symlink(self, tmp_path: Path) -> None:
        """A skill that exists only via a symlink (e.g. a user's manual ln -s
        into a separate checkout) must not be treated as an idempotent
        re-install: the overwrite prompt should apply instead."""
        from lola.targets.install import _generation_is_idempotent

        real = tmp_path / "dest"
        real.mkdir()

        external = tmp_path / "external"
        external.mkdir()
        (external / "f.txt").write_text("same")
        (real / "link").symlink_to(external, target_is_directory=True)

        def generate(d: Path) -> bool:
            (d / "link").mkdir(parents=True)
            (d / "link" / "f.txt").write_text("same")
            return True

        assert _generation_is_idempotent(generate, real) is False

    def test_returns_false_when_base_is_symlink(self, tmp_path: Path) -> None:
        """A symlinked destination root is never treated as idempotent."""
        from lola.targets.install import _generation_is_idempotent

        external = tmp_path / "external"
        external.mkdir()
        (external / "f.txt").write_text("same")
        real = tmp_path / "dest"
        real.symlink_to(external, target_is_directory=True)

        def generate(d: Path) -> bool:
            (d / "f.txt").write_text("same")
            return True

        assert _generation_is_idempotent(generate, real) is False


class TestInstallSkillsSymlink:
    """Skills whose destination is a pre-existing symlink."""

    def _make_module(self, tmp_path: Path, content: str = "new") -> Module:
        module_dir = tmp_path / "mod"
        skill_dir = module_dir / "skills" / "skill1"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(content)
        (skill_dir / "data.txt").write_text("data")
        return Module(
            name="mymod", path=module_dir, content_path=module_dir, skills=["skill1"]
        )

    def test_overwrite_replaces_directory_symlink_with_real_copy(
        self, tmp_path: Path
    ) -> None:
        """Overwriting a skill whose directory is a symlink creates a real
        managed copy instead of writing through the link."""
        from unittest import mock

        from lola.targets.claude_code import ClaudeCodeTarget
        from lola.targets.install import _install_skills

        proj = tmp_path / "proj"
        skills_dir = proj / ".claude" / "skills"
        skills_dir.mkdir(parents=True)

        external = tmp_path / "external"
        external.mkdir()
        (external / "SKILL.md").write_text("old")
        (external / "data.txt").write_text("data")
        link = skills_dir / "skill1"
        link.symlink_to(external, target_is_directory=True)

        module = self._make_module(tmp_path, content="new")
        with (
            mock.patch("lola.targets.install.is_interactive", return_value=True),
            mock.patch("click.confirm", return_value=True),
        ):
            installed, failed = _install_skills(
                ClaudeCodeTarget(), module, module.path, str(proj), "project"
            )

        assert installed == ["skill1"]
        assert failed == []
        assert not link.is_symlink()
        assert (skills_dir / "skill1" / "SKILL.md").is_file()
        assert (skills_dir / "skill1" / "SKILL.md").read_text() == "new"
        # The external target is left untouched.
        assert (external / "SKILL.md").read_text() == "old"

    def test_overwrite_replaces_file_symlink_with_real_copy(
        self, tmp_path: Path
    ) -> None:
        """A skill directory that is a file symlink no longer crashes on
        overwrite; it is replaced with a real directory."""
        from unittest import mock

        from lola.targets.claude_code import ClaudeCodeTarget
        from lola.targets.install import _install_skills

        proj = tmp_path / "proj"
        skills_dir = proj / ".claude" / "skills"
        skills_dir.mkdir(parents=True)

        external = tmp_path / "external"
        external.mkdir()
        (external / "SKILL.md").write_text("old")
        link = skills_dir / "skill1"
        link.symlink_to(external / "SKILL.md")

        module = self._make_module(tmp_path, content="new")
        with (
            mock.patch("lola.targets.install.is_interactive", return_value=True),
            mock.patch("click.confirm", return_value=True),
        ):
            installed, failed = _install_skills(
                ClaudeCodeTarget(), module, module.path, str(proj), "project"
            )

        assert installed == ["skill1"]
        assert failed == []
        assert not link.is_symlink()
        assert (skills_dir / "skill1" / "SKILL.md").read_text() == "new"

    def test_overwrite_replaces_dangling_skill_symlink(self, tmp_path: Path) -> None:
        """A dangling skill symlink still triggers the overwrite path."""
        from unittest import mock

        from lola.targets.claude_code import ClaudeCodeTarget
        from lola.targets.install import _install_skills

        proj = tmp_path / "proj"
        skills_dir = proj / ".claude" / "skills"
        skills_dir.mkdir(parents=True)
        link = skills_dir / "skill1"
        link.symlink_to(tmp_path / "missing-target", target_is_directory=True)

        module = self._make_module(tmp_path, content="new")
        with (
            mock.patch("lola.targets.install.is_interactive", return_value=True),
            mock.patch("click.confirm", return_value=True),
        ):
            installed, failed = _install_skills(
                ClaudeCodeTarget(), module, module.path, str(proj), "project"
            )

        assert installed == ["skill1"]
        assert failed == []
        assert not link.is_symlink()
        assert (link / "SKILL.md").read_text() == "new"

    def test_non_interactive_symlink_conflict_requires_force(
        self, tmp_path: Path, capsys
    ) -> None:
        """Non-interactive installs report the conflict and preserve the link."""
        from unittest import mock

        from lola.targets.claude_code import ClaudeCodeTarget
        from lola.targets.install import _install_skills

        proj = tmp_path / "proj"
        skills_dir = proj / ".claude" / "skills"
        skills_dir.mkdir(parents=True)

        external = tmp_path / "external"
        external.mkdir()
        (external / "SKILL.md").write_text("external")
        link = skills_dir / "skill1"
        link.symlink_to(external, target_is_directory=True)

        module = self._make_module(tmp_path, content="new")
        with (
            mock.patch("lola.targets.install.is_interactive", return_value=False),
            mock.patch("lola.targets.install.click.confirm") as confirm,
        ):
            installed, failed = _install_skills(
                ClaudeCodeTarget(), module, module.path, str(proj), "project"
            )

        assert installed == []
        assert failed == ["skill1"]
        assert link.is_symlink()
        assert (external / "SKILL.md").read_text() == "external"
        confirm.assert_not_called()
        assert "use --force" in capsys.readouterr().out


class TestRunInstallHook:
    """Tests for _run_install_hook()."""

    def test_hook_executes_successfully(self, tmp_path):
        """Hook script executes and returns successfully."""
        from lola.targets.install import _run_install_hook

        module_dir = tmp_path / "mymodule"
        module_dir.mkdir()
        script_dir = module_dir / "scripts"
        script_dir.mkdir()
        script = script_dir / "test.sh"
        script.write_text("#!/bin/bash\necho 'Hook executed'")
        script.chmod(0o755)

        module = Module(name="mymodule", path=module_dir, content_path=module_dir)
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        _run_install_hook(
            "pre-install",
            "scripts/test.sh",
            module,
            module_dir,
            str(project_dir),
            "claude-code",
            "project",
        )

    def test_hook_receives_environment_variables(self, tmp_path):
        """Hook script receives all LOLA_* environment variables."""
        from lola.targets.install import _run_install_hook

        module_dir = tmp_path / "mymodule"
        module_dir.mkdir()
        script_dir = module_dir / "scripts"
        script_dir.mkdir()
        output_file = tmp_path / "env_output.txt"
        script = script_dir / "check_env.sh"
        script.write_text(
            f"""#!/bin/bash
echo "MODULE_NAME=$LOLA_MODULE_NAME" > {output_file}
echo "MODULE_PATH=$LOLA_MODULE_PATH" >> {output_file}
echo "PROJECT_PATH=$LOLA_PROJECT_PATH" >> {output_file}
echo "ASSISTANT=$LOLA_ASSISTANT" >> {output_file}
echo "SCOPE=$LOLA_SCOPE" >> {output_file}
echo "HOOK=$LOLA_HOOK" >> {output_file}
"""
        )
        script.chmod(0o755)

        module = Module(name="mymodule", path=module_dir, content_path=module_dir)
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        _run_install_hook(
            "pre-install",
            "scripts/check_env.sh",
            module,
            module_dir,
            str(project_dir),
            "claude-code",
            "project",
        )

        env_output = output_file.read_text()
        assert "MODULE_NAME=mymodule" in env_output
        assert f"MODULE_PATH={module_dir}" in env_output
        assert f"PROJECT_PATH={project_dir}" in env_output
        assert "ASSISTANT=claude-code" in env_output
        assert "SCOPE=project" in env_output
        assert "HOOK=pre-install" in env_output

    def test_hook_fails_raises_installation_error(self, tmp_path):
        """Hook script failure raises InstallationError."""
        from lola.targets.install import _run_install_hook
        from lola.exceptions import InstallationError
        import pytest

        module_dir = tmp_path / "mymodule"
        module_dir.mkdir()
        script_dir = module_dir / "scripts"
        script_dir.mkdir()
        script = script_dir / "fail.sh"
        script.write_text("#!/bin/bash\nexit 1")
        script.chmod(0o755)

        module = Module(name="mymodule", path=module_dir, content_path=module_dir)
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        with pytest.raises(InstallationError) as exc_info:
            _run_install_hook(
                "pre-install",
                "scripts/fail.sh",
                module,
                module_dir,
                str(project_dir),
                "claude-code",
                "project",
            )

        assert "pre-install script failed" in str(exc_info.value)

    def test_hook_missing_raises_installation_error(self, tmp_path):
        """Missing hook script raises InstallationError."""
        from lola.targets.install import _run_install_hook
        from lola.exceptions import InstallationError
        import pytest

        module_dir = tmp_path / "mymodule"
        module_dir.mkdir()

        module = Module(name="mymodule", path=module_dir, content_path=module_dir)
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        with pytest.raises(InstallationError) as exc_info:
            _run_install_hook(
                "pre-install",
                "scripts/missing.sh",
                module,
                module_dir,
                str(project_dir),
                "claude-code",
                "project",
            )

        assert "script not found" in str(exc_info.value)

    def test_hook_path_traversal_raises_installation_error(self, tmp_path):
        """Security test: Hook with path traversal raises InstallationError."""
        from lola.targets.install import _run_install_hook
        from lola.exceptions import InstallationError
        import pytest

        module_dir = tmp_path / "mymodule"
        module_dir.mkdir()

        malicious_script = tmp_path.parent / "malicious.sh"
        malicious_script.write_text("#!/bin/bash\necho 'pwned'")
        malicious_script.chmod(0o755)

        module = Module(name="mymodule", path=module_dir, content_path=module_dir)
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        with pytest.raises(InstallationError) as exc_info:
            _run_install_hook(
                "pre-install",
                "../../malicious.sh",
                module,
                module_dir,
                str(project_dir),
                "claude-code",
                "project",
            )

        assert "outside module directory" in str(exc_info.value)
