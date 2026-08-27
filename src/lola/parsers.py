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
import subprocess  # nosec B404 - required for git clone
import tarfile
import tempfile
import zipfile
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional, cast
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
    """Download a file from a URL to a local path.

    Args:
        url: HTTP or HTTPS URL to download from
        dest_path: Local path to save the downloaded file

    Raises:
        ValueError: If URL scheme is not http or https
        RuntimeError: If download fails
    """
    # Validate URL scheme for security
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"URL must use http or https scheme, got: {parsed.scheme!r}")

    try:
        with urlopen(url, timeout=60) as response:  # nosec B310 - http/https validated above
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


def _find_plugin_root(root: Path) -> Optional[Path]:
    """Return the shallowest directory holding an Agent Plugins manifest.

    Agent Plugins packages keep their commands/agents under a client
    namespace directory (``dev.getlola/commands``), so the SKILL.md and
    ``commands/`` heuristics below would otherwise select the namespace
    directory and drop ``plugin.json`` and ``skills/`` on the floor.
    """
    roots = [path.parent for path in root.rglob("plugin.json") if path.is_file()]
    if not roots:
        return None
    return min(roots, key=lambda path: len(path.parts))


class SourceHandler(ABC):
    """Base class for module source handlers."""

    @abstractmethod
    def can_handle(self, source: str) -> bool:  # pragma: no cover
        pass

    @abstractmethod
    def fetch(
        self,
        source: str,
        dest_dir: Path,
        module_content_dirname: Optional[str] = None,
        ref: Optional[str] = None,
    ) -> Path:  # pragma: no cover
        pass


class GitSourceHandler(SourceHandler):
    """Handler for git repository sources."""

    def can_handle(self, source: str) -> bool:
        if source.endswith(".git"):
            return True
        parsed = urlparse(source)
        if parsed.scheme in ("git", "ssh"):
            return True
        # Accept any HTTP(S) URL with a valid host as a potential git source.
        # Archive URLs (.zip, .tar*) are already handled by ZipUrlSourceHandler
        # and TarUrlSourceHandler which run before this handler in
        # SOURCE_HANDLERS, so they won't reach here.
        if parsed.scheme in ("http", "https") and parsed.netloc:
            return True
        return False

    def _is_commit_hash(self, ref: Optional[str]) -> bool:
        """Check if ref looks like a commit hash."""
        if not ref or len(ref) < 7:
            return False
        # Assume it is a commit hash if it is an hex number
        try:
            int(ref, 16)
        except ValueError:
            return False
        return True

    def fetch(
        self,
        source: str,
        dest_dir: Path,
        module_content_dirname: Optional[str] = None,
        ref: Optional[str] = None,
    ) -> Path:
        repo_name = source.rstrip("/").split("/")[-1]
        if repo_name.endswith(".git"):
            repo_name = repo_name[:-4]
        repo_name = validate_module_name(repo_name)

        module_dir = dest_dir / repo_name
        if module_dir.exists():
            shutil.rmtree(module_dir)

        # Detect if ref is a commit hash
        is_commit = ref and self._is_commit_hash(ref)

        if is_commit:
            # For commit hashes, we need to clone without depth restrictions
            # then checkout the specific commit
            clone_cmd = ["git", "clone", "--", source, str(module_dir)]
            result = subprocess.run(  # nosec B603 B607 - list args (no shell), git from PATH is intentional
                clone_cmd,
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                raise RuntimeError(f"Git clone failed: {result.stderr}")

            # Checkout the specific commit
            # Type checker: is_commit=True guarantees ref is not None
            checkout_cmd = ["git", "-C", str(module_dir), "checkout", cast(str, ref)]
            result = subprocess.run(  # nosec B603 B607 - list args (no shell), git from PATH is intentional
                checkout_cmd,
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                raise RuntimeError(f"Git checkout failed: {result.stderr}")
        else:
            # For branches and tags, use shallow clone with --depth 1
            if ref and ref.startswith("-"):
                raise ValueError(f"Invalid ref '{ref}': refs cannot start with '-'")
            clone_cmd = ["git", "clone", "--depth", "1"]
            if ref:
                clone_cmd.extend(["--branch", ref])
            clone_cmd.extend(["--", source, str(module_dir)])

            result = subprocess.run(  # nosec B603 B607 - list args (no shell), git from PATH is intentional
                clone_cmd,
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

    def fetch(
        self,
        source: str,
        dest_dir: Path,
        module_content_dirname: Optional[str] = None,
        ref: Optional[str] = None,
    ) -> Path:
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
        # Flat archive - wrap contents in a directory named after the archive
        module_dir = tmp_path / default_name
        module_dir.mkdir()
        for item in contents:
            shutil.move(str(item), str(module_dir / item.name))
        return module_dir

    def _find_module_dir(self, root: Path) -> Optional[Path]:
        plugin_root = _find_plugin_root(root)
        if plugin_root is not None:
            return plugin_root

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
            if (
                not str(member_path).startswith(str(dest) + os.sep)
                and member_path != dest
            ):
                raise SecurityError(f"Zip Slip attack detected: {member}")
        zf.extractall(dest)  # nosec B202 - zipfile (not tarfile); Zip Slip check above


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

    def fetch(
        self,
        source: str,
        dest_dir: Path,
        module_content_dirname: Optional[str] = None,
        ref: Optional[str] = None,
    ) -> Path:
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
        # Flat archive - wrap contents in a directory named after the archive
        # Strip common tar extensions to get a clean name
        stem = filename
        for ext in (".tar.gz", ".tar.bz2", ".tar.xz", ".tgz", ".tar"):
            if stem.lower().endswith(ext):
                stem = stem[: -len(ext)]
                break
        module_dir = tmp_path / stem
        module_dir.mkdir()
        for item in contents:
            shutil.move(str(item), str(module_dir / item.name))
        return module_dir

    def _find_module_dir(self, root: Path) -> Optional[Path]:
        plugin_root = _find_plugin_root(root)
        if plugin_root is not None:
            return plugin_root

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

    def __init__(self):
        # Helper instance for reusing ZipSourceHandler methods
        self._zip_handler = ZipSourceHandler()

    def can_handle(self, source: str) -> bool:
        parsed = urlparse(source)
        return parsed.scheme in ("http", "https") and parsed.path.lower().endswith(
            ".zip"
        )

    def fetch(
        self,
        source: str,
        dest_dir: Path,
        module_content_dirname: Optional[str] = None,
        ref: Optional[str] = None,
    ) -> Path:
        parsed = urlparse(source)
        filename = Path(parsed.path).name
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            zip_path = tmp_path / filename
            download_file(source, zip_path)

            extract_path = tmp_path / "extracted"
            extract_path.mkdir()
            with zipfile.ZipFile(zip_path, "r") as zf:
                # Reuse ZipSourceHandler's Zip Slip protection
                self._zip_handler._safe_extract(zf, extract_path)

            # Reuse ZipSourceHandler's module directory detection
            module_dir = self._zip_handler._find_module_dir(
                extract_path
            ) or self._zip_handler._fallback_module_dir(
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

    def __init__(self):
        # Helper instance for reusing TarSourceHandler methods
        self._tar_handler = TarSourceHandler()

    def can_handle(self, source: str) -> bool:
        parsed = urlparse(source)
        if parsed.scheme not in ("http", "https"):
            return False
        path_lower = parsed.path.lower()
        return any(path_lower.endswith(ext) for ext in self.TAR_EXTENSIONS)

    def fetch(
        self,
        source: str,
        dest_dir: Path,
        module_content_dirname: Optional[str] = None,
        ref: Optional[str] = None,
    ) -> Path:
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

            # Reuse TarSourceHandler's module directory detection
            module_dir = self._tar_handler._find_module_dir(
                extract_path
            ) or self._tar_handler._fallback_module_dir(extract_path, filename)
            module_name = validate_module_name(module_dir.name)

            final_dir = dest_dir / module_name
            if final_dir.exists():
                shutil.rmtree(final_dir)
            shutil.copytree(module_dir, final_dir)
        return final_dir


class FolderSourceHandler(SourceHandler):
    """Handler for local folder sources.

    Mirrors the zip/tar handlers: locate the module subtree (SKILL.md or
    commands/) and copy only that subtree, filtering out generated artifacts
    (virtualenvs, caches, prior .lola/ install state). When the source is a
    git repo, .gitignore is honored via ``git ls-files``.
    """

    # Excluded by directory name regardless of .gitignore presence. Covers
    # tools that don't ship a useful .gitignore and the case where the source
    # is not a git repo at all. ``.lola`` matters most: a project that has
    # been installed-to contains a copy of the registered module, and an
    # unfiltered re-add would copy that copy into itself.
    ALWAYS_IGNORE: frozenset[str] = frozenset(
        {
            ".git",
            ".svn",
            ".hg",
            ".venv",
            "venv",
            ".env",
            "__pycache__",
            ".pytest_cache",
            ".mypy_cache",
            ".tox",
            ".ruff_cache",
            "node_modules",
            ".lola",
            ".test-output",
            ".coverage",
            ".DS_Store",
        }
    )

    def can_handle(self, source: str) -> bool:
        path = Path(source)
        return path.exists() and path.is_dir()

    def fetch(
        self,
        source: str,
        dest_dir: Path,
        module_content_dirname: Optional[str] = None,
        ref: Optional[str] = None,
    ) -> Path:
        source_path = Path(source).resolve()
        kept = self._git_kept_paths(source_path)
        # When the caller specifies a content directory (marketplace path,
        # explicit --module-content), trust them: copy the whole source and
        # let the downstream Module loader navigate. Otherwise locate the
        # module subtree by walking for SKILL.md / commands/, like the
        # zip/tar handlers do.
        if module_content_dirname:
            module_root = source_path
        else:
            module_root = self._find_module_root(source_path, kept) or source_path
        module_name = validate_module_name(module_root.name)

        final_dir = dest_dir / module_name
        # shutil.rmtree below would otherwise destroy part of the source if
        # the destination resolves to a path inside it (LOLA_HOME under cwd,
        # ``.lola/modules`` inside the source, etc.).
        if final_dir.resolve().is_relative_to(source_path):
            raise SourceError(source, f"destination is inside source: {final_dir}")

        if final_dir.exists():
            shutil.rmtree(final_dir)

        # symlinks=False (default) resolves links and copies their targets,
        # which preserves modules that share files via symlinks pointing
        # outside the module subtree. Do not change this.
        shutil.copytree(
            module_root,
            final_dir,
            ignore=self._make_ignore(source_path, module_root, kept),
        )
        return final_dir

    def _git_kept_paths(self, source_path: Path) -> Optional[set[Path]]:
        """Return source-relative paths git considers kept, or None.

        ``None`` means the source is not a git repo (or git is unavailable),
        in which case callers fall back to ``ALWAYS_IGNORE`` only.
        """
        if not (source_path / ".git").exists():
            return None
        try:
            result = subprocess.run(  # nosec B603 B607 - list args, git from PATH is intentional
                [
                    "git",
                    "-C",
                    str(source_path),
                    "ls-files",
                    "-z",
                    "--cached",
                    "--others",
                    "--exclude-standard",
                ],
                capture_output=True,
                text=True,
                check=True,
                timeout=30,
            )
        except (
            subprocess.CalledProcessError,
            subprocess.TimeoutExpired,
            FileNotFoundError,
        ):
            return None
        # Drop ALWAYS_IGNORE components even when git tracks them. A committed
        # ``.lola/modules/<stale>/skills/<x>/SKILL.md`` from a prior install
        # otherwise wins ``_find_module_root`` over the real module subtree.
        paths = (Path(path) for path in result.stdout.split("\0") if path)
        return {
            p for p in paths if not any(part in self.ALWAYS_IGNORE for part in p.parts)
        }

    def _find_module_root(
        self, source_path: Path, kept: Optional[set[Path]]
    ) -> Optional[Path]:
        """Locate the module subtree by scanning for SKILL.md or commands/*.md."""
        candidates = self._candidate_files(source_path, kept)
        # An Agent Plugins manifest marks its own package root.
        plugin_rels = [rel.parent for rel in candidates if rel.name == "plugin.json"]
        if plugin_rels:
            return source_path / min(plugin_rels, key=lambda rel: len(rel.parts))
        # Prefer SKILL.md
        for rel in candidates:
            if rel.name == SKILL_FILE:
                skill_dir = source_path / rel.parent
                # A bare SKILL.md at the source root has no enclosing module
                # to point at — returning skill_dir.parent here would walk
                # outside the source. Skip and let the caller fall back to
                # source_path.
                if skill_dir == source_path:
                    continue
                if skill_dir.parent.name == "skills":
                    return skill_dir.parent.parent
                return skill_dir.parent
        # Fall back to commands/*.md
        for rel in candidates:
            if rel.suffix == ".md" and rel.parent.name == "commands":
                return source_path / rel.parent.parent
        return None

    def _candidate_files(
        self, source_path: Path, kept: Optional[set[Path]]
    ) -> list[Path]:
        """Source-relative file paths to scan for module markers."""
        if kept is not None:
            return sorted(kept)
        out: list[Path] = []
        for root, dirs, files in os.walk(source_path):
            dirs[:] = [d for d in dirs if d not in self.ALWAYS_IGNORE]
            rel_root = Path(root).relative_to(source_path)
            out.extend(rel_root / f for f in files)
        return sorted(out)

    def _make_ignore(
        self,
        source_path: Path,
        module_root: Path,
        kept: Optional[set[Path]],
    ):
        """Return a ``shutil.copytree`` ignore callback for the module subtree."""
        module_rel = module_root.relative_to(source_path)
        kept_dirs: set[Path] = (
            {p for k in kept for p in k.parents} if kept is not None else set()
        )

        def ignore(dirname: str, files: list[str]) -> list[str]:
            dir_in_source = module_rel / Path(dirname).relative_to(module_root)
            ignored: list[str] = []
            for name in files:
                if name in self.ALWAYS_IGNORE:
                    ignored.append(name)
                    continue
                if kept is None:
                    continue
                rel = dir_in_source / name
                full_path = Path(dirname) / name
                # Treat symlinks as regular files, not directories
                if not full_path.is_symlink() and full_path.is_dir():
                    if rel not in kept_dirs:
                        ignored.append(name)
                elif rel not in kept:
                    ignored.append(name)
            return ignored

        return ignore


SOURCE_HANDLERS: list[SourceHandler] = [
    ZipUrlSourceHandler(),
    TarUrlSourceHandler(),
    GitSourceHandler(),
    ZipSourceHandler(),
    TarSourceHandler(),
    FolderSourceHandler(),
]


def fetch_module(
    source: str,
    dest_dir: Path,
    module_content_dirname: Optional[str] = None,
    ref: Optional[str] = None,
) -> Path:
    """Fetch a module from any supported source.

    Args:
        source: Source location (git URL, zip, tar, folder, or URL)
        dest_dir: Destination directory for the fetched module
        module_content_dirname: Optional custom directory name for module content
                               (e.g., "foo/modules", "/" for root, None for default)
        ref: Optional git branch, tag, or commit reference (only used for git sources)

    Raises:
        UnsupportedSourceError: If the source type is not supported.
        SourceError: If fetching fails.
    """
    for handler in SOURCE_HANDLERS:
        if handler.can_handle(source):
            return handler.fetch(source, dest_dir, module_content_dirname, ref)
    raise UnsupportedSourceError(source)


def move_fetched_module_to_name(
    module_path: Path, module_name: str, dest_dir: Path | None = None
) -> Path:
    """Store a fetched module under an explicit registry module name.

    Source handlers derive the destination directory from the repository or
    archive name. Marketplace catalogs can intentionally expose that source
    under a different module name, so marketplace installs need to normalize
    the fetched directory before saving registry metadata.

    Existing target directories are never overwritten here; callers must decide
    whether reinstall/update semantics should replace an existing module.
    """
    module_name = validate_module_name(module_name)
    target_dir = dest_dir or module_path.parent
    target_dir.mkdir(parents=True, exist_ok=True)
    renamed_path = target_dir / module_name
    if module_path == renamed_path:
        return module_path

    if renamed_path.exists():
        if module_path.exists():
            shutil.rmtree(module_path)
        raise FileExistsError(
            f"Module '{module_name}' already exists at {renamed_path}"
        )

    return Path(shutil.move(str(module_path), str(renamed_path)))


def fetch_module_as_name(
    source: str,
    dest_dir: Path,
    module_name: str,
    module_content_dirname: Optional[str] = None,
    ref: Optional[str] = None,
) -> Path:
    """Fetch a module and store it under an explicit registry module name.

    The fetch happens in an isolated temporary directory first, so source
    handlers cannot delete or replace existing modules that happen to share the
    repository/archive-derived folder name.
    """
    module_name = validate_module_name(module_name)
    final_path = dest_dir / module_name
    if final_path.exists():
        raise FileExistsError(f"Module '{module_name}' already exists at {final_path}")

    with tempfile.TemporaryDirectory() as tmp_dir:
        module_path = fetch_module(source, Path(tmp_dir), module_content_dirname, ref)
        return move_fetched_module_to_name(module_path, module_name, dest_dir)


def detect_source_type(source: str) -> str:
    """Detect the type of source."""
    for handler in SOURCE_HANDLERS:
        if handler.can_handle(source):
            return handler.__class__.__name__.replace("SourceHandler", "").lower()
    return "unknown"


def predict_module_name(source: str) -> Optional[str]:
    """
    Predict the module name that will be derived from a source.

    This function mirrors the name extraction logic used by source handlers,
    allowing us to predict the module name before fetching. Used to check
    for existing modules and prevent accidental overwrites.

    Args:
        source: Source location (git URL, zip path, tar path, folder path, or URL)

    Returns:
        Predicted module name (validated), or None if prediction not possible

    Note:
        For archive sources (zip/tar), this provides best-effort prediction based
        on filename. The actual module name may differ if archive has complex structure.
        Returns None in uncertain cases to skip checks conservatively.
    """
    module_name = None
    source_type = detect_source_type(source)

    try:
        if source_type == "git":
            # Extract repo name from git URL - urlparse handles trailing slashes
            parsed = urlparse(source)
            repo_name = Path(parsed.path).name
            if repo_name.endswith(".git"):
                repo_name = repo_name[:-4]
            module_name = validate_module_name(repo_name)

        elif source_type == "folder":
            # Mirror FolderSourceHandler.fetch: locate the module subtree so
            # the predicted name matches what fetch will actually produce.
            # Otherwise the overwrite check guards the wrong name and a
            # collision under the real fetched name slips through silently.
            source_path = Path(source).resolve()
            handler = FolderSourceHandler()
            kept = handler._git_kept_paths(source_path)
            module_root = handler._find_module_root(source_path, kept) or source_path
            module_name = validate_module_name(module_root.name)

        elif source_type == "zip":
            # Best guess: use zip filename stem
            # Note: Actual name might differ if archive has complex structure
            module_name = validate_module_name(Path(source).stem)

        elif source_type == "tar":
            # Best guess: use tar filename stem after removing extensions
            # Note: Actual name might differ if archive has complex structure
            filename = Path(source).name
            stem = filename
            for ext in (".tar.gz", ".tar.bz2", ".tar.xz", ".tgz", ".tar"):
                if stem.lower().endswith(ext):
                    stem = stem[: -len(ext)]
                    break
            module_name = validate_module_name(stem)

        elif source_type == "zipurl":
            # Extract filename from URL and use stem
            parsed = urlparse(source)
            filename = Path(parsed.path).name
            module_name = validate_module_name(Path(filename).stem)

        elif source_type == "tarurl":
            # Extract filename from URL and strip tar extensions
            parsed = urlparse(source)
            filename = Path(parsed.path).name
            stem = filename
            for ext in (".tar.gz", ".tar.bz2", ".tar.xz", ".tgz", ".tar"):
                if stem.lower().endswith(ext):
                    stem = stem[: -len(ext)]
                    break
            module_name = validate_module_name(stem)

    except (ModuleNameError, Exception):
        # If prediction fails (e.g., invalid name), return None
        # This will skip the existence check (conservative approach)
        module_name = None

    return module_name


def save_source_info(
    module_path: Path,
    source: str,
    source_type: str,
    content_dirname: Optional[str] = None,
    ref: Optional[str] = None,
):
    """Save source information for a module."""
    source_file = module_path / SOURCE_FILE
    source_file.parent.mkdir(parents=True, exist_ok=True)

    if source_type in ("folder", "zip", "tar"):
        source = str(Path(source).resolve())

    data = {"source": source, "type": source_type}
    if content_dirname is not None:
        data["content_dirname"] = content_dirname
    if ref is not None:
        data["ref"] = ref
    with open(source_file, "w") as f:
        yaml.dump(data, f, default_flow_style=False)


def load_source_info(module_path: Path) -> Optional[dict[str, str]]:
    """Load source information for a module."""
    source_file = module_path / SOURCE_FILE
    if not source_file.exists():
        return None
    with open(source_file, "r") as f:
        data = yaml.safe_load(f)
    return dict(data) if isinstance(data, dict) else None


def update_module(module_path: Path) -> str:
    """Update a module from its original source.

    This function fetches into a temporary location first, then atomically
    swaps the new module into place. This ensures the original module is
    preserved if the fetch fails.

    Returns:
        Success message describing the update.

    Raises:
        SourceError: If the update fails for any reason.
    """
    source_info = load_source_info(module_path)
    if not source_info:
        raise SourceError(
            str(module_path), "No source information found. Module cannot be updated."
        )

    source = source_info.get("source")
    source_type = source_info.get("type")
    content_dirname = source_info.get("content_dirname")
    ref = source_info.get("ref")
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

    # Fetch into a temporary directory first (atomic update pattern)
    with tempfile.TemporaryDirectory(dir=dest_dir) as tmp_dir:
        tmp_path = Path(tmp_dir)

        try:
            new_path = handler.fetch(source, tmp_path, ref=ref)

            # Rename to match expected module name if needed
            if new_path.name != module_name:
                renamed_path = tmp_path / module_name
                new_path.rename(renamed_path)
                new_path = renamed_path

            # Save source info to the new module
            save_source_info(new_path, source, source_type, content_dirname, ref)

            # Atomic swap: move old module to backup, move new module in place
            backup_path = dest_dir / f".{module_name}.backup"

            # Remove any stale backup from previous failed updates
            if backup_path.exists():
                shutil.rmtree(backup_path)

            # Move current module to backup (if it exists)
            if module_path.exists():
                module_path.rename(backup_path)

            try:
                # Move new module into place
                shutil.move(str(new_path), str(module_path))
            except Exception:
                # Restore backup on failure
                if backup_path.exists():
                    backup_path.rename(module_path)
                raise

            # Success - remove backup
            if backup_path.exists():
                shutil.rmtree(backup_path)

            return f"Updated from {source_type} source"
        except SourceError:
            raise
        except Exception as e:
            raise SourceError(source, f"Update failed: {e}") from e
