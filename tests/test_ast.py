"""The PART 12 exchange shape, published by this binding.

The AST is what every integration that is not "source to HTML" needs - an
editor, a linter, a converter - and this binding had no way to reach it at all.
The tree comes from the ENGINE's serializer (`carve_rs::to_json`), not from a
walker written here: carve-rb kept its own copy for a while and it drifted in
three ways nobody downstream could see, which is the failure this avoids.
"""

import json

import carve


def test_root_carries_exactly_the_three_fields():
    # PART 12 section 7. Frontmatter and footnote definitions are block nodes in
    # the tree, not root fields.
    ast = carve.parse("---\ntitle: T\n---\n\nBody[^a].\n\n[^a]: note\n")

    assert sorted(ast) == ["children", "srcByteLength", "type"]
    assert ast["type"] == "document"
    types = [child["type"] for child in ast["children"]]
    assert types == ["frontmatter", "paragraph", "footnote"]


def test_frontmatter_is_raw_not_parsed():
    # A parsed mapping cannot be serialized back to the bytes the author wrote,
    # so the wire carries the block verbatim plus its format.
    frontmatter = carve.parse("---toml\nx = 1\n---\n\nBody.\n")["children"][0]

    assert frontmatter["type"] == "frontmatter"
    assert frontmatter["format"] == "toml"
    assert frontmatter["content"] == "x = 1"
    # Section 4 requires a position on every node but the root, and the engine
    # places this one now. Asserting the whole dict pinned its ABSENCE, so the
    # test failed on the engine getting better rather than worse.
    assert "pos" in frontmatter


def test_nodes_carry_codepoint_positions():
    # PART 12 section 4: 1-based lines and columns, 0-based offsets, ends
    # exclusive, counted in CODEPOINTS. The astral character is the point - bytes
    # and UTF-16 units agree with codepoints below U+10000, so a wrong unit is
    # unobservable without one.
    ast = carve.parse("\U0001F600 *b*\n")
    strong = ast["children"][0]["children"][-1]

    assert strong["type"] == "strong"
    assert strong["pos"]["startColumn"] == 3
    assert strong["pos"]["startOffset"] == 2


def test_a_span_the_engine_cannot_place_is_absent_not_invented():
    # Section 4 again: "MUST NOT emit `pos` with invented values".
    #
    # The input matters. A single-line cell's text IS a verbatim slice of the
    # source, and the engine places it - this test used one and asserted the
    # position was absent, which held only while the engine could not do better.
    # A cell continued across lines with `+` is genuinely unplaceable: the two
    # halves are joined by a space the source does not contain, so the value is
    # not a slice of it at any offset (PART 12 section 1a merges the run; the
    # merged span would cover the delimiter and the newline).
    source = "|= a |= b |\n| x | A long description |\n+     | that continues     |\n"
    cell = carve.parse(source)["children"][0]["rows"][1]["cells"][1]

    assert "pos" in cell, "the cell itself is a slice of the source"
    text = cell["children"][0]
    assert text["value"] == "A long description that continues"
    assert "pos" not in text, "a value joined across lines must not claim a span"


def test_parse_json_returns_the_same_tree_as_parse():
    source = "# H\n\n- a\n- b\n"

    assert json.loads(carve.parse_json(source)) == carve.parse(source)
