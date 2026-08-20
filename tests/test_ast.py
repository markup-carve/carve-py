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
    # The input matters. A cell continued across lines with `+` is genuinely
    # unplaceable: the two halves are joined by a space the source does not
    # contain, and the halves are not even adjacent - the next column's text
    # sits between them - so neither the cell nor its value is a slice of the
    # source at any offset.
    #
    # PART 12 names this exact case among the REASSEMBLED nodes that must omit
    # `pos`: "A table cell continued on a `+` line, the hard break a line block
    # makes from a soft one, ... all have values that are not a slice of the
    # source at any offset, so no honest span exists." The omission applies to
    # the cell itself, not only to the text it carries.
    source = "|= a |= b |\n| x | A long description |\n+     | that continues     |\n"
    cell = carve.parse(source)["children"][0]["rows"][1]["cells"][1]

    assert "pos" not in cell, "a cell reassembled across lines must not claim a span"
    text = cell["children"][0]
    assert text["value"] == "A long description that continues"
    assert "pos" not in text, "a value joined across lines must not claim a span"


def test_parse_json_returns_the_same_tree_as_parse():
    source = "# H\n\n- a\n- b\n"

    assert json.loads(carve.parse_json(source)) == carve.parse(source)


def test_parse_carries_positions_unless_asked_otherwise():
    """The AST entry points have always returned spans, and still must.

    `positions` reaching the engine's own default here would silently strip
    `pos` from every existing caller's tree - the kind of change that passes
    every test that was adjusted to it.
    """
    source = "# Title\n"

    assert "pos" in carve.parse(source)["children"][0]
    assert "pos" in json.loads(carve.parse_json(source))["children"][0]
    assert "pos" not in carve.parse(source, positions=False)["children"][0]
