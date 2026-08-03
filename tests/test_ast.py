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
    #
    # Asserted field by field rather than by whole-dict equality: the engine may
    # add a field the spec allows - it added `pos` - and an equality check turns
    # that into a failure here that says nothing about frontmatter. What this
    # test is for is that the CONTENT is raw.
    frontmatter = carve.parse("---toml\nx = 1\n---\n\nBody.\n")["children"][0]

    assert frontmatter["type"] == "frontmatter"
    assert frontmatter["format"] == "toml"
    assert frontmatter["content"] == "x = 1"
    assert "children" not in frontmatter


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


def test_a_published_span_slices_back_to_its_own_text():
    # Section 4 again: "MUST NOT emit `pos` with invented values".
    #
    # Stated as the property rather than as "this node has no span". The engine
    # places more of the tree over time - a table cell's text used to carry no
    # position and now does - and an absence assertion turns each of those
    # improvements into a failure that says nothing about correctness. What
    # section 4 forbids is a span pointing somewhere else, so check exactly that:
    # every published span must slice back to the text it belongs to.
    #
    # The escaped pipe is the case worth carrying. The parser splits the run at
    # the escape, so a span that spanned the whole reassembled cell text would
    # not be a slice of the source at any offset.
    source = "| a \\| b | c |\n|---|---|\n| d | e |\n"
    codepoints = list(source)
    wrong = []

    def check(node):
        if not isinstance(node, dict):
            return
        if node.get("type") == "text" and "pos" in node:
            span = node["pos"]
            sliced = "".join(codepoints[span["startOffset"]:span["endOffset"]])
            if sliced != node["value"]:
                wrong.append(f"{span} is {sliced!r}, want {node['value']!r}")
        for value in node.values():
            if isinstance(value, list):
                for child in value:
                    check(child)
            elif isinstance(value, dict):
                check(value)

    check(carve.parse(source))
    assert wrong == [], f"{len(wrong)} span(s) do not contain their own text: {wrong}"


def test_parse_json_returns_the_same_tree_as_parse():
    source = "# H\n\n- a\n- b\n"

    assert json.loads(carve.parse_json(source)) == carve.parse(source)
