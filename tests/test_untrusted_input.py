"""Tests for the safe-render keywords: `safe` and `profile`.

Carve's normative hardening is always on, so these cover the one construct that
is emitted verbatim by design (a `=html` raw block) plus the profile presets.
"""

import carve
import pytest

RAW_HTML = "# Heading\n\n```=html\n<script>alert(1)</script>\n```\n"


def test_safe_escapes_a_raw_html_block():
    out = carve.to_html(RAW_HTML, safe=True)
    assert "&lt;script&gt;" in out
    assert "<script>" not in out


def test_raw_html_is_emitted_verbatim_by_default():
    """Pairs with the test above.

    Without this, a change that stopped emitting raw HTML at all would leave the
    `safe=True` assertion green for the wrong reason.
    """
    assert "<script>alert(1)</script>" in carve.to_html(RAW_HTML)


def test_safe_composes_with_extensions():
    out = carve.to_html(RAW_HTML, extensions=["details"], safe=True)
    assert "&lt;script&gt;" in out
    assert "<script>" not in out


def test_safe_composes_with_static_mode():
    out = carve.to_html(RAW_HTML, mode="static", safe=True)
    assert "<script>" not in out


def test_profile_restricts_constructs():
    assert "<h1" not in carve.to_html(RAW_HTML, profile="comment")
    # And the default keeps the heading, so the check above can fail.
    assert "<h1" in carve.to_html(RAW_HTML)


def test_unknown_profile_raises():
    with pytest.raises(ValueError) as excinfo:
        carve.to_html("# Hi", profile="nope")
    message = str(excinfo.value)
    assert "comment" in message
    assert "minimal" in message


def test_profile_length_cap_raises_instead_of_returning_empty_html():
    """The infallible engine entry point answers a rejection with "".

    A caller cannot tell that from a document that legitimately rendered to
    nothing, so the binding raises instead.
    """
    with pytest.raises(ValueError) as excinfo:
        carve.to_html("x" * 20_000, profile="minimal")
    assert "Profile violations" in str(excinfo.value)


def test_input_under_the_cap_still_renders():
    """Makes the check above able to fail rather than passing on any raise."""
    assert "<p>hello</p>" in carve.to_html("hello", profile="minimal")


def test_profile_applies_to_the_other_targets_too():
    """A profile reaches markdown / plain / ansi, not only HTML.

    The comment profile disallows headings, so the heading becomes text. In the
    Markdown target that text is escaped (`\\# Heading`), because a bare `#`
    would re-parse as a heading downstream - the filtering would otherwise undo
    itself.
    """
    md = carve.to_markdown(RAW_HTML, profile="comment")
    assert "\\# Heading" in md
    assert not md.startswith("# ")

    # Unfiltered, the heading stays a real heading, so the check above can fail.
    assert carve.to_markdown(RAW_HTML).startswith("# Heading")

    assert "Heading" in carve.to_plain_text(RAW_HTML, profile="comment")


@pytest.mark.parametrize("func", ["to_markdown", "to_plain_text", "to_ansi"])
def test_profile_is_not_swallowed_by_the_no_extension_fast_path(func):
    """These three take a fast path when no extensions are requested.

    That path returned before `profile` was read, so the keyword was accepted
    and silently ignored - which is worse than not offering it. Both a bad name
    and a rejection must still surface.
    """
    render = getattr(carve, func)
    with pytest.raises(ValueError):
        render("hi", profile="nope")
    with pytest.raises(ValueError):
        render("x" * 20_000, profile="minimal")


def test_non_html_targets_never_emit_live_raw_html():
    """Why there is no `safe` keyword on those targets: nothing to switch off."""
    assert "<script>" not in carve.to_markdown(RAW_HTML)
    assert "<script>" not in carve.to_plain_text(RAW_HTML)
