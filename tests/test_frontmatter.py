"""Tests for the frontmatter module."""

from lola import frontmatter as fm


class TestParse:
    """Tests for fm.parse()"""

    def test_parse_with_frontmatter(self):
        """Parse content with valid frontmatter."""
        content = """---
description: Test description
argument-hint: "<arg>"
---

Body content here.
"""
        metadata, body = fm.parse(content)
        assert metadata["description"] == "Test description"
        assert metadata["argument-hint"] == "<arg>"
        assert "Body content here." in body

    def test_parse_without_frontmatter(self):
        """Parse content without frontmatter."""
        content = "Just plain content"
        metadata, body = fm.parse(content)
        assert metadata == {}
        assert body == content

    def test_parse_with_quoted_brackets(self):
        """Parse frontmatter with quoted brackets (YAML array syntax)."""
        content = """---
description: Test command
argument-hint: "[--flag] [--other]"
---

Content.
"""
        metadata, body = fm.parse(content)
        assert metadata["description"] == "Test command"
        assert metadata["argument-hint"] == "[--flag] [--other]"

    def test_parse_empty_frontmatter(self):
        """Parse content with empty frontmatter."""
        content = """---
---

Body.
"""
        metadata, body = fm.parse(content)
        assert metadata == {}
        assert "Body." in body


class TestParseFile:
    """Tests for fm.parse_file()"""

    def test_parse_file_exists(self, tmp_path):
        """Parse a file that exists."""
        test_file = tmp_path / "test.md"
        test_file.write_text("""---
name: test
description: A test file
---

Content here.
""")
        metadata, body = fm.parse_file(test_file)
        assert metadata["name"] == "test"
        assert metadata["description"] == "A test file"
        assert "Content here." in body

    def test_parse_file_not_exists(self, tmp_path):
        """Parse a file that doesn't exist."""
        test_file = tmp_path / "nonexistent.md"
        metadata, body = fm.parse_file(test_file)
        assert metadata == {}
        assert body == ""


class TestValidateCommand:
    """Tests for fm.validate_command()"""

    def test_valid_command(self, tmp_path):
        """Validate a properly formatted command file."""
        cmd_file = tmp_path / "test.md"
        cmd_file.write_text("""---
description: A test command
argument-hint: "<arg>"
---

Command instructions.
""")
        errors = fm.validate_command(cmd_file)
        assert errors == []

    def test_missing_frontmatter(self, tmp_path):
        """Validate command without frontmatter."""
        cmd_file = tmp_path / "test.md"
        cmd_file.write_text("Just content, no frontmatter.")
        errors = fm.validate_command(cmd_file)
        assert len(errors) == 1
        assert "Missing frontmatter" in errors[0]

    def test_missing_description(self, tmp_path):
        """Validate command with missing description."""
        cmd_file = tmp_path / "test.md"
        cmd_file.write_text("""---
argument-hint: "<arg>"
---

Content.
""")
        errors = fm.validate_command(cmd_file)
        assert len(errors) == 1
        assert "description" in errors[0].lower()

    def test_unquoted_brackets_parsed_as_array(self, tmp_path):
        """Unquoted brackets are parsed as YAML array (not string)."""
        cmd_file = tmp_path / "test.md"
        cmd_file.write_text("""---
description: Test
argument-hint: [--flag]
---

Content.
""")
        # python-frontmatter parses [--flag] as a list, not a string
        # This is valid YAML, just not what the user intended
        metadata = fm.get_metadata(cmd_file)
        # The value is parsed as a list, not a string
        assert isinstance(metadata.get("argument-hint"), list)


class TestGetDescription:
    """Tests for fm.get_description()"""

    def test_get_description_exists(self, tmp_path):
        """Get description from file with description."""
        test_file = tmp_path / "test.md"
        test_file.write_text("""---
description: My description
---

Content.
""")
        desc = fm.get_description(test_file)
        assert desc == "My description"

    def test_get_description_missing(self, tmp_path):
        """Get description from file without description."""
        test_file = tmp_path / "test.md"
        test_file.write_text("""---
name: test
---

Content.
""")
        desc = fm.get_description(test_file)
        assert desc is None

    def test_get_description_no_file(self, tmp_path):
        """Get description from nonexistent file."""
        test_file = tmp_path / "nonexistent.md"
        desc = fm.get_description(test_file)
        assert desc is None


class TestGetMetadata:
    """Tests for fm.get_metadata()"""

    def test_get_metadata(self, tmp_path):
        """Get all metadata from file."""
        test_file = tmp_path / "test.md"
        test_file.write_text("""---
name: myskill
description: A skill
version: 1.0.0
---

Content.
""")
        metadata = fm.get_metadata(test_file)
        assert metadata["name"] == "myskill"
        assert metadata["description"] == "A skill"
        assert metadata["version"] == "1.0.0"
