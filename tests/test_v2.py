"""Carve 0.2 public calls through the installed native wheel."""

import carve
import pytest


def test_render_and_safe_default():
    assert carve.render("Hello *world*")["html"] == "<p>Hello <strong>world</strong></p>"
    assert "<script>" not in carve.render("```=html\n<script>x</script>\n```")["html"]
    assert "<script>" in carve.render("```=html\n<script>x</script>\n```", {"rawHtml": True})["html"]
    assert carve.to_html("Hi") == "<p>Hi</p>"


def test_render_diagnostics_and_options():
    result = carve.render("# Heading", {"mode": "static"}, diagnostics=True)
    assert "<h1" in result["html"]
    assert isinstance(result["diagnostics"], list)
    assert isinstance(result["suppressedDiagnostics"], int)
    with pytest.raises(carve.CarveError, match="unknown option") as caught:
        carve.render("Hi", {"notAnOption": True})
    assert caught.value.name == "CarveOptionError"
    assert caught.value.category == "usage"
    assert caught.value.status == 2


def test_parse_and_tree_writer():
    parsed = carve.parse("Hello *world*", diagnostics=True)
    assert isinstance(parsed["tree"], dict)
    assert isinstance(parsed["diagnostics"], list)
    assert "<strong>world</strong>" in carve.write(parsed["tree"])["output"]
    assert carve.call({"call": "render", "tree": parsed["tree"]})["html"] == carve.render("Hello *world*")["html"]
    encoded = carve.call({"call": "encodeTree", "tree": parsed["tree"]})["json"]
    assert carve.call({"call": "decodeTree", "json": encoded})["tree"] == parsed["tree"]
    assert carve.parse_json("Hello *world*")


def test_lint_and_generic_byte_input():
    assert carve.lint("Hello")["diagnostics"] == []
    parsed = carve.call({"call": "parse", "sourceBytes": [72, 105]})
    assert isinstance(parsed["tree"], dict)


def test_lint_reports_utf8_byte_ranges():
    source = "é\n\n{#orphan}\n\n"
    [warning] = carve.lint(source)["diagnostics"]
    assert warning["code"] == "unattached-block-attribute"
    assert warning["channel"] == "lint"
    start = warning["range"]["startOffset"]
    end = warning["range"]["endOffset"]
    assert source.encode("utf-8")[start:end] == b"{#orphan}"


def test_parse_positions_and_surrogate_input():
    tree = carve.parse("A\ud800B")["tree"]
    assert tree["children"][0]["children"][0]["value"] == "A\ufffdB"
    assert "pos" in tree["children"][0]
    assert "pos" not in carve.parse("Hi", positions=False)["tree"]["children"][0]


def test_generic_call_normalizes_lone_surrogates_without_mutating_request():
    request = {"call": "render", "source": "A\ud800B"}
    assert carve.call(request) == carve.render("A\ud800B")
    assert request["source"] == "A\ud800B"


def test_raw_html_and_url_security_defaults():
    source = "```=html\n<script>x</script>\n```"
    assert "<script>" not in carve.render(source)["html"]
    assert "<script>" in carve.render(source, {"rawHtml": True})["html"]
    assert 'href=""' in carve.render("[go](javascript:alert(1))")["html"]


def test_standard_extension_selection():
    assert carve.to_html_with_extensions("Hi", []) == carve.to_html("Hi")
    assert "carve.tabs" in carve.extensions()
    source = "::: tabs\n::: tab {title=A}\nx\n:::\n:::\n"
    html = carve.to_html(source, extensions=["carve.tabs"], renderers={"carve.tabs": "standard"})
    assert html == carve.render(source, {"extensions": ["carve.tabs"], "renderers": {"carve.tabs": "standard"}})["html"]
    assert carve.to_html_with_extensions(":wiki[Page]", ["carve.wiki"]) == "<p>Page</p>"


def test_extension_selection_refusals():
    with pytest.raises(carve.CarveError) as unknown:
        carve.to_html("Hi", extensions=["math-block"])
    assert unknown.value.name == "CarveOptionError"
    with pytest.raises(carve.CarveError, match="C2-T-010"):
        carve.to_html("Hi", renderers={"carve.tabs": lambda node: ""})


def test_removed_markdown_import_is_explicit():
    with pytest.raises(carve.CarveError, match="C2-T-003"):
        carve.from_markdown("# Hi")


@pytest.mark.parametrize("target,function", [
    ("markdown", carve.to_markdown),
    ("plain", carve.to_plain_text),
    ("ansi", carve.to_ansi),
])
def test_unregistered_writers_report_the_target(target, function):
    with pytest.raises(carve.CarveError, match=target + " writer not available yet"):
        function("# Hi")


def test_source_writer_and_html_import():
    assert carve.fmt("# H")["source"] == "= H\n"
    assert carve.to_carve("# H") == "= H\n"
    imported = carve.import_document("<p>Hi</p>")
    assert imported["source"] == "Hi\n"
    assert imported["tree"]["type"] == "document"
    assert carve.from_html("<p>Hi</p>")["source"] == "Hi\n"


def test_include_root(tmp_path):
    (tmp_path / "part.crv").write_text("*included*", encoding="utf-8")
    result = carve.render("{{ part.crv }}", {"includes": {"root": str(tmp_path), "file": "book.crv"}})
    assert "included" in result["html"]


def test_include_dependency_and_root_refusals(tmp_path):
    (tmp_path / "part.crv").write_text("From child.", encoding="utf-8")
    options = {"includes": {"root": str(tmp_path), "file": "book.crv"}}
    parsed = carve.parse("{{ part.crv }}", options)
    dependencies = carve.call({"call": "includeDependencies", "tree": parsed["tree"], "file": "book.crv"})
    assert dependencies == {"dependencies": [{"file": "part.crv", "from": "book.crv", "path": "part.crv", "read": True}]}
    refused = carve.render("{{ ../outside.crv }}", options, diagnostics=True)
    assert "outside.crv" in refused["html"]
    assert "include-outside-root" in [row["code"] for row in refused["diagnostics"]]
    missing = carve.render("{{ missing.crv }}", options, diagnostics=True)
    assert "include-not-found" in [row["code"] for row in missing["diagnostics"]]


@pytest.mark.skip(reason="Carve 0.2 Markdown writer pending in carve-rs issues 4327 and 4349")
def test_pending_markdown_writer():
    assert carve.to_markdown("# H")


@pytest.mark.skip(reason="Carve 0.2 plain writer pending in carve-rs issues 4327 and 4349")
def test_pending_plain_writer():
    assert carve.to_plain_text("# H")


@pytest.mark.skip(reason="Carve 0.2 ANSI writer pending in carve-rs issues 4327 and 4349")
def test_pending_ansi_writer():
    assert carve.to_ansi("# H")


@pytest.mark.xfail(strict=True, reason="carve-rs issue 4351: include-unresolved names an empty path")
def test_unresolved_include_loss_names_its_file(tmp_path):
    result = carve.render("{{ missing.crv }}", {"includes": {"root": str(tmp_path)}}, diagnostics=True)
    [loss] = [row for row in result["diagnostics"] if row["code"] == "include-unresolved"]
    assert loss["message"] == 'Include "missing.crv" could not be resolved.'
