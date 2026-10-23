"""Aligned table formatting and include-region selection (markup-carve/carve#3333).

The alignment rows are the spec's shared fixtures, read from the spec checkout
next to CARVE_SPEC_CORPUS; unset, those tests skip like the corpus does. The
region expectations were taken from carve-rs `select_include_region` directly.
"""

import json
import os
import pathlib

import carve
import pytest

CORPUS = os.environ.get("CARVE_SPEC_CORPUS")


def _alignment_rows():
    if not CORPUS:
        return []
    path = pathlib.Path(CORPUS).parent.parent / "resources" / "spec" / "table-alignment-fixtures.json"
    return json.loads(path.read_text(encoding="utf-8"))


ROWS = _alignment_rows()

needs_spec = pytest.mark.skipif(
    not CORPUS, reason="CARVE_SPEC_CORPUS not set (see .github/workflows/ci.yml)"
)


@needs_spec
def test_alignment_fixtures_are_present():
    assert len(ROWS) >= 13


@needs_spec
@pytest.mark.parametrize("row", ROWS, ids=[row["name"] for row in ROWS])
def test_align_tables_matches_the_shared_fixture(row):
    assert carve.to_carve(row["canonical"], align_tables=True) == row["aligned"]
    assert carve.to_carve(row["canonical"], strict=True, align_tables=True) == row["aligned"]


@needs_spec
@pytest.mark.parametrize("row", ROWS, ids=[row["name"] for row in ROWS])
def test_aligned_output_formats_back_to_canonical(row):
    assert carve.to_carve(row["aligned"]) == row["canonical"]


def test_align_tables_is_off_by_default():
    source = "| a | longer |\n| < | c |\n"
    assert carve.to_carve(source) == source
    assert carve.to_carve(source, align_tables=True) == "| a | longer |\n| < | c      |\n"


DOC = (
    "intro\n"
    "%% #region setup\n"
    "a\n"
    "b\n"
    "%% #endregion\n"
    "// #region code\n"
    "x\n"
    "// #endregion\n"
)


@pytest.mark.parametrize(
    ("name", "mode", "expected"),
    [
        ("setup", "carve", (3, 4)),
        ("setup", "code", (3, 4)),
        ("code", "code", (7, 7)),
    ],
)
def test_select_include_region(name, mode, expected):
    assert carve.select_include_region(DOC, name, mode) == expected


@pytest.mark.parametrize("mode", ["carve", "code"])
def test_a_leading_bom_does_not_hide_a_line_one_marker(mode):
    source = "\ufeff%% #region b\ny\n%% #endregion\n"
    assert carve.select_include_region(source, "b", mode) == (2, 2)


def test_an_html_comment_marker_counts_only_in_code_mode():
    source = "<!-- #region h -->\nz\n<!-- #endregion -->\n"
    assert carve.select_include_region(source, "h", "code") == (2, 2)
    with pytest.raises(carve.IncludeRegionError):
        carve.select_include_region(source, "h", "carve")


def test_an_empty_region_ends_before_it_starts():
    source = "%% #region e\n%% #endregion\n"
    assert carve.select_include_region(source, "e", "carve") == (2, 1)


@pytest.mark.parametrize(
    ("source", "name", "mode"),
    [
        (DOC, "code", "carve"),
        (DOC, "missing", "code"),
        ("%% #region a\nx\n", "a", "carve"),
        ("%% #region a\n%% #endregion\n%% #region a\n%% #endregion\n", "a", "code"),
    ],
    ids=["comment-marker-in-carve-mode", "missing", "unpaired", "duplicate"],
)
def test_an_invalid_region_raises_with_the_rule_id(source, name, mode):
    with pytest.raises(carve.IncludeRegionError) as caught:
        carve.select_include_region(source, name, mode)
    assert caught.value.rule == "include-region-invalid"
    assert isinstance(caught.value, ValueError)


def test_an_unknown_mode_is_refused():
    with pytest.raises(ValueError, match="mode must be"):
        carve.select_include_region(DOC, "setup", "markdown")


def test_an_include_that_is_not_utf8_warns_as_non_text(tmp_path):
    (tmp_path / "blob.crv").write_bytes(b"ok \xff\xfe\n")
    result = carve.render_with_includes("{{ blob.crv }}\n", str(tmp_path))
    assert [w["rule"] for w in result["warnings"]] == ["include-non-text"]
