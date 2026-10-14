"""Schema checks for the repo-level registry files (see CONTRIBUTING 'Registry fields')."""

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
REQUIRED = {
    "name", "display_name", "version", "description", "requires", "homepage",
    "source_url", "install_cmd", "entry_point", "skill_md", "category",
    "contributors",
}


def _load(name):
    return json.loads((REPO_ROOT / name).read_text(encoding="utf-8"))["clis"]


@pytest.mark.parametrize("fname", ["registry.json", "public_registry.json"])
def test_names_unique(fname):
    names = [c["name"] for c in _load(fname)]
    assert len(names) == len(set(names))


@pytest.mark.parametrize("fname", ["registry.json", "public_registry.json"])
def test_required_fields_and_contributors_shape(fname):
    for c in _load(fname):
        # Public (third-party) entries may install via npm/other managers.
        optional = {"install_cmd"} if fname == "public_registry.json" else set()
        missing = REQUIRED - c.keys() - optional
        assert not missing, f"{c.get('name')} missing {sorted(missing)}"
        assert "contributor" not in c and "contributor_url" not in c, (
            f"{c['name']} uses legacy contributor fields; use 'contributors' list"
        )
        assert isinstance(c["contributors"], list)
        for ct in c["contributors"]:
            assert ct.get("name") and ct.get("url")


def test_in_repo_skill_md_paths_exist():
    for c in _load("registry.json"):
        skill = c.get("skill_md")
        if skill and not skill.startswith("http"):
            assert (REPO_ROOT / skill).is_file(), f"{c['name']}: {skill} not found"
