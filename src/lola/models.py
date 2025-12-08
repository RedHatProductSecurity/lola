"""
models:
    Data models for lola modules, skills, and installations
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
import yaml

from lola.config import MODULE_MANIFEST, SKILL_FILE


@dataclass
class Skill:
    """Represents a skill within a module."""
    name: str
    path: Path
    description: Optional[str] = None

    @classmethod
    def from_path(cls, skill_path: Path) -> 'Skill':
        """Load a skill from its directory path."""
        skill_file = skill_path / SKILL_FILE
        description = None

        if skill_file.exists():
            content = skill_file.read_text()
            # Try to extract description from frontmatter or first paragraph
            lines = content.strip().split('\n')
            for line in lines:
                if line.strip() and not line.startswith('#') and not line.startswith('---'):
                    description = line.strip()[:100]
                    break

        return cls(
            name=skill_path.name,
            path=skill_path,
            description=description
        )


@dataclass
class Module:
    """Represents a lola module."""
    name: str
    path: Path
    version: str = "0.1.0"
    skills: list[str] = field(default_factory=list)
    description: Optional[str] = None

    @classmethod
    def from_path(cls, module_path: Path) -> Optional['Module']:
        """
        Load a module from its directory path.

        Expects a .lola/module.yml file in the module directory.
        """
        manifest_path = module_path / MODULE_MANIFEST

        if not manifest_path.exists():
            return None

        with open(manifest_path, 'r') as f:
            data = yaml.safe_load(f) or {}

        # Validate module type
        if data.get('type') != 'lola/module':
            return None

        return cls(
            name=module_path.name,
            path=module_path,
            version=data.get('version', '0.1.0'),
            skills=data.get('skills', []),
            description=data.get('description'),
        )

    def get_skill_paths(self) -> list[Path]:
        """Get the full paths to all skills in this module."""
        return [self.path / skill for skill in self.skills]

    def validate(self) -> tuple[bool, list[str]]:
        """
        Validate the module structure.

        Returns:
            Tuple of (is_valid, list of error messages)
        """
        errors = []

        # Check manifest exists
        manifest = self.path / MODULE_MANIFEST
        if not manifest.exists():
            errors.append(f"Missing manifest: {MODULE_MANIFEST}")

        # Check each skill exists and has SKILL.md
        for skill_rel in self.skills:
            skill_path = self.path / skill_rel
            if not skill_path.exists():
                errors.append(f"Skill directory not found: {skill_rel}")
            elif not (skill_path / SKILL_FILE).exists():
                errors.append(f"Missing {SKILL_FILE} in skill: {skill_rel}")

        return len(errors) == 0, errors


@dataclass
class Installation:
    """Represents an installed module."""
    module_name: str
    assistant: str
    scope: str
    project_path: Optional[str] = None
    skills: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary for YAML serialization."""
        result = {
            'module': self.module_name,
            'assistant': self.assistant,
            'scope': self.scope,
            'skills': self.skills,
        }
        if self.project_path:
            result['project_path'] = self.project_path
        return result

    @classmethod
    def from_dict(cls, data: dict) -> 'Installation':
        """Create from dictionary."""
        return cls(
            module_name=data.get('module', ''),
            assistant=data.get('assistant', ''),
            scope=data.get('scope', 'user'),
            project_path=data.get('project_path'),
            skills=data.get('skills', []),
        )


class InstallationRegistry:
    """Manages the installed.yml file."""

    def __init__(self, registry_path: Path):
        self.path = registry_path
        self._installations: list[Installation] = []
        self._load()

    def _load(self):
        """Load installations from file."""
        if not self.path.exists():
            self._installations = []
            return

        with open(self.path, 'r') as f:
            data = yaml.safe_load(f) or {}

        self._installations = [
            Installation.from_dict(inst)
            for inst in data.get('installations', [])
        ]

    def _save(self):
        """Save installations to file."""
        self.path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            'version': '1.0',
            'installations': [inst.to_dict() for inst in self._installations]
        }

        with open(self.path, 'w') as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)

    def add(self, installation: Installation):
        """Add an installation record."""
        # Remove any existing installation with same key
        self._installations = [
            inst for inst in self._installations
            if not (inst.module_name == installation.module_name and
                    inst.assistant == installation.assistant and
                    inst.scope == installation.scope and
                    inst.project_path == installation.project_path)
        ]
        self._installations.append(installation)
        self._save()

    def remove(self, module_name: str, assistant: str = None,
               scope: str = None, project_path: str = None) -> list[Installation]:
        """
        Remove installation records matching the criteria.

        Returns list of removed installations.
        """
        removed = []
        kept = []

        for inst in self._installations:
            matches = inst.module_name == module_name
            if assistant:
                matches = matches and inst.assistant == assistant
            if scope:
                matches = matches and inst.scope == scope
            if project_path:
                matches = matches and inst.project_path == project_path

            if matches:
                removed.append(inst)
            else:
                kept.append(inst)

        self._installations = kept
        self._save()
        return removed

    def find(self, module_name: str) -> list[Installation]:
        """Find all installations of a module."""
        return [
            inst for inst in self._installations
            if inst.module_name == module_name
        ]

    def all(self) -> list[Installation]:
        """Get all installations."""
        return self._installations.copy()
