"""
sources:
    Module source handlers for git repos, zip files, tar files, and folders
"""

import os
import shutil
import subprocess
import tarfile
import tempfile
import zipfile
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse
from urllib.request import urlopen
from urllib.error import URLError

import yaml

from lola.config import SKILL_FILE


def download_file(url: str, dest_path: Path) -> None:
    """
    Download a file from a URL to a local path.

    Args:
        url: URL to download from
        dest_path: Local path to save the file

    Raises:
        RuntimeError: If download fails
    """
    try:
        with urlopen(url, timeout=60) as response:
            with open(dest_path, "wb") as f:
                shutil.copyfileobj(response, f)
    except URLError as e:
        raise RuntimeError(f"Failed to download {url}: {e}")
    except Exception as e:
        raise RuntimeError(f"Download error: {e}")


# File to track module source for updates
SOURCE_FILE = ".lola/source.yml"


def validate_module_name(name: str) -> str:
    """
    Validate and sanitize a module name to prevent directory traversal attacks.

    Args:
        name: The proposed module name

    Returns:
        The validated module name

    Raises:
        ValueError: If the name is invalid or potentially malicious
    """
    if not name:
        raise ValueError("Module name cannot be empty")

    # Reject path traversal attempts
    if name in (".", ".."):
        raise ValueError(f"Invalid module name: '{name}' (path traversal not allowed)")

    if "/" in name or "\\" in name:
        raise ValueError(f"Invalid module name: '{name}' (path separators not allowed)")

    # Reject names starting with . (hidden files/special dirs)
    if name.startswith("."):
        raise ValueError(f"Invalid module name: '{name}' (cannot start with '.')")

    # Reject names with null bytes or other control characters
    if any(ord(c) < 32 for c in name):
        raise ValueError(
            f"Invalid module name: '{name}' (control characters not allowed)"
        )

    return name


class SourceHandler(ABC):
    """Base class for module source handlers."""

    @abstractmethod
    def can_handle(self, source: str) -> bool:
        """Check if this handler can handle the given source."""
        pass

    @abstractmethod
    def fetch(self, source: str, dest_dir: Path) -> Path:
        """
        Fetch module from source to destination directory.

        Args:
            source: Source location (URL, path, etc.)
            dest_dir: Directory to store the fetched module

        Returns:
            Path to the fetched module directory
        """
        pass


class GitSourceHandler(SourceHandler):
    """Handler for git repository sources."""

    def can_handle(self, source: str) -> bool:
        """Check if source is a git URL or ends with .git."""
        if source.endswith(".git"):
            return True
        parsed = urlparse(source)
        if parsed.scheme in ("git", "ssh"):
            return True
        if parsed.scheme in ("http", "https") and (
            "github.com" in source
            or "gitlab.com" in source
            or "bitbucket.org" in source
        ):
            return True
        return False

    def fetch(self, source: str, dest_dir: Path) -> Path:
        """Clone git repository to destination."""
        # Extract repo name from URL
        repo_name = source.rstrip("/").split("/")[-1]
        if repo_name.endswith(".git"):
            repo_name = repo_name[:-4]

        # Validate module name to prevent directory traversal
        repo_name = validate_module_name(repo_name)

        module_dir = dest_dir / repo_name

        if module_dir.exists():
            shutil.rmtree(module_dir)

        # Clone the repository
        result = subprocess.run(
            ["git", "clone", "--depth", "1", source, str(module_dir)],
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            raise RuntimeError(f"Git clone failed: {result.stderr}")

        # Remove .git directory to save space
        git_dir = module_dir / ".git"
        if git_dir.exists():
            shutil.rmtree(git_dir)

        return module_dir


class ZipSourceHandler(SourceHandler):
    """Handler for zip file sources."""

    def can_handle(self, source: str) -> bool:
        """Check if source is a zip file."""
        return source.endswith(".zip") and Path(source).exists()

    def fetch(self, source: str, dest_dir: Path) -> Path:
        """Extract zip file to destination."""
        source_path = Path(source)

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)

            with zipfile.ZipFile(source_path, "r") as zf:
                self._safe_extract(zf, tmp_path)

            # Find the module directory (may be nested)
            module_dir = self._find_module_dir(tmp_path)
            if not module_dir:
                # Use the extracted contents directly
                contents = list(tmp_path.iterdir())
                if len(contents) == 1 and contents[0].is_dir():
                    module_dir = contents[0]
                else:
                    module_dir = tmp_path

            # Determine module name
            module_name = module_dir.name
            if module_name == tmp_path.name:
                module_name = source_path.stem

            # Validate module name to prevent directory traversal
            module_name = validate_module_name(module_name)

            final_dir = dest_dir / module_name
            if final_dir.exists():
                shutil.rmtree(final_dir)

            shutil.copytree(module_dir, final_dir)

        return final_dir

    def _find_module_dir(self, root: Path) -> Optional[Path]:
        """Find directory containing skills (SKILL.md) or commands."""
        # First, try to find a SKILL.md anywhere
        for path in root.rglob(SKILL_FILE):
            # Return the parent of the skill folder (the module)
            return path.parent.parent

        # Or look for a commands/ directory with .md files
        for path in root.rglob("commands"):
            if path.is_dir() and list(path.glob("*.md")):
                return path.parent

        return None

    def _safe_extract(self, zf: zipfile.ZipFile, dest: Path) -> None:
        """Safely extract zip contents, preventing Zip Slip attacks."""
        dest = dest.resolve()
        for member in zf.namelist():
            # Normalize the path and check for traversal
            member_path = (dest / member).resolve()
            if (
                not str(member_path).startswith(str(dest) + os.sep)
                and member_path != dest
            ):
                raise ValueError(f"Zip Slip attack detected: {member}")
        # All members are safe, extract them
        zf.extractall(dest)


class TarSourceHandler(SourceHandler):
    """Handler for tar/tar.gz/tar.bz2 file sources."""

    def can_handle(self, source: str) -> bool:
        """Check if source is a tar file."""
        source_lower = source.lower()
        is_tar = (
            source_lower.endswith(".tar")
            or source_lower.endswith(".tar.gz")
            or source_lower.endswith(".tgz")
            or source_lower.endswith(".tar.bz2")
            or source_lower.endswith(".tar.xz")
        )
        return is_tar and Path(source).exists()

    def fetch(self, source: str, dest_dir: Path) -> Path:
        """Extract tar file to destination."""
        source_path = Path(source)

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)

            with tarfile.open(source_path, "r:*") as tf:
                tf.extractall(tmp_path, filter="data")

            # Find the module directory (may be nested)
            module_dir = self._find_module_dir(tmp_path)
            if not module_dir:
                # Use the extracted contents directly
                contents = list(tmp_path.iterdir())
                if len(contents) == 1 and contents[0].is_dir():
                    module_dir = contents[0]
                else:
                    module_dir = tmp_path

            # Determine module name
            module_name = module_dir.name
            if module_name == tmp_path.name:
                # Strip extensions from source name
                module_name = source_path.name
                for ext in [".tar.gz", ".tgz", ".tar.bz2", ".tar.xz", ".tar"]:
                    if module_name.lower().endswith(ext):
                        module_name = module_name[: -len(ext)]
                        break

            # Validate module name to prevent directory traversal
            module_name = validate_module_name(module_name)

            final_dir = dest_dir / module_name
            if final_dir.exists():
                shutil.rmtree(final_dir)

            shutil.copytree(module_dir, final_dir)

        return final_dir

    def _find_module_dir(self, root: Path) -> Optional[Path]:
        """Find directory containing skills (SKILL.md) or commands."""
        # First, try to find a SKILL.md anywhere
        for path in root.rglob(SKILL_FILE):
            # Return the parent of the skill folder (the module)
            return path.parent.parent

        # Or look for a commands/ directory with .md files
        for path in root.rglob("commands"):
            if path.is_dir() and list(path.glob("*.md")):
                return path.parent

        return None


class ZipUrlSourceHandler(SourceHandler):
    """Handler for zip file URLs."""

    def can_handle(self, source: str) -> bool:
        """Check if source is a URL to a zip file."""
        parsed = urlparse(source)
        if parsed.scheme not in ("http", "https"):
            return False
        # Check if the path ends with .zip
        return parsed.path.lower().endswith(".zip")

    def fetch(self, source: str, dest_dir: Path) -> Path:
        """Download and extract zip file from URL."""
        parsed = urlparse(source)
        # Extract filename from URL path
        filename = Path(parsed.path).name

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            zip_path = tmp_path / filename

            # Download the zip file
            download_file(source, zip_path)

            # Extract to a subdirectory
            extract_path = tmp_path / "extracted"
            extract_path.mkdir()

            with zipfile.ZipFile(zip_path, "r") as zf:
                # Safe extraction
                dest = extract_path.resolve()
                for member in zf.namelist():
                    member_path = (dest / member).resolve()
                    if (
                        not str(member_path).startswith(str(dest) + os.sep)
                        and member_path != dest
                    ):
                        raise ValueError(f"Zip Slip attack detected: {member}")
                zf.extractall(extract_path)

            # Find the module directory (may be nested)
            module_dir = self._find_module_dir(extract_path)
            if not module_dir:
                contents = list(extract_path.iterdir())
                if len(contents) == 1 and contents[0].is_dir():
                    module_dir = contents[0]
                else:
                    module_dir = extract_path

            # Determine module name
            module_name = module_dir.name
            if module_name == extract_path.name:
                module_name = Path(filename).stem

            # Validate module name to prevent directory traversal
            module_name = validate_module_name(module_name)

            final_dir = dest_dir / module_name
            if final_dir.exists():
                shutil.rmtree(final_dir)

            shutil.copytree(module_dir, final_dir)

        return final_dir

    def _find_module_dir(self, root: Path) -> Optional[Path]:
        """Find directory containing skills (SKILL.md) or commands."""
        # First, try to find a SKILL.md anywhere
        for path in root.rglob(SKILL_FILE):
            # Return the parent of the skill folder (the module)
            return path.parent.parent

        # Or look for a commands/ directory with .md files
        for path in root.rglob("commands"):
            if path.is_dir() and list(path.glob("*.md")):
                return path.parent

        return None


class TarUrlSourceHandler(SourceHandler):
    """Handler for tar file URLs."""

    TAR_EXTENSIONS = (".tar", ".tar.gz", ".tgz", ".tar.bz2", ".tar.xz")

    def can_handle(self, source: str) -> bool:
        """Check if source is a URL to a tar file."""
        parsed = urlparse(source)
        if parsed.scheme not in ("http", "https"):
            return False
        path_lower = parsed.path.lower()
        return any(path_lower.endswith(ext) for ext in self.TAR_EXTENSIONS)

    def fetch(self, source: str, dest_dir: Path) -> Path:
        """Download and extract tar file from URL."""
        parsed = urlparse(source)
        filename = Path(parsed.path).name

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            tar_path = tmp_path / filename

            # Download the tar file
            download_file(source, tar_path)

            # Extract to a subdirectory
            extract_path = tmp_path / "extracted"
            extract_path.mkdir()

            with tarfile.open(tar_path, "r:*") as tf:
                tf.extractall(extract_path, filter="data")

            # Find the module directory (may be nested)
            module_dir = self._find_module_dir(extract_path)
            if not module_dir:
                contents = list(extract_path.iterdir())
                if len(contents) == 1 and contents[0].is_dir():
                    module_dir = contents[0]
                else:
                    module_dir = extract_path

            # Determine module name
            module_name = module_dir.name
            if module_name == extract_path.name:
                # Strip extensions from filename
                module_name = filename
                for ext in [".tar.gz", ".tgz", ".tar.bz2", ".tar.xz", ".tar"]:
                    if module_name.lower().endswith(ext):
                        module_name = module_name[: -len(ext)]
                        break

            # Validate module name to prevent directory traversal
            module_name = validate_module_name(module_name)

            final_dir = dest_dir / module_name
            if final_dir.exists():
                shutil.rmtree(final_dir)

            shutil.copytree(module_dir, final_dir)

        return final_dir

    def _find_module_dir(self, root: Path) -> Optional[Path]:
        """Find directory containing skills (SKILL.md) or commands."""
        # First, try to find a SKILL.md anywhere
        for path in root.rglob(SKILL_FILE):
            # Return the parent of the skill folder (the module)
            return path.parent.parent

        # Or look for a commands/ directory with .md files
        for path in root.rglob("commands"):
            if path.is_dir() and list(path.glob("*.md")):
                return path.parent

        return None


class FolderSourceHandler(SourceHandler):
    """Handler for local folder sources."""

    def can_handle(self, source: str) -> bool:
        """Check if source is a local folder."""
        path = Path(source)
        return path.exists() and path.is_dir()

    def fetch(self, source: str, dest_dir: Path) -> Path:
        """Copy folder to destination."""
        source_path = Path(source).resolve()
        module_name = source_path.name

        # Validate module name to prevent directory traversal
        module_name = validate_module_name(module_name)

        final_dir = dest_dir / module_name
        if final_dir.exists():
            shutil.rmtree(final_dir)

        shutil.copytree(source_path, final_dir)

        return final_dir


# Registry of all source handlers
# Order matters:
# 1. Zip/Tar URL handlers come first (to catch GitHub archive URLs before git handler)
# 2. Git handler (for .git URLs and git hosting sites)
# 3. Local file handlers
# 4. Folder handler last (most generic)
SOURCE_HANDLERS = [
    ZipUrlSourceHandler(),
    TarUrlSourceHandler(),
    GitSourceHandler(),
    ZipSourceHandler(),
    TarSourceHandler(),
    FolderSourceHandler(),
]


def fetch_module(source: str, dest_dir: Path) -> Path:
    """
    Fetch a module from any supported source.

    Args:
        source: Source location (git URL, zip path, tar path, or folder path)
        dest_dir: Directory to store the fetched module

    Returns:
        Path to the fetched module directory

    Raises:
        ValueError: If no handler can process the source
    """
    for handler in SOURCE_HANDLERS:
        if handler.can_handle(source):
            return handler.fetch(source, dest_dir)

    raise ValueError(
        f"Cannot handle source: {source}\n"
        f"Supported sources: git repos, .zip/.tar URLs, local .zip/.tar files, or local folders"
    )


def detect_source_type(source: str) -> str:
    """Detect the type of source."""
    for handler in SOURCE_HANDLERS:
        if handler.can_handle(source):
            return handler.__class__.__name__.replace("SourceHandler", "").lower()
    return "unknown"


def save_source_info(module_path: Path, source: str, source_type: str):
    """
    Save source information for a module.

    Args:
        module_path: Path to the module directory
        source: Original source string (URL or path)
        source_type: Type of source (git, zip, tar, zipurl, tarurl, folder)
    """
    source_file = module_path / SOURCE_FILE
    source_file.parent.mkdir(parents=True, exist_ok=True)

    # For local paths (not URLs), store the absolute resolved path
    if source_type in ("folder", "zip", "tar"):
        source = str(Path(source).resolve())
    # URL types (zipurl, tarurl, git) keep the original URL

    data = {
        "source": source,
        "type": source_type,
    }

    with open(source_file, "w") as f:
        yaml.dump(data, f, default_flow_style=False)


def load_source_info(module_path: Path) -> Optional[dict]:
    """
    Load source information for a module.

    Args:
        module_path: Path to the module directory

    Returns:
        Dict with 'source' and 'type' keys, or None if not found
    """
    source_file = module_path / SOURCE_FILE
    if not source_file.exists():
        return None

    with open(source_file, "r") as f:
        return yaml.safe_load(f)


def update_module(module_path: Path) -> tuple[bool, str]:
    """
    Update a module from its original source.

    Args:
        module_path: Path to the module directory

    Returns:
        Tuple of (success, message)
    """
    source_info = load_source_info(module_path)
    if not source_info:
        return False, "No source information found. Module cannot be updated."

    source = source_info.get("source")
    source_type = source_info.get("type")

    if not source or not source_type:
        return False, "Invalid source information."

    # Validate source still exists/is accessible (for local sources only)
    if source_type == "folder":
        if not Path(source).exists():
            return False, f"Source folder no longer exists: {source}"
    elif source_type in ("zip", "tar"):
        if not Path(source).exists():
            return False, f"Source archive no longer exists: {source}"
    # URL sources (zipurl, tarurl, git) will be validated during fetch

    # Find the appropriate handler
    handler = None
    for h in SOURCE_HANDLERS:
        handler_type = h.__class__.__name__.replace("SourceHandler", "").lower()
        if handler_type == source_type:
            handler = h
            break

    if not handler:
        return False, f"Unknown source type: {source_type}"

    # Re-fetch the module
    module_name = module_path.name
    dest_dir = module_path.parent

    # Remove existing module
    if module_path.exists():
        shutil.rmtree(module_path)

    # Fetch fresh copy
    try:
        new_path = handler.fetch(source, dest_dir)

        # Rename if necessary (in case source changed name)
        if new_path.name != module_name:
            final_path = dest_dir / module_name
            if new_path != final_path:
                new_path.rename(final_path)
                new_path = final_path

        # Re-save source info
        save_source_info(new_path, source, source_type)

        return True, f"Updated from {source_type} source"
    except Exception as e:
        return False, f"Update failed: {e}"
