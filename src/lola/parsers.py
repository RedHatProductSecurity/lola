"""
sources:
    Module source fetching for lola.

This file handles fetching modules from various sources:
- Git repositories
- Zip/tar archives (local and remote URLs)
- Local folders
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tarfile
import tempfile
import zipfile
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional
from urllib.error import URLError
from urllib.parse import urlparse
from urllib.request import urlopen

import yaml

from lola.config import SKILL_FILE
from lola.exceptions import (
    ModuleNameError,
    SecurityError,
    SourceError,
    UnsupportedSourceError,
)

SOURCE_TYPES = ["git", "zip", "tar", "folder", "zipurl", "tarurl"]


# =============================================================================
# Module source fetching
# =============================================================================


def download_file(url: str, dest_path: Path) -> None:
    """Download a file from a URL to a local path."""
    try:
        with urlopen(url, timeout=60) as response:
            with open(dest_path, "wb") as f:
                shutil.copyfileobj(response, f)
    except URLError as e:
        raise RuntimeError(f"Failed to download {url}: {e}")
    except Exception as e:
        raise RuntimeError(f"Download error: {e}")


SOURCE_FILE = ".lola/source.yml"


def validate_module_name(name: str) -> str:
    """Validate and sanitize a module name to prevent traversal attacks.

    Raises:
        ModuleNameError: If the name is invalid.
    """
    if not name:
        raise ModuleNameError(name, "name cannot be empty")
    if name in (".", ".."):
        raise ModuleNameError(name, "path traversal not allowed")
    if "/" in name or "\\" in name:
        raise ModuleNameError(name, "path separators not allowed")
    if name.startswith("."):
        raise ModuleNameError(name, "cannot start with '.'")
    if any(ord(c) < 32 for c in name):
        raise ModuleNameError(name, "control characters not allowed")
    return name


class SourceHandler(ABC):
    """Base class for module source handlers."""

    @abstractmethod
    def can_handle(self, source: str) -> bool:  # pragma: no cover
        pass

    @abstractmethod
    def fetch(self, source: str, dest_dir: Path) -> Path:  # pragma: no cover
        pass


class GitSourceHandler(SourceHandler):
    """Handler for git repository sources."""

    def can_handle(self, source: str) -> bool:
        if source.endswith(".git"):
            return True
        parsed = urlparse(source)
        if parsed.scheme in ("git", "ssh"):
            return True
        if parsed.scheme in ("http", "https") and (
            "github.com" in source or "gitlab.com" in source or "bitbucket.org" in source
        ):
            return True
        return False

    def fetch(self, source: str, dest_dir: Path) -> Path:
        repo_name = source.rstrip("/").split("/")[-1]
        if repo_name.endswith(".git"):
            repo_name = repo_name[:-4]
        repo_name = validate_module_name(repo_name)

        module_dir = dest_dir / repo_name
        if module_dir.exists():
            shutil.rmtree(module_dir)

        result = subprocess.run(
            ["git", "clone", "--depth", "1", source, str(module_dir)],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(f"Git clone failed: {result.stderr}")

        git_dir = module_dir / ".git"
        if git_dir.exists():
            shutil.rmtree(git_dir)
        return module_dir


class ZipSourceHandler(SourceHandler):
    """Handler for zip file sources."""

    def can_handle(self, source: str) -> bool:
        return source.endswith(".zip") and Path(source).exists()

    def fetch(self, source: str, dest_dir: Path) -> Path:
        source_path = Path(source)
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            with zipfile.ZipFile(source_path, "r") as zf:
                self._safe_extract(zf, tmp_path)

            module_dir = self._find_module_dir(tmp_path) or self._fallback_module_dir(
                tmp_path, source_path.stem
            )
            module_name = validate_module_name(module_dir.name)

            final_dir = dest_dir / module_name
            if final_dir.exists():
                shutil.rmtree(final_dir)
            shutil.copytree(module_dir, final_dir)
        return final_dir

    def _fallback_module_dir(self, tmp_path: Path, default_name: str) -> Path:
        contents = list(tmp_path.iterdir())
        if len(contents) == 1 and contents[0].is_dir():
            return contents[0]
        # Name doesn't matter here; caller uses module_dir.name
        # but we still return tmp_path for flat archives.
        _ = default_name
        return tmp_path

    def _find_module_dir(self, root: Path) -> Optional[Path]:
        for path in root.rglob(SKILL_FILE):
            skill_dir = path.parent
            maybe_skills_dir = skill_dir.parent
            if maybe_skills_dir.name == "skills":
                return maybe_skills_dir.parent
            return maybe_skills_dir

        for path in root.rglob("commands"):
            if path.is_dir() and list(path.glob("*.md")):
                return path.parent
        return None

    def _safe_extract(self, zf: zipfile.ZipFile, dest: Path) -> None:
        dest = dest.resolve()
        for member in zf.namelist():
            member_path = (dest / member).resolve()
            if not str(member_path).startswith(str(dest) + os.sep) and member_path != dest:
                raise SecurityError(f"Zip Slip attack detected: {member}")
        zf.extractall(dest)


class TarSourceHandler(SourceHandler):
    """Handler for tar/tar.gz/tar.bz2 file sources."""

    def can_handle(self, source: str) -> bool:
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
        source_path = Path(source)
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            with tarfile.open(source_path, "r:*") as tf:
                tf.extractall(tmp_path, filter="data")

            module_dir = self._find_module_dir(tmp_path) or self._fallback_module_dir(
                tmp_path, source_path.name
            )
            module_name = validate_module_name(module_dir.name)

            final_dir = dest_dir / module_name
            if final_dir.exists():
                shutil.rmtree(final_dir)
            shutil.copytree(module_dir, final_dir)
        return final_dir

    def _fallback_module_dir(self, tmp_path: Path, filename: str) -> Path:
        contents = list(tmp_path.iterdir())
        if len(contents) == 1 and contents[0].is_dir():
            return contents[0]
        _ = filename
        return tmp_path

    def _find_module_dir(self, root: Path) -> Optional[Path]:
        for path in root.rglob(SKILL_FILE):
            skill_dir = path.parent
            maybe_skills_dir = skill_dir.parent
            if maybe_skills_dir.name == "skills":
                return maybe_skills_dir.parent
            return maybe_skills_dir

        for path in root.rglob("commands"):
            if path.is_dir() and list(path.glob("*.md")):
                return path.parent
        return None


class ZipUrlSourceHandler(SourceHandler):
    """Handler for zip file URLs."""

    def can_handle(self, source: str) -> bool:
        parsed = urlparse(source)
        return parsed.scheme in ("http", "https") and parsed.path.lower().endswith(".zip")

    def fetch(self, source: str, dest_dir: Path) -> Path:
        parsed = urlparse(source)
        filename = Path(parsed.path).name
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            zip_path = tmp_path / filename
            download_file(source, zip_path)

            extract_path = tmp_path / "extracted"
            extract_path.mkdir()
            with zipfile.ZipFile(zip_path, "r") as zf:
                dest = extract_path.resolve()
                for member in zf.namelist():
                    member_path = (dest / member).resolve()
                    if not str(member_path).startswith(str(dest) + os.sep) and member_path != dest:
                        raise SecurityError(f"Zip Slip attack detected: {member}")
                zf.extractall(extract_path)

            module_dir = ZipSourceHandler()._find_module_dir(extract_path) or ZipSourceHandler()._fallback_module_dir(
                extract_path, Path(filename).stem
            )
            module_name = validate_module_name(module_dir.name)

            final_dir = dest_dir / module_name
            if final_dir.exists():
                shutil.rmtree(final_dir)
            shutil.copytree(module_dir, final_dir)
        return final_dir


class TarUrlSourceHandler(SourceHandler):
    """Handler for tar file URLs."""

    TAR_EXTENSIONS = (".tar", ".tar.gz", ".tgz", ".tar.bz2", ".tar.xz")

    def can_handle(self, source: str) -> bool:
        parsed = urlparse(source)
        if parsed.scheme not in ("http", "https"):
            return False
        path_lower = parsed.path.lower()
        return any(path_lower.endswith(ext) for ext in self.TAR_EXTENSIONS)

    def fetch(self, source: str, dest_dir: Path) -> Path:
        parsed = urlparse(source)
        filename = Path(parsed.path).name
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            tar_path = tmp_path / filename
            download_file(source, tar_path)

            extract_path = tmp_path / "extracted"
            extract_path.mkdir()
            with tarfile.open(tar_path, "r:*") as tf:
                tf.extractall(extract_path, filter="data")

            module_dir = TarSourceHandler()._find_module_dir(extract_path) or TarSourceHandler()._fallback_module_dir(
                extract_path, filename
            )
            module_name = validate_module_name(module_dir.name)

            final_dir = dest_dir / module_name
            if final_dir.exists():
                shutil.rmtree(final_dir)
            shutil.copytree(module_dir, final_dir)
        return final_dir


class FolderSourceHandler(SourceHandler):
    """Handler for local folder sources."""

    def can_handle(self, source: str) -> bool:
        path = Path(source)
        return path.exists() and path.is_dir()

    def fetch(self, source: str, dest_dir: Path) -> Path:
        source_path = Path(source).resolve()
        module_name = validate_module_name(source_path.name)

        final_dir = dest_dir / module_name
        if final_dir.exists():
            shutil.rmtree(final_dir)
        shutil.copytree(source_path, final_dir)
        return final_dir


SOURCE_HANDLERS: list[SourceHandler] = [
    ZipUrlSourceHandler(),
    TarUrlSourceHandler(),
    GitSourceHandler(),
    ZipSourceHandler(),
    TarSourceHandler(),
    FolderSourceHandler(),
]


def fetch_module(source: str, dest_dir: Path) -> Path:
    """Fetch a module from any supported source.

    Raises:
        UnsupportedSourceError: If the source type is not supported.
        SourceError: If fetching fails.
    """
    for handler in SOURCE_HANDLERS:
        if handler.can_handle(source):
            return handler.fetch(source, dest_dir)
    raise UnsupportedSourceError(source)


def detect_source_type(source: str) -> str:
    """Detect the type of source."""
    for handler in SOURCE_HANDLERS:
        if handler.can_handle(source):
            return handler.__class__.__name__.replace("SourceHandler", "").lower()
    return "unknown"


def save_source_info(module_path: Path, source: str, source_type: str):
    """Save source information for a module."""
    source_file = module_path / SOURCE_FILE
    source_file.parent.mkdir(parents=True, exist_ok=True)

    if source_type in ("folder", "zip", "tar"):
        source = str(Path(source).resolve())

    data = {"source": source, "type": source_type}
    with open(source_file, "w") as f:
        yaml.dump(data, f, default_flow_style=False)


def load_source_info(module_path: Path) -> Optional[dict]:
    """Load source information for a module."""
    source_file = module_path / SOURCE_FILE
    if not source_file.exists():
        return None
    with open(source_file, "r") as f:
        return yaml.safe_load(f)


def update_module(module_path: Path) -> str:
    """Update a module from its original source.

    Returns:
        Success message describing the update.

    Raises:
        SourceError: If the update fails for any reason.
    """
    source_info = load_source_info(module_path)
    if not source_info:
        raise SourceError(str(module_path), "No source information found. Module cannot be updated.")

    source = source_info.get("source")
    source_type = source_info.get("type")
    if not source or not source_type:
        raise SourceError(str(module_path), "Invalid source information.")

    if source_type == "folder":
        if not Path(source).exists():
            raise SourceError(source, f"Source folder no longer exists: {source}")
    elif source_type in ("zip", "tar"):
        if not Path(source).exists():
            raise SourceError(source, f"Source archive no longer exists: {source}")

    handler = None
    for h in SOURCE_HANDLERS:
        handler_type = h.__class__.__name__.replace("SourceHandler", "").lower()
        if handler_type == source_type:
            handler = h
            break
    if not handler:
        raise SourceError(source, f"Unknown source type: {source_type}")

    module_name = module_path.name
    dest_dir = module_path.parent

    if module_path.exists():
        shutil.rmtree(module_path)

    try:
        new_path = handler.fetch(source, dest_dir)

        if new_path.name != module_name:
            final_path = dest_dir / module_name
            if new_path != final_path:
                new_path.rename(final_path)
                new_path = final_path

        save_source_info(new_path, source, source_type)
        return f"Updated from {source_type} source"
    except Exception as e:
        raise SourceError(source, f"Update failed: {e}") from e


