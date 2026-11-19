"""Native 0.2 renderers and transforms through Python callables."""
import gc
import weakref

import carve


def note_tree():
    return {
        "type": "document", "astVersion": "2.0",
        "extensions": [{"name": "ex.note", "version": "1", "required": False, "slots": []}],
        "children": [{"type": "block_extension", "name": "ex.note", "version": "1",
                      "children": [], "fallback": [{"type": "paragraph", "children": [
                          {"type": "text", "value": "fallback"}]}]}],
    }


def permalink(tree):
    for node in tree["children"]:
        if node["type"] == "heading":
            ident = node["generatedId"]
            node["attrs"] = {"id": ident}
            node["children"].append({"type": "link", "href": "#" + ident,
                                     "children": [{"type": "text", "value": "¶"}]})
    return tree


def test_heading_permalink_transform():
    assert carve.to_html("# Guide", transforms=[permalink]) == (
        '<section id="Guide">\n  <h1>Guide<a href="#Guide">¶</a></h1>\n</section>')


def test_renderer_channels_and_fallback():
    renderers = {"ex.note": {"static": lambda node: "<aside>" + node["name"] + "</aside>"}}
    result = carve.render_with_host("", tree=note_tree(), options={"mode": "static"}, renderers=renderers)
    assert result["html"] == "<aside>ex.note</aside>"
    result = carve.render_with_host("", tree=note_tree(), renderers=renderers)
    assert result["html"] == "<p>fallback</p>"


def test_failing_renderer_and_transform_keep_fallback_or_view():
    def boom(_value):
        raise RuntimeError("callback failed")

    result = carve.render_with_host("", tree=note_tree(), renderers={"ex.note": boom})
    assert result["html"] == "<p>fallback</p>"
    assert [entry["code"] for entry in result["diagnostics"]] == ["extension-renderer-failed"]
    result = carve.render_with_host("# Guide", transforms=[boom])
    assert result["html"] == carve.to_html("# Guide")
    assert [entry["code"] for entry in result["diagnostics"]] == ["extension-transform-failed"]
    result = carve.render_with_host("", tree=note_tree(), renderers={"ex.note": lambda _: 42})
    assert result["diagnostics"][0]["code"] == "extension-renderer-failed"


def test_callback_lifetime_during_and_after_render():
    class Renderer:
        def __call__(self, _node):
            gc.collect()
            return "<aside>alive</aside>"

    callback = Renderer()
    reference = weakref.ref(callback)
    result = carve.render_with_host("", tree=note_tree(), renderers={"ex.note": callback})
    assert result["html"] == "<aside>alive</aside>"
    assert reference() is callback
    del callback
    gc.collect()
    assert reference() is None


def test_code_fence_can_take_a_host_renderer_through_a_transform():
    source = "```mermaid\ngraph TD;\n```"

    def claim(tree):
        tree["extensions"] = [{"name": "ex.mermaid", "version": "1", "required": False, "slots": []}]
        for index, node in enumerate(tree["children"]):
            if node["type"] == "code_block" and node.get("syntax") == "mermaid":
                tree["children"][index] = {"type": "block_extension", "name": "ex.mermaid",
                                           "version": "1", "children": [], "fallback": [node]}
        return tree

    result = carve.render_with_host(source, options={"mode": "static"},
                                    renderers={"ex.mermaid": {"static": lambda node:
                                        "<svg>" + node["fallback"][0]["value"].strip() + "</svg>"}},
                                    transforms=[claim])
    assert result["html"] == "<svg>graph TD;</svg>"
    assert result["diagnostics"] == []


def test_standard_renderer_remains_selected_with_transform():
    source = "::: tabs\n::: tab {title=A}\nx\n:::\n:::\n"
    options = {"extensions": ["carve.tabs"]}
    renderers = {"carve.tabs": "standard"}
    expected = carve.to_html(source, extensions=["carve.tabs"], renderers=renderers)
    assert carve.to_html(source, extensions=["carve.tabs"], renderers=renderers,
                         transforms=[lambda tree: tree]) == expected


def test_declared_version_and_existing_render_options():
    tree = note_tree()
    tree["extensions"][0]["version"] = "2"
    tree["children"][0]["version"] = "2"
    result = carve.render_with_host("", tree=tree,
                                    renderers={"ex.note": lambda _: "<aside>version 2</aside>"})
    assert result["html"] == "<aside>version 2</aside>"
    assert carve.to_html("Ship :rocket:", {"symbols": {"rocket": "🚀"}},
                         transforms=[lambda value: value]) == "<p>Ship 🚀</p>"


def test_standard_selection_in_options_and_aria_configuration():
    source = "::: tabs\n::: tab {title=A}\nx\n:::\n:::\n"
    options = {"extensions": ["carve.tabs"],
               "renderers": {"carve.tabs": {"standard": {"mode": "aria"}}}}
    expected = carve.render(source, options)["html"]
    assert carve.to_html(source, options, transforms=[lambda tree: tree]) == expected
    assert carve.to_html(source, extensions=["carve.tabs"],
                         renderers={"carve.tabs": {"standard": {"mode": "aria"}}}) == expected
