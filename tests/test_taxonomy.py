from pathlib import Path

import pytest

from ai_email_agent.taxonomy import TaxonomyError, load_categories


def test_loads_default_taxonomy_from_configs():
    categories = load_categories()
    names = {c.name for c in categories}
    assert names == {"support", "sales", "billing", "spam"}
    assert all(c.description for c in categories)


def test_missing_file_raises(tmp_path: Path):
    with pytest.raises(TaxonomyError, match="not found"):
        load_categories(tmp_path / "does-not-exist.yaml")


def test_malformed_yaml_raises(tmp_path: Path):
    path = tmp_path / "categories.yaml"
    path.write_text("categories: [unterminated")
    with pytest.raises(TaxonomyError, match="not valid YAML"):
        load_categories(path)


def test_missing_categories_key_raises(tmp_path: Path):
    path = tmp_path / "categories.yaml"
    path.write_text("not_categories: []")
    with pytest.raises(TaxonomyError, match="non-empty 'categories' list"):
        load_categories(path)


def test_entry_missing_description_raises(tmp_path: Path):
    path = tmp_path / "categories.yaml"
    path.write_text("categories:\n  - name: support\n")
    with pytest.raises(TaxonomyError, match="non-empty 'name' and 'description'"):
        load_categories(path)


def test_duplicate_name_raises(tmp_path: Path):
    path = tmp_path / "categories.yaml"
    path.write_text(
        "categories:\n"
        "  - name: support\n    description: a\n"
        "  - name: support\n    description: b\n"
    )
    with pytest.raises(TaxonomyError, match="duplicate category name"):
        load_categories(path)
