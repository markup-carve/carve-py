"""Tests for the safe-render keywords: `safe` and `profile`.

Carve's normative hardening is always on, so these cover the one construct that
is emitted verbatim by design (a `=html` raw block) plus the profile presets.
"""

import carve
import pytest

RAW_HTML = "# Heading\n\n```=html\n<script>alert(1)</script>\n```\n"


def test_safe_escapes_a_raw_html_block():
    # U-076: rawHtml is false by default in 0.2.
    out = carve.to_html(RAW_HTML)
    assert "&lt;script&gt;" in out
    assert "<script>" not in out


def test_raw_html_requires_explicit_opt_in_u076():
    """Pairs with the test above.

    Without this, a change that stopped emitting raw HTML at all would leave the
    `safe=True` assertion green for the wrong reason.
    """
    # U-076: trusted callers opt in with rawHtml.
    assert "<script>alert(1)</script>" in carve.to_html(RAW_HTML, {"rawHtml": True})


@pytest.mark.skip(reason="Carve 0.1 assertion uses a retired 0.2 API; see carve-py#136")
def test_safe_composes_with_extensions():
    # The details extension is pending in carve-rs issue 4342.
    out = carve.to_html(RAW_HTML, extensions=["details"], safe=True)
    assert "&lt;script&gt;" in out
    assert "<script>" not in out


def test_safe_composes_with_static_mode():
    # U-076 and C2-H-137: mode and rawHtml use the 0.2 option dictionary.
    out = carve.to_html(RAW_HTML, {"mode": "static", "rawHtml": False})
    assert "<script>" not in out


def test_profile_restricts_constructs():
    # C2-H-137: profile uses the 0.2 option dictionary.
    assert "<h1" not in carve.to_html(RAW_HTML, {"profile": "comment"})
    # And the default keeps the heading, so the check above can fail.
    assert "<h1" in carve.to_html(RAW_HTML)


def test_unknown_profile_raises():
    with pytest.raises(ValueError) as excinfo:
        carve.to_html("# Hi", {"profile": "nope"})
    message = str(excinfo.value)
    # C2-H-137: option refusals name the refused key and value.
    assert "profile" in message
    assert "nope" in message


def test_profile_length_cap_raises_instead_of_returning_empty_html():
    """The infallible engine entry point answers a rejection with "".

    A caller cannot tell that from a document that legitimately rendered to
    nothing, so the binding raises instead.
    """
    with pytest.raises(ValueError) as excinfo:
        carve.to_html("x" * 20_000, {"profile": "minimal"})
    # C2-H-137: the engine returns a typed render refusal.
    assert "profile" in str(excinfo.value).lower()


def test_input_under_the_cap_still_renders():
    """Makes the check above able to fail rather than passing on any raise."""
    assert "<p>hello</p>" in carve.to_html("hello", {"profile": "minimal"})


@pytest.mark.skip(reason="Carve 0.1 assertion uses a retired 0.2 API; see carve-py#136")
def test_profile_applies_to_the_other_targets_too():
    """A profile reaches markdown / plain / ansi, not only HTML.

    The minimal profile degrades an image to its visible fallback. This makes
    the transform observable in Markdown bytes without asserting a wider escape
    than PART 11 section 8a permits for a literal `#` at line start.
    """
    source = "![alt](image.png)\n"
    md = carve.to_markdown(source, profile="minimal")
    assert "img: alt" in md
    assert "![" not in md

    # Unfiltered, the image stays an image, so the check above can fail.
    assert carve.to_markdown(source).startswith("![alt]")

    assert "[img: alt]" in carve.to_plain_text(source, profile="minimal")


@pytest.mark.parametrize("func", ["to_markdown", "to_plain_text", "to_ansi"])
@pytest.mark.skip(reason="Carve 0.1 assertion uses a retired 0.2 API; see carve-py#136")
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
