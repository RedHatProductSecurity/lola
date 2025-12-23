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
def sample_module_with_instructions(tmp_path):
    """Create a sample module with AGENTS.md instructions for testing."""
    module_dir = tmp_path / "sample-module"
    module_dir.mkdir()

    # Create skill directory
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

    # Create command file
    commands_dir = module_dir / "commands"
    commands_dir.mkdir()
    (commands_dir / "cmd1.md").write_text("""---
description: A test command
---

Do something with $ARGUMENTS.
""")

    # Create agent file
    agents_dir = module_dir / "agents"
    agents_dir.mkdir()
    (agents_dir / "agent1.md").write_text("""---
name: agent1
description: A test agent
model: inherit
---

Instructions for the test agent.
""")

    # Create module instructions
    (module_dir / "AGENTS.md").write_text("""# Sample Module

This module provides sample skills, commands, and agents for testing.

## When to Use

- **Sample skill**: Use skill1 for sample operations
- **Sample command**: Use /cmd1 to do something
- **Sample agent**: Delegate to agent1 for complex tasks
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


@pytest.fixture
def sample_module_with_module_subdir(tmp_path):
    """Create a sample module with the new module/ subdirectory structure.

    Structure:
        sample-module/
        ├── README.md           # Repo-level documentation
        └── module/             # All lola-importable content
            ├── skills/
            │   └── skill1/
            │       └── SKILL.md
            ├── commands/
            │   └── cmd1.md
            ├── agents/
            │   └── agent1.md
            ├── mcps.json
            └── AGENTS.md
    """
    module_dir = tmp_path / "sample-module"
    module_dir.mkdir()

    # Create README.md at repo root
    (module_dir / "README.md").write_text("""# Sample Module

A sample module for testing the module/ subdirectory structure.
""")

    # Create module/ subdirectory for all lola content
    module_content_dir = module_dir / "module"
    module_content_dir.mkdir()

    # Create skill directory
    skills_dir = module_content_dir / "skills"
    skills_dir.mkdir()
    skill_dir = skills_dir / "skill1"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("""---
name: skill1
description: A test skill with module/ structure
---

# Skill 1

This is a test skill in the module/ subdirectory.
""")

    # Create command file
    commands_dir = module_content_dir / "commands"
    commands_dir.mkdir()
    (commands_dir / "cmd1.md").write_text("""---
description: A test command with module/ structure
argument-hint: "[args]"
---

Do something with $ARGUMENTS.
""")

    # Create agent file
    agents_dir = module_content_dir / "agents"
    agents_dir.mkdir()
    (agents_dir / "agent1.md").write_text("""---
description: A test agent with module/ structure
---

Instructions for the test agent.
""")

    # Create mcps.json
    import json

    (module_content_dir / "mcps.json").write_text(
        json.dumps(
            {
                "mcpServers": {
                    "test-server": {
                        "command": "npx",
                        "args": ["-y", "@test/server"],
                        "env": {"API_KEY": "${API_KEY}"},
                    }
                }
            },
            indent=2,
        )
    )

    # Create module instructions
    (module_content_dir / "AGENTS.md").write_text("""# Sample Module

This module provides sample skills, commands, and agents for testing.

## When to Use

- **Skill1**: Use skill1 for sample operations
- **Cmd1**: Use /sample-module.cmd1 to do something
- **Agent1**: Delegate to @sample-module.agent1 for complex tasks
""")

    return module_dir


@pytest.fixture
def legacy_module(tmp_path):
    """Create a legacy module WITHOUT module/ subdirectory (old structure).

    Structure:
        legacy-module/
        ├── skills/
        │   └── skill1/
        │       └── SKILL.md
        ├── commands/
        │   └── cmd1.md
        ├── agents/
        │   └── agent1.md
        └── AGENTS.md
    """
    module_dir = tmp_path / "legacy-module"
    module_dir.mkdir()

    # Create skill directory at root (legacy structure)
    skills_dir = module_dir / "skills"
    skills_dir.mkdir()
    skill_dir = skills_dir / "skill1"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("""---
name: skill1
description: A legacy test skill
---

# Skill 1

This is a legacy test skill.
""")

    # Create command file at root (legacy structure)
    commands_dir = module_dir / "commands"
    commands_dir.mkdir()
    (commands_dir / "cmd1.md").write_text("""---
description: A legacy test command
---

Do something with $ARGUMENTS.
""")

    # Create agent file at root (legacy structure)
    agents_dir = module_dir / "agents"
    agents_dir.mkdir()
    (agents_dir / "agent1.md").write_text("""---
description: A legacy test agent
---

Instructions for the legacy test agent.
""")

    # Create module instructions at root (legacy structure)
    (module_dir / "AGENTS.md").write_text("""# Legacy Module

This is a legacy module structure.
""")

    return module_dir


@pytest.fixture
def registered_module_with_module_subdir(
    mock_lola_home, sample_module_with_module_subdir
):
    """Create and register a module with module/ subdirectory in the mock LOLA_HOME."""
    import shutil

    dest = mock_lola_home["modules"] / "sample-module"
    shutil.copytree(sample_module_with_module_subdir, dest)

    return dest


@pytest.fixture
def marketplace_with_modules(tmp_path):
    """Create a marketplace with test modules."""
    import yaml

    market_dir = tmp_path / "market"
    cache_dir = market_dir / "cache"
    market_dir.mkdir(parents=True)
    cache_dir.mkdir(parents=True)

    ref_data = {
        "name": "official",
        "url": "https://example.com/market.yml",
        "enabled": True,
    }
    cache_data = {
        "name": "Official Marketplace",
        "description": "Official catalog",
        "version": "1.0.0",
        "url": "https://example.com/market.yml",
        "enabled": True,
        "modules": [
            {
                "name": "git-tools",
                "description": "Git utilities",
                "version": "1.0.0",
                "repository": "https://github.com/test/git-tools.git",
            },
            {
                "name": "python-utils",
                "description": "Python utilities",
                "version": "1.2.0",
                "repository": "https://github.com/test/python-utils.git",
            },
        ],
    }

    with open(market_dir / "official.yml", "w") as f:
        yaml.dump(ref_data, f)
    with open(cache_dir / "official.yml", "w") as f:
        yaml.dump(cache_data, f)

    return {"market_dir": market_dir, "cache_dir": cache_dir}


@pytest.fixture
def marketplace_disabled(tmp_path):
    """Create a disabled marketplace."""
    import yaml

    market_dir = tmp_path / "market"
    cache_dir = market_dir / "cache"
    market_dir.mkdir(parents=True)
    cache_dir.mkdir(parents=True)

    ref_data = {
        "name": "disabled-market",
        "url": "https://example.com/disabled.yml",
        "enabled": False,
    }
    cache_data = {
        "name": "Disabled Marketplace",
        "version": "1.0.0",
        "url": "https://example.com/disabled.yml",
        "enabled": False,
        "modules": [
            {
                "name": "test-module",
                "description": "Test module",
                "version": "1.0.0",
                "repository": "https://github.com/test/test.git",
            }
        ],
    }

    with open(market_dir / "disabled-market.yml", "w") as f:
        yaml.dump(ref_data, f)
    with open(cache_dir / "disabled-market.yml", "w") as f:
        yaml.dump(cache_data, f)

    return {"market_dir": market_dir, "cache_dir": cache_dir}
