"""The 0.2 tabs renderer reserves generated ids in the document namespace.

C2-X-039 through C2-X-048 replace the 0.1 citations renderer's generated
reference ids with the standard tabs renderer's controls and labels.
"""

import carve

TABS = '::: tabs\n::: tab "A"\nx\n:::\n:::\n'
OPTIONS = {"extensions": ["carve.tabs"], "renderers": {"carve.tabs": "standard"}}


def render(source: str) -> str:
    return carve.to_html(source, OPTIONS)


def test_no_collision_ids_are_stable():
    html = render(TABS)
    assert 'id="tabs-1-0"' in html
    assert 'for="tabs-1-0"' in html


def test_no_collision_output_shape_is_stable():
    assert render(TABS) == (
        '<div class="tabs" role="group" aria-label="Tabs"><input type="radio" '
        'name="tabs-1" id="tabs-1-0" checked><label for="tabs-1-0">A</label>'
        '<div class="tab-panel" role="group" aria-label="A"><p>x</p></div></div>'
    )


def test_heading_slug_keeps_the_base_id():
    assert '<section id="tabs-1-0">' in render('# tabs 1 0\n\n' + TABS)


def test_reference_entry_avoids_the_heading_slug():
    assert 'id="tabs-2-0"' in render('# tabs 1 0\n\n' + TABS)


def test_citation_href_follows_the_bumped_reference_id():
    html = render('# tabs 1 0\n\n' + TABS)
    assert 'for="tabs-2-0"' in html
    assert 'for="tabs-1-0"' not in html


def test_explicit_id_keeps_the_base_id():
    assert '<p id="tabs-1-0">Reserved.</p>' in render('{#tabs-1-0}\nReserved.\n\n' + TABS)


def test_reference_entry_avoids_the_explicit_id():
    html = render('{#tabs-1-0}\nReserved.\n\n' + TABS)
    assert 'id="tabs-2-0"' in html
    assert 'for="tabs-2-0"' in html


def test_no_duplicate_dom_ids_remain():
    html = render('{#tabs-1-0}\nReserved.\n\n' + TABS)
    assert html.count('id="tabs-1-0"') == 1


def test_suffix_skips_already_reserved_candidates():
    html = render('{#tabs-1-0}\nA.\n\n{#tabs-2-0}\nB.\n\n' + TABS)
    assert 'id="tabs-3-0"' in html
    assert 'for="tabs-3-0"' in html
