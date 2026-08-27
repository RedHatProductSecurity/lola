Feature: Module initialization
  As a module author, I want to scaffold a new module
  so that I have a complete template to customize.

  Scenario: Initialize a new module
    When I run lola "mod init test-module"
    Then the exit code should be 0
    And the output should contain "Initialized module test-module"
    And the directory "{project}/test-module" should exist
    And the file "{project}/test-module/plugin.json" should exist

  Scenario: Initialize a module when directory already exists
    When I run lola "mod init test-module"
    And I run lola "mod init test-module"
    Then the exit code should be 1
    And the output should contain "already exists"

  Scenario: Initialize an Agent Plugins package by default
    When I run lola "mod init portable-plugin"
    Then the exit code should be 0
    And the file "{project}/portable-plugin/plugin.json" should exist
    And the file "{project}/portable-plugin/mcp.json" should exist
    And the file "{project}/portable-plugin/skills/example-skill/SKILL.md" should exist
    And the file "{project}/portable-plugin/dev.getlola/commands/example-command.md" should exist
    And the file "{project}/portable-plugin/dev.getlola/agents/example-agent.md" should exist

  Scenario: Initialize a legacy Lola module
    When I run lola "mod init legacy-module --format lola"
    Then the exit code should be 0
    And the file "{project}/legacy-module/module/mcps.json" should exist
    And the file "{project}/legacy-module/module/AGENTS.md" should exist
