"""Tests for sync CLI command."""

import pytest
from unittest.mock import patch

from lola.cli.sync import (
    sync_cmd,
    resolve_and_fetch_module,
    _fetch_from_marketplace_quiet,
)
from lola.sync import ModuleSpec


@pytest.fixture
def mock_sync_environment(tmp_path, mock_lola_home, sample_module):
    """Set up environment for sync command testing."""
    # Copy sample module to mock modules directory
    modules_dir = mock_lola_home["modules"]
    module_dest = modules_dir / "sample-module"
    import shutil

    shutil.copytree(sample_module, module_dest)

    # Create source info
    source_info_file = module_dest / ".lola-source.json"
    import json

    source_info_file.write_text(
        json.dumps(
            {
                "source": "https://example.com/sample-module.git",
                "source_type": "git",
            }
        )
    )

    # Create project directory
    project_dir = tmp_path / "project"
    project_dir.mkdir()

    # Patch additional paths for sync command
    with (
        patch("lola.cli.sync.MODULES_DIR", modules_dir),
        patch("lola.cli.sync.MARKET_DIR", mock_lola_home["home"] / "market"),
        patch("lola.cli.sync.CACHE_DIR", mock_lola_home["home"] / "market" / "cache"),
    ):
        yield {
            "project": project_dir,
            "modules": modules_dir,
            "home": mock_lola_home["home"],
        }


class TestSyncCommand:
    """Tests for sync command."""

    def test_sync_missing_config_file(self, cli_runner, tmp_path, mock_lola_home):
        """Test sync with missing config file."""
        project = tmp_path / "project"
        project.mkdir()

        with patch("lola.cli.sync.MODULES_DIR", mock_lola_home["modules"]):
            result = cli_runner.invoke(sync_cmd, [str(project)])

        assert result.exit_code != 0
        assert "Config file not found" in result.output

    def test_sync_empty_config_file(self, cli_runner, mock_sync_environment):
        """Test sync with empty config file."""
        project = mock_sync_environment["project"]
        lolareq = project / ".lola-req"
        lolareq.write_text("# Just comments\n\n")

        result = cli_runner.invoke(sync_cmd, [str(project)])

        assert result.exit_code == 0
        assert "No modules specified" in result.output

    def test_sync_installs_simple_module(self, cli_runner, mock_sync_environment):
        """Test sync installs a simple module."""
        project = mock_sync_environment["project"]
        lolareq = project / ".lola-req"
        lolareq.write_text("sample-module\n")

        result = cli_runner.invoke(sync_cmd, [str(project)])

        assert result.exit_code == 0
        assert "sample-module" in result.output
        assert "Installed:" in result.output or "installed" in result.output.lower()

    def test_sync_skips_already_installed(self, cli_runner, mock_sync_environment):
        """Test sync skips already installed modules."""
        project = mock_sync_environment["project"]
        lolareq = project / ".lola-req"
        lolareq.write_text("sample-module\n")

        # Install once
        result1 = cli_runner.invoke(sync_cmd, [str(project)])
        assert result1.exit_code == 0

        # Install again - should skip
        result2 = cli_runner.invoke(sync_cmd, [str(project)])
        assert result2.exit_code == 0
        assert "Skipped:" in result2.output or "skipped" in result2.output.lower()

    def test_sync_multiple_modules(self, cli_runner, mock_sync_environment, tmp_path):
        """Test sync with multiple modules."""
        # Create a second module
        modules_dir = mock_sync_environment["modules"]
        module2_src = tmp_path / "module2"
        module2_src.mkdir()
        skills_dir = module2_src / "skills" / "skill2"
        skills_dir.mkdir(parents=True)
        (skills_dir / "SKILL.md").write_text(
            "---\ndescription: Skill 2\n---\n\n# Skill 2"
        )

        import shutil

        shutil.copytree(module2_src, modules_dir / "module2")

        project = mock_sync_environment["project"]
        lolareq = project / ".lola-req"
        lolareq.write_text("sample-module\nmodule2\n")

        result = cli_runner.invoke(sync_cmd, [str(project)])

        assert result.exit_code == 0
        # Should install both
        assert "Installed: 2" in result.output or result.output.count("✓") >= 2

    def test_sync_with_comments_and_blanks(self, cli_runner, mock_sync_environment):
        """Test sync ignores comments and blank lines."""
        project = mock_sync_environment["project"]
        lolareq = project / ".lola-req"
        lolareq.write_text(
            """
# This is a comment
sample-module

# Another module would go here
"""
        )

        result = cli_runner.invoke(sync_cmd, [str(project)])

        assert result.exit_code == 0
        assert "sample-module" in result.output

    def test_sync_dry_run(self, cli_runner, mock_sync_environment):
        """Test sync with --dry-run flag."""
        project = mock_sync_environment["project"]
        lolareq = project / ".lola-req"
        lolareq.write_text("sample-module\n")

        result = cli_runner.invoke(sync_cmd, [str(project), "--dry-run"])

        assert result.exit_code == 0
        assert "Would install" in result.output

    def test_sync_verbose(self, cli_runner, mock_sync_environment):
        """Test sync with --verbose flag."""
        project = mock_sync_environment["project"]
        lolareq = project / ".lola-req"
        lolareq.write_text("sample-module\n")

        result = cli_runner.invoke(sync_cmd, [str(project), "-v"])

        assert result.exit_code == 0
        # Verbose should show more details

    def test_sync_custom_config_file(self, cli_runner, mock_sync_environment):
        """Test sync with custom config file path."""
        project = mock_sync_environment["project"]
        custom_file = project / "custom.lola-req"
        custom_file.write_text("sample-module\n")

        result = cli_runner.invoke(sync_cmd, [str(project), "--file", str(custom_file)])

        assert result.exit_code == 0
        assert "sample-module" in result.output

    def test_sync_nonexistent_module(self, cli_runner, mock_sync_environment):
        """Test sync with non-existent module."""
        project = mock_sync_environment["project"]
        lolareq = project / ".lola-req"
        lolareq.write_text("nonexistent-module\n")

        result = cli_runner.invoke(sync_cmd, [str(project)])

        assert result.exit_code != 0
        assert "Failed:" in result.output or "not found" in result.output.lower()

    def test_sync_continue_on_error(self, cli_runner, mock_sync_environment):
        """Test that sync continues when one module fails."""
        project = mock_sync_environment["project"]
        lolareq = project / ".lola-req"
        lolareq.write_text("nonexistent-module\nsample-module\n")

        result = cli_runner.invoke(sync_cmd, [str(project)])

        # Should fail overall but show summary
        assert "Failed:" in result.output
        # Sample-module might still be processed (depending on order)


class TestSyncWithAssistantFlag:
    """Tests for sync command with -a/--assistant flag."""

    def test_sync_with_assistant_flag(self, cli_runner, mock_sync_environment):
        """Test sync with -a flag installs only to specified assistant."""
        project = mock_sync_environment["project"]
        lolareq = project / ".lola-req"
        lolareq.write_text("sample-module\n")

        result = cli_runner.invoke(sync_cmd, [str(project), "-a", "claude-code"])

        assert result.exit_code == 0
        assert "sample-module" in result.output
        assert "claude-code" in result.output

    def test_sync_with_assistant_long_flag(self, cli_runner, mock_sync_environment):
        """Test sync with --assistant flag."""
        project = mock_sync_environment["project"]
        lolareq = project / ".lola-req"
        lolareq.write_text("sample-module\n")

        result = cli_runner.invoke(
            sync_cmd, [str(project), "--assistant", "claude-code"]
        )

        assert result.exit_code == 0
        assert "claude-code" in result.output

    def test_sync_assistant_flag_only_installs_specified(
        self, cli_runner, mock_sync_environment
    ):
        """Test that -a flag restricts to only the specified assistant."""
        project = mock_sync_environment["project"]
        lolareq = project / ".lola-req"
        lolareq.write_text("sample-module\n")

        result = cli_runner.invoke(sync_cmd, [str(project), "-a", "cursor"])

        assert result.exit_code == 0
        assert "cursor" in result.output
        assert "claude-code" not in result.output

    def test_sync_module_name_with_assistant_fragment(
        self, cli_runner, mock_sync_environment
    ):
        """Test that #assistant= fragment works on plain module names."""
        project = mock_sync_environment["project"]
        lolareq = project / ".lola-req"
        lolareq.write_text("sample-module#assistant=claude-code\n")

        result = cli_runner.invoke(sync_cmd, [str(project)])

        assert result.exit_code == 0
        assert "claude-code" in result.output

    def test_sync_invalid_assistant(self, cli_runner, mock_sync_environment):
        """Test sync with invalid assistant name."""
        project = mock_sync_environment["project"]
        lolareq = project / ".lola-req"
        lolareq.write_text("sample-module\n")

        result = cli_runner.invoke(sync_cmd, [str(project), "-a", "invalid-assistant"])

        assert result.exit_code != 0

    def test_sync_multiple_assistant_flags(self, cli_runner, mock_sync_environment):
        """Test sync with multiple -a flags installs to all specified assistants."""
        project = mock_sync_environment["project"]
        lolareq = project / ".lola-req"
        lolareq.write_text("sample-module\n")

        result = cli_runner.invoke(
            sync_cmd, [str(project), "-a", "cursor", "-a", "claude-code"]
        )

        assert result.exit_code == 0
        assert "cursor" in result.output
        assert "claude-code" in result.output

    def test_sync_without_assistant_installs_all(
        self, cli_runner, mock_sync_environment
    ):
        """Test sync without -a flag installs to all assistants."""
        project = mock_sync_environment["project"]
        lolareq = project / ".lola-req"
        lolareq.write_text("sample-module\n")

        result = cli_runner.invoke(sync_cmd, [str(project)])

        assert result.exit_code == 0
        assert "sample-module" in result.output
        # Without -a, output should include multiple target assistants
        assert "claude-code" in result.output
        assert "cursor" in result.output


class TestSyncWithVersions:
    """Tests for sync command with version constraints."""

    def test_sync_with_version_exact(self, cli_runner, mock_sync_environment):
        """Test sync with exact version constraint."""
        project = mock_sync_environment["project"]
        lolareq = project / ".lola-req"
        lolareq.write_text("sample-module==1.0.0\n")

        # This will fail since sample-module doesn't have version in registry
        # but tests the parsing
        _ = cli_runner.invoke(sync_cmd, [str(project)])

        # Either installs or shows version requirement
        # The actual behavior depends on whether version is available

    def test_sync_with_version_range(self, cli_runner, mock_sync_environment):
        """Test sync with version range constraint."""
        project = mock_sync_environment["project"]
        lolareq = project / ".lola-req"
        lolareq.write_text("sample-module>=1.0.0\n")

        _ = cli_runner.invoke(sync_cmd, [str(project)])

        # Should parse successfully (even if module doesn't have version)

    def test_sync_with_tilde_version(self, cli_runner, mock_sync_environment):
        """Test sync with tilde version constraint."""
        project = mock_sync_environment["project"]
        lolareq = project / ".lola-req"
        lolareq.write_text("sample-module~1.2\n")

        _ = cli_runner.invoke(sync_cmd, [str(project)])

        # Should parse tilde spec correctly

    def test_sync_with_caret_version(self, cli_runner, mock_sync_environment):
        """Test sync with caret version constraint."""
        project = mock_sync_environment["project"]
        lolareq = project / ".lola-req"
        lolareq.write_text("sample-module^1.2\n")

        _ = cli_runner.invoke(sync_cmd, [str(project)])

        # Should parse caret spec correctly


class TestSyncWithMarketplace:
    """Tests for sync command with marketplace integration."""

    def test_fetch_from_marketplace_quiet_renames_repository_folder_to_module_name(
        self, tmp_path
    ):
        """Sync marketplace fetches should use the marketplace module name."""
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
            patch("lola.cli.sync.MODULES_DIR", modules_dir),
            patch("lola.cli.sync.MARKET_DIR", market_dir),
            patch("lola.cli.sync.CACHE_DIR", cache_dir),
            patch("lola.cli.sync.save_source_info"),
        ):
            module_path, module_dict = _fetch_from_marketplace_quiet(
                "demo", "claude-md-management"
            )

        assert module_dict["name"] == "claude-md-management"
        assert module_path.name == "claude-md-management"
        assert module_path.exists()
        assert (modules_dir / "claude-md-management").exists()
        assert not (modules_dir / "anthropics-claude-plugins-official").exists()

    def test_sync_searches_marketplace_when_module_not_in_registry(
        self,
        cli_runner,
        tmp_path,
        mock_lola_home,
        sample_module,
        marketplace_with_modules,
    ):
        """Test that sync searches marketplaces when module is not in registry."""
        from unittest.mock import patch

        # Create project directory
        project = tmp_path / "project"
        project.mkdir()

        # Create .lola-req with module that's in marketplace but not in registry
        lolareq = project / ".lola-req"
        lolareq.write_text("git-tools\n")

        # Patch marketplace dirs and fetch function
        with (
            patch("lola.cli.sync.MODULES_DIR", mock_lola_home["modules"]),
            patch("lola.cli.sync.MARKET_DIR", marketplace_with_modules["market_dir"]),
            patch("lola.cli.sync.CACHE_DIR", marketplace_with_modules["cache_dir"]),
            patch("lola.cli.sync._fetch_from_marketplace_quiet") as mock_fetch,
            patch("lola.cli.sync.load_registered_module") as mock_load,
        ):
            # Set up mock_fetch to create the module when called
            git_tools_module = mock_lola_home["modules"] / "git-tools"

            def create_module(marketplace_name, module_name):
                git_tools_module.mkdir()
                skills = git_tools_module / "skills" / "git"
                skills.mkdir(parents=True)
                (skills / "SKILL.md").write_text(
                    "---\ndescription: Git tools\n---\n\n# Git Tools"
                )
                return git_tools_module, {"version": "1.0.0"}

            mock_fetch.side_effect = create_module

            # mock_load should return a valid Module object
            from lola.models import Module

            mock_load.side_effect = lambda path: Module.from_path(path)

            # Mock select_marketplace to return first marketplace automatically
            with patch(
                "lola.market.manager.MarketplaceRegistry.select_marketplace",
                return_value="official",
            ):
                result = cli_runner.invoke(sync_cmd, [str(project)])

            # Should have successfully installed from marketplace
            assert result.exit_code == 0
            assert "git-tools" in result.output
            mock_fetch.assert_called_once_with("official", "git-tools")

    def test_sync_searches_marketplace_user_cancels(
        self, cli_runner, tmp_path, mock_lola_home, marketplace_with_modules
    ):
        """Test that sync handles user cancellation when selecting marketplace."""
        from unittest.mock import patch

        # Create project directory
        project = tmp_path / "project"
        project.mkdir()

        # Create .lola-req with module that's in marketplace but not in registry
        lolareq = project / ".lola-req"
        lolareq.write_text("git-tools\n")

        # Patch marketplace dirs
        with (
            patch("lola.cli.sync.MODULES_DIR", mock_lola_home["modules"]),
            patch("lola.cli.sync.MARKET_DIR", marketplace_with_modules["market_dir"]),
            patch("lola.cli.sync.CACHE_DIR", marketplace_with_modules["cache_dir"]),
        ):
            # Mock select_marketplace to return None (user cancelled)
            with patch(
                "lola.market.manager.MarketplaceRegistry.select_marketplace",
                return_value=None,
            ):
                result = cli_runner.invoke(sync_cmd, [str(project)])

            # Should fail with cancellation message
            assert result.exit_code != 0
            assert "Failed:" in result.output or "cancelled" in result.output.lower()


class TestSyncWithGitUrls:
    """Tests for sync command with git+ URL syntax."""

    def test_sync_with_git_plus_https(self, cli_runner, mock_sync_environment):
        """Test sync with git+https:// URL."""
        from unittest.mock import patch

        project = mock_sync_environment["project"]
        lolareq = project / ".lola-req"
        lolareq.write_text("git+https://github.com/user/test-module.git\n")

        # Mock the fetch_module_as_name and detect_source_type functions
        with (
            patch("lola.cli.sync.fetch_module_as_name") as mock_fetch,
            patch("lola.cli.sync.detect_source_type") as mock_detect,
            patch("lola.cli.sync.save_source_info"),
            patch("lola.cli.sync.load_registered_module") as mock_load,
        ):
            mock_detect.return_value = "git"

            def create_module(source, dest, name, **kwargs):
                mod = dest / name
                mod.mkdir(parents=True, exist_ok=True)
                skills = mod / "skills" / "test"
                skills.mkdir(parents=True)
                (skills / "SKILL.md").write_text(
                    "---\ndescription: Test\n---\n\n# Test"
                )
                return mod

            mock_fetch.side_effect = create_module
            # mock_load should return a valid Module object
            from lola.models import Module

            mock_load.side_effect = lambda path: Module.from_path(path)

            _result = cli_runner.invoke(sync_cmd, [str(project)])

            # Should have stripped git+ prefix and used the URL
            mock_detect.assert_called_with("https://github.com/user/test-module.git")

    def test_sync_with_git_plus_ssh(self, cli_runner, mock_sync_environment):
        """Test sync with git+ssh:// URL."""
        from unittest.mock import patch

        project = mock_sync_environment["project"]
        lolareq = project / ".lola-req"
        lolareq.write_text("git+ssh://git@github.com/user/test-module.git\n")

        with (
            patch("lola.cli.sync.fetch_module_as_name") as mock_fetch,
            patch("lola.cli.sync.detect_source_type") as mock_detect,
            patch("lola.cli.sync.save_source_info"),
            patch("lola.cli.sync.load_registered_module") as mock_load,
        ):
            mock_detect.return_value = "git"

            def create_module(source, dest, name, **kwargs):
                mod = dest / name
                mod.mkdir(parents=True, exist_ok=True)
                skills = mod / "skills" / "test"
                skills.mkdir(parents=True)
                (skills / "SKILL.md").write_text(
                    "---\ndescription: Test\n---\n\n# Test"
                )
                return mod

            mock_fetch.side_effect = create_module
            # mock_load should return a valid Module object
            from lola.models import Module

            mock_load.side_effect = lambda path: Module.from_path(path)

            _result = cli_runner.invoke(sync_cmd, [str(project)])

            # Should have stripped git+ prefix
            mock_detect.assert_called_with("ssh://git@github.com/user/test-module.git")


class TestSyncSubdirectoryNameDerivation:
    """Regression tests for #177: subdirectory-aware module name derivation."""

    def _make_spec(self, url, subdirectory=None):
        """Build a ModuleSpec for a URL with optional subdirectory."""
        return ModuleSpec(
            raw_line=url,
            module_ref=url.split("#")[0] if "#" in url else url,
            subdirectory=subdirectory,
        )

    def _create_module_dir(self, modules_dir, name):
        """Create a minimal valid module directory."""
        mod = modules_dir / name
        mod.mkdir(parents=True, exist_ok=True)
        skills = mod / "skills" / "s"
        skills.mkdir(parents=True)
        (skills / "SKILL.md").write_text("---\ndescription: test\n---\n")
        return mod

    def test_subdirectory_uses_basename_as_module_name(self, tmp_path):
        """Module name comes from subdirectory basename, not URL."""
        modules_dir = tmp_path / "modules"
        modules_dir.mkdir()

        spec = self._make_spec(
            "https://github.com/quay/ai-helpers.git",
            subdirectory="plugins/dev",
        )

        with (
            patch("lola.cli.sync.MODULES_DIR", modules_dir),
            patch("lola.cli.sync.fetch_module_as_name") as mock_fetch,
            patch("lola.cli.sync.detect_source_type", return_value="git"),
            patch("lola.cli.sync.save_source_info"),
        ):
            mock_fetch.side_effect = lambda src, dest, name, **kw: (
                self._create_module_dir(dest, name)
            )
            name, _ = resolve_and_fetch_module(spec, verbose=False)

        assert name == "ai-helpers-dev"
        mock_fetch.assert_called_once()
        assert mock_fetch.call_args.args[2] == "ai-helpers-dev"

    def test_no_subdirectory_uses_url_stem(self, tmp_path):
        """Without subdirectory, module name comes from URL stem."""
        modules_dir = tmp_path / "modules"
        modules_dir.mkdir()

        spec = self._make_spec("https://github.com/quay/ai-helpers.git")

        with (
            patch("lola.cli.sync.MODULES_DIR", modules_dir),
            patch("lola.cli.sync.fetch_module_as_name") as mock_fetch,
            patch("lola.cli.sync.detect_source_type", return_value="git"),
            patch("lola.cli.sync.save_source_info"),
        ):
            mock_fetch.side_effect = lambda src, dest, name, **kw: (
                self._create_module_dir(dest, name)
            )
            name, _ = resolve_and_fetch_module(spec, verbose=False)

        assert name == "ai-helpers"
        mock_fetch.assert_called_once()
        assert mock_fetch.call_args.args[2] == "ai-helpers"

    def test_two_subdirectories_same_repo_get_distinct_names(self, tmp_path):
        """Two entries from the same repo with different subdirectories get distinct names."""
        modules_dir = tmp_path / "modules"
        modules_dir.mkdir()

        spec1 = self._make_spec(
            "https://github.com/quay/ai-helpers.git",
            subdirectory="plugins/dev",
        )
        spec2 = self._make_spec(
            "https://github.com/quay/ai-helpers.git",
            subdirectory="plugins/jira-planning",
        )

        with (
            patch("lola.cli.sync.MODULES_DIR", modules_dir),
            patch("lola.cli.sync.fetch_module_as_name") as mock_fetch,
            patch("lola.cli.sync.detect_source_type", return_value="git"),
            patch("lola.cli.sync.save_source_info"),
        ):
            mock_fetch.side_effect = lambda src, dest, name, **kw: (
                self._create_module_dir(dest, name)
            )

            name1, _ = resolve_and_fetch_module(spec1, verbose=False)
            name2, _ = resolve_and_fetch_module(spec2, verbose=False)

        assert name1 == "ai-helpers-dev"
        assert name2 == "ai-helpers-jira-planning"
        assert name1 != name2

    def test_root_subdirectory_falls_back_to_url_stem(self, tmp_path):
        """Edge case: #subdirectory=/ falls back to URL stem."""
        modules_dir = tmp_path / "modules"
        modules_dir.mkdir()

        spec = self._make_spec(
            "https://github.com/quay/ai-helpers.git",
            subdirectory="/",
        )

        with (
            patch("lola.cli.sync.MODULES_DIR", modules_dir),
            patch("lola.cli.sync.fetch_module_as_name") as mock_fetch,
            patch("lola.cli.sync.detect_source_type", return_value="git"),
            patch("lola.cli.sync.save_source_info"),
        ):
            mock_fetch.side_effect = lambda src, dest, name, **kw: (
                self._create_module_dir(dest, name)
            )
            name, _ = resolve_and_fetch_module(spec, verbose=False)

        assert name == "ai-helpers"
        assert mock_fetch.call_args.args[2] == "ai-helpers"

    def test_deep_subdirectory_uses_repo_stem_plus_leaf(self, tmp_path):
        """Deep subdirectory path uses repo stem + leaf directory name."""
        modules_dir = tmp_path / "modules"
        modules_dir.mkdir()

        spec = self._make_spec(
            "https://github.com/quay/ai-helpers.git",
            subdirectory="a/b/c/mymod",
        )

        with (
            patch("lola.cli.sync.MODULES_DIR", modules_dir),
            patch("lola.cli.sync.fetch_module_as_name") as mock_fetch,
            patch("lola.cli.sync.detect_source_type", return_value="git"),
            patch("lola.cli.sync.save_source_info"),
        ):
            mock_fetch.side_effect = lambda src, dest, name, **kw: (
                self._create_module_dir(dest, name)
            )
            name, _ = resolve_and_fetch_module(spec, verbose=False)

        assert name == "ai-helpers-mymod"

    def test_trailing_slash_subdirectory(self, tmp_path):
        """Trailing slash on subdirectory is handled correctly."""
        modules_dir = tmp_path / "modules"
        modules_dir.mkdir()

        spec = self._make_spec(
            "https://github.com/quay/ai-helpers.git",
            subdirectory="plugins/dev/",
        )

        with (
            patch("lola.cli.sync.MODULES_DIR", modules_dir),
            patch("lola.cli.sync.fetch_module_as_name") as mock_fetch,
            patch("lola.cli.sync.detect_source_type", return_value="git"),
            patch("lola.cli.sync.save_source_info"),
        ):
            mock_fetch.side_effect = lambda src, dest, name, **kw: (
                self._create_module_dir(dest, name)
            )
            name, _ = resolve_and_fetch_module(spec, verbose=False)

        assert name == "ai-helpers-dev"
