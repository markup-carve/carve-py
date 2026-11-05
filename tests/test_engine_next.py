"""API and readings of the engine release after 0.1.13."""

import json

import carve


def test_decision_trace_is_a_header_then_one_record_per_line():
    records = [json.loads(line) for line in carve.decision_trace("- a\n  b\n\n> q\n").splitlines()]
    assert records[0] == {"trace": "carve-decision-trace", "version": 1, "engine": "carve-rs"}
    assert [record["line"] for record in records[1:]] == [1, 2, 3, 4]
    assert records[4]["owner"] == "doc/quote:4"


def test_caption_hints_are_opt_in():
    source = "![a](b.png)\n\nFigure 1: a cat\n"
    assert carve.lint(source) == []
    [warning] = carve.lint(source, caption_hints=True)
    assert warning["rule"] == "caption-looking-paragraph"
    assert (warning["line"], source[warning["start"]]) == (3, "F")


def test_the_writer_spells_breaks_and_alignment_canonically():
    assert carve.to_carve("a\n\n---\n\nb\n") == "a\n\n***\n\nb\n"
    assert carve.to_carve("|=> A |= B |\n| x | y |\n") == "|={>} A |= B |\n| x | y |\n"
    assert carve.to_carve("| A | B |\n|--:|---|\n| x | y |\n") == "|={>} A |= B |\n| x | y |\n"


def test_lint_names_the_deprecated_spellings():
    rules = [warning["rule"] for warning in carve.lint("|=> A |\n| x |\n\n---\n")]
    assert rules == ["deprecated-cell-alignment", "thematic-break-spelling"]


def test_markdown_import_reads_alerts_and_html_comments():
    assert carve.from_markdown("> [!NOTE]\n> hi\n")["value"] == "::: note\nhi\n:::\n"
    codes = [row["code"] for row in carve.from_markdown("<!-- c -->\n\npara\n")["report"]["diagnostics"]]
    assert "markdown-html-comment" in codes
