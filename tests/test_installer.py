"""Tests for the core/installer module."""

import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
import yaml

from lola.core.installer import (
    get_registry,
    copy_module_to_local,
    install_to_assistant,
)
from lola.models import Module, InstallationRegistry, Installation


class TestGetRegistry:
    """Tests for get_registry()."""

    def test_returns_registry(self, tmp_path):
        """Returns an InstallationRegistry."""
        with patch('lola.core.installer.INSTALLED_FILE', tmp_path / 'installed.yml'):
            registry = get_registry()

        assert isinstance(registry, InstallationRegistry)


class TestCopyModuleToLocal:
    """Tests for copy_module_to_local()."""

    def test_copies_module(self, tmp_path):
        """Copies module to local modules path."""
        # Create source module
        source_dir = tmp_path / 'source' / 'mymodule'
        source_dir.mkdir(parents=True)
        (source_dir / 'SKILL.md').write_text('# My Skill')
        (source_dir / 'subdir').mkdir()
        (source_dir / 'subdir' / 'file.txt').write_text('content')

        module = Module(name='mymodule', path=source_dir)

        local_modules = tmp_path / 'local' / '.lola' / 'modules'

        result = copy_module_to_local(module, local_modules)

        assert result == local_modules / 'mymodule'
        assert result.exists()
        assert (result / 'SKILL.md').read_text() == '# My Skill'
        assert (result / 'subdir' / 'file.txt').read_text() == 'content'

    def test_same_path_returns_unchanged(self, tmp_path):
        """Returns same path if source and dest are identical."""
        module_dir = tmp_path / '.lola' / 'modules' / 'mymodule'
        module_dir.mkdir(parents=True)
        (module_dir / 'SKILL.md').write_text('# My Skill')

        module = Module(name='mymodule', path=module_dir)

        local_modules = tmp_path / '.lola' / 'modules'

        result = copy_module_to_local(module, local_modules)

        assert result == module_dir

    def test_overwrites_existing(self, tmp_path):
        """Overwrites existing module directory."""
        # Create source module
        source_dir = tmp_path / 'source' / 'mymodule'
        source_dir.mkdir(parents=True)
        (source_dir / 'new.txt').write_text('new content')

        module = Module(name='mymodule', path=source_dir)

        local_modules = tmp_path / 'local' / '.lola' / 'modules'
        local_modules.mkdir(parents=True)

        # Create existing directory
        existing = local_modules / 'mymodule'
        existing.mkdir()
        (existing / 'old.txt').write_text('old content')

        result = copy_module_to_local(module, local_modules)

        assert (result / 'new.txt').exists()
        assert not (result / 'old.txt').exists()

    def test_removes_existing_symlink(self, tmp_path):
        """Removes existing symlink before copying."""
        # Create source module
        source_dir = tmp_path / 'source' / 'mymodule'
        source_dir.mkdir(parents=True)
        (source_dir / 'SKILL.md').write_text('# My Skill')

        module = Module(name='mymodule', path=source_dir)

        local_modules = tmp_path / 'local' / '.lola' / 'modules'
        local_modules.mkdir(parents=True)

        # Create a symlink
        target = tmp_path / 'target'
        target.mkdir()
        symlink = local_modules / 'mymodule'
        symlink.symlink_to(target)

        result = copy_module_to_local(module, local_modules)

        assert not result.is_symlink()
        assert result.is_dir()
        assert (result / 'SKILL.md').exists()


class TestInstallToAssistant:
    """Tests for install_to_assistant()."""

    def setup_method(self):
        """Set up test fixtures."""
        self.ui_mock = MagicMock()

    def create_test_module(self, tmp_path, name='testmod', skills=None, commands=None):
        """Helper to create a test module structure."""
        module_dir = tmp_path / 'modules' / name
        module_dir.mkdir(parents=True)

        # Create .lola/module.yml
        lola_dir = module_dir / '.lola'
        lola_dir.mkdir()
        manifest = {
            'type': 'lola/module',
            'version': '1.0.0',
            'skills': skills or [],
            'commands': commands or [],
        }
        (lola_dir / 'module.yml').write_text(yaml.dump(manifest))

        # Create skill directories
        if skills:
            for skill in skills:
                skill_dir = module_dir / skill
                skill_dir.mkdir()
                (skill_dir / 'SKILL.md').write_text(f"""---
description: {skill} description
---

# {skill}

Content.
""")

        # Create command files
        if commands:
            commands_dir = module_dir / 'commands'
            commands_dir.mkdir()
            for cmd in commands:
                (commands_dir / f'{cmd}.md').write_text(f"""---
description: {cmd} command
---

Do {cmd}.
""")

        return Module.from_path(module_dir)

    def test_install_claude_code_user_skills(self, tmp_path):
        """Install skills to claude-code user scope."""
        module = self.create_test_module(tmp_path, skills=['skill1'])

        local_modules = tmp_path / '.lola' / 'modules'
        registry = InstallationRegistry(tmp_path / 'installed.yml')
        skill_dest = tmp_path / 'skills'

        with patch('lola.core.installer.ui', self.ui_mock), \
             patch('lola.core.installer.get_assistant_skill_path', return_value=skill_dest), \
             patch('lola.core.installer.get_assistant_command_path', return_value=None):

            count = install_to_assistant(
                module=module,
                assistant='claude-code',
                scope='user',
                project_path=None,
                local_modules=local_modules,
                registry=registry,
            )

        assert count == 1
        # Check skill was installed
        assert (skill_dest / 'testmod-skill1' / 'SKILL.md').exists()

    def test_install_claude_code_commands(self, tmp_path):
        """Install commands to claude-code."""
        module = self.create_test_module(tmp_path, commands=['cmd1'])

        local_modules = tmp_path / '.lola' / 'modules'
        registry = InstallationRegistry(tmp_path / 'installed.yml')
        command_dest = tmp_path / 'commands'

        with patch('lola.core.installer.ui', self.ui_mock), \
             patch('lola.core.installer.get_assistant_skill_path', return_value=None), \
             patch('lola.core.installer.get_assistant_command_path', return_value=command_dest):

            count = install_to_assistant(
                module=module,
                assistant='claude-code',
                scope='user',
                project_path=None,
                local_modules=local_modules,
                registry=registry,
            )

        assert count == 1
        # Check command was installed
        assert (command_dest / 'testmod-cmd1.md').exists()

    def test_install_gemini_cli_user_skills_skipped(self, tmp_path):
        """Gemini CLI user scope skills are skipped."""
        module = self.create_test_module(tmp_path, skills=['skill1'])

        local_modules = tmp_path / '.lola' / 'modules'
        registry = InstallationRegistry(tmp_path / 'installed.yml')

        with patch('lola.core.installer.ui', self.ui_mock), \
             patch('lola.core.installer.get_assistant_skill_path') as skill_path_mock, \
             patch('lola.core.installer.get_assistant_command_path', return_value=None):

            count = install_to_assistant(
                module=module,
                assistant='gemini-cli',
                scope='user',
                project_path=None,
                local_modules=local_modules,
                registry=registry,
            )

        # Skills should be skipped, not installed
        assert count == 0
        skill_path_mock.assert_not_called()

    def test_install_cursor_user_skills_skipped(self, tmp_path):
        """Cursor user scope skills are skipped."""
        module = self.create_test_module(tmp_path, skills=['skill1'])

        local_modules = tmp_path / '.lola' / 'modules'
        registry = InstallationRegistry(tmp_path / 'installed.yml')

        with patch('lola.core.installer.ui', self.ui_mock), \
             patch('lola.core.installer.get_assistant_skill_path') as skill_path_mock, \
             patch('lola.core.installer.get_assistant_command_path', return_value=None):

            count = install_to_assistant(
                module=module,
                assistant='cursor',
                scope='user',
                project_path=None,
                local_modules=local_modules,
                registry=registry,
            )

        # Skills should be skipped
        assert count == 0
        skill_path_mock.assert_not_called()

    def test_install_records_installation(self, tmp_path):
        """Installation is recorded in registry."""
        module = self.create_test_module(tmp_path, skills=['skill1'], commands=['cmd1'])

        local_modules = tmp_path / '.lola' / 'modules'
        registry = InstallationRegistry(tmp_path / 'installed.yml')
        skill_dest = tmp_path / 'skills'
        command_dest = tmp_path / 'commands'

        with patch('lola.core.installer.ui', self.ui_mock), \
             patch('lola.core.installer.get_assistant_skill_path', return_value=skill_dest), \
             patch('lola.core.installer.get_assistant_command_path', return_value=command_dest):

            install_to_assistant(
                module=module,
                assistant='claude-code',
                scope='user',
                project_path=None,
                local_modules=local_modules,
                registry=registry,
            )

        # Check registry
        installations = registry.find('testmod')
        assert len(installations) == 1
        assert installations[0].assistant == 'claude-code'
        assert installations[0].scope == 'user'
        assert 'testmod-skill1' in installations[0].skills
        assert 'cmd1' in installations[0].commands

    def test_install_missing_skill_source(self, tmp_path):
        """Handle missing skill source gracefully."""
        # Create module without actual skill directory
        module_dir = tmp_path / 'modules' / 'testmod'
        module_dir.mkdir(parents=True)
        lola_dir = module_dir / '.lola'
        lola_dir.mkdir()
        manifest = {'type': 'lola/module', 'version': '1.0.0', 'skills': ['missing']}
        (lola_dir / 'module.yml').write_text(yaml.dump(manifest))

        module = Module.from_path(module_dir)

        local_modules = tmp_path / '.lola' / 'modules'
        registry = InstallationRegistry(tmp_path / 'installed.yml')
        skill_dest = tmp_path / 'skills'

        with patch('lola.core.installer.ui', self.ui_mock), \
             patch('lola.core.installer.get_assistant_skill_path', return_value=skill_dest), \
             patch('lola.core.installer.get_assistant_command_path', return_value=None):

            count = install_to_assistant(
                module=module,
                assistant='claude-code',
                scope='user',
                project_path=None,
                local_modules=local_modules,
                registry=registry,
            )

        assert count == 0

    def test_install_missing_command_source(self, tmp_path):
        """Handle missing command source gracefully."""
        # Create module without actual command file
        module_dir = tmp_path / 'modules' / 'testmod'
        module_dir.mkdir(parents=True)
        lola_dir = module_dir / '.lola'
        lola_dir.mkdir()
        (module_dir / 'commands').mkdir()  # Empty commands dir
        manifest = {'type': 'lola/module', 'version': '1.0.0', 'commands': ['missing']}
        (lola_dir / 'module.yml').write_text(yaml.dump(manifest))

        module = Module.from_path(module_dir)

        local_modules = tmp_path / '.lola' / 'modules'
        registry = InstallationRegistry(tmp_path / 'installed.yml')
        command_dest = tmp_path / 'commands'

        with patch('lola.core.installer.ui', self.ui_mock), \
             patch('lola.core.installer.get_assistant_skill_path', return_value=None), \
             patch('lola.core.installer.get_assistant_command_path', return_value=command_dest):

            count = install_to_assistant(
                module=module,
                assistant='claude-code',
                scope='user',
                project_path=None,
                local_modules=local_modules,
                registry=registry,
            )

        assert count == 0
