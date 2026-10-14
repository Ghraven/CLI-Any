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


def test_names_unique_across_registries():
    # cli_hub.registry merges both files and matches names case-insensitively.
    names = [c["name"].lower() for f in ("registry.json", "public_registry.json") for c in _load(f)]
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
        assert isinstance(c["contributors"], list) and c["contributors"], (
            f"{c['name']} needs at least one contributor"
        )
        for ct in c["contributors"]:
            assert ct.get("name") and ct.get("url")


@pytest.mark.parametrize("fname", ["registry.json", "public_registry.json"])
def test_in_repo_skill_md_paths_exist(fname):
    for c in _load(fname):
        skill = c.get("skill_md")
        # URLs and installer commands (e.g. "npx skills add ...") are not local paths.
        if not skill or skill.startswith("http") or " " in skill:
            continue
        assert not Path(skill).is_absolute() and ".." not in Path(skill).parts, (
            f"{c['name']}: {skill} must be a relative in-repo path"
        )
        assert (REPO_ROOT / skill).is_file(), f"{c['name']}: {skill} not found"


def test_qgis_skill_md_is_canonical():
    # Regression: qgis once pointed at a harness-internal copy instead of root skills/.
    qgis = next(c for c in _load("registry.json") if c["name"] == "qgis")
    assert qgis["skill_md"] == "skills/cli-anything-qgis/SKILL.md"
    assert qgis["source_url"].endswith("/QGIS/agent-harness")
