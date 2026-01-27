"""Tests for agent support."""

from lola.models import Agent, Module
from lola.frontmatter import validate_agent
from lola.targets import get_target


class TestAgentModel:
    """Tests for the Agent dataclass."""

    def test_from_path_with_full_frontmatter(self, tmp_path):
        """Load agent from file with complete frontmatter."""
        agent_file = tmp_path / "test-agent.md"
        agent_file.write_text("""---
name: test-agent
description: A test agent for testing
model: sonnet
---

Agent instructions here.
""")
        agent = Agent.from_path(agent_file)
        assert agent.name == "test-agent"
        assert agent.description == "A test agent for testing"
        assert agent.model == "sonnet"

    def test_from_path_without_model(self, tmp_path):
        """Load agent without model field."""
        agent_file = tmp_path / "simple.md"
        agent_file.write_text("""---
description: Simple agent
---

Content.
""")
        agent = Agent.from_path(agent_file)
        assert agent.name == "simple"
        assert agent.description == "Simple agent"
        assert agent.model is None

    def test_from_path_nonexistent_file(self, tmp_path):
        """Load agent from nonexistent file."""
        agent_file = tmp_path / "missing.md"
        agent = Agent.from_path(agent_file)
        assert agent.name == "missing"
        assert agent.description is None
        assert agent.model is None


class TestModuleWithAgents:
    """Tests for Module with agents."""

    def test_from_path_auto_discovers_agents(self, tmp_path):
        """Module.from_path auto-discovers agents in agents/ directory."""
        module_dir = tmp_path / "mymodule"
        module_dir.mkdir()

        agents_dir = module_dir / "agents"
        agents_dir.mkdir()
        (agents_dir / "agent1.md").write_text("---\ndescription: Agent 1\n---\n")
        (agents_dir / "agent2.md").write_text("---\ndescription: Agent 2\n---\n")

        module = Module.from_path(module_dir)
        assert module is not None
        assert module.agents == ["agent1", "agent2"]

    def test_from_path_module_with_only_agents(self, tmp_path):
        """Module with only agents is valid."""
        module_dir = tmp_path / "agent-only"
        module_dir.mkdir()

        agents_dir = module_dir / "agents"
        agents_dir.mkdir()
        (agents_dir / "myagent.md").write_text("---\ndescription: My agent\n---\n")

        module = Module.from_path(module_dir)
        assert module is not None
        assert len(module.agents) == 1
        assert len(module.skills) == 0
        assert len(module.commands) == 0

    def test_get_agent_paths(self, tmp_path):
        """Get full paths to agents."""
        module = Module(
            name="test",
            path=tmp_path,
            content_path=tmp_path,
            agents=["agent1", "agent2"],
        )
        paths = module.get_agent_paths()
        assert len(paths) == 2
        assert paths[0] == tmp_path / "agents" / "agent1.md"
        assert paths[1] == tmp_path / "agents" / "agent2.md"

    def test_agents_not_confused_with_skills(self, tmp_path):
        """Ensure agents dir is not treated as a skill."""
        module_dir = tmp_path / "mixed"
        module_dir.mkdir()

        # Create a skill in skills/ directory
        skills_dir = module_dir / "skills"
        skills_dir.mkdir()
        skill_dir = skills_dir / "myskill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("---\ndescription: A skill\n---\n")

        # Create an agent
        agents_dir = module_dir / "agents"
        agents_dir.mkdir()
        (agents_dir / "myagent.md").write_text("---\ndescription: An agent\n---\n")

        module = Module.from_path(module_dir)
        assert module is not None
        assert module.skills == ["myskill"]
        assert module.agents == ["myagent"]
        # agents dir should NOT be in skills
        assert "agents" not in module.skills


class TestValidateAgentFrontmatter:
    """Tests for agent frontmatter validation."""

    def test_valid_frontmatter(self, tmp_path):
        """Validate valid agent file."""
        agent_file = tmp_path / "agent.md"
        agent_file.write_text("""---
description: My agent
model: opus
---

Content.
""")
        errors = validate_agent(agent_file)
        assert errors == []

    def test_missing_description(self, tmp_path):
        """Validate agent without required description."""
        agent_file = tmp_path / "agent.md"
        agent_file.write_text("""---
model: sonnet
---

Content.
""")
        errors = validate_agent(agent_file)
        assert len(errors) == 1
        assert "description" in errors[0].lower()

    def test_missing_frontmatter(self, tmp_path):
        """Validate agent without frontmatter."""
        agent_file = tmp_path / "agent.md"
        agent_file.write_text("Just content, no frontmatter.")
        errors = validate_agent(agent_file)
        assert len(errors) >= 1
        assert "frontmatter" in errors[0].lower()


class TestAgentConfig:
    """Tests for agent configuration."""

    def test_claude_code_supports_agents(self):
        """Claude Code supports agents."""
        target = get_target("claude-code")
        assert target.supports_agents is True

    def test_cursor_supports_agents(self):
        """Cursor 2.4+ supports subagents."""
        target = get_target("cursor")
        assert target.supports_agents is True

    def test_gemini_does_not_support_agents(self):
        """Gemini doesn't support agents."""
        target = get_target("gemini-cli")
        assert target.supports_agents is False

    def test_get_agent_path_claude_project(self, tmp_path):
        """Get Claude Code project agent path."""
        target = get_target("claude-code")
        path = target.get_agent_path(str(tmp_path))
        assert path == tmp_path / ".claude" / "agents"

    def test_get_agent_path_cursor_project(self, tmp_path):
        """Get Cursor project agent path (2.4+)."""
        target = get_target("cursor")
        path = target.get_agent_path(str(tmp_path))
        assert path == tmp_path / ".cursor" / "agents"

    def test_get_agent_path_gemini_returns_none(self):
        """Gemini's get_agent_path returns None."""
        target = get_target("gemini-cli")
        path = target.get_agent_path("/tmp")
        assert path is None


class TestAgentGenerator:
    """Tests for agent generator functions."""

    def test_generate_claude_agent(self, tmp_path):
        """Generate Claude agent file."""
        source = tmp_path / "source" / "myagent.md"
        source.parent.mkdir()
        source.write_text("""---
name: myagent
description: Test agent
model: inherit
---

Instructions.
""")

        target = get_target("claude-code")
        dest_dir = tmp_path / "dest"
        success = target.generate_agent(source, dest_dir, "myagent", "mymodule")

        assert success
        output_file = dest_dir / "mymodule.myagent.md"
        assert output_file.exists()
        content = output_file.read_text()
        # Claude Code requires name to match the filename for @agent-name references
        assert "name: mymodule.myagent" in content
        assert "Instructions." in content

    def test_generate_claude_agent_missing_source(self, tmp_path):
        """Generate fails gracefully for missing source."""
        target = get_target("claude-code")
        source = tmp_path / "missing.md"
        dest_dir = tmp_path / "dest"
        success = target.generate_agent(source, dest_dir, "myagent", "mymodule")
        assert not success

    def test_get_agent_filename(self):
        """Get properly formatted agent filename."""
        target = get_target("claude-code")
        filename = target.get_agent_filename("mymodule", "myagent")
        assert filename == "mymodule.myagent.md"
