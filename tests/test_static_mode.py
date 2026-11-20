"""Static tabs and native host renderers through the Carve 0.2 API."""

import carve
import pytest

MERMAID = "```mermaid\ngraph TD; A-->B;\n```"
MATH = "```math\n\\int_0^1 x^2 dx\n```"
TABS = '::: tabs\n::: tab "A"\nbody\n:::\n:::\n'
TAB_OPTIONS = {'extensions': ['carve.tabs'], 'renderers': {'carve.tabs': 'standard'}}


def render_fence(source, callback, syntax='mermaid'):
    def claim(tree):
        tree['extensions'] = [{
            'name': 'ex.fence', 'version': '1', 'required': False, 'slots': [],
        }]
        for index, node in enumerate(tree['children']):
            if node['type'] == 'code_block' and node.get('syntax') == syntax:
                tree['children'][index] = {
                    'type': 'block_extension', 'name': 'ex.fence', 'version': '1',
                    'children': [], 'fallback': [node],
                }
        return tree

    return carve.render_with_host(
        source, options={'mode': 'static'},
        renderers={'ex.fence': {'static': callback}}, transforms=[claim],
    )


def test_tabs_static_uses_static_panels():
    out = carve.to_html(TABS, {**TAB_OPTIONS, 'mode': 'static'})
    assert '<section class="tabs-panel">' in out
    assert '<h3 class="tabs-label">A</h3>' in out


def test_tabs_interactive_uses_controls():
    out = carve.to_html(TABS, {**TAB_OPTIONS, 'mode': 'interactive'})
    assert '<input type="radio"' in out
    assert '<div class="tab-panel"' in out


def test_mode_omitted_equals_interactive():
    assert carve.to_html(TABS, TAB_OPTIONS) == carve.to_html(
        TABS, {**TAB_OPTIONS, 'mode': 'interactive'}
    )


def test_mermaid_static_no_renderer_degrades_to_source():
    out = carve.to_html(MERMAID, {'mode': 'static'})
    assert '<pre>' in out and '<code' in out
    assert '<svg>' not in out


def test_mermaid_static_with_renderer_injects_output():
    out = render_fence(
        MERMAID, lambda node: '<svg>' + node['fallback'][0]['value'].strip() + '</svg>'
    )
    assert '<svg>graph TD; A-->B;</svg>' in out['html']


def test_math_host_renderer_receives_block_node():
    calls = []

    def render_math(node):
        calls.append(node)
        return '<math>' + node['fallback'][0]['value'].strip() + '</math>'

    out = render_fence(MATH, render_math, syntax='math')
    assert len(calls) == 1
    assert calls[0]['name'] == 'ex.fence'
    assert r'\int_0^1' in out['html']
    assert 'class="math inline"' in carve.to_html('$`x`')


def test_renderer_that_raises_falls_back_to_source():
    def boom(_node):
        raise RuntimeError('boom')

    out = render_fence(MERMAID, boom)
    assert 'A--&gt;B' in out['html']
    assert 'extension-renderer-failed' in [row['code'] for row in out['diagnostics']]


def test_failing_renderer_fallback_escapes_html():
    src = '```mermaid\n<img src=x onerror=alert(1)>\n```'

    def boom(_node):
        raise RuntimeError('boom')

    out = render_fence(src, boom)['html']
    assert '<img src=x onerror=alert(1)>' not in out
    assert '&lt;img src=x onerror=alert(1)&gt;' in out


def test_failing_renderer_returns_non_string_escapes_html():
    src = '```mermaid\n<b>x</b>\n```'
    out = render_fence(src, lambda _node: 123)
    assert '<b>x</b>' not in out['html']
    assert '&lt;b&gt;x&lt;/b&gt;' in out['html']
    assert 'extension-renderer-failed' in [row['code'] for row in out['diagnostics']]


def test_bogus_mode_raises_value_error():
    with pytest.raises(carve.CarveError, match='mode'):
        carve.to_html('x', {'mode': 'bogus'})


def test_standard_renderer_callback_is_refused():
    with pytest.raises(carve.CarveError, match='renderers'):
        carve.to_html('x', renderers={'carve.tabs': lambda node: 'x'})


def test_to_html_with_extensions_supports_static_mode():
    out = carve.to_html_with_extensions(
        TABS, ['carve.tabs'],
        {'mode': 'static', 'renderers': {'carve.tabs': 'standard'}},
    )
    assert '<section class="tabs-panel">' in out
