"""Extension-generated ids join the document id namespace (extensions
contract section 2.6; markup-carve/carve#238).

carve-py never reimplements the renderer, so the deduplication itself lives
in the carve-rs engine: ids minted by extensions must be reserved in the same
namespace as explicit `{#id}` attributes and generated heading ids, using the
heading mechanism (first use keeps the base name, each collision takes the
next free 1-based numeric suffix, skipping candidates already reserved).

These tests pin that behavior end-to-end through the binding for the affected
extension that exists in the engine: citations (`ref-{key}` reference-entry
ids and the citation hrefs that point at them). Scope notes:

- The engine has no tabs or code-group extensions, so the `tabset-N` /
  `codegroup-N` scenarios from carve-js / carve-php have no analog here.
- The `cite-{key}-{n}` back-link anchors render only when a bibliography pool
  is supplied, which this binding does not expose; the carve-rs test suite
  covers them.

The collision tests skip (with the reason below) while the pinned carve-lang
revision predates the engine fix; they activate on the next dependency bump.
Scenarios mirror carve-js test/extension-id-namespace.test.ts for parity.
"""

import carve
import pytest

# A minimal cited document: one citation, an in-document definition, and the
# auto-appended references list carrying `<li id="ref-foo">`.
CITED = "See [@foo].\n\n[@foo]: Foo, Author (2020). The Foo Paper.\n"


def render(source: str) -> str:
    return carve.to_html(source, extensions=["citations"])


def _engine_dedupes_extension_ids() -> bool:
    """Probe whether the linked carve-rs engine reserves extension ids."""
    html = render("{#ref-foo}\nReserved.\n\n" + CITED)
    return 'id="ref-foo-2"' in html


needs_engine_fix = pytest.mark.skipif(
    not _engine_dedupes_extension_ids(),
    reason=(
        "pinned carve-lang engine predates the extension-id-namespace fix "
        "(markup-carve/carve#238); bump the carve-rs dependency"
    ),
)


# --- No collision: ids stay byte-identical ---------------------------------


def test_no_collision_ids_are_stable():
    html = render(CITED)
    assert 'href="#ref-foo"' in html
    assert '<li id="ref-foo">' in html


def test_no_collision_output_shape_is_stable():
    # Golden pin: a document without id collisions must render byte-identical
    # before and after the engine fix.
    assert render(CITED) == (
        '<p>See [<a data-cite-key="foo" href="#ref-foo">1</a>].</p>\n'
        '<ol class="references">\n'
        '  <li id="ref-foo">Foo, Author (2020). The Foo Paper.</li>\n'
        "</ol>"
    )


# --- A heading auto-slug collides with the generated reference id ----------


HEADING_SRC = "# ref foo\n\n" + CITED


@needs_engine_fix
def test_heading_slug_keeps_the_base_id():
    assert '<section id="ref-foo">' in render(HEADING_SRC)


@needs_engine_fix
def test_reference_entry_avoids_the_heading_slug():
    assert '<li id="ref-foo-2">' in render(HEADING_SRC)


@needs_engine_fix
def test_citation_href_follows_the_bumped_reference_id():
    html = render(HEADING_SRC)
    assert 'href="#ref-foo-2"' in html
    assert 'href="#ref-foo"' not in html


# --- An explicit {#id} attribute collides with the generated id ------------


EXPLICIT_SRC = "{#ref-foo}\nReserved.\n\n" + CITED


@needs_engine_fix
def test_explicit_id_keeps_the_base_id():
    assert '<p id="ref-foo">Reserved.</p>' in render(EXPLICIT_SRC)


@needs_engine_fix
def test_reference_entry_avoids_the_explicit_id():
    html = render(EXPLICIT_SRC)
    assert '<li id="ref-foo-2">' in html
    assert 'href="#ref-foo-2"' in html


@needs_engine_fix
def test_no_duplicate_dom_ids_remain():
    html = render(EXPLICIT_SRC)
    assert html.count('id="ref-foo"') == 1  # the explicit paragraph only


@needs_engine_fix
def test_suffix_skips_already_reserved_candidates():
    # ref-foo and ref-foo-2 are both taken, so the generated id jumps to -3.
    html = render("{#ref-foo}\nA.\n\n{#ref-foo-2}\nB.\n\n" + CITED)
    assert '<li id="ref-foo-3">' in html
    assert 'href="#ref-foo-3"' in html
