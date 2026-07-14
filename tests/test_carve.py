"""Tests for the compiled `carve` Python binding.

These import the real native module and assert on actual conversions, so they
only pass once the wheel is built and installed (maturin develop / build).
"""

import carve
import pytest


def test_module_has_version():
    assert isinstance(carve.__version__, str)
    assert carve.__version__  # non-empty


def test_heading():
    out = carve.to_html("# Hi")
    assert "<h1" in out
    assert "Hi" in out


def test_bold():
    # Carve bold is *x* -> <strong>
    out = carve.to_html("*x*")
    assert "<strong>x</strong>" in out


def test_italic():
    # Carve italic is /x/ -> <em>
    out = carve.to_html("/x/")
    assert "<em>x</em>" in out


def test_list():
    out = carve.to_html("- one\n- two\n")
    assert "<ul>" in out
    assert "<li>one</li>" in out
    assert "<li>two</li>" in out


def test_link():
    out = carve.to_html("[text](https://example.com)")
    assert '<a href="https://example.com">text</a>' in out


def test_inline_code():
    out = carve.to_html("use `code` here")
    assert "<code>code</code>" in out


def test_table():
    out = carve.to_html("| a | b |\n|---|---|\n| 1 | 2 |\n")
    assert "<table>" in out
    assert "<th>a</th>" in out
    assert "<td>1</td>" in out


def test_combined_bold_italic():
    out = carve.to_html("*bold* and /italic/")
    assert "<strong>bold</strong>" in out
    assert "<em>italic</em>" in out


# --- Extensions ----------------------------------------------------------

MATH_SRC = "``` math\nx^2\n```\n"


def test_math_block_extension_changes_output():
    core = carve.to_html(MATH_SRC)
    ext = carve.to_html(MATH_SRC, extensions=["math_block"])
    # Core renders the fenced block as a code block; the extension renders math.
    assert 'class="language-math"' in core
    assert "math display" not in core
    assert '<div class="math display">\\[x^2\\]</div>' in ext
    assert core != ext


def test_to_html_with_extensions_helper():
    ext = carve.to_html_with_extensions(MATH_SRC, ["math_block"])
    assert "math display" in ext


def test_list_table_extension_changes_output():
    src = "::: list-table\n- - A\n  - B\n:::"
    core = carve.to_html(src)
    ext = carve.to_html(src, extensions=["list_table"])
    assert "<table" in ext
    assert core != ext


def test_empty_extensions_is_core():
    assert carve.to_html(MATH_SRC, extensions=[]) == carve.to_html(MATH_SRC)


def test_unknown_extension_raises():
    with pytest.raises(ValueError):
        carve.to_html("# Hi", extensions=["does_not_exist"])


def test_code_callouts_extension_changes_output():
    # A fenced code block with a <1> marker at the end of a line, followed by
    # a paragraph of callout definitions, triggers the code-callouts extension.
    src = "``` python\nresult = 1 + 1  <1>\n```\n\n<1> The sum.\n"
    core = carve.to_html(src)
    ext = carve.to_html(src, extensions=["code-callouts"])
    # The extension wraps the marker as <b class="callout">.
    assert 'class="callout"' in ext
    assert core != ext


def test_extensions_list():
    exts = carve.extensions()
    assert isinstance(exts, list)
    assert "math_block" in exts
    assert "list_table" in exts
    assert "code-callouts" in exts


# --- Other renderers -----------------------------------------------------

def test_to_markdown():
    out = carve.to_markdown("# Hi")
    assert "Hi" in out


def test_to_plain_text():
    out = carve.to_plain_text("# Hi")
    assert "Hi" in out


def test_to_ansi():
    out = carve.to_ansi("# Hi")
    assert "Hi" in out


# --- Engine language surface ---------------------------------------------
#
# These exercise the carve-rs engine through the binding's public API, so a
# stale engine pin in Cargo.lock shows up as a test failure rather than as a
# silently outdated language.

def test_superscript_and_subscript_are_braced_only():
    # Bare `^x^` / `,x,` are literal text; only the braced forms mark up.
    literal = carve.to_html("a ^2^ b and H,2,O")
    assert "<sup>" not in literal
    assert "<sub>" not in literal

    marked = carve.to_html("x{^2^} and H{,2,}O")
    assert "<sup>2</sup>" in marked
    assert "<sub>2</sub>" in marked


def test_symbol_inline_is_recognized():
    # An unmapped symbol renders its `:name:` source, but it is a real Symbol
    # node - attaching attributes proves it parsed as one rather than as text.
    assert '<span class="emoji">:smile:</span>' in carve.to_html(":smile:{.emoji}")


def test_symbol_word_boundary_guard():
    # A `:` preceded by a word character does not open a symbol.
    out = carve.to_html("a:b:c and 10:30: and me@example.com")
    assert "<span" not in out
    assert "a:b:c" in out
