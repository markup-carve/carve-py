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

    assert frontmatter == {"type": "frontmatter", "format": "toml", "content": "x = 1"}


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
    # Section 4 again: "MUST NOT emit `pos` with invented values". A cell's TEXT
    # is reassembled - the parser unescapes `\\|` on the way in - so it is not a
    # verbatim slice of the source and carries no span, while the cell around it,
    # which is a slice, does.
    cell = carve.parse("| a | b |\n|---|---|\n| c | d |\n")["children"][0]["rows"][0]["cells"][0]

    assert "pos" in cell
    assert "pos" not in cell["children"][0]


def test_parse_json_returns_the_same_tree_as_parse():
    source = "# H\n\n- a\n- b\n"

    assert json.loads(carve.parse_json(source)) == carve.parse(source)
