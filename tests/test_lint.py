"""The linter binding.

The defect class `carve.lint` reports is the silent one: the document parses,
the renderer emits something, and what the author wrote never reaches the page.
So these tests assert on what a warning SAYS and where it POINTS, not merely
that some warning came back - a binding that returned an empty list for
everything would satisfy the weaker check on every clean document, which is
most of them.
"""

import carve


ORPHAN = "{#orphan .cls}\n\n"


def test_a_clean_document_reports_nothing():
    assert carve.lint("# Title\n\nA paragraph.\n") == []


def test_an_unattached_block_attribute_is_reported():
    warnings = carve.lint(ORPHAN)
    assert len(warnings) == 1
    warning = warnings[0]
    assert warning["rule"] == "unattached-block-attribute"
    assert warning["line"] == 1
    assert warning["column"] == 1
    assert "reaches no block" in warning["message"]


def test_a_warning_carries_every_documented_field():
    warning = carve.lint(ORPHAN)[0]
    assert set(warning) == {"line", "column", "rule", "message", "start", "end"}
    assert isinstance(warning["line"], int)
    assert isinstance(warning["column"], int)
    assert isinstance(warning["rule"], str)
    assert isinstance(warning["message"], str)
    assert isinstance(warning["start"], int)
    assert isinstance(warning["end"], int)


def test_the_offsets_slice_the_offending_text():
    source = ORPHAN
    warning = carve.lint(source)[0]
    assert source[warning["start"] : warning["end"]] == "{#orphan .cls}"


def test_the_offsets_are_codepoints_not_bytes():
    """The one thing this binding does that a direct wrapper would not.

    The Rust API reports byte offsets, deliberately - a Rust caller slices
    `&str` with them. Python slices by codepoint, so handing those through
    unconverted mis-slices every document carrying a non-ASCII character
    before a warning. "e-acute" is two bytes and one codepoint, so ten of them
    make the two units differ by exactly ten and a byte offset cannot pass by
    accident.
    """
    prefix = "é" * 10 + "\n\n"
    source = prefix + ORPHAN
    warning = carve.lint(source)[0]

    assert warning["start"] == len(prefix)
    assert warning["start"] != len(prefix.encode("utf-8"))
    assert source[warning["start"] : warning["end"]] == "{#orphan .cls}"


def test_a_multibyte_character_inside_the_warning_still_slices():
    """The span itself, not only the text before it, may hold non-ASCII.

    The non-ASCII goes in a quoted VALUE rather than in a class name, because
    Carve's attribute identifiers are strict ASCII - `{#orphan .café}` is not
    an attribute line at all, so it produces no warning to slice and would
    make this test pass without measuring anything.
    """
    source = '{#orphan key="café"}\n\n'
    warning = carve.lint(source)[0]
    assert source[warning["start"] : warning["end"]] == '{#orphan key="café"}'


def test_every_warning_in_a_document_slices_correctly():
    """Two warnings, so the second's offsets are exercised after the first."""
    # An attribute line followed by a block ATTACHES, so a document needs two
    # genuinely unattached ones: the quote's own, which its container ends
    # before anything follows it, and one at the end of the document. The
    # accented prefix keeps byte and codepoint offsets apart for both.
    source = "éé\n\n> {#inner}\n\ntext\n\n{#outer}\n\n"
    warnings = carve.lint(source)
    assert len(warnings) == 2
    assert source[warnings[0]["start"] : warnings[0]["end"]] == "{#inner}"
    assert source[warnings[1]["start"] : warnings[1]["end"]] == "{#outer}"


def test_extensions_is_accepted():
    """The only option the engine's linter reads, so the only one exposed."""
    assert carve.lint(ORPHAN, extensions=["details"])[0]["rule"] == (
        "unattached-block-attribute"
    )


def test_an_unknown_extension_is_refused():
    """Rather than silently linting with the extension absent."""
    try:
        carve.lint(ORPHAN, extensions=["definitely-not-an-extension"])
    except ValueError:
        return
    raise AssertionError("an unknown extension was accepted")


def test_an_empty_document_reports_nothing_and_does_not_crash():
    assert carve.lint("") == []
