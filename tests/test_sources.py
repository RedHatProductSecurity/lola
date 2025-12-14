"""Tests for the sources module."""

import tarfile
import zipfile
from unittest.mock import patch, MagicMock

import pytest
import yaml

from lola.parsers import (
    download_file,
    validate_module_name,
    GitSourceHandler,
    ZipSourceHandler,
    TarSourceHandler,
    ZipUrlSourceHandler,
    TarUrlSourceHandler,
    FolderSourceHandler,
    fetch_module,
    detect_source_type,
    save_source_info,
    load_source_info,
    update_module,
    SOURCE_FILE,
)


class TestValidateModuleName:
    """Tests for validate_module_name()."""

    def test_valid_name(self):
        """Accept valid module names."""
        assert validate_module_name("mymodule") == "mymodule"
        assert validate_module_name("my-module") == "my-module"
        assert validate_module_name("my_module") == "my_module"
        assert validate_module_name("module123") == "module123"

    def test_empty_name(self):
        """Reject empty names."""
        with pytest.raises(ValueError, match="cannot be empty"):
            validate_module_name("")

    def test_path_traversal_dot(self):
        """Reject . and .. names."""
        with pytest.raises(ValueError, match="path traversal"):
            validate_module_name(".")
        with pytest.raises(ValueError, match="path traversal"):
            validate_module_name("..")

    def test_path_separators(self):
        """Reject names with path separators."""
        with pytest.raises(ValueError, match="path separators"):
            validate_module_name("foo/bar")
        with pytest.raises(ValueError, match="path separators"):
            validate_module_name("foo\\bar")

    def test_hidden_names(self):
        """Reject names starting with dot."""
        with pytest.raises(ValueError, match="cannot start with"):
            validate_module_name(".hidden")

    def test_control_characters(self):
        """Reject names with control characters."""
        with pytest.raises(ValueError, match="control characters"):
            validate_module_name("foo\x00bar")
        with pytest.raises(ValueError, match="control characters"):
            validate_module_name("foo\nbar")


class TestGitSourceHandler:
    """Tests for GitSourceHandler."""

    def setup_method(self):
        """Set up handler for tests."""
        self.handler = GitSourceHandler()

    def test_can_handle_git_extension(self):
        """Handle URLs ending with .git."""
        assert self.handler.can_handle("https://example.com/repo.git") is True
        assert self.handler.can_handle("git@example.com:user/repo.git") is True

    def test_can_handle_git_scheme(self):
        """Handle git:// and ssh:// schemes."""
        assert self.handler.can_handle("git://github.com/user/repo") is True
        assert self.handler.can_handle("ssh://git@github.com/user/repo") is True

    def test_can_handle_github(self):
        """Handle GitHub HTTPS URLs."""
        assert self.handler.can_handle("https://github.com/user/repo") is True

    def test_can_handle_gitlab(self):
        """Handle GitLab HTTPS URLs."""
        assert self.handler.can_handle("https://gitlab.com/user/repo") is True

    def test_can_handle_bitbucket(self):
        """Handle Bitbucket HTTPS URLs."""
        assert self.handler.can_handle("https://bitbucket.org/user/repo") is True

    def test_cannot_handle_random_url(self):
        """Don't handle random HTTP URLs."""
        assert self.handler.can_handle("https://example.com/somefile") is False

    def test_cannot_handle_local_path(self):
        """Don't handle local paths."""
        assert self.handler.can_handle("/path/to/folder") is False


class TestZipSourceHandler:
    """Tests for ZipSourceHandler."""

    def setup_method(self):
        """Set up handler for tests."""
        self.handler = ZipSourceHandler()

    def test_can_handle_existing_zip(self, tmp_path):
        """Handle existing zip files."""
        zip_file = tmp_path / "test.zip"
        with zipfile.ZipFile(zip_file, "w") as zf:
            zf.writestr("test.txt", "content")
        assert self.handler.can_handle(str(zip_file)) is True

    def test_cannot_handle_nonexistent_zip(self, tmp_path):
        """Don't handle nonexistent zip files."""
        zip_file = tmp_path / "nonexistent.zip"
        assert self.handler.can_handle(str(zip_file)) is False

    def test_cannot_handle_non_zip(self, tmp_path):
        """Don't handle non-zip files."""
        txt_file = tmp_path / "test.txt"
        txt_file.write_text("content")
        assert self.handler.can_handle(str(txt_file)) is False

    def test_fetch_simple_zip(self, tmp_path):
        """Fetch from a simple zip file."""
        # Create a zip file
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        zip_file = source_dir / "mymodule.zip"

        with zipfile.ZipFile(zip_file, "w") as zf:
            zf.writestr("mymodule/file.txt", "content")

        dest_dir = tmp_path / "dest"
        dest_dir.mkdir()

        result = self.handler.fetch(str(zip_file), dest_dir)

        assert result.exists()
        assert (result / "file.txt").exists()

    def test_fetch_zip_with_skill(self, tmp_path):
        """Fetch zip that contains a skill (SKILL.md)."""
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        zip_file = source_dir / "archive.zip"

        with zipfile.ZipFile(zip_file, "w") as zf:
            zf.writestr(
                "nested/mymodule/myskill/SKILL.md",
                "---\ndescription: test\n---\n# Skill",
            )

        dest_dir = tmp_path / "dest"
        dest_dir.mkdir()

        result = self.handler.fetch(str(zip_file), dest_dir)

        assert result.exists()
        assert (result / "myskill" / "SKILL.md").exists()


class TestTarSourceHandler:
    """Tests for TarSourceHandler."""

    def setup_method(self):
        """Set up handler for tests."""
        self.handler = TarSourceHandler()

    def test_can_handle_tar(self, tmp_path):
        """Handle .tar files."""
        tar_file = tmp_path / "test.tar"
        with tarfile.open(tar_file, "w"):
            pass  # Empty tar
        assert self.handler.can_handle(str(tar_file)) is True

    def test_can_handle_tar_gz(self, tmp_path):
        """Handle .tar.gz files."""
        tar_file = tmp_path / "test.tar.gz"
        with tarfile.open(tar_file, "w:gz"):
            pass
        assert self.handler.can_handle(str(tar_file)) is True

    def test_can_handle_tgz(self, tmp_path):
        """Handle .tgz files."""
        tar_file = tmp_path / "test.tgz"
        with tarfile.open(tar_file, "w:gz"):
            pass
        assert self.handler.can_handle(str(tar_file)) is True

    def test_can_handle_tar_bz2(self, tmp_path):
        """Handle .tar.bz2 files."""
        tar_file = tmp_path / "test.tar.bz2"
        with tarfile.open(tar_file, "w:bz2"):
            pass
        assert self.handler.can_handle(str(tar_file)) is True

    def test_cannot_handle_nonexistent_tar(self, tmp_path):
        """Don't handle nonexistent tar files."""
        tar_file = tmp_path / "nonexistent.tar.gz"
        assert self.handler.can_handle(str(tar_file)) is False

    def test_fetch_simple_tar(self, tmp_path):
        """Fetch from a simple tar file."""
        source_dir = tmp_path / "source"
        source_dir.mkdir()

        # Create content to tar
        content_dir = source_dir / "mymodule"
        content_dir.mkdir()
        (content_dir / "file.txt").write_text("content")

        tar_file = source_dir / "mymodule.tar.gz"
        with tarfile.open(tar_file, "w:gz") as tf:
            tf.add(content_dir, arcname="mymodule")

        dest_dir = tmp_path / "dest"
        dest_dir.mkdir()

        result = self.handler.fetch(str(tar_file), dest_dir)

        assert result.exists()
        assert (result / "file.txt").exists()


class TestZipUrlSourceHandler:
    """Tests for ZipUrlSourceHandler."""

    def setup_method(self):
        """Set up handler for tests."""
        self.handler = ZipUrlSourceHandler()

    def test_can_handle_http_zip(self):
        """Handle HTTP zip URLs."""
        assert self.handler.can_handle("http://example.com/file.zip") is True
        assert self.handler.can_handle("https://example.com/path/file.zip") is True

    def test_cannot_handle_local_zip(self, tmp_path):
        """Don't handle local zip files."""
        zip_file = tmp_path / "test.zip"
        assert self.handler.can_handle(str(zip_file)) is False

    def test_cannot_handle_non_zip_url(self):
        """Don't handle non-zip URLs."""
        assert self.handler.can_handle("https://example.com/file.tar.gz") is False
        assert self.handler.can_handle("https://github.com/user/repo") is False


class TestTarUrlSourceHandler:
    """Tests for TarUrlSourceHandler."""

    def setup_method(self):
        """Set up handler for tests."""
        self.handler = TarUrlSourceHandler()

    def test_can_handle_http_tar(self):
        """Handle HTTP tar URLs."""
        assert self.handler.can_handle("http://example.com/file.tar") is True
        assert self.handler.can_handle("https://example.com/file.tar.gz") is True
        assert self.handler.can_handle("https://example.com/file.tgz") is True
        assert self.handler.can_handle("https://example.com/file.tar.bz2") is True
        assert self.handler.can_handle("https://example.com/file.tar.xz") is True

    def test_cannot_handle_local_tar(self, tmp_path):
        """Don't handle local tar files."""
        tar_file = tmp_path / "test.tar.gz"
        assert self.handler.can_handle(str(tar_file)) is False

    def test_cannot_handle_zip_url(self):
        """Don't handle zip URLs."""
        assert self.handler.can_handle("https://example.com/file.zip") is False


class TestFolderSourceHandler:
    """Tests for FolderSourceHandler."""

    def setup_method(self):
        """Set up handler for tests."""
        self.handler = FolderSourceHandler()

    def test_can_handle_existing_folder(self, tmp_path):
        """Handle existing folders."""
        folder = tmp_path / "mymodule"
        folder.mkdir()
        assert self.handler.can_handle(str(folder)) is True

    def test_cannot_handle_nonexistent_folder(self, tmp_path):
        """Don't handle nonexistent folders."""
        folder = tmp_path / "nonexistent"
        assert self.handler.can_handle(str(folder)) is False

    def test_cannot_handle_file(self, tmp_path):
        """Don't handle files."""
        file = tmp_path / "test.txt"
        file.write_text("content")
        assert self.handler.can_handle(str(file)) is False

    def test_fetch_folder(self, tmp_path):
        """Fetch from a folder."""
        source_dir = tmp_path / "mymodule"
        source_dir.mkdir()
        (source_dir / "file.txt").write_text("content")
        (source_dir / "subdir").mkdir()
        (source_dir / "subdir" / "nested.txt").write_text("nested")

        dest_dir = tmp_path / "dest"
        dest_dir.mkdir()

        result = self.handler.fetch(str(source_dir), dest_dir)

        assert result.name == "mymodule"
        assert (result / "file.txt").exists()
        assert (result / "subdir" / "nested.txt").exists()

    def test_fetch_overwrites_existing(self, tmp_path):
        """Fetch overwrites existing destination."""
        source_dir = tmp_path / "mymodule"
        source_dir.mkdir()
        (source_dir / "new.txt").write_text("new content")

        dest_dir = tmp_path / "dest"
        dest_dir.mkdir()

        # Create existing destination
        existing = dest_dir / "mymodule"
        existing.mkdir()
        (existing / "old.txt").write_text("old content")

        result = self.handler.fetch(str(source_dir), dest_dir)

        assert (result / "new.txt").exists()
        assert not (result / "old.txt").exists()


class TestDetectSourceType:
    """Tests for detect_source_type()."""

    def test_detect_folder(self, tmp_path):
        """Detect folder source type."""
        folder = tmp_path / "mymodule"
        folder.mkdir()
        assert detect_source_type(str(folder)) == "folder"

    def test_detect_zip(self, tmp_path):
        """Detect zip source type."""
        zip_file = tmp_path / "test.zip"
        with zipfile.ZipFile(zip_file, "w") as zf:
            zf.writestr("test.txt", "content")
        assert detect_source_type(str(zip_file)) == "zip"

    def test_detect_tar(self, tmp_path):
        """Detect tar source type."""
        tar_file = tmp_path / "test.tar.gz"
        with tarfile.open(tar_file, "w:gz"):
            pass
        assert detect_source_type(str(tar_file)) == "tar"

    def test_detect_git(self):
        """Detect git source type."""
        assert detect_source_type("https://github.com/user/repo") == "git"
        assert detect_source_type("https://example.com/repo.git") == "git"

    def test_detect_zipurl(self):
        """Detect zip URL source type."""
        assert detect_source_type("https://example.com/file.zip") == "zipurl"

    def test_detect_tarurl(self):
        """Detect tar URL source type."""
        assert detect_source_type("https://example.com/file.tar.gz") == "tarurl"

    def test_detect_unknown(self, tmp_path):
        """Detect unknown source type."""
        file = tmp_path / "random.txt"
        file.write_text("content")
        assert detect_source_type(str(file)) == "unknown"


class TestFetchModule:
    """Tests for fetch_module()."""

    def test_fetch_from_folder(self, tmp_path):
        """Fetch module from folder."""
        source_dir = tmp_path / "mymodule"
        source_dir.mkdir()
        (source_dir / "file.txt").write_text("content")

        dest_dir = tmp_path / "dest"
        dest_dir.mkdir()

        result = fetch_module(str(source_dir), dest_dir)

        assert result.exists()
        assert (result / "file.txt").read_text() == "content"

    def test_fetch_from_zip(self, tmp_path):
        """Fetch module from zip file."""
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        zip_file = source_dir / "mymodule.zip"

        with zipfile.ZipFile(zip_file, "w") as zf:
            zf.writestr("mymodule/file.txt", "content")

        dest_dir = tmp_path / "dest"
        dest_dir.mkdir()

        result = fetch_module(str(zip_file), dest_dir)

        assert result.exists()

    def test_fetch_unsupported_source(self, tmp_path):
        """Raise error for unsupported source."""
        file = tmp_path / "random.txt"
        file.write_text("content")

        dest_dir = tmp_path / "dest"
        dest_dir.mkdir()

        with pytest.raises(ValueError, match="Cannot handle source"):
            fetch_module(str(file), dest_dir)


class TestSourceInfo:
    """Tests for save_source_info() and load_source_info()."""

    def test_save_and_load(self, tmp_path):
        """Save and load source info."""
        module_path = tmp_path / "mymodule"
        module_path.mkdir()

        save_source_info(module_path, "https://example.com/repo.git", "git")

        info = load_source_info(module_path)
        assert info is not None
        assert info["source"] == "https://example.com/repo.git"
        assert info["type"] == "git"

    def test_save_local_path_resolves(self, tmp_path):
        """Local paths are resolved to absolute paths."""
        module_path = tmp_path / "mymodule"
        module_path.mkdir()

        source_dir = tmp_path / "source"
        source_dir.mkdir()

        save_source_info(module_path, str(source_dir), "folder")

        info = load_source_info(module_path)
        assert info["source"] == str(source_dir.resolve())

    def test_load_nonexistent(self, tmp_path):
        """Load returns None for nonexistent module."""
        module_path = tmp_path / "nonexistent"
        info = load_source_info(module_path)
        assert info is None

    def test_creates_lola_dir(self, tmp_path):
        """Creates .lola directory if needed."""
        module_path = tmp_path / "mymodule"
        module_path.mkdir()

        save_source_info(module_path, "https://example.com", "git")

        assert (module_path / ".lola").exists()
        assert (module_path / SOURCE_FILE).exists()


class TestUpdateModule:
    """Tests for update_module()."""

    def test_update_from_folder(self, tmp_path):
        """Update module from folder source."""
        # Create source folder
        source_dir = tmp_path / "source" / "mymodule"
        source_dir.mkdir(parents=True)
        (source_dir / "original.txt").write_text("v1")

        # Create destination and initial copy
        dest_dir = tmp_path / "dest"
        dest_dir.mkdir()
        module_path = dest_dir / "mymodule"
        module_path.mkdir()
        (module_path / "original.txt").write_text("v1")
        save_source_info(module_path, str(source_dir), "folder")

        # Update source
        (source_dir / "original.txt").write_text("v2")
        (source_dir / "new.txt").write_text("new content")

        # Update module
        success, message = update_module(module_path)

        assert success is True
        assert "Updated" in message
        assert (module_path / "original.txt").read_text() == "v2"
        assert (module_path / "new.txt").exists()

    def test_update_no_source_info(self, tmp_path):
        """Update fails when no source info."""
        module_path = tmp_path / "mymodule"
        module_path.mkdir()

        success, message = update_module(module_path)

        assert success is False
        assert "No source information" in message

    def test_update_source_missing(self, tmp_path):
        """Update fails when source folder is missing."""
        module_path = tmp_path / "mymodule"
        module_path.mkdir()

        # Save info for nonexistent source
        nonexistent = tmp_path / "nonexistent"
        save_source_info(module_path, str(nonexistent), "folder")

        success, message = update_module(module_path)

        assert success is False
        assert "no longer exists" in message

    def test_update_invalid_source_info(self, tmp_path):
        """Update fails with invalid source info."""
        module_path = tmp_path / "mymodule"
        module_path.mkdir()

        # Write invalid source info
        source_file = module_path / SOURCE_FILE
        source_file.parent.mkdir(parents=True, exist_ok=True)
        with open(source_file, "w") as f:
            yaml.dump({"source": None, "type": None}, f)

        success, message = update_module(module_path)

        assert success is False
        assert "Invalid source" in message

    def test_update_unknown_source_type(self, tmp_path):
        """Update fails with unknown source type."""
        module_path = tmp_path / "mymodule"
        module_path.mkdir()

        source_file = module_path / SOURCE_FILE
        source_file.parent.mkdir(parents=True, exist_ok=True)
        with open(source_file, "w") as f:
            yaml.dump({"source": "something", "type": "unknowntype"}, f)

        success, message = update_module(module_path)

        assert success is False
        assert "Unknown source type" in message

    def test_update_zip_source_missing(self, tmp_path):
        """Update fails when zip source file is missing."""
        module_path = tmp_path / "mymodule"
        module_path.mkdir()

        nonexistent_zip = tmp_path / "nonexistent.zip"
        save_source_info(module_path, str(nonexistent_zip), "zip")

        success, message = update_module(module_path)

        assert success is False
        assert "no longer exists" in message

    def test_update_tar_source_missing(self, tmp_path):
        """Update fails when tar source file is missing."""
        module_path = tmp_path / "mymodule"
        module_path.mkdir()

        nonexistent_tar = tmp_path / "nonexistent.tar.gz"
        save_source_info(module_path, str(nonexistent_tar), "tar")

        success, message = update_module(module_path)

        assert success is False
        assert "no longer exists" in message

    def test_update_from_zip(self, tmp_path):
        """Update module from zip source."""
        # Create initial zip
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        zip_file = source_dir / "mymodule.zip"

        with zipfile.ZipFile(zip_file, "w") as zf:
            zf.writestr("mymodule/file.txt", "v1")

        # Create destination and initial copy
        dest_dir = tmp_path / "dest"
        dest_dir.mkdir()
        module_path = dest_dir / "mymodule"
        module_path.mkdir()
        (module_path / "file.txt").write_text("v1")
        save_source_info(module_path, str(zip_file), "zip")

        # Update zip
        with zipfile.ZipFile(zip_file, "w") as zf:
            zf.writestr("mymodule/file.txt", "v2")
            zf.writestr("mymodule/new.txt", "new content")

        # Update module
        success, message = update_module(module_path)

        assert success is True
        assert "Updated" in message

    def test_update_from_tar(self, tmp_path):
        """Update module from tar source."""
        # Create initial tar
        source_dir = tmp_path / "source"
        source_dir.mkdir()

        content_dir = source_dir / "mymodule"
        content_dir.mkdir()
        (content_dir / "file.txt").write_text("v1")

        tar_file = source_dir / "mymodule.tar.gz"
        with tarfile.open(tar_file, "w:gz") as tf:
            tf.add(content_dir, arcname="mymodule")

        # Create destination and initial copy
        dest_dir = tmp_path / "dest"
        dest_dir.mkdir()
        module_path = dest_dir / "mymodule"
        module_path.mkdir()
        (module_path / "file.txt").write_text("v1")
        save_source_info(module_path, str(tar_file), "tar")

        # Update tar
        (content_dir / "file.txt").write_text("v2")
        with tarfile.open(tar_file, "w:gz") as tf:
            tf.add(content_dir, arcname="mymodule")

        # Update module
        success, message = update_module(module_path)

        assert success is True
        assert "Updated" in message

    def test_update_renames_if_needed(self, tmp_path):
        """Update handles source name changes."""
        # Create source folder with different name
        source_dir = tmp_path / "source" / "newname"
        source_dir.mkdir(parents=True)
        (source_dir / "file.txt").write_text("content")

        # Create destination
        dest_dir = tmp_path / "dest"
        dest_dir.mkdir()
        module_path = dest_dir / "mymodule"
        module_path.mkdir()
        save_source_info(module_path, str(source_dir), "folder")

        # Update module
        success, message = update_module(module_path)

        assert success is True
        # Module should still be at original name
        assert (dest_dir / "mymodule").exists()


class TestDownloadFile:
    """Tests for download_file()."""

    def test_download_success(self, tmp_path):
        """Download file successfully."""
        dest_path = tmp_path / "downloaded.txt"

        with patch("lola.parsers.urlopen") as mock_urlopen:
            mock_response = MagicMock()
            mock_response.__enter__ = MagicMock(return_value=mock_response)
            mock_response.__exit__ = MagicMock(return_value=False)
            mock_response.read.side_effect = [b"test content", b""]
            mock_urlopen.return_value = mock_response

            download_file("https://example.com/file.txt", dest_path)

        mock_urlopen.assert_called_once()

    def test_download_url_error(self, tmp_path):
        """Raise error on URL failure."""
        from urllib.error import URLError

        dest_path = tmp_path / "downloaded.txt"

        with patch("lola.parsers.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = URLError("Connection failed")

            with pytest.raises(RuntimeError, match="Failed to download"):
                download_file("https://example.com/file.txt", dest_path)

    def test_download_generic_error(self, tmp_path):
        """Raise error on generic failure."""
        dest_path = tmp_path / "downloaded.txt"

        with patch("lola.parsers.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = Exception("Generic error")

            with pytest.raises(RuntimeError, match="Download error"):
                download_file("https://example.com/file.txt", dest_path)


class TestGitSourceHandlerFetch:
    """Tests for GitSourceHandler.fetch()."""

    def setup_method(self):
        """Set up handler for tests."""
        self.handler = GitSourceHandler()

    def test_fetch_success(self, tmp_path):
        """Clone git repository successfully."""
        dest_dir = tmp_path / "dest"
        dest_dir.mkdir()

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stderr="")

            # Mock the directory creation that git clone would do
            repo_dir = dest_dir / "repo"
            repo_dir.mkdir()
            (repo_dir / ".git").mkdir()

            self.handler.fetch("https://github.com/user/repo.git", dest_dir)

        assert mock_run.called
        assert "git" in mock_run.call_args[0][0]
        assert "clone" in mock_run.call_args[0][0]

    def test_fetch_strips_git_extension(self, tmp_path):
        """Strip .git extension from repo name."""
        dest_dir = tmp_path / "dest"
        dest_dir.mkdir()

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stderr="")

            # Mock directory creation
            repo_dir = dest_dir / "myrepo"
            repo_dir.mkdir()

            self.handler.fetch("https://github.com/user/myrepo.git", dest_dir)

        # Check the destination path passed to git clone
        call_args = mock_run.call_args[0][0]
        assert "myrepo" in call_args[-1]  # Last arg is destination
        assert ".git" not in call_args[-1]

    def test_fetch_clone_failure(self, tmp_path):
        """Raise error on clone failure."""
        dest_dir = tmp_path / "dest"
        dest_dir.mkdir()

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1, stderr="fatal: repository not found"
            )

            with pytest.raises(RuntimeError, match="Git clone failed"):
                self.handler.fetch("https://github.com/user/nonexistent.git", dest_dir)

    def test_fetch_removes_existing(self, tmp_path):
        """Remove existing directory before clone."""
        dest_dir = tmp_path / "dest"
        dest_dir.mkdir()

        # Create existing directory
        existing = dest_dir / "repo"
        existing.mkdir()
        (existing / "old_file.txt").write_text("old")

        def mock_clone(*args, **kwargs):
            # Simulate git clone creating the directory
            repo_dir = dest_dir / "repo"
            repo_dir.mkdir(exist_ok=True)
            (repo_dir / ".git").mkdir(exist_ok=True)
            return MagicMock(returncode=0, stderr="")

        with patch("subprocess.run", side_effect=mock_clone):
            self.handler.fetch("https://github.com/user/repo.git", dest_dir)

        # Old file should be gone (directory was removed before clone)
        assert not (dest_dir / "repo" / "old_file.txt").exists()


class TestZipSlipPrevention:
    """Tests for Zip Slip attack prevention."""

    def test_zip_safe_extract_blocks_traversal(self, tmp_path):
        """Block zip entries with path traversal."""
        handler = ZipSourceHandler()

        # Create a malicious zip with path traversal
        zip_file = tmp_path / "malicious.zip"
        with zipfile.ZipFile(zip_file, "w") as zf:
            # This creates an entry that tries to escape
            zf.writestr("../../../etc/passwd", "malicious content")

        dest_dir = tmp_path / "dest"
        dest_dir.mkdir()

        with pytest.raises(ValueError, match="Zip Slip"):
            handler.fetch(str(zip_file), dest_dir)


class TestTarSourceHandlerAdvanced:
    """Advanced tests for TarSourceHandler."""

    def setup_method(self):
        """Set up handler for tests."""
        self.handler = TarSourceHandler()

    def test_fetch_tar_with_skill(self, tmp_path):
        """Fetch tar that contains a skill (SKILL.md)."""
        source_dir = tmp_path / "source"
        source_dir.mkdir()

        # Create module structure with skill
        module_dir = source_dir / "nested" / "mymodule"
        module_dir.mkdir(parents=True)
        skill_dir = module_dir / "myskill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("---\ndescription: test\n---\n# Skill")

        # Create tar
        tar_file = source_dir / "archive.tar.gz"
        with tarfile.open(tar_file, "w:gz") as tf:
            tf.add(source_dir / "nested", arcname="nested")

        dest_dir = tmp_path / "dest"
        dest_dir.mkdir()

        result = self.handler.fetch(str(tar_file), dest_dir)

        assert result.exists()
        assert (result / "myskill" / "SKILL.md").exists()

    def test_fetch_strips_tar_extensions(self, tmp_path):
        """Strip various tar extensions from module name."""
        source_dir = tmp_path / "source"
        source_dir.mkdir()

        for ext, mode in [
            (".tar", "w"),
            (".tar.gz", "w:gz"),
            (".tgz", "w:gz"),
            (".tar.bz2", "w:bz2"),
            (".tar.xz", "w:xz"),
        ]:
            content_dir = source_dir / "content"
            content_dir.mkdir(exist_ok=True)
            (content_dir / "file.txt").write_text("content")

            tar_file = source_dir / f"mymodule{ext}"
            with tarfile.open(tar_file, mode) as tf:
                tf.add(content_dir, arcname="content")

            dest_dir = tmp_path / f"dest{ext.replace('.', '_')}"
            dest_dir.mkdir()

            result = self.handler.fetch(str(tar_file), dest_dir)
            # Module name should not have extension
            assert ext not in result.name
