"""Tests for the install CLI commands."""

import shutil
from unittest.mock import patch

from lola.cli.install import (
    _fetch_from_marketplace,
    install_cmd,
    uninstall_cmd,
    update_cmd,
    list_installed_cmd,
)
from lola.market.manager import parse_market_ref, parse_ref_suffix
from lola.models import Installation, InstallationRegistry


class TestInstallCmd:
    """Tests for install command."""

    def test_install_help(self, cli_runner):
        """Show install help."""
        result = cli_runner.invoke(install_cmd, ["--help"])
        assert result.exit_code == 0
        assert "Install a module" in result.output

    def test_install_missing_module(self, cli_runner, tmp_path):
        """Fail when module not found."""
        modules_dir = tmp_path / ".lola" / "modules"
        modules_dir.mkdir(parents=True)

        with (
            patch("lola.cli.install.MODULES_DIR", modules_dir),
            patch("lola.cli.install.ensure_lola_dirs"),
        ):
            result = cli_runner.invoke(install_cmd, ["nonexistent"])

        assert result.exit_code == 1
        assert "not found" in result.output

    def test_install_defaults_to_cwd(self, cli_runner, tmp_path):
        """Install uses current directory when no path provided."""
        modules_dir = tmp_path / ".lola" / "modules"
        modules_dir.mkdir(parents=True)

        with (
            patch("lola.cli.install.MODULES_DIR", modules_dir),
            patch("lola.cli.install.ensure_lola_dirs"),
        ):
            result = cli_runner.invoke(install_cmd, ["mymodule"])

        # Should fail because module doesn't exist (not because of missing path)
        assert result.exit_code == 1
        assert "not found" in result.output

    def test_install_project_path_not_exists(self, cli_runner, tmp_path):
        """Fail with guidance when project path doesn't exist."""
        modules_dir = tmp_path / ".lola" / "modules"
        modules_dir.mkdir(parents=True)
        missing_path = tmp_path / "missing"

        with (
            patch("lola.cli.install.MODULES_DIR", modules_dir),
            patch("lola.cli.install.ensure_lola_dirs"),
        ):
            result = cli_runner.invoke(install_cmd, ["mymodule", str(missing_path)])

        assert result.exit_code == 1
        assert f"Project path does not exist: {missing_path}" in result.output
        assert "pass --create to have lola create it" in result.output

    def test_install_create_project_path(self, cli_runner, sample_module, tmp_path):
        """--create creates a missing project path before installing."""
        modules_dir = tmp_path / ".lola" / "modules"
        modules_dir.mkdir(parents=True)
        installed_file = tmp_path / ".lola" / "installed.yml"
        project_path = tmp_path / "new-project"
        shutil.copytree(sample_module, modules_dir / "sample-module")

        with (
            patch("lola.cli.install.MODULES_DIR", modules_dir),
            patch("lola.cli.install.ensure_lola_dirs"),
            patch("lola.cli.install.get_registry") as mock_registry,
            patch("lola.cli.install.get_local_modules_path", return_value=modules_dir),
            patch("lola.cli.install.install_to_assistant", return_value=1),
        ):
            mock_registry.return_value = InstallationRegistry(installed_file)
            result = cli_runner.invoke(
                install_cmd,
                ["sample-module", str(project_path), "-a", "claude-code", "--create"],
            )

        assert result.exit_code == 0, result.output
        assert project_path.is_dir()
        assert "Installing" in result.output

    def test_install_module(self, cli_runner, sample_module, tmp_path):
        """Install a module successfully."""
        modules_dir = tmp_path / ".lola" / "modules"
        modules_dir.mkdir(parents=True)
        installed_file = tmp_path / ".lola" / "installed.yml"

        # Copy sample module to registry
        shutil.copytree(sample_module, modules_dir / "sample-module")

        # Create mock assistant paths
        skill_dest = tmp_path / "skills"
        command_dest = tmp_path / "commands"
        skill_dest.mkdir()
        command_dest.mkdir()

        with (
            patch("lola.cli.install.MODULES_DIR", modules_dir),
            patch("lola.cli.install.ensure_lola_dirs"),
            patch("lola.cli.install.get_registry") as mock_registry,
            patch("lola.cli.install.get_local_modules_path", return_value=modules_dir),
            patch(
                "lola.cli.install.install_to_assistant", return_value=1
            ) as mock_install,
        ):
            mock_registry.return_value = InstallationRegistry(installed_file)
            result = cli_runner.invoke(
                install_cmd, ["sample-module", "-a", "claude-code"]
            )

        assert result.exit_code == 0
        assert "Installing" in result.output
        mock_install.assert_called_once()

    def test_install_with_pre_install_flag(self, cli_runner):
        """CLI --pre-install flag is accepted."""
        result = cli_runner.invoke(install_cmd, ["--help"])
        assert result.exit_code == 0
        assert "--pre-install" in result.output

    def test_install_with_post_install_flag(self, cli_runner):
        """CLI --post-install flag is accepted."""
        result = cli_runner.invoke(install_cmd, ["--help"])
        assert result.exit_code == 0
        assert "--post-install" in result.output

    def test_hook_precedence_cli_over_module(self, tmp_path):
        """CLI flags take precedence over module lola.yaml hooks."""
        from lola.models import Module

        module_dir = tmp_path / "test-module"
        module_dir.mkdir()

        lola_yaml = module_dir / "lola.yaml"
        lola_yaml.write_text(
            """hooks:
  pre-install: scripts/module-pre.sh
"""
        )

        skills_dir = module_dir / "skills" / "test-skill"
        skills_dir.mkdir(parents=True)
        (skills_dir / "SKILL.md").write_text(
            """---
name: test
description: Test skill
---
# Test"""
        )

        module = Module.from_path(module_dir, content_dirname="/")
        assert module is not None
        assert module.pre_install_hook == "scripts/module-pre.sh"


class TestMarketplaceReference:
    """Tests for marketplace reference parsing."""

    def test_parse_market_ref_valid(self):
        """Parse valid marketplace reference."""
        result = parse_market_ref("@official/git-tools")
        assert result is not None
        marketplace_name, module_name = result
        assert marketplace_name == "official"
        assert module_name == "git-tools"

    def test_parse_market_ref_invalid(self):
        """Invalid marketplace reference returns None."""
        assert parse_market_ref("git-tools") is None
        assert parse_market_ref("official/git-tools") is None
        assert parse_market_ref("@official") is None

    def test_fetch_from_marketplace_renames_repository_folder_to_module_name(
        self, tmp_path
    ):
        """Marketplace installs should be stored under the marketplace module name."""
        modules_dir = tmp_path / ".lola" / "modules"
        modules_dir.mkdir(parents=True)
        market_dir = tmp_path / ".lola" / "market"
        cache_dir = tmp_path / ".lola" / "market" / "cache"
        market_dir.mkdir(parents=True)
        cache_dir.mkdir(parents=True)

        source_repo = tmp_path / "anthropics-claude-plugins-official"
        source_repo.mkdir()
        skills_dir = source_repo / "skills" / "module"
        skills_dir.mkdir(parents=True)
        (skills_dir / "SKILL.md").write_text("---\ndescription: x\n---\n")

        (market_dir / "demo.yml").write_text(
            "name: demo\nurl: file:///tmp/demo.yml\nenabled: true\n"
        )
        (cache_dir / "demo.yml").write_text(
            "name: demo\nurl: file:///tmp/demo.yml\nenabled: true\n"
            "modules:\n"
            "  - name: claude-md-management\n"
            "    description: Tools\n"
            "    version: 1.0.0\n"
            f"    repository: {source_repo.as_posix()}\n"
        )

        with (
            patch("lola.cli.install.MODULES_DIR", modules_dir),
            patch("lola.cli.install.MARKET_DIR", market_dir),
            patch("lola.cli.install.CACHE_DIR", cache_dir),
            patch("lola.cli.install.save_source_info"),
        ):
            module_path, module_dict = _fetch_from_marketplace(
                "demo", "claude-md-management"
            )

        assert module_dict["name"] == "claude-md-management"
        assert module_path.name == "claude-md-management"
        assert module_path.exists()
        assert (modules_dir / "claude-md-management").exists()
        assert not (modules_dir / "anthropics-claude-plugins-official").exists()

    def test_fetch_from_marketplace_passes_ref_from_module_dict(self, tmp_path):
        """ref field in marketplace YAML is passed to fetch_module_as_name."""
        modules_dir = tmp_path / ".lola" / "modules"
        modules_dir.mkdir(parents=True)
        market_dir = tmp_path / ".lola" / "market"
        cache_dir = tmp_path / ".lola" / "market" / "cache"
        market_dir.mkdir(parents=True)
        cache_dir.mkdir(parents=True)

        source_repo = tmp_path / "my-skills"
        source_repo.mkdir()

        (market_dir / "demo.yml").write_text(
            "name: demo\nurl: file:///tmp/demo.yml\nenabled: true\n"
        )
        (cache_dir / "demo.yml").write_text(
            "name: demo\nurl: file:///tmp/demo.yml\nenabled: true\n"
            "modules:\n"
            "  - name: pinned-module\n"
            "    description: Pinned\n"
            "    version: 1.0.0\n"
            f"    repository: {source_repo.as_posix()}\n"
            "    ref: v1.2.0\n"
        )

        from unittest.mock import patch

        with (
            patch("lola.cli.install.MODULES_DIR", modules_dir),
            patch("lola.cli.install.MARKET_DIR", market_dir),
            patch("lola.cli.install.CACHE_DIR", cache_dir),
            patch("lola.cli.install.detect_source_type", return_value="git"),
            patch("lola.cli.install.save_source_info") as mock_save,
            patch(
                "lola.cli.install.fetch_module_as_name",
                return_value=modules_dir / "pinned-module",
            ) as mock_fetch,
        ):
            (modules_dir / "pinned-module").mkdir()
            _fetch_from_marketplace("demo", "pinned-module")

        mock_fetch.assert_called_once()
        _, _, _, _, ref_arg = mock_fetch.call_args[0]
        assert ref_arg == "v1.2.0"
        mock_save.assert_called_once()
        assert mock_save.call_args[0][4] == "v1.2.0"

    def test_fetch_from_marketplace_ref_override_wins(self, tmp_path):
        """ref_override takes precedence over the marketplace YAML ref."""
        modules_dir = tmp_path / ".lola" / "modules"
        modules_dir.mkdir(parents=True)
        market_dir = tmp_path / ".lola" / "market"
        cache_dir = tmp_path / ".lola" / "market" / "cache"
        market_dir.mkdir(parents=True)
        cache_dir.mkdir(parents=True)

        source_repo = tmp_path / "my-skills"
        source_repo.mkdir()

        (market_dir / "demo.yml").write_text(
            "name: demo\nurl: file:///tmp/demo.yml\nenabled: true\n"
        )
        (cache_dir / "demo.yml").write_text(
            "name: demo\nurl: file:///tmp/demo.yml\nenabled: true\n"
            "modules:\n"
            "  - name: pinned-module\n"
            "    description: Pinned\n"
            "    version: 1.0.0\n"
            f"    repository: {source_repo.as_posix()}\n"
            "    ref: v1.0.0\n"
        )

        from unittest.mock import patch

        with (
            patch("lola.cli.install.MODULES_DIR", modules_dir),
            patch("lola.cli.install.MARKET_DIR", market_dir),
            patch("lola.cli.install.CACHE_DIR", cache_dir),
            patch("lola.cli.install.detect_source_type", return_value="git"),
            patch("lola.cli.install.save_source_info") as mock_save,
            patch(
                "lola.cli.install.fetch_module_as_name",
                return_value=modules_dir / "pinned-module",
            ) as mock_fetch,
        ):
            (modules_dir / "pinned-module").mkdir()
            _fetch_from_marketplace("demo", "pinned-module", ref_override="develop")

        _, _, _, _, ref_arg = mock_fetch.call_args[0]
        assert ref_arg == "develop"
        assert mock_save.call_args[0][4] == "develop"

    def test_fetch_from_marketplace_no_ref(self, tmp_path):
        """Module dict without ref field passes ref=None (backward compat)."""
        modules_dir = tmp_path / ".lola" / "modules"
        modules_dir.mkdir(parents=True)
        market_dir = tmp_path / ".lola" / "market"
        cache_dir = tmp_path / ".lola" / "market" / "cache"
        market_dir.mkdir(parents=True)
        cache_dir.mkdir(parents=True)

        source_repo = tmp_path / "my-skills"
        source_repo.mkdir()

        (market_dir / "demo.yml").write_text(
            "name: demo\nurl: file:///tmp/demo.yml\nenabled: true\n"
        )
        (cache_dir / "demo.yml").write_text(
            "name: demo\nurl: file:///tmp/demo.yml\nenabled: true\n"
            "modules:\n"
            "  - name: unpinned\n"
            "    description: No ref\n"
            "    version: 1.0.0\n"
            f"    repository: {source_repo.as_posix()}\n"
        )

        from unittest.mock import patch

        with (
            patch("lola.cli.install.MODULES_DIR", modules_dir),
            patch("lola.cli.install.MARKET_DIR", market_dir),
            patch("lola.cli.install.CACHE_DIR", cache_dir),
            patch("lola.cli.install.save_source_info") as mock_save,
            patch(
                "lola.cli.install.fetch_module_as_name",
                return_value=modules_dir / "unpinned",
            ) as mock_fetch,
        ):
            (modules_dir / "unpinned").mkdir()
            _fetch_from_marketplace("demo", "unpinned")

        _, _, _, _, ref_arg = mock_fetch.call_args[0]
        assert ref_arg is None
        assert mock_save.call_args[0][4] is None

    def test_parse_ref_suffix_used_in_module_at_ref_install(self):
        """parse_ref_suffix splits 'module@ref' correctly for lola install."""
        name, ref = parse_ref_suffix("tools@v1.0.0")
        assert name == "tools"
        assert ref == "v1.0.0"

    def test_parse_ref_suffix_marketplace_module_at_ref(self):
        """parse_ref_suffix handles module part after parse_market_ref."""
        # Simulates @marketplace/module@ref → parse_market_ref → ("mkt", "module@ref")
        # then parse_ref_suffix on the module part
        name, ref = parse_ref_suffix("my-module@develop")
        assert name == "my-module"
        assert ref == "develop"

    def test_marketplace_install_lists_catalog_name_and_registry_record(
        self, cli_runner, tmp_path
    ):
        """Marketplace installs should list and persist the catalog module name."""
        modules_dir = tmp_path / ".lola" / "modules"
        modules_dir.mkdir(parents=True)
        installed_file = tmp_path / ".lola" / "installed.yml"
        market_dir = tmp_path / ".lola" / "market"
        cache_dir = tmp_path / ".lola" / "market" / "cache"
        market_dir.mkdir(parents=True)
        cache_dir.mkdir(parents=True)
        project_path = tmp_path / "project"
        project_path.mkdir()

        source_repo = tmp_path / "claude-plugins-official"
        module_content = source_repo / "plugins" / "claude-md-management"
        skills_dir = module_content / "skills" / "claude-md-improver"
        skills_dir.mkdir(parents=True)
        (skills_dir / "SKILL.md").write_text("---\ndescription: x\n---\n")

        (market_dir / "demo.yml").write_text(
            "name: demo\nurl: file:///tmp/demo.yml\nenabled: true\n"
        )
        (cache_dir / "demo.yml").write_text(
            "name: demo\nurl: file:///tmp/demo.yml\nenabled: true\n"
            "modules:\n"
            "  - name: claude-md-management\n"
            "    description: Tools\n"
            "    version: 1.0.0\n"
            f"    repository: {source_repo.as_posix()}\n"
            "    path: plugins/claude-md-management\n"
        )

        with (
            patch("lola.cli.install.MODULES_DIR", modules_dir),
            patch("lola.cli.install.MARKET_DIR", market_dir),
            patch("lola.cli.install.CACHE_DIR", cache_dir),
            patch("lola.cli.install.ensure_lola_dirs"),
            patch(
                "lola.cli.install.get_registry",
                side_effect=lambda: InstallationRegistry(installed_file),
            ),
        ):
            install_result = cli_runner.invoke(
                install_cmd,
                [
                    "@demo/claude-md-management",
                    "-a",
                    "claude-code",
                    str(project_path),
                ],
            )
            list_result = cli_runner.invoke(list_installed_cmd, [])

        assert install_result.exit_code == 0, install_result.output
        assert list_result.exit_code == 0, list_result.output
        assert "claude-md-management" in list_result.output
        assert "claude-plugins-official" not in list_result.output

        registry_records = InstallationRegistry(installed_file).all()
        assert len(registry_records) == 1
        assert registry_records[0].module_name == "claude-md-management"

        installed_text = installed_file.read_text()
        assert "module: claude-md-management" in installed_text
        assert "module: claude-plugins-official" not in installed_text


class TestInstallRefBehavior:
    """Tests for @ref handling edge cases (PR #197 review fixes)."""

    def test_ref_override_on_registered_git_module_refetches(self, tmp_path):
        """install module@ref re-fetches at the new ref when the module is already registered."""
        from unittest.mock import MagicMock, patch

        modules_dir = tmp_path / "modules"
        modules_dir.mkdir()
        mod_path = modules_dir / "my-mod"
        mod_path.mkdir()

        from lola.parsers import save_source_info as _save

        _save(mod_path, "https://example.com/repo.git", "git", ref="v1.0.0")

        new_path = modules_dir / "my-mod"

        with (
            patch("lola.cli.install.MODULES_DIR", modules_dir),
            patch("lola.cli.install.ensure_lola_dirs"),
            patch(
                "lola.cli.install.fetch_module_as_name", return_value=new_path
            ) as mock_fetch,
            patch("lola.cli.install.save_source_info") as mock_save,
            patch("lola.cli.install.get_registry") as mock_registry,
            patch("lola.cli.install.load_registered_module") as mock_load,
            patch("lola.cli.install.default_assistants", return_value=["claude-code"]),
            patch("lola.cli.install.TARGETS", {"claude-code": MagicMock()}),
            patch("lola.cli.install.install_to_assistant", return_value=MagicMock()),
            patch("lola.cli.install.get_target", return_value=MagicMock()),
            patch("lola.cli.install.copy_module_to_local", return_value=MagicMock()),
        ):
            mock_registry.return_value.find.return_value = []
            mock_registry.return_value.add = MagicMock()
            mock_load.return_value = MagicMock(
                skills=[],
                commands=[],
                agents=[],
                mcps=[],
                has_instructions=False,
                validate=lambda: (True, []),
            )
            from click.testing import CliRunner

            result = CliRunner().invoke(
                install_cmd, ["my-mod@v2.0.0", "-a", "claude-code", "-s", "user"]
            )

        assert result.exit_code == 0
        # fetch_module_as_name must have been called with ref="v2.0.0"
        assert mock_fetch.call_args[0][4] == "v2.0.0"
        # save_source_info must persist the new ref
        assert mock_save.call_args[0][4] == "v2.0.0"

    def test_ref_override_on_non_git_registered_module_errors(self, tmp_path):
        """install module@ref errors when the registered module is not git-sourced."""
        from lola.parsers import save_source_info as _save

        modules_dir = tmp_path / "modules"
        modules_dir.mkdir()
        mod_path = modules_dir / "my-mod"
        mod_path.mkdir()
        _save(mod_path, str(tmp_path / "source"), "folder")

        with (
            patch("lola.cli.install.MODULES_DIR", modules_dir),
            patch("lola.cli.install.ensure_lola_dirs"),
        ):
            from click.testing import CliRunner

            result = CliRunner().invoke(
                install_cmd, ["my-mod@v1.0.0", "-a", "claude-code", "-s", "user"]
            )

        assert result.exit_code == 1
        assert "not a git-sourced module" in result.output

    def test_ref_on_non_git_marketplace_repository_errors(self, tmp_path):
        """_fetch_from_marketplace rejects ref when repository is a zip/tar URL."""

        market_dir = tmp_path / "market"
        cache_dir = market_dir / "cache"
        market_dir.mkdir()
        cache_dir.mkdir()

        ref_data = {
            "name": "mkt",
            "url": "https://example.com/mkt.yml",
            "enabled": True,
        }
        import yaml

        (market_dir / "mkt.yml").write_text(yaml.dump(ref_data))

        cache_data = {
            "name": "mkt",
            "url": "https://example.com/mkt.yml",
            "version": "1.0",
            "enabled": True,
            "modules": [
                {
                    "name": "zipmod",
                    "description": "d",
                    "version": "1.0",
                    "repository": "https://example.com/module.zip",
                    "ref": "v1.0.0",
                }
            ],
        }
        (cache_dir / "mkt.yml").write_text(yaml.dump(cache_data))

        with (
            patch("lola.cli.install.MARKET_DIR", market_dir),
            patch("lola.cli.install.CACHE_DIR", cache_dir),
            patch("lola.cli.install.MODULES_DIR", tmp_path / "modules"),
            patch("lola.cli.install.ensure_lola_dirs"),
        ):
            from click.testing import CliRunner

            result = CliRunner().invoke(
                install_cmd, ["@mkt/zipmod", "-a", "claude-code", "-s", "user"]
            )

        assert result.exit_code == 1
        assert "Cannot pin ref" in result.output


class TestUninstallCmd:
    """Tests for uninstall command."""

    def test_uninstall_help(self, cli_runner):
        """Show uninstall help."""
        result = cli_runner.invoke(uninstall_cmd, ["--help"])
        assert result.exit_code == 0
        assert "Uninstall a module" in result.output

    def test_uninstall_no_installations(self, cli_runner, tmp_path):
        """Warn when no installations found."""
        installed_file = tmp_path / ".lola" / "installed.yml"
        installed_file.parent.mkdir(parents=True)

        with (
            patch("lola.cli.install.ensure_lola_dirs"),
            patch("lola.cli.install.get_registry") as mock_registry,
        ):
            mock_registry.return_value = InstallationRegistry(installed_file)
            result = cli_runner.invoke(uninstall_cmd, ["nonexistent"])

        assert result.exit_code == 0
        assert "No installations found" in result.output

    def test_uninstall_with_force(self, cli_runner, tmp_path):
        """Uninstall with force flag."""
        installed_file = tmp_path / ".lola" / "installed.yml"
        installed_file.parent.mkdir(parents=True)

        # Create registry with installation
        registry = InstallationRegistry(installed_file)
        inst = Installation(
            module_name="mymodule",
            assistant="claude-code",
            scope="user",
            skills=["mymodule.skill1"],
            commands=["cmd1"],
        )
        registry.add(inst)

        # Create mock skill/command paths
        skill_dest = tmp_path / "skills"
        skill_dir = skill_dest / "mymodule.skill1"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text("content")

        command_dest = tmp_path / "commands"
        command_dest.mkdir()
        (command_dest / "mymodule.cmd1.md").write_text("content")

        # Create mock target
        from unittest.mock import MagicMock

        mock_target = MagicMock()
        mock_target.get_skill_path.return_value = skill_dest
        mock_target.get_command_path.return_value = command_dest
        mock_target.get_command_filename.return_value = "mymodule.cmd1.md"
        mock_target.remove_skill.return_value = True

        with (
            patch("lola.cli.install.ensure_lola_dirs"),
            patch("lola.cli.install.get_registry", return_value=registry),
            patch("lola.cli.install.get_target", return_value=mock_target),
        ):
            result = cli_runner.invoke(uninstall_cmd, ["mymodule", "-f"])

        assert result.exit_code == 0
        assert "Uninstalled" in result.output


class TestUpdateCmd:
    """Tests for update command."""

    def test_update_help(self, cli_runner):
        """Show update help."""
        result = cli_runner.invoke(update_cmd, ["--help"])
        assert result.exit_code == 0
        assert "Regenerate assistant files" in result.output

    def test_update_no_installations(self, cli_runner, tmp_path):
        """Warn when no installations to update."""
        installed_file = tmp_path / ".lola" / "installed.yml"
        installed_file.parent.mkdir(parents=True)

        with (
            patch("lola.cli.install.ensure_lola_dirs"),
            patch("lola.cli.install.get_registry") as mock_registry,
        ):
            mock_registry.return_value = InstallationRegistry(installed_file)
            result = cli_runner.invoke(update_cmd, [])

        assert result.exit_code == 0
        assert "No installations to update" in result.output

    def test_update_specific_module(self, cli_runner, sample_module, tmp_path):
        """Update a specific module."""
        from unittest.mock import MagicMock

        modules_dir = tmp_path / ".lola" / "modules"
        modules_dir.mkdir(parents=True)
        installed_file = tmp_path / ".lola" / "installed.yml"

        # Copy sample module to registry
        shutil.copytree(sample_module, modules_dir / "sample-module")

        # Create registry with installation
        registry = InstallationRegistry(installed_file)
        inst = Installation(
            module_name="sample-module",
            assistant="claude-code",
            scope="user",
            skills=["sample-module-skill1"],
            commands=["cmd1"],
        )
        registry.add(inst)

        # Create mock paths
        skill_dest = tmp_path / "skills"
        skill_dest.mkdir()
        command_dest = tmp_path / "commands"
        command_dest.mkdir()

        # Create mock target
        mock_target = MagicMock()
        mock_target.get_skill_path.return_value = skill_dest
        mock_target.get_command_path.return_value = command_dest
        mock_target.get_command_filename.side_effect = lambda m, c: f"{m}-{c}.md"
        mock_target.remove_skill.return_value = True
        mock_target.generate_skill.return_value = True
        mock_target.generate_command.return_value = True

        with (
            patch("lola.cli.install.MODULES_DIR", modules_dir),
            patch("lola.cli.install.ensure_lola_dirs"),
            patch("lola.cli.install.get_registry", return_value=registry),
            patch("lola.cli.install.get_local_modules_path", return_value=modules_dir),
            patch("lola.cli.install.get_target", return_value=mock_target),
        ):
            result = cli_runner.invoke(update_cmd, ["sample-module"])

        assert result.exit_code == 0
        assert "Update complete" in result.output

    def test_update_removes_orphaned_commands(self, cli_runner, tmp_path):
        """Update removes orphaned command files when command removed from module."""
        from unittest.mock import MagicMock

        modules_dir = tmp_path / ".lola" / "modules"
        modules_dir.mkdir(parents=True)
        installed_file = tmp_path / ".lola" / "installed.yml"

        # Create a module with only one command (cmd1 removed)
        module_dir = modules_dir / "mymodule"
        module_dir.mkdir()

        # Create skill (auto-discovered via SKILL.md)
        skill_dir = module_dir / "skill1"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("---\ndescription: Skill 1\n---\nContent")

        # Create command (auto-discovered from commands/*.md)
        commands_dir = module_dir / "commands"
        commands_dir.mkdir()
        (commands_dir / "cmd2.md").write_text("---\ndescription: Cmd 2\n---\nContent")

        # Create registry with old installation (had cmd1 and cmd2)
        registry = InstallationRegistry(installed_file)
        inst = Installation(
            module_name="mymodule",
            assistant="claude-code",
            scope="user",
            skills=["mymodule.skill1"],
            commands=["cmd1", "cmd2"],  # cmd1 is orphaned
        )
        registry.add(inst)

        # Create mock paths with orphaned file
        skill_dest = tmp_path / "skills"
        skill_dest.mkdir()
        command_dest = tmp_path / "commands"
        command_dest.mkdir()

        # Create orphaned command file
        orphan_cmd = command_dest / "mymodule.cmd1.md"
        orphan_cmd.write_text("orphaned content")

        # Create mock target that actually removes command files
        def mock_remove_command(dest, cmd, mod):
            target_file = dest / f"{mod}.{cmd}.md"
            if target_file.exists():
                target_file.unlink()
                return True
            return True

        mock_target = MagicMock()
        mock_target.get_skill_path.return_value = skill_dest
        mock_target.get_command_path.return_value = command_dest
        mock_target.get_command_filename.side_effect = lambda m, c: f"{m}.{c}.md"
        mock_target.remove_skill.return_value = True
        mock_target.remove_command.side_effect = mock_remove_command
        mock_target.generate_skill.return_value = True
        mock_target.generate_command.return_value = True

        with (
            patch("lola.cli.install.MODULES_DIR", modules_dir),
            patch("lola.cli.install.ensure_lola_dirs"),
            patch("lola.cli.install.get_registry", return_value=registry),
            patch("lola.cli.install.get_local_modules_path", return_value=modules_dir),
            patch("lola.cli.install.get_target", return_value=mock_target),
        ):
            result = cli_runner.invoke(update_cmd, ["mymodule"])

        assert result.exit_code == 0
        assert "orphaned" in result.output.lower()
        assert not orphan_cmd.exists(), "Orphaned command file should be removed"

    def test_update_removes_orphaned_skills(self, cli_runner, tmp_path):
        """Update removes orphaned skill files when skill removed from module."""
        from unittest.mock import MagicMock

        modules_dir = tmp_path / ".lola" / "modules"
        modules_dir.mkdir(parents=True)
        installed_file = tmp_path / ".lola" / "installed.yml"

        # Create a module with only skill1 (skill2 removed)
        module_dir = modules_dir / "mymodule"
        module_dir.mkdir()

        # Create skills directory with skill (auto-discovered via SKILL.md) - skill2 was removed
        skills_dir = module_dir / "skills"
        skills_dir.mkdir()
        skill_dir = skills_dir / "skill1"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("---\ndescription: Skill 1\n---\nContent")

        # Create registry with old installation (had skill1 and skill2)
        registry = InstallationRegistry(installed_file)
        inst = Installation(
            module_name="mymodule",
            assistant="claude-code",
            scope="user",
            skills=["mymodule.skill1", "mymodule.skill2"],  # skill2 is orphaned
            commands=[],
        )
        registry.add(inst)

        # Create mock paths with orphaned file
        skill_dest = tmp_path / "skills"
        skill_dest.mkdir()
        command_dest = tmp_path / "commands"
        command_dest.mkdir()

        # Create orphaned skill directory
        orphan_skill = skill_dest / "mymodule.skill2"
        orphan_skill.mkdir()
        (orphan_skill / "SKILL.md").write_text("orphaned content")

        # Create mock target with remove_skill that actually removes the dir
        def mock_remove_skill(dest, name):
            target = dest / name
            if target.exists():
                shutil.rmtree(target)
                return True
            return False

        mock_target = MagicMock()
        mock_target.get_skill_path.return_value = skill_dest
        mock_target.get_command_path.return_value = command_dest
        mock_target.get_command_filename.side_effect = lambda m, c: f"{m}-{c}.md"
        mock_target.remove_skill.side_effect = mock_remove_skill
        mock_target.generate_skill.return_value = True
        mock_target.generate_command.return_value = True
        mock_target.uses_managed_section = False  # Not a managed section target

        with (
            patch("lola.cli.install.MODULES_DIR", modules_dir),
            patch("lola.cli.install.ensure_lola_dirs"),
            patch("lola.cli.install.get_registry", return_value=registry),
            patch("lola.cli.install.get_local_modules_path", return_value=modules_dir),
            patch("lola.cli.install.get_target", return_value=mock_target),
        ):
            result = cli_runner.invoke(update_cmd, ["mymodule"])

        assert result.exit_code == 0
        assert "orphaned" in result.output.lower()
        assert not orphan_skill.exists(), "Orphaned skill directory should be removed"

    def test_update_updates_registry_after_cleanup(self, cli_runner, tmp_path):
        """Update updates registry to reflect current module state."""
        from unittest.mock import MagicMock

        modules_dir = tmp_path / ".lola" / "modules"
        modules_dir.mkdir(parents=True)
        installed_file = tmp_path / ".lola" / "installed.yml"

        # Create a module with fewer items than registry
        module_dir = modules_dir / "mymodule"
        module_dir.mkdir()

        # Create skills directory with skill (auto-discovered via SKILL.md)
        skills_dir = module_dir / "skills"
        skills_dir.mkdir()
        skill_dir = skills_dir / "skill1"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("---\ndescription: Skill 1\n---\nContent")

        # Create command (auto-discovered from commands/*.md)
        commands_dir = module_dir / "commands"
        commands_dir.mkdir()
        (commands_dir / "cmd1.md").write_text("---\ndescription: Cmd 1\n---\nContent")

        # Create registry with old installation (had more items)
        registry = InstallationRegistry(installed_file)
        inst = Installation(
            module_name="mymodule",
            assistant="claude-code",
            scope="user",
            skills=["mymodule.skill1", "mymodule.skill2", "mymodule.skill3"],
            commands=["cmd1", "cmd2"],
        )
        registry.add(inst)

        # Create mock paths
        skill_dest = tmp_path / "skills"
        skill_dest.mkdir()
        command_dest = tmp_path / "commands"
        command_dest.mkdir()

        # Create mock target
        mock_target = MagicMock()
        mock_target.get_skill_path.return_value = skill_dest
        mock_target.get_command_path.return_value = command_dest
        mock_target.get_command_filename.side_effect = lambda m, c: f"{m}.{c}.md"
        mock_target.remove_skill.return_value = True
        mock_target.generate_skill.return_value = True
        mock_target.generate_command.return_value = True

        with (
            patch("lola.cli.install.MODULES_DIR", modules_dir),
            patch("lola.cli.install.ensure_lola_dirs"),
            patch("lola.cli.install.get_registry", return_value=registry),
            patch("lola.cli.install.get_local_modules_path", return_value=modules_dir),
            patch("lola.cli.install.get_target", return_value=mock_target),
        ):
            result = cli_runner.invoke(update_cmd, ["mymodule"])

        assert result.exit_code == 0

        # Registry should now reflect current module state (unprefixed skill names)
        updated_inst = registry.find("mymodule")[0]
        assert set(updated_inst.skills) == {"skill1"}
        assert set(updated_inst.commands) == {"cmd1"}

    def test_update_uses_prefixed_name_on_conflict(self, cli_runner, tmp_path):
        """Update uses prefixed skill name when another module owns the unprefixed name."""
        from unittest.mock import MagicMock

        modules_dir = tmp_path / ".lola" / "modules"
        modules_dir.mkdir(parents=True)
        installed_file = tmp_path / ".lola" / "installed.yml"
        project_path = tmp_path / "project"
        project_path.mkdir()

        # Create module1 with skill "shared"
        module1_dir = modules_dir / "module1"
        module1_dir.mkdir()
        skills1_dir = module1_dir / "skills"
        skills1_dir.mkdir()
        skill1_dir = skills1_dir / "shared"
        skill1_dir.mkdir()
        (skill1_dir / "SKILL.md").write_text(
            "---\ndescription: Shared skill\n---\nModule 1"
        )

        # Create module2 with skill "shared" (same name)
        module2_dir = modules_dir / "module2"
        module2_dir.mkdir()
        skills2_dir = module2_dir / "skills"
        skills2_dir.mkdir()
        skill2_dir = skills2_dir / "shared"
        skill2_dir.mkdir()
        (skill2_dir / "SKILL.md").write_text(
            "---\ndescription: Shared skill\n---\nModule 2"
        )

        # Create registry with both modules installed to same project/assistant
        registry = InstallationRegistry(installed_file)
        inst1 = Installation(
            module_name="module1",
            assistant="claude-code",
            scope="project",
            project_path=str(project_path),
            skills=["shared"],  # module1 owns "shared"
        )
        inst2 = Installation(
            module_name="module2",
            assistant="claude-code",
            scope="project",
            project_path=str(project_path),
            skills=["shared"],  # module2 also claims "shared" (will conflict)
        )
        registry.add(inst1)
        registry.add(inst2)

        # Create mock paths
        skill_dest = project_path / ".claude" / "skills"
        skill_dest.mkdir(parents=True)

        # Create mock target
        mock_target = MagicMock()
        mock_target.get_skill_path.return_value = skill_dest
        mock_target.get_command_path.return_value = (
            project_path / ".claude" / "commands"
        )
        mock_target.get_agent_path.return_value = project_path / ".claude" / "agents"
        mock_target.get_mcp_path.return_value = project_path / ".claude" / "mcp.json"
        mock_target.get_instructions_path.return_value = None
        mock_target.uses_managed_section = False
        mock_target.generate_skill.return_value = True
        mock_target.remove_skill.return_value = True

        with (
            patch("lola.cli.install.MODULES_DIR", modules_dir),
            patch("lola.cli.install.ensure_lola_dirs"),
            patch("lola.cli.install.get_registry", return_value=registry),
            patch("lola.cli.install.get_local_modules_path", return_value=modules_dir),
            patch("lola.cli.install.get_target", return_value=mock_target),
        ):
            result = cli_runner.invoke(update_cmd, ["module2", "-v"])

        assert result.exit_code == 0

        # module2 should use prefixed name since module1 owns "shared"
        updated_inst2 = [
            i for i in registry.find("module2") if i.project_path == str(project_path)
        ][0]
        assert "module2_shared" in updated_inst2.skills, (
            f"Expected 'module2_shared' in skills, got {updated_inst2.skills}"
        )
        assert "shared" not in updated_inst2.skills, (
            "module2 should not have unprefixed 'shared' since module1 owns it"
        )


class TestListInstalledCmd:
    """Tests for installed (list) command."""

    def test_list_help(self, cli_runner):
        """Show list help."""
        result = cli_runner.invoke(list_installed_cmd, ["--help"])
        assert result.exit_code == 0
        assert "List all installed modules" in result.output

    def test_list_empty(self, cli_runner, tmp_path):
        """List when no modules installed."""
        installed_file = tmp_path / ".lola" / "installed.yml"
        installed_file.parent.mkdir(parents=True)

        with (
            patch("lola.cli.install.ensure_lola_dirs"),
            patch("lola.cli.install.get_registry") as mock_registry,
        ):
            mock_registry.return_value = InstallationRegistry(installed_file)
            result = cli_runner.invoke(list_installed_cmd, [])

        assert result.exit_code == 0
        assert "No modules installed" in result.output

    def test_list_with_installations(self, cli_runner, tmp_path):
        """List installed modules."""
        installed_file = tmp_path / ".lola" / "installed.yml"
        installed_file.parent.mkdir(parents=True)

        # Create registry with installations
        registry = InstallationRegistry(installed_file)
        registry.add(
            Installation(
                module_name="module1",
                assistant="claude-code",
                scope="user",
                skills=["module1-skill1"],
            )
        )
        registry.add(
            Installation(
                module_name="module2",
                assistant="cursor",
                scope="user",
                commands=["cmd1"],
            )
        )

        with (
            patch("lola.cli.install.ensure_lola_dirs"),
            patch("lola.cli.install.get_registry", return_value=registry),
        ):
            result = cli_runner.invoke(list_installed_cmd, [])

        assert result.exit_code == 0
        assert "module1" in result.output
        assert "module2" in result.output
        assert "Installed (2 modules)" in result.output

    def test_list_filter_by_assistant(self, cli_runner, tmp_path):
        """Filter list by assistant."""
        installed_file = tmp_path / ".lola" / "installed.yml"
        installed_file.parent.mkdir(parents=True)

        # Create registry with installations
        registry = InstallationRegistry(installed_file)
        registry.add(
            Installation(
                module_name="module1",
                assistant="claude-code",
                scope="user",
            )
        )
        registry.add(
            Installation(
                module_name="module2",
                assistant="cursor",
                scope="user",
            )
        )

        with (
            patch("lola.cli.install.ensure_lola_dirs"),
            patch("lola.cli.install.get_registry", return_value=registry),
        ):
            result = cli_runner.invoke(list_installed_cmd, ["-a", "claude-code"])

        assert result.exit_code == 0
        assert "module1" in result.output
        assert "module2" not in result.output
        assert "Installed (1 module" in result.output

    def test_list_shows_version_and_ref(self, cli_runner, tmp_path):
        """lola list shows version and ref when set on Installation."""
        installed_file = tmp_path / ".lola" / "installed.yml"
        installed_file.parent.mkdir(parents=True)

        registry = InstallationRegistry(installed_file)
        registry.add(
            Installation(
                module_name="pinned-mod",
                assistant="claude-code",
                scope="user",
                version="1.2.0",
                ref="v1.2.0",
            )
        )

        with (
            patch("lola.cli.install.ensure_lola_dirs"),
            patch("lola.cli.install.get_registry", return_value=registry),
        ):
            result = cli_runner.invoke(list_installed_cmd, [])

        assert result.exit_code == 0
        assert "version: 1.2.0" in result.output
        assert "ref: v1.2.0" in result.output

    def test_list_omits_version_ref_when_absent(self, cli_runner, tmp_path):
        """lola list does not show version/ref lines when they are not set."""
        installed_file = tmp_path / ".lola" / "installed.yml"
        installed_file.parent.mkdir(parents=True)

        registry = InstallationRegistry(installed_file)
        registry.add(
            Installation(
                module_name="plain-mod",
                assistant="claude-code",
                scope="user",
            )
        )

        with (
            patch("lola.cli.install.ensure_lola_dirs"),
            patch("lola.cli.install.get_registry", return_value=registry),
        ):
            result = cli_runner.invoke(list_installed_cmd, [])

        assert result.exit_code == 0
        assert "version:" not in result.output
        assert "ref:" not in result.output

    def test_installation_ref_roundtrip(self, tmp_path):
        """Installation.ref persists to YAML and loads back correctly."""
        installed_file = tmp_path / "installed.yml"
        registry = InstallationRegistry(installed_file)
        registry.add(
            Installation(
                module_name="mod",
                assistant="claude-code",
                scope="user",
                version="2.0.0",
                ref="v2.0.0",
            )
        )

        registry2 = InstallationRegistry(installed_file)
        insts = registry2.find("mod")
        assert len(insts) == 1
        assert insts[0].version == "2.0.0"
        assert insts[0].ref == "v2.0.0"

    def test_installation_backward_compat_no_ref(self, tmp_path):
        """Old installed.yml without ref field loads without error, ref is None."""
        installed_file = tmp_path / "installed.yml"
        # Write the legacy YAML shape directly — no 'ref' key, matching files
        # written before the ref field was introduced.
        installed_file.write_text(
            "installations:\n"
            "- module: mod\n"
            "  assistant: claude-code\n"
            "  scope: user\n"
            "  version: '1.0.0'\n"
            "  skills: []\n"
            "  commands: []\n"
            "  agents: []\n"
            "  mcps: []\n"
            "  has_instructions: false\n"
        )

        registry = InstallationRegistry(installed_file)
        insts = registry.find("mod")
        assert len(insts) == 1
        assert insts[0].ref is None


# ---------------------------------------------------------------------------
# Interactive prompt tests (001-interactive-prompts)
# ---------------------------------------------------------------------------


class TestInstallCmdInteractive:
    """Tests for install_cmd interactive prompts (T009, T010, T011)."""

    def test_install_no_module_noninteractive_errors(self, cli_runner, tmp_path):
        """T009: non-interactive + no module_name → SystemExit(1)."""
        with (
            patch("lola.cli.install.ensure_lola_dirs"),
            patch("lola.prompts.is_interactive", return_value=False),
            patch("lola.cli.install.is_interactive", return_value=False),
        ):
            result = cli_runner.invoke(install_cmd, [])
        assert result.exit_code == 1
        assert "non-interactive" in result.output

    def test_install_no_module_interactive_no_modules_registered(
        self, cli_runner, tmp_path
    ):
        """T009: interactive + no modules registered → message, exit 0."""
        with (
            patch("lola.cli.install.ensure_lola_dirs"),
            patch("lola.cli.install.is_interactive", return_value=True),
            patch("lola.cli.install.list_registered_modules", return_value=[]),
        ):
            result = cli_runner.invoke(install_cmd, [])
        assert result.exit_code == 0
        assert "No modules registered" in result.output

    def test_install_no_module_interactive_picker_cancelled(self, cli_runner, tmp_path):
        """T009: interactive + user cancels module picker → SystemExit(130)."""
        with (
            patch("lola.cli.install.ensure_lola_dirs"),
            patch("lola.cli.install.is_interactive", return_value=True),
            patch(
                "lola.cli.install.list_registered_modules",
                return_value=[_fake_module("my-mod")],
            ),
            patch("lola.cli.install.select_module", return_value=None),
        ):
            result = cli_runner.invoke(install_cmd, [])
        assert result.exit_code == 130
        assert "Cancelled" in result.output

    def test_install_no_assistant_interactive_picker_used(
        self, cli_runner, sample_module, tmp_path
    ):
        """T010: interactive + no -a flag → select_assistants is called."""
        modules_dir = tmp_path / ".lola" / "modules"
        modules_dir.mkdir(parents=True)
        installed_file = tmp_path / ".lola" / "installed.yml"
        shutil.copytree(sample_module, modules_dir / "sample-module")

        with (
            patch("lola.cli.install.MODULES_DIR", modules_dir),
            patch("lola.cli.install.ensure_lola_dirs"),
            patch("lola.cli.install.get_registry") as mock_registry,
            patch("lola.cli.install.get_local_modules_path", return_value=modules_dir),
            patch("lola.cli.install.install_to_assistant", return_value=1),
            patch("lola.cli.install.is_interactive", return_value=True),
            patch(
                "lola.cli.install.select_assistants", return_value=["claude-code"]
            ) as mock_select,
        ):
            mock_registry.return_value = InstallationRegistry(installed_file)
            result = cli_runner.invoke(install_cmd, ["sample-module"])

        assert result.exit_code == 0
        mock_select.assert_called_once()

    def test_install_explicit_assistant_no_prompt(
        self, cli_runner, sample_module, tmp_path
    ):
        """T010: explicit -a flag → select_assistants is NOT called."""
        modules_dir = tmp_path / ".lola" / "modules"
        modules_dir.mkdir(parents=True)
        installed_file = tmp_path / ".lola" / "installed.yml"
        shutil.copytree(sample_module, modules_dir / "sample-module")

        with (
            patch("lola.cli.install.MODULES_DIR", modules_dir),
            patch("lola.cli.install.ensure_lola_dirs"),
            patch("lola.cli.install.get_registry") as mock_registry,
            patch("lola.cli.install.get_local_modules_path", return_value=modules_dir),
            patch("lola.cli.install.install_to_assistant", return_value=1),
            patch("lola.cli.install.is_interactive", return_value=True),
            patch("lola.cli.install.select_assistants") as mock_select,
        ):
            mock_registry.return_value = InstallationRegistry(installed_file)
            result = cli_runner.invoke(
                install_cmd, ["sample-module", "-a", "claude-code"]
            )

        assert result.exit_code == 0
        mock_select.assert_not_called()

    def test_install_assistant_picker_cancelled_exits_130(
        self, cli_runner, sample_module, tmp_path
    ):
        """T011: user cancels assistant picker → exit 130, no installation."""
        modules_dir = tmp_path / ".lola" / "modules"
        modules_dir.mkdir(parents=True)
        installed_file = tmp_path / ".lola" / "installed.yml"
        shutil.copytree(sample_module, modules_dir / "sample-module")

        with (
            patch("lola.cli.install.MODULES_DIR", modules_dir),
            patch("lola.cli.install.ensure_lola_dirs"),
            patch("lola.cli.install.get_registry") as mock_registry,
            patch("lola.cli.install.get_local_modules_path", return_value=modules_dir),
            patch("lola.cli.install.install_to_assistant") as mock_install,
            patch("lola.cli.install.is_interactive", return_value=True),
            patch("lola.cli.install.select_assistants", return_value=[]),
        ):
            mock_registry.return_value = InstallationRegistry(installed_file)
            result = cli_runner.invoke(install_cmd, ["sample-module"])

        assert result.exit_code == 130
        mock_install.assert_not_called()


def _fake_module(name: str):
    """Create a minimal Module-like object for testing."""
    from unittest.mock import MagicMock

    m = MagicMock()
    m.name = name
    return m


# ---------------------------------------------------------------------------
# T016: uninstall_cmd interactive module picker (US2)
# ---------------------------------------------------------------------------


class TestUninstallCmdInteractive:
    """T016: tests for lola uninstall with optional module_name."""

    def test_uninstall_no_module_noninteractive_errors(self, cli_runner):
        """Non-interactive with no module_name → exit 1."""
        with (
            patch("lola.cli.install.ensure_lola_dirs"),
            patch("lola.cli.install.is_interactive", return_value=False),
        ):
            result = cli_runner.invoke(uninstall_cmd, [])

        assert result.exit_code == 1

    def test_uninstall_no_module_interactive_no_modules_installed(
        self, cli_runner, tmp_path
    ):
        """Interactive with no installed modules → message and exit 0."""
        installed_file = tmp_path / "installed.yml"
        with (
            patch("lola.cli.install.ensure_lola_dirs"),
            patch("lola.cli.install.is_interactive", return_value=True),
            patch("lola.cli.install.get_registry") as mock_reg,
        ):
            mock_reg.return_value = InstallationRegistry(installed_file)
            result = cli_runner.invoke(uninstall_cmd, [])

        assert result.exit_code == 0
        assert "No modules installed" in result.output

    def test_uninstall_no_module_interactive_picker_cancelled(
        self, cli_runner, tmp_path
    ):
        """Interactive picker cancelled → exit 130."""
        installed_file = tmp_path / "installed.yml"
        registry = InstallationRegistry(installed_file)
        registry.add(
            Installation(
                module_name="my-module",
                assistant="claude-code",
                scope="user",
            )
        )
        with (
            patch("lola.cli.install.ensure_lola_dirs"),
            patch("lola.cli.install.is_interactive", return_value=True),
            patch("lola.cli.install.get_registry", return_value=registry),
            patch("lola.cli.install.select_module", return_value=None),
        ):
            result = cli_runner.invoke(uninstall_cmd, [])

        assert result.exit_code == 130

    def test_uninstall_no_module_interactive_picker_selects(self, cli_runner, tmp_path):
        """Interactive picker returns module → proceeds with uninstall flow."""
        installed_file = tmp_path / "installed.yml"
        registry = InstallationRegistry(installed_file)
        registry.add(
            Installation(
                module_name="my-module",
                assistant="claude-code",
                scope="user",
            )
        )
        with (
            patch("lola.cli.install.ensure_lola_dirs"),
            patch("lola.cli.install.is_interactive", return_value=True),
            patch("lola.cli.install.get_registry", return_value=registry),
            patch("lola.cli.install.select_module", return_value="my-module"),
            patch("lola.cli.install.click.confirm", return_value=False),
        ):
            result = cli_runner.invoke(uninstall_cmd, [], input="n\n")

        # The uninstall flow ran (found the module, asked for confirmation)
        assert "my-module" in result.output

    def test_uninstall_multiple_installations_interactive_picker(
        self, cli_runner, tmp_path
    ):
        """Multiple installations in interactive mode → select_installations prompt."""
        installed_file = tmp_path / "installed.yml"
        registry = InstallationRegistry(installed_file)
        registry.add(
            Installation(
                module_name="my-module",
                assistant="claude-code",
                scope="project",
                project_path="/proj/a",
            )
        )
        registry.add(
            Installation(
                module_name="my-module",
                assistant="cursor",
                scope="project",
                project_path="/proj/a",
            )
        )
        with (
            patch("lola.cli.install.ensure_lola_dirs"),
            patch("lola.cli.install.is_interactive", return_value=True),
            patch("lola.cli.install.get_registry", return_value=registry),
            patch(
                "lola.cli.install.select_installations",
                return_value=[],
            ) as mock_sel,
        ):
            result = cli_runner.invoke(uninstall_cmd, ["my-module"])

        mock_sel.assert_called_once()
        assert "Cancelled" in result.output

    def test_uninstall_multiple_installations_noninteractive_confirm_all(
        self, cli_runner, tmp_path
    ):
        """Multiple installations in non-interactive mode → 'Uninstall all?' prompt."""
        installed_file = tmp_path / "installed.yml"
        registry = InstallationRegistry(installed_file)
        registry.add(
            Installation(
                module_name="my-module",
                assistant="claude-code",
                scope="project",
                project_path="/proj/a",
            )
        )
        registry.add(
            Installation(
                module_name="my-module",
                assistant="cursor",
                scope="project",
                project_path="/proj/a",
            )
        )
        with (
            patch("lola.cli.install.ensure_lola_dirs"),
            patch("lola.cli.install.is_interactive", return_value=False),
            patch("lola.cli.install.get_registry", return_value=registry),
            patch("lola.cli.install.click.confirm", return_value=False),
        ):
            result = cli_runner.invoke(uninstall_cmd, ["my-module"])

        assert "Multiple installations found" in result.output
        assert "Cancelled" in result.output

    def test_uninstall_explicit_module_no_prompt(self, cli_runner, tmp_path):
        """Explicit module_name argument → select_module is NOT called."""
        installed_file = tmp_path / "installed.yml"
        registry = InstallationRegistry(installed_file)
        with (
            patch("lola.cli.install.ensure_lola_dirs"),
            patch("lola.cli.install.get_registry", return_value=registry),
            patch("lola.cli.install.select_module") as mock_picker,
        ):
            cli_runner.invoke(uninstall_cmd, ["my-module"])

        mock_picker.assert_not_called()
