"""Include region selection and Markdown import over the pinned 0.2 engine."""

import carve
import pytest

DOC = (
    "intro\n"
    "%% #region setup\n"
    "one\n"
    "two\n"
    "%% #endregion\n"
    "// #region code\n"
    "x = 1\n"
    "// #endregion\n"
)


@pytest.mark.parametrize(
    ("name", "mode", "expected"),
    [("setup", "carve", (3, 4)), ("setup", "code", (3, 4)), ("code", "code", (7, 7))],
)
def test_select_include_region(name, mode, expected):
    assert carve.select_include_region(DOC, name, mode) == expected


def test_select_include_region_defaults_to_carve_markers():
    assert carve.select_include_region(DOC, "setup") == (3, 4)


def test_an_empty_region_ends_before_it_starts():
    assert carve.select_include_region("%% #region e\n%% #endregion\n", "e") == (2, 1)


def test_a_leading_bom_does_not_hide_a_line_one_marker():
    assert carve.select_include_region("﻿%% #region b\ny\n%% #endregion\n", "b") == (2, 2)


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
def test_an_invalid_region_raises_with_the_rule(source, name, mode):
    with pytest.raises(carve.IncludeRegionError) as caught:
        carve.select_include_region(source, name, mode)
    assert caught.value.rule == "include-region-invalid"
    assert isinstance(caught.value, ValueError)


def test_an_unknown_region_mode_is_refused():
    with pytest.raises(ValueError, match="mode must be"):
        carve.select_include_region(DOC, "setup", "markdown")


def test_from_markdown_reads_gfm():
    imported = carve.from_markdown("| a |\n|---|\n| b |\n\n~~gone~~ *em*\n")
    assert imported["source"] == carve.call(
        {"call": "importDocument", "source": "| a |\n|---|\n| b |\n\n~~gone~~ *em*\n", "from": "gfm"}
    )["source"]
    assert imported["tree"]["type"] == "document"
    assert "|=" in imported["source"]


@pytest.mark.parametrize("source_format", ["markdown", "gfm", "djot"])
def test_import_document_takes_the_engine_formats(source_format):
    imported = carve.import_document("*em*\n", source_format)
    expected = carve.call({"call": "importDocument", "source": "*em*\n", "from": source_format})
    assert imported["source"] == expected["source"]


def test_import_document_refuses_an_unknown_format():
    with pytest.raises(carve.CarveError) as caught:
        carve.import_document("x", "rtf")
    assert caught.value.name == "CarveOptionError"
