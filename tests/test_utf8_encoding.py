"""Windows-safe UTF-8 (and BOM) reads for module files (#224)."""

from pathlib import Path

from lola.frontmatter import get_metadata, parse_file, validate_skill


def test_parse_file_with_emoji(tmp_path: Path):
    skill = tmp_path / "SKILL.md"
    skill.write_bytes(
        "---\nname: example\ndescription: test skill\n---\n⚠️ warning\n".encode("utf-8")
    )
    meta, body = parse_file(skill)
    assert meta.get("name") == "example"
    assert "⚠️" in body
    assert "warning" in body


def test_parse_file_with_utf8_bom(tmp_path: Path):
    skill = tmp_path / "SKILL.md"
    # BOM + frontmatter — without utf-8-sig, startswith("---") fails and
    # frontmatter.load() returns empty metadata without raising.
    skill.write_bytes(
        "\ufeff---\nname: example\ndescription: test skill\n---\nbody\n".encode("utf-8")
    )
    # validate_skill uses read_text + startswith("---")
    errors = validate_skill(skill)
    assert not any("Missing YAML frontmatter" in e for e in errors), errors

    # parse_file / get_metadata must also see the frontmatter fields
    meta, body = parse_file(skill)
    assert meta.get("name") == "example"
    assert meta.get("description") == "test skill"
    assert "body" in body
    assert get_metadata(skill).get("name") == "example"
