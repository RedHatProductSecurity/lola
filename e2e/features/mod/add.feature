Feature: Module registration
  As a user, I want to register modules from various sources
  so that I can install them to my AI assistants.

  Scenario: Add a module from a local folder
    Given a module "my-module" with skills, commands, and agents
    When I run lola "mod add {module_path}"
    Then the exit code should be 0
    And the output should contain "Added my-module"
    And the directory "{lola_home}/modules/my-module" should exist

  Scenario: Add a module that already exists
    Given a module "my-module" with skills, commands, and agents
    And the module "my-module" is registered
    When I run lola "mod add {module_path}"
    Then the output should contain "already exists"

  Scenario: Add an Agent Plugins package by its manifest name
    Given an Agent Plugins package in "repository-name" named "manifest-name"
    When I run lola "mod add {module_path}"
    Then the exit code should be 0
    And the output should contain "Added manifest-name"
    And the directory "{lola_home}/modules/manifest-name" should exist
