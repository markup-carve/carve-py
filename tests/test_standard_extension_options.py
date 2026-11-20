import carve
import pytest


OPTIONS = {
    "carve.wiki": {"css_class": "links", "new_window": True},
    "carve.mathBlock": {"language": "tex"},
    "carve.codeGroup": {"idPrefix": "panels"},
    "carve.colorSwatch": {"shape": "round"},
    "carve.references": {"mode": "author-date"},
    "carve.index": {"backrefLabel": "Return"},
    "carve.smartQuotes": {"locale": "de"},
    "carve.tabNormalize": {"width": 4},
    "carve.fencedRender.abc": {"label": "Music"},
    "carve.fencedRender.chart": {"label": "Chart"},
    "carve.fencedRender.d2": {"label": "Diagram"},
    "carve.fencedRender.graphviz": {"label": "Graph"},
    "carve.fencedRender.mermaid": {"label": "Flowchart"},
    "carve.fencedRender.plantuml": {"label": "UML"},
    "carve.fencedRender.vega-lite": {"label": "Visualization"},
    "carve.fencedRender.wavedrom": {"label": "Waveform"},
}


@pytest.mark.parametrize("name", carve.extensions())
def test_every_bundled_extension_accepts_a_configured_entry(name):
    entry = {"name": name, "options": OPTIONS.get(name, {})}
    assert carve.render("Text\n", {"extensions": [entry]})["html"] == "<p>Text</p>"


def test_smart_quotes_locale_reaches_all_render_entry_points():
    entry = {"name": "carve.smartQuotes", "options": {"locale": "de"}}
    source = '"hi"\n'
    expected = "<p>„hi“</p>"
    assert carve.render(source, {"extensions": [entry]})["html"] == expected
    assert carve.to_html(source, extensions=[entry]) == expected
    assert carve.to_html_with_extensions(source, [entry]) == expected
    assert carve.render_with_host(source, {"extensions": [entry]})["html"] == expected
    assert carve.to_html(source, extensions=["carve.smartQuotes"]) != expected


def test_wiki_options_change_the_standard_renderer():
    entry = {"name": "carve.wiki", "options": {"css_class": "links", "new_window": True}}
    html = carve.to_html(":wiki[Page]", extensions=[entry], renderers={"carve.wiki": "standard"})
    assert 'class="links"' in html
    assert 'target="_blank"' in html


@pytest.mark.parametrize("name,options,source,visible", [
    ("carve.mathBlock", {"language": "tex"}, "```tex\nx\n```\n", '<div class="math display" role="math">'),
    ("carve.codeGroup", {"idPrefix": "panels"}, "::: code-group\n```js [NPM]\nnpm i\n```\n:::\n", 'id="panels-1-tab-1"'),
    ("carve.colorSwatch", {"shape": "round"}, ":color[#123456]\n", "swatch-chip-round"),
    ("carve.references", {"mode": "author-date"}, "See :cite[doe].\n\n::: references\n:: doe\n: Doe (2020).\n:::\n", '<ul class="references">'),
    ("carve.index", {"backrefLabel": "Return"}, "See :index[HTTP].\n\n::: index\n:::\n", 'aria-label="Return HTTP"'),
    ("carve.tabNormalize", {"width": 4}, "```\na\tb\n```\n", "a    b"),
    ("carve.fencedRender.mermaid", {"label": "Flowchart"}, "```mermaid\na-->b\n```\n", 'aria-label="Flowchart"'),
])
def test_configured_option_has_a_visible_effect(name, options, source, visible):
    entry = {"name": name, "options": options}
    before = carve.to_html(source, extensions=[name], renderers={name: "standard"})
    after = carve.to_html(source, extensions=[entry], renderers={name: "standard"})
    assert visible in after
    assert after != before


@pytest.mark.parametrize("name,options", [
    ("carve.mathBlock", {"language": "tex"}),
    ("carve.codeGroup", {"idPrefix": "panels"}),
    ("carve.colorSwatch", {"shape": "round"}),
    ("carve.references", {"mode": "author-date"}),
    ("carve.index", {"backrefLabel": "Return"}),
    ("carve.tabNormalize", {"width": 4}),
    ("carve.fencedRender.mermaid", {"label": "Flowchart"}),
])
def test_unknown_option_is_a_typed_option_error_for_each_configurable_family(name, options):
    with pytest.raises(carve.CarveError, match="unknown option misspelled") as raised:
        carve.render("Text", {"extensions": [{"name": name, "options": {**options, "misspelled": True}}]})
    assert raised.value.name == "CarveOptionError"
    assert raised.value.category == "usage"


def test_wrong_option_type_and_unknown_extension_are_option_errors():
    for entry, phrase in (
        ({"name": "carve.wiki", "options": {"newWindow": "yes"}}, "newWindow must be a boolean"),
        ({"name": "carve.smartQuotes", "options": {"locale": 1}}, "locale must be a string"),
        ({"name": "carve.missing", "options": {}}, "carve.missing"),
    ):
        with pytest.raises(carve.CarveError, match=phrase) as raised:
            carve.render("Text", {"extensions": [entry]})
        assert raised.value.name == "CarveOptionError"


def test_a_plain_name_and_a_configured_entry_can_share_the_list():
    html = carve.to_html('"hi" and :wiki[Page]', extensions=[
        "carve.wiki", {"name": "carve.smartQuotes", "options": {"locale": "de"}}
    ])
    assert "„hi“" in html
    assert "Page" in html
