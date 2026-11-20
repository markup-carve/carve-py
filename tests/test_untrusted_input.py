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


def test_safe_composes_with_extensions():
    out = carve.to_html(RAW_HTML, {'extensions': ['carve.tabs'], 'rawHtml': False})
    assert '&lt;script&gt;' in out
    assert '<script>' not in out


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


def test_other_targets_use_tree_writer():
    source = '![alt](image.png)\n'
    plain = carve.to_plain_text(source)
    assert 'alt' in plain
    tree = carve.parse(source)['tree']
    assert carve.write(tree, 'markdown')['output'] == carve.to_markdown(source)
    assert carve.write(tree, 'plain')['output'] == plain


@pytest.mark.parametrize("func", ["to_markdown", "to_plain_text", "to_ansi"])
def test_writer_helpers_refuse_retired_profile_keyword(func):
    render = getattr(carve, func)
    with pytest.raises(TypeError, match='profile'):
        render('hi', profile='nope')
    with pytest.raises(carve.CarveError, match='profile'):
        carve.render('hi', {'profile': 'nope'})


def test_non_html_targets_never_emit_live_raw_html():
    """Why there is no `safe` keyword on those targets: nothing to switch off."""
    assert "<script>" not in carve.to_markdown(RAW_HTML)
    assert "<script>" not in carve.to_plain_text(RAW_HTML)
