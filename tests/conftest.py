"""Shared pytest fixtures for lola tests."""

from unittest.mock import patch

import pytest
from click.testing import CliRunner


@pytest.fixture
def cli_runner():
    """Provide a Click CLI test runner."""
    return CliRunner()


@pytest.fixture
def isolated_cli_runner():
    """Provide an isolated Click CLI test runner with temp directory."""
    runner = CliRunner()
    with runner.isolated_filesystem():
        yield runner


@pytest.fixture
def mock_lola_home(tmp_path):
    """Create a mock LOLA_HOME directory structure."""
    lola_home = tmp_path / ".lola"
    modules_dir = lola_home / "modules"
    modules_dir.mkdir(parents=True)

    with (
        patch("lola.config.LOLA_HOME", lola_home),
        patch("lola.config.MODULES_DIR", modules_dir),
        patch("lola.config.INSTALLED_FILE", lola_home / "installed.yml"),
        patch("lola.cli.mod.MODULES_DIR", modules_dir),
        patch("lola.cli.mod.INSTALLED_FILE", lola_home / "installed.yml"),
        patch("lola.cli.install.MODULES_DIR", modules_dir),
    ):
        yield {
            "home": lola_home,
            "modules": modules_dir,
            "installed": lola_home / "installed.yml",
        }


@pytest.fixture
def sample_module(tmp_path):
    """Create a sample module for testing."""
    module_dir = tmp_path / "sample-module"
    module_dir.mkdir()

    # Create skill directory (preferred structure: skills/<name>/SKILL.md)
    skills_dir = module_dir / "skills"
    skills_dir.mkdir()
    skill_dir = skills_dir / "skill1"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("""---
description: A test skill
---

# Skill 1

This is a test skill.
""")

    # Create command file (auto-discovered from commands/*.md)
    commands_dir = module_dir / "commands"
    commands_dir.mkdir()
    (commands_dir / "cmd1.md").write_text("""---
description: A test command
---

Do something with $ARGUMENTS.
""")

    # Create agent file (auto-discovered from agents/*.md)
    agents_dir = module_dir / "agents"
    agents_dir.mkdir()
    (agents_dir / "agent1.md").write_text("""---
name: agent1
description: A test agent
model: inherit
---

Instructions for the test agent.
""")

    return module_dir


@pytest.fixture
def registered_module(mock_lola_home, sample_module):
    """Create and register a module in the mock LOLA_HOME."""
    import shutil

    dest = mock_lola_home["modules"] / "sample-module"
    shutil.copytree(sample_module, dest)

    return dest


@pytest.fixture
def mock_assistant_paths(tmp_path):
    """Create mock assistant paths for testing installations."""
    paths = {
        "claude-code": {
            "skills": tmp_path / ".claude" / "skills",
            "commands": tmp_path / ".claude" / "commands",
            "agents": tmp_path / ".claude" / "agents",
        },
        "cursor": {
            "skills": tmp_path / ".cursor" / "rules",
            "commands": tmp_path / ".cursor" / "commands",
        },
        "gemini-cli": {
            "skills": tmp_path / ".gemini" / "GEMINI.md",
            "commands": tmp_path / ".gemini" / "commands",
        },
    }

    # Create directories
    for assistant, dirs in paths.items():
        if assistant != "gemini-cli":
            dirs["skills"].mkdir(parents=True, exist_ok=True)
        else:
            dirs["skills"].parent.mkdir(parents=True, exist_ok=True)
        dirs["commands"].mkdir(parents=True, exist_ok=True)
        if "agents" in dirs:
            dirs["agents"].mkdir(parents=True, exist_ok=True)

    return paths
