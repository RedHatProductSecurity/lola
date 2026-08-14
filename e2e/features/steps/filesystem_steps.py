"""Step definitions for filesystem preconditions and assertions."""

import json
from pathlib import Path

from behave import given, then

from support.cli import resolve_path
from support.fixtures import (
    create_module_full,
    register_module,
)


@given('a module "{name}" with skills, commands, and agents')
def step_module_full(context, name):
    """Create a module source directory with one skill, command, and agent."""
    source_dir = context.tmp_dir / "sources"
    source_dir.mkdir(exist_ok=True)
    module_path = create_module_full(source_dir, name)
    context.modules[name] = module_path


@given('an Agent Plugins package in "{directory}" named "{name}"')
def step_agent_plugin(context, directory, name):
    """Create a portable plugin whose directory and manifest names differ."""
    source_dir = context.tmp_dir / "sources" / directory
    skill_dir = source_dir / "skills" / "skill1"
    skill_dir.mkdir(parents=True)
    (source_dir / "plugin.json").write_text(
        json.dumps(
            {
                "$schema": (
                    "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"
                ),
                "name": name,
            }
        )
    )
    (skill_dir / "SKILL.md").write_text(
        "---\nname: skill1\ndescription: Test skill\n---\n"
    )
    context.modules[name] = source_dir


@given('the module "{name}" is registered')
def step_module_registered(context, name):
    """Copy a module into LOLA_HOME/modules/ to simulate `lola mod add`."""
    assert name in context.modules, (
        f'Module "{name}" not set up. '
        f"Add a preceding 'Given a module \"{name}\" with ...' step."
    )
    register_module(context.lola_home, context.modules[name], name)


@then('the directory "{path}" should exist')
def step_dir_exists(context, path):
    """Assert that a directory exists at the resolved path."""
    resolved = resolve_path(context, path)
    assert Path(resolved).is_dir(), f"Expected directory to exist: {resolved}"


@then('the directory "{path}" should not exist')
def step_dir_not_exists(context, path):
    """Assert that no directory exists at the resolved path."""
    resolved = resolve_path(context, path)
    assert not Path(resolved).is_dir(), f"Expected directory NOT to exist: {resolved}"


@given('the module "{name}" is installed to "{assistant}"')
def step_module_installed(context, name, assistant):
    """Register a module and install it to an assistant via the CLI."""
    assert name in context.modules, (
        f'Module "{name}" not set up. '
        f"Add a preceding 'Given a module \"{name}\" with ...' step."
    )
    register_module(context.lola_home, context.modules[name], name)
    result = context.cli.run("install", name, "-a", assistant)
    assert result.exit_code == 0, (
        f"Failed to install {name} to {assistant}.\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )


@then('the file "{path}" should exist')
def step_file_exists(context, path):
    """Assert that a file exists at the resolved path."""
    resolved = resolve_path(context, path)
    assert Path(resolved).is_file(), f"Expected file to exist: {resolved}"
