"""0.2 verified examples exercise the binding against the pinned spec corpus."""

import json
import os
from pathlib import Path

import carve
import pytest


CORPUS = os.environ.get("CARVE_SPEC2_EXAMPLES")
pytestmark = pytest.mark.skipif(not CORPUS, reason="Carve 0.2 examples path not supplied")


def test_verified_render_examples():
    rows = json.loads(Path(CORPUS).read_text(encoding="utf-8"))["examples"]
    catalog = json.loads((Path(CORPUS).parent.parent / "data" / "options.json").read_text(encoding="utf-8"))
    parse_keys = {
        option["name"] for option in catalog["options"]
        if set([option["read_by"]] if isinstance(option["read_by"], str) else option["read_by"])
        & {"parse", "resolve"}
    }
    selected = [
        row for row in rows
        if row.get("kind") == "render"
        and row.get("status") == "verified"
        and isinstance(row.get("expected", {}).get("html"), str)
    ]
    assert len(selected) >= 273
    for row in selected:
        options = row.get("options") or {}
        assert carve.render(row["input"], options)["html"] == row["expected"]["html"], row["id"]
        expected_tree = row["expected"].get("tree")
        if isinstance(expected_tree, dict):
            # C2-A-162 compares tree value; generated position metadata is
            # separately covered by direct parse tests.
            parse_options = {key: value for key, value in options.items() if key in parse_keys}
            assert carve.parse(row["input"], parse_options)["tree"]["children"] == expected_tree["children"], row["id"]


def test_source_only_lint_clause_cases():
    rows = json.loads(Path(CORPUS).with_name("clause-cases.json").read_text(encoding="utf-8"))["cases"]
    selected = [
        row for row in rows
        if row.get("kind") == "lint" and isinstance(row.get("input"), str)
        and not row.get("files") and not row.get("options")
    ]
    assert len(selected) >= 371
    for row in selected:
        actual = [entry["code"] for entry in carve.lint(row["input"])["diagnostics"]]
        expected = [
            entry if isinstance(entry, str) else entry["code"]
            for entry in row["expected"].get("diagnostics", [])
        ]
        assert all(code in actual for code in expected), row["id"]


def test_cc800_ordered_list_kind_split():
    source = "v. a\nvi. b\n"
    assert "ordered-list-kind-split" in [entry["code"] for entry in carve.lint(source)["diagnostics"]]
