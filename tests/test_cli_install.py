"""Tests for the install CLI commands."""

import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
import yaml
from click.testing import CliRunner

from lola.main import main
from lola.cli.install import install_cmd, uninstall_cmd, update_cmd, list_installed_cmd
from lola.models import Installation, InstallationRegistry


class TestInstallCmd:
    """Tests for install command."""

    def test_install_help(self, cli_runner):
        """Show install help."""
        result = cli_runner.invoke(install_cmd, ['--help'])
        assert result.exit_code == 0
        assert 'Install a module' in result.output

    def test_install_missing_module(self, cli_runner, tmp_path):
        """Fail when module not found."""
        modules_dir = tmp_path / '.lola' / 'modules'
        modules_dir.mkdir(parents=True)

        with patch('lola.cli.install.MODULES_DIR', modules_dir), \
             patch('lola.cli.install.ensure_lola_dirs'):
            result = cli_runner.invoke(install_cmd, ['nonexistent'])

        assert result.exit_code == 1
        assert 'not found' in result.output

    def test_install_project_scope_without_path(self, cli_runner, tmp_path):
        """Fail project scope without path."""
        modules_dir = tmp_path / '.lola' / 'modules'
        modules_dir.mkdir(parents=True)

        with patch('lola.cli.install.MODULES_DIR', modules_dir), \
             patch('lola.cli.install.ensure_lola_dirs'):
            result = cli_runner.invoke(install_cmd, ['mymodule', '-s', 'project'])

        assert result.exit_code == 1
        assert 'Project path required' in result.output

    def test_install_project_path_not_exists(self, cli_runner, tmp_path):
        """Fail when project path doesn't exist."""
        modules_dir = tmp_path / '.lola' / 'modules'
        modules_dir.mkdir(parents=True)

        with patch('lola.cli.install.MODULES_DIR', modules_dir), \
             patch('lola.cli.install.ensure_lola_dirs'):
            result = cli_runner.invoke(install_cmd, ['mymodule', '-s', 'project', '/nonexistent/path'])

        assert result.exit_code == 1
        assert 'does not exist' in result.output

    def test_install_module(self, cli_runner, sample_module, tmp_path):
        """Install a module successfully."""
        modules_dir = tmp_path / '.lola' / 'modules'
        modules_dir.mkdir(parents=True)
        installed_file = tmp_path / '.lola' / 'installed.yml'

        # Copy sample module to registry
        shutil.copytree(sample_module, modules_dir / 'sample-module')

        # Create mock assistant paths
        skill_dest = tmp_path / 'skills'
        command_dest = tmp_path / 'commands'
        skill_dest.mkdir()
        command_dest.mkdir()

        with patch('lola.cli.install.MODULES_DIR', modules_dir), \
             patch('lola.cli.install.ensure_lola_dirs'), \
             patch('lola.cli.install.get_registry') as mock_registry, \
             patch('lola.cli.install.get_local_modules_path', return_value=modules_dir), \
             patch('lola.cli.install.install_to_assistant', return_value=1) as mock_install:

            mock_registry.return_value = InstallationRegistry(installed_file)
            result = cli_runner.invoke(install_cmd, ['sample-module', '-a', 'claude-code'])

        assert result.exit_code == 0
        assert 'Installing' in result.output
        mock_install.assert_called_once()


class TestUninstallCmd:
    """Tests for uninstall command."""

    def test_uninstall_help(self, cli_runner):
        """Show uninstall help."""
        result = cli_runner.invoke(uninstall_cmd, ['--help'])
        assert result.exit_code == 0
        assert 'Uninstall a module' in result.output

    def test_uninstall_no_installations(self, cli_runner, tmp_path):
        """Warn when no installations found."""
        installed_file = tmp_path / '.lola' / 'installed.yml'
        installed_file.parent.mkdir(parents=True)

        with patch('lola.cli.install.ensure_lola_dirs'), \
             patch('lola.cli.install.get_registry') as mock_registry:
            mock_registry.return_value = InstallationRegistry(installed_file)
            result = cli_runner.invoke(uninstall_cmd, ['nonexistent'])

        assert result.exit_code == 0
        assert 'No installations found' in result.output

    def test_uninstall_with_force(self, cli_runner, tmp_path):
        """Uninstall with force flag."""
        installed_file = tmp_path / '.lola' / 'installed.yml'
        installed_file.parent.mkdir(parents=True)

        # Create registry with installation
        registry = InstallationRegistry(installed_file)
        inst = Installation(
            module_name='mymodule',
            assistant='claude-code',
            scope='user',
            skills=['mymodule-skill1'],
            commands=['cmd1'],
        )
        registry.add(inst)

        # Create mock skill/command paths
        skill_dest = tmp_path / 'skills'
        skill_dir = skill_dest / 'mymodule-skill1'
        skill_dir.mkdir(parents=True)
        (skill_dir / 'SKILL.md').write_text('content')

        command_dest = tmp_path / 'commands'
        command_dest.mkdir()
        (command_dest / 'mymodule-cmd1.md').write_text('content')

        with patch('lola.cli.install.ensure_lola_dirs'), \
             patch('lola.cli.install.get_registry', return_value=registry), \
             patch('lola.cli.install.get_assistant_skill_path', return_value=skill_dest), \
             patch('lola.cli.install.get_assistant_command_path', return_value=command_dest):
            result = cli_runner.invoke(uninstall_cmd, ['mymodule', '-f'])

        assert result.exit_code == 0
        assert 'Uninstalled' in result.output


class TestUpdateCmd:
    """Tests for update command."""

    def test_update_help(self, cli_runner):
        """Show update help."""
        result = cli_runner.invoke(update_cmd, ['--help'])
        assert result.exit_code == 0
        assert 'Regenerate assistant files' in result.output

    def test_update_no_installations(self, cli_runner, tmp_path):
        """Warn when no installations to update."""
        installed_file = tmp_path / '.lola' / 'installed.yml'
        installed_file.parent.mkdir(parents=True)

        with patch('lola.cli.install.ensure_lola_dirs'), \
             patch('lola.cli.install.get_registry') as mock_registry:
            mock_registry.return_value = InstallationRegistry(installed_file)
            result = cli_runner.invoke(update_cmd, [])

        assert result.exit_code == 0
        assert 'No installations to update' in result.output

    def test_update_specific_module(self, cli_runner, sample_module, tmp_path):
        """Update a specific module."""
        modules_dir = tmp_path / '.lola' / 'modules'
        modules_dir.mkdir(parents=True)
        installed_file = tmp_path / '.lola' / 'installed.yml'

        # Copy sample module to registry
        shutil.copytree(sample_module, modules_dir / 'sample-module')

        # Create registry with installation
        registry = InstallationRegistry(installed_file)
        inst = Installation(
            module_name='sample-module',
            assistant='claude-code',
            scope='user',
            skills=['sample-module-skill1'],
            commands=['cmd1'],
        )
        registry.add(inst)

        # Create mock paths
        skill_dest = tmp_path / 'skills'
        skill_dest.mkdir()
        command_dest = tmp_path / 'commands'
        command_dest.mkdir()

        with patch('lola.cli.install.MODULES_DIR', modules_dir), \
             patch('lola.cli.install.ensure_lola_dirs'), \
             patch('lola.cli.install.get_registry', return_value=registry), \
             patch('lola.cli.install.get_local_modules_path', return_value=modules_dir), \
             patch('lola.cli.install.get_assistant_skill_path', return_value=skill_dest), \
             patch('lola.cli.install.get_assistant_command_path', return_value=command_dest):
            result = cli_runner.invoke(update_cmd, ['sample-module'])

        assert result.exit_code == 0
        assert 'Update complete' in result.output


class TestListInstalledCmd:
    """Tests for installed (list) command."""

    def test_list_help(self, cli_runner):
        """Show list help."""
        result = cli_runner.invoke(list_installed_cmd, ['--help'])
        assert result.exit_code == 0
        assert 'List all installed modules' in result.output

    def test_list_empty(self, cli_runner, tmp_path):
        """List when no modules installed."""
        installed_file = tmp_path / '.lola' / 'installed.yml'
        installed_file.parent.mkdir(parents=True)

        with patch('lola.cli.install.ensure_lola_dirs'), \
             patch('lola.cli.install.get_registry') as mock_registry:
            mock_registry.return_value = InstallationRegistry(installed_file)
            result = cli_runner.invoke(list_installed_cmd, [])

        assert result.exit_code == 0
        assert 'No modules installed' in result.output

    def test_list_with_installations(self, cli_runner, tmp_path):
        """List installed modules."""
        installed_file = tmp_path / '.lola' / 'installed.yml'
        installed_file.parent.mkdir(parents=True)

        # Create registry with installations
        registry = InstallationRegistry(installed_file)
        registry.add(Installation(
            module_name='module1',
            assistant='claude-code',
            scope='user',
            skills=['module1-skill1'],
        ))
        registry.add(Installation(
            module_name='module2',
            assistant='cursor',
            scope='user',
            commands=['cmd1'],
        ))

        with patch('lola.cli.install.ensure_lola_dirs'), \
             patch('lola.cli.install.get_registry', return_value=registry):
            result = cli_runner.invoke(list_installed_cmd, [])

        assert result.exit_code == 0
        assert 'module1' in result.output
        assert 'module2' in result.output
        assert 'Installed modules (2)' in result.output

    def test_list_filter_by_assistant(self, cli_runner, tmp_path):
        """Filter list by assistant."""
        installed_file = tmp_path / '.lola' / 'installed.yml'
        installed_file.parent.mkdir(parents=True)

        # Create registry with installations
        registry = InstallationRegistry(installed_file)
        registry.add(Installation(
            module_name='module1',
            assistant='claude-code',
            scope='user',
        ))
        registry.add(Installation(
            module_name='module2',
            assistant='cursor',
            scope='user',
        ))

        with patch('lola.cli.install.ensure_lola_dirs'), \
             patch('lola.cli.install.get_registry', return_value=registry):
            result = cli_runner.invoke(list_installed_cmd, ['-a', 'claude-code'])

        assert result.exit_code == 0
        assert 'module1' in result.output
        assert 'module2' not in result.output
        assert 'Installed modules (1)' in result.output
