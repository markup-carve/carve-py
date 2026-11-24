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
    # U-055: the GFM separator is a body row in 0.2, so use native headers.
    out = carve.to_html("|= a |= b |\n| 1 | 2 |\n")
    assert "<table>" in out
    # PART 10 SST9: a header cell states what it heads, `col` in the leading
    # header-row run. The bare `<th>a</th>` this used to assert was the output
    # of an engine that predated the rule, and no other check here would have
    # noticed the difference.
    assert '<th scope="col">a</th>' in out
    assert "<td>1</td>" in out


def test_combined_bold_italic():
    out = carve.to_html("*bold* and /italic/")
    assert "<strong>bold</strong>" in out
    assert "<em>italic</em>" in out


# --- Extensions ----------------------------------------------------------

MATH_SRC = "``` math\nx^2\n```\n"


def test_core_display_math_and_retired_extension_refusal():
    core = carve.to_html(MATH_SRC)
    math = carve.to_html('$$`x^2`')
    assert 'class="language-math"' in core
    assert 'class="math display"' in math
    assert r'\[x^2\]' in math
    with pytest.raises(carve.CarveError, match='math_block'):
        carve.to_html(MATH_SRC, extensions=['math_block'])


def test_to_html_with_extensions_helper():
    src = '::: tabs\n::: tab "A"\nx\n:::\n:::\n'
    assert carve.to_html_with_extensions(src, ['carve.tabs']) == carve.to_html(
        src, extensions=['carve.tabs']
    )


def test_native_table_and_retired_list_table_refusal():
    src = '|= A |= B |\n| x | y |\n'
    assert '<table>' in carve.to_html(src)
    with pytest.raises(carve.CarveError, match='list_table'):
        carve.to_html(src, extensions=['list_table'])


def test_empty_extensions_is_core():
    assert carve.to_html(MATH_SRC, extensions=[]) == carve.to_html(MATH_SRC)


def test_unknown_extension_raises():
    with pytest.raises(ValueError):
        carve.to_html("# Hi", extensions=["does_not_exist"])


def test_retired_code_callouts_are_refused():
    src = '```python\nresult = 1 + 1  <1>\n```\n\n<1> The sum.\n'
    assert '<pre>' in carve.to_html(src)
    with pytest.raises(carve.CarveError, match='code-callouts'):
        carve.to_html(src, extensions=['code-callouts'])


def test_extensions_list():
    exts = carve.extensions()
    assert isinstance(exts, list)
    assert set(exts) == {
        'carve.autolink', 'carve.externalLinks', 'carve.headingNumbers',
        'carve.headingPermalinks', 'carve.headingReference', 'carve.linkPolicy', 'carve.toc', 'carve.tocPlacement',
        'carve.cite', 'carve.codeCallouts', 'carve.codeGroup', 'carve.colorSwatch', 'carve.details',
        'carve.fencedRender.abc', 'carve.fencedRender.chart', 'carve.fencedRender.d2', 'carve.fencedRender.graphviz',
        'carve.fencedRender.mermaid', 'carve.fencedRender.plantuml', 'carve.fencedRender.vega-lite', 'carve.fencedRender.wavedrom',
        'carve.glossary', 'carve.imgFence.image', 'carve.imgFence.img', 'carve.index', 'carve.inlineFootnotesToParentheses',
        'carve.listTable', 'carve.mathBlock', 'carve.references', 'carve.semanticSpan', 'carve.smartQuotes',
        'carve.spoiler', 'carve.spoilerBlock', 'carve.tabNormalize', 'carve.tabs', 'carve.wiki',
    }


def test_extensions_list_covers_what_the_engine_registers():
    for name in ('carve.cite', 'carve.imgFence.image', 'carve.imgFence.img', 'carve.tabs', 'carve.wiki'):
        assert name in carve.extensions(), name


def test_navigation_extensions_are_listed_and_selectable():
    for name in ['carve.autolink', 'carve.externalLinks', 'carve.headingNumbers', 'carve.headingPermalinks', 'carve.headingReference', 'carve.linkPolicy', 'carve.toc', 'carve.tocPlacement']:
        assert name in carve.extensions()
        assert carve.to_html("Hi", extensions=[name]) == "<p>Hi</p>"


def test_retired_extension_aliases_are_refused():
    src = '::: tabs\n::: tab "A"\nx\n:::\n:::\n'
    for retired in ('heading_permalinks', 'heading-permalinks'):
        with pytest.raises(carve.CarveError, match=retired):
            carve.to_html(src, extensions=[retired])


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


def test_to_carve():
    # C2-W-035: the canonical writer writes a heading with `=`.
    assert carve.to_carve("# Hi\n\n\nBody") == "= Hi\n\nBody\n"


def test_import_html():
    # C2-T-005: importDocument returns tree, source and diagnostics instead of
    # the 0.1 value and report.
    html = carve.from_html('<p>Hello <strong>world</strong></p>')
    assert html["source"] == "Hello *world*\n"
    assert html["diagnostics"] == []
    assert html["tree"]["type"] == "document"


def test_markdown_import_uses_the_engine_call():
    # C2-T-003 leaves Markdown import outside the 0.2 core. The pinned engine
    # still offers it through the generic importDocument call.
    imported = carve.call({
        'call': 'importDocument', 'source': '*em* and **strong**', 'from': 'markdown',
    })
    assert imported['source'] == '/em/ and *strong*\n'
    assert imported['diagnostics'] == []


def test_markdown_import_preserves_ordered_task_text():
    imported = carve.call({
        'call': 'importDocument', 'source': '1. [ ] ordered task\n', 'from': 'markdown',
    })
    assert imported['source'] == '. \\[ ] ordered task\n'
    assert imported['diagnostics'] == []


def test_html_import_reports_dropped_attributes():
    # 0.2 renames the 0.1 attribute-dropped report row to the import-attribute-dropped
    # render-loss entry (data/lint-rules.json) and gives a byte range instead of an XPath.
    result = carve.from_html('<p onclick="alert(1)">hello</p>')
    assert result["source"] == "hello\n"
    [row] = result["diagnostics"]
    assert row["code"] == "import-attribute-dropped"
    assert row["channel"] == "render-loss"
    assert row["severity"] == "warning"
    assert row["foreignType"] == "p"


def test_markdown_depth_refusal_is_a_value_error():
    with pytest.raises(carve.CarveError, match='nesting limit'):
        carve.call({
            'call': 'importDocument', 'source': '> ' * 512 + 'text\n',
            'from': 'markdown',
        })
    assert carve.to_html('after refusal') == '<p>after refusal</p>'


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


# --- symbols map -------------------------------------------------------------


def test_symbols_map_renders_mapped_value():
    # C2-H-137: 0.2 options travel in one dictionary.
    out = carve.to_html("Ship it :rocket:", {"symbols": {"rocket": "🚀"}})
    assert "Ship it 🚀" in out
    assert ":rocket:" not in out


def test_symbols_map_works_alongside_extensions():
    src = '::: tabs\n::: tab "A"\nShip :rocket:.\n:::\n:::\n'
    opts = {'extensions': ['carve.tabs'], 'renderers': {'carve.tabs': 'standard'}, 'symbols': {'rocket': '🚀'}}
    assert '🚀' in carve.to_html(src, opts)
    assert '🚀' in carve.to_html_with_extensions(src, ['carve.tabs'], {'symbols': {'rocket': '🚀'}})


def test_symbols_map_plus_one_is_a_valid_name():
    assert "nice 👍" in carve.to_html("nice :+1:", {"symbols": {"+1": "👍"}})


def test_unmapped_symbol_stays_literal_with_a_map_active():
    out = carve.to_html(":rocket: and :shrug:", {"symbols": {"rocket": "🚀"}})
    assert "🚀" in out
    assert ":shrug:" in out


def test_symbols_map_does_not_defeat_the_word_boundary_guard():
    # Each of these names WOULD map if the leading word-boundary guard were lost.
    out = carve.to_html(
        "a:b:c and 10:30: and me@example.com",
        {"symbols": {"b": "MAPPED-B", "30": "MAPPED-30", "example": "MAPPED-EX"}},
    )
    assert "a:b:c" in out
    assert "10:30:" in out
    assert "me@example.com" in out
    assert "MAPPED-" not in out


def test_symbol_value_is_trusted_raw_output_not_escaped():
    # Documented contract: a symbol value is inserted RAW into the target format
    # (same trust class as the `renderers` map), so markup comes through as
    # markup. Never build a symbols map from untrusted input.
    out = carve.to_html(":bold:", {"symbols": {"bold": "<b>x</b>"}})
    assert "<b>x</b>" in out
    assert "&lt;b&gt;" not in out


def test_symbols_map_rejects_non_string_values():
    # C2-H-137: the 0.2 option boundary reports invalid values as CarveOptionError.
    with pytest.raises(carve.CarveError, match="symbols"):
        carve.to_html(":n:", {"symbols": {"n": 1}})


def test_retired_fenced_render_presets_are_refused():
    for name in ('fenced-render-plantuml', 'fenced-render-graphviz', 'fenced-render-d2', 'fenced-render-wavedrom', 'fenced-render-vega-lite', 'fenced-render-abc'):
        assert name not in carve.extensions()
        with pytest.raises(carve.CarveError, match=name):
            carve.to_html('Hi', extensions=[name])


# The fenced-render assertions below match an OPENING TAG PREFIX rather than a
# complete tag: `<pre class="plantuml"` and not `<pre class="plantuml">`. What
# they are about is the tag and the class the preset derives, and the engine is
# free to add attributes beside them - carve-rs 1e4b5a6 added `role="img"` and
# an `aria-label` to every diagram, which broke three of these while changing
# nothing they exist to check. Re-adding the `>` re-pins the whole attribute
# list to whatever the engine emitted the day it was written.
def test_plantuml_fence_keeps_language():
    for lang in ('plantuml', 'puml'):
        out = carve.to_html(f'```{lang}\nA -> B\n```')
        assert f'class="language-{lang}"' in out


def test_graphviz_fence_keeps_language():
    out = carve.to_html('```dot\na -> b\n```')
    assert 'class="language-dot"' in out
def test_standard_renderer_option_validation():
    src = '::: tabs\n::: tab "One"\nFirst.\n:::\n:::\n'
    with pytest.raises(carve.CarveError, match='extension_options'):
        carve.to_html(src, {'extension_options': {'tabs': {'mode': 'aria'}}})
    out = carve.to_html(src, {'extensions': ['carve.tabs'], 'renderers': {'carve.tabs': {'standard': {'mode': 'aria'}}}})
    assert 'role="tablist"' in out


def test_extension_options_enum_validation():
    src = '::: tabs\n::: tab "One"\nFirst.\n:::\n:::\n'
    out = carve.to_html(src, {'extensions': ['carve.tabs'], 'renderers': {'carve.tabs': {'standard': {'mode': 'aria'}}}})
    assert 'role="tablist"' in out
    with pytest.raises(carve.CarveError, match='mode'):
        carve.to_html(src, {'extensions': ['carve.tabs'], 'renderers': {'carve.tabs': {'standard': {'mode': 'script'}}}})


@pytest.mark.parametrize("name, option", [
    ("autolink", {"allowed_schemes": ["https"]}), ("code-group", {"wrapper_class": "cg"}),
    ("external-links", {"nofollow": True}), ("fenced-render", {"languages": ["diagram"]}),
    ("heading-level-shift", {"shift": 2}), ("heading-numbers", {"crossref": "title"}),
    ("heading-permalinks", {"levels": [2]}), ("heading-reference", {"css_class": "ref"}),
    ("math-block", {"language": "tex"}), ("img-fence", {"allow_style": True}),
    ("table-of-contents", {"list_type": "ol", "position": "bottom"}),
    ("tabs", {"id_prefix": "custom"}), ("wikilinks", {"new_window": True}),
])
def test_retired_extension_option_structs_are_refused(name, option):
    with pytest.raises(carve.CarveError, match='extension_options'):
        carve.to_html('# Heading', {'extension_options': {name: option}})
    with pytest.raises(carve.CarveError, match='not a standard extension'):
        carve.to_html('# Heading', extensions=[name])


def test_canonical_extension_options_reach_renderer():
    src = '::: tabs\n::: tab "One"\nFirst.\n:::\n:::\n'
    html = carve.to_html(src, {'extensions': ['carve.tabs'], 'renderers': {'carve.tabs': {'standard': {'mode': 'aria'}}}})
    assert 'role="tablist"' in html
    with pytest.raises(carve.CarveError, match='tabs'):
        carve.to_html(src, extensions=['tabs'])


def test_retired_fenced_render_refusal_keeps_core_fence():
    source = '```mermaid\ngraph LR\n```\n'
    assert 'class="language-mermaid"' in carve.to_html(source)
    with pytest.raises(carve.CarveError, match='fenced-render'):
        carve.to_html(source, extensions=['fenced-render'])


def test_a_lone_pipe_carrying_row_attributes_does_not_crash():
    """carve-rs#2341. Under the engine carve-py 0.1.6 shipped (carve-lang
    0.1.7) this input panicked inside the table check, so a Python caller got a
    `PanicException` and a backtrace on stderr instead of a value - a crash
    reachable from the public API on input a user can type. The line is
    paragraph text, so there is nothing to refuse.
    """
    for source in ("|{.r}", "|{#i}", "a\n|{.r}\n"):
        assert "<p>" in carve.to_html(source)
    assert carve.to_html("|{.r}") == "<p>|{.r}</p>"


def test_every_exported_function_is_declared_in_the_stub():
    """`carve.pyi` ships inside the wheel as `carve/__init__.pyi` beside a
    `py.typed`, so it is the contract a consumer type-checks against, and a
    function missing from it is invisible to them however well it works.

    Nothing measured that. `test_the_stub_declares_the_new_entry_point` in
    tests/test_includes.py names ONE function, so a second omission passes;
    deleting `render_ast_json` from the stub left this suite at 205 passed.
    Deriving the list from the registrations is what makes the next addition
    fail instead of the one after it being noticed by an embedder.
    """
    import pathlib
    import re

    root = pathlib.Path(__file__).resolve().parent.parent
    registered = set(
        re.findall(
            r"wrap_pyfunction!\(\s*([A-Za-z_][A-Za-z0-9_]*)",
            (root / "src" / "lib.rs").read_text(encoding="utf-8"),
        )
    )
    assert registered, "no #[pyfunction] registrations found; this check moved"

    stub = (root / "carve.pyi").read_text(encoding="utf-8")
    declared = set(re.findall(r"^def ([A-Za-z_][A-Za-z0-9_]*)\(", stub, re.M))

    assert registered - declared == set(), (
        "exported but absent from carve.pyi: "
        + ", ".join(sorted(registered - declared))
    )
    # The module really exposes each one, so the stub is not describing a
    # function that no longer exists.
    for name in sorted(registered):
        assert callable(getattr(carve, name)), name


def test_formatting_keeps_a_denied_scheme_exactly_as_authored():
    """carve-rs#2248. Formatting must not change the destination it parsed. The
    previous engine percent-encoded the parentheses of a denied scheme, so
    `carve fmt` rewrote the author's URL while the HTML target was already
    blanking it: two different answers to one destination.

    The pairing is the point. Canonical Carve preserves, HTML filters.
    """
    for source in (
        "[x](javascript:alert(1))\n",
        "![x](javascript:alert(1))\n",
        "<javascript:alert(1)>\n",
    ):
        assert carve.to_carve(source) == source, source
        assert "%28" not in carve.to_carve(source)

    # The render still refuses the destination, so preserving it in the source
    # is not a hole.
    assert carve.to_html("[x](javascript:alert(1))\n") == '<p><a href="">x</a></p>'
    assert carve.to_html("![x](javascript:alert(1))\n") == '<img src="" alt="x">'


def test_formatting_does_not_double_a_backslash_the_reparse_does_not_need():
    for source in (
        '{#i key="t\\zu"}\npara\n',
        '[x](u "t\\zu")\n',
        '[a]: u "t\\zu"\n\n[a]\n',
    ):
        formatted = carve.to_carve(source)
        assert 't\\zu' in formatted
        assert 't\\\\zu' not in formatted
        assert carve.to_html(formatted) == carve.to_html(source)
