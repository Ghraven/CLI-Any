"""Non-finite rotation / sync offset values must be rejected with ValueError."""

import json

import pytest

from cli_anything.obs_studio.core import audio as audio_mod
from cli_anything.obs_studio.core import project as project_mod
from cli_anything.obs_studio.core import sources as src_mod


@pytest.fixture
def proj():
    p = project_mod.create_project()
    src_mod.add_source(p, "color")
    audio_mod.add_audio_source(p)
    return p


@pytest.mark.parametrize("bad", ["nan", "inf", "-inf", float("nan"), float("inf"), "abc"])
def test_set_rotation_rejects_non_finite(proj, bad):
    with pytest.raises(ValueError):
        src_mod.set_source_property(proj, 0, "rotation", bad)
    assert proj["scenes"][0]["sources"][0]["rotation"] == 0
    json.dumps(proj, allow_nan=False)


def test_set_rotation_accepts_finite(proj):
    src = src_mod.set_source_property(proj, 0, "rotation", "45.5")
    assert src["rotation"] == 45.5


@pytest.mark.parametrize("bad", ["nan", "abc", float("inf"), float("nan")])
def test_sync_offset_rejects_non_finite(proj, bad):
    with pytest.raises(ValueError):
        audio_mod.set_sync_offset(proj, 0, bad)
    assert proj["audio_sources"][0]["sync_offset"] == 0


def test_sync_offset_accepts_int(proj):
    assert audio_mod.set_sync_offset(proj, 0, "-120")["sync_offset"] == -120
