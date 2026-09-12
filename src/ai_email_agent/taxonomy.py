"""Category taxonomy for email classification.

Loaded from ``configs/categories.yaml`` (not hardcoded) so the label set can
be extended without a code change — the Phase 1 acceptance criterion this
module exists to satisfy.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

# src/ai_email_agent/taxonomy.py -> src/ai_email_agent -> src -> project root
_DEFAULT_PATH = Path(__file__).resolve().parents[2] / "configs" / "categories.yaml"


@dataclass(frozen=True)
class Category:
    name: str
    description: str


class TaxonomyError(ValueError):
    """Raised when the category taxonomy file is missing or malformed."""


def load_categories(path: Path | str | None = None) -> list[Category]:
    """Load the category taxonomy from a YAML file.

    ``path`` defaults to ``configs/categories.yaml``. A missing or malformed
    file is a hard error regardless of whether ``path`` was explicit or the
    default — classifying against a silently-empty taxonomy would produce a
    wrong result with no signal that anything went wrong.
    """
    target = Path(path) if path is not None else _DEFAULT_PATH
    if not target.exists():
        raise TaxonomyError(f"category taxonomy file not found: {target}")

    try:
        raw = yaml.safe_load(target.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise TaxonomyError(f"category taxonomy file is not valid YAML: {target}: {exc}") from exc

    entries = raw.get("categories") if isinstance(raw, dict) else None
    if not isinstance(entries, list) or not entries:
        raise TaxonomyError(
            f"category taxonomy file must define a non-empty 'categories' list: {target}"
        )

    categories: list[Category] = []
    seen_names: set[str] = set()
    for entry in entries:
        name = entry.get("name") if isinstance(entry, dict) else None
        description = entry.get("description") if isinstance(entry, dict) else None
        if not isinstance(name, str) or not name.strip() or not isinstance(description, str) or not description.strip():
            raise TaxonomyError(
                f"each category must have a non-empty 'name' and 'description', got: {entry!r}"
            )
        name = name.strip()
        if name in seen_names:
            raise TaxonomyError(f"duplicate category name in taxonomy file: {name!r}")
        seen_names.add(name)
        categories.append(Category(name=name, description=" ".join(description.split())))

    return categories
