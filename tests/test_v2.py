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


def test_raw_html_and_url_security_defaults():
    source = "```=html\n<script>x</script>\n```"
    assert "<script>" not in carve.render(source)["html"]
    assert "<script>" in carve.render(source, {"rawHtml": True})["html"]
    assert 'href=""' in carve.render("[go](javascript:alert(1))")["html"]


def test_compatibility_spellings_reject_unavailable_extensions():
    assert carve.to_html_with_extensions("Hi", []) == carve.to_html("Hi")
    assert carve.extensions() == []
    with pytest.raises(carve.CarveError, match="not available yet"):
        carve.to_html("Hi", extensions=["math-block"])
    with pytest.raises(carve.CarveError, match="not available yet"):
        carve.to_html("Hi", renderers={"math": lambda source: source})


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


def test_unregistered_source_writer_and_html_import_report_gap():
    with pytest.raises(carve.CarveError, match="format is not available"):
        carve.fmt("# Hi")
    with pytest.raises(carve.CarveError, match="importDocument is not available"):
        carve.import_document("<p>Hi</p>")


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


@pytest.mark.skip(reason="Carve 0.2 source writer pending in carve-rs issue 4327")
def test_pending_source_writer():
    assert carve.fmt("# H")["source"]


@pytest.mark.skip(reason="Carve 0.2 Markdown writer pending in carve-rs issue 4327")
def test_pending_markdown_writer():
    assert carve.to_markdown("# H")


@pytest.mark.skip(reason="Carve 0.2 plain writer pending in carve-rs issue 4327")
def test_pending_plain_writer():
    assert carve.to_plain_text("# H")


@pytest.mark.skip(reason="Carve 0.2 ANSI writer pending in carve-rs issue 4327")
def test_pending_ansi_writer():
    assert carve.to_ansi("# H")


@pytest.mark.skip(reason="Carve 0.2 HTML importer pending in carve-rs issue 4328")
def test_pending_html_import():
    assert carve.import_document("<p>Hi</p>")["source"]


@pytest.mark.skip(reason="Carve 0.2 extension registration pending in carve-rs issue 4329")
def test_pending_extension_registration():
    assert carve.render("```math\nx\n```", {"extensions": ["math-block"]})
