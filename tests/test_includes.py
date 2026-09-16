"""`carve.render_with_includes`: contained `{{ path }}` expansion from disk.

The containment root is the whole security story here, so most of these assert
a REFUSAL rather than an expansion, and each one names the denial class the
engine reports rather than settling for "the text is not in the output".
"""

import json
import pathlib

import carve
import pytest


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


@pytest.fixture
def book(tmp_path):
    """A small book under `root/`, with a file OUTSIDE it to aim at."""
    root = tmp_path / "root"
    write(root / "main.crv", "Before.\n\n{{ chapters/one.crv }}\n\nAfter.\n")
    write(root / "chapters" / "one.crv", "One.\n\n{{ ../shared/glossary.crv }}\n")
    write(root / "shared" / "glossary.crv", "Glossary body.\n")
    write(tmp_path / "outside" / "secret.crv", "SECRET-MARKER\n")
    return root


def render(root, source, **kwargs):
    return carve.render_with_includes(source, str(root), **kwargs)


def rules(result):
    return [warning["rule"] for warning in result["warnings"]]


def denials(result):
    return {dep["id"]: dep["denial"] for dep in result["dependencies"]}


def test_a_file_backed_document_expands_its_include(book):
    result = render(book, (book / "main.crv").read_text(), source_path="main.crv")
    assert "<p>One.</p>" in result["output"]


def test_a_nested_relative_path_resolves_against_the_including_file(book):
    # `chapters/one.crv` asks for `../shared/glossary.crv`. Resolved against the
    # ROOT that would be `root/../shared`, which is outside and would be denied.
    result = render(book, (book / "main.crv").read_text(), source_path="main.crv")
    assert "<p>Glossary body.</p>" in result["output"]


def test_a_root_document_resolves_relative_to_its_own_directory(book):
    # `source_path` is what tells the resolver where the document IS. Without
    # it the root document's relative includes are read from the containment
    # root, which is a different directory the moment the document is nested.
    source = (book / "chapters" / "one.crv").read_text()
    result = render(book, source, source_path="chapters/one.crv")
    assert "<p>Glossary body.</p>" in result["output"]


def test_the_same_document_without_a_source_path_climbs_out_of_the_root(book):
    source = (book / "chapters" / "one.crv").read_text()
    result = render(book, source)
    assert denials(result) == {"../shared/glossary.crv": "outside-root"}


def test_a_warning_in_the_root_document_names_its_source_path(book):
    result = render(book, "{{ nope.crv }}\n", source_path="main.crv")
    assert result["warnings"][0]["file"] == "main.crv"


def test_an_expansion_reports_every_target_it_read(book):
    # Also the separator guard. Ids are `/`-separated on every platform so a
    # host can match them against its own page paths; on POSIX that is what the
    # native separator gives anyway, so only the Windows wheel job can fail
    # this one - and it did, on the first push of this file.
    result = render(book, (book / "main.crv").read_text(), source_path="main.crv")
    assert [dep["id"] for dep in result["dependencies"]] == [
        "chapters/one.crv",
        "shared/glossary.crv",
    ]


def test_a_dependency_that_was_read_is_marked_resolved(book):
    result = render(book, (book / "main.crv").read_text(), source_path="main.crv")
    assert [dep["resolved"] for dep in result["dependencies"]] == [True, True]


def test_a_traversal_out_of_the_root_is_denied(book):
    result = render(book, "{{ ../outside/secret.crv }}\n")
    assert denials(result) == {"../outside/secret.crv": "outside-root"}


def test_a_denied_traversal_leaves_the_directive_literal(book):
    result = render(book, "{{ ../outside/secret.crv }}\n")
    assert "SECRET-MARKER" not in result["output"]


def test_a_symlink_pointing_out_of_the_root_is_denied(book, tmp_path):
    link = book / "escape.crv"
    link.symlink_to(tmp_path / "outside" / "secret.crv")
    result = render(book, "{{ escape.crv }}\n")
    assert denials(result) == {"escape.crv": "outside-root"}


def test_a_symlink_escape_does_not_reach_the_output(book, tmp_path):
    link = book / "escape.crv"
    link.symlink_to(tmp_path / "outside" / "secret.crv")
    result = render(book, "{{ escape.crv }}\n")
    assert "SECRET-MARKER" not in result["output"]


def test_a_missing_target_is_denied_as_not_found(book):
    result = render(book, "{{ nope.crv }}\n")
    assert denials(result) == {"nope.crv": "not-found"}


def test_a_missing_target_is_still_reported_as_a_dependency(book):
    # A host watching only what it read would never learn that a target the
    # author is about to create has appeared.
    result = render(book, "{{ nope.crv }}\n")
    assert result["dependencies"] == [
        {"id": "nope.crv", "resolved": False, "denial": "not-found"}
    ]


def test_an_absolute_include_path_is_denied_by_default(book):
    result = render(book, "{{ %s }}\n" % (book / "shared" / "glossary.crv"))
    assert list(denials(result).values()) == ["include-denied"]


def test_allow_absolute_admits_a_target_that_is_still_inside_the_root(book):
    result = render(
        book,
        "{{ %s }}\n" % (book / "shared" / "glossary.crv"),
        allow_absolute=True,
    )
    assert "<p>Glossary body.</p>" in result["output"]


def test_allow_absolute_does_not_widen_the_root(book, tmp_path):
    result = render(
        book,
        "{{ %s }}\n" % (tmp_path / "outside" / "secret.crv"),
        allow_absolute=True,
    )
    assert list(denials(result).values()) == ["outside-root"]


def test_a_cycle_is_refused(book):
    write(book / "a.crv", "A.\n\n{{ b.crv }}\n")
    write(book / "b.crv", "B.\n\n{{ a.crv }}\n")
    result = render(book, (book / "a.crv").read_text(), source_path="a.crv")
    assert rules(result) == ["include-cycle"]


def test_a_cycle_is_attributed_to_the_file_it_arose_in(book):
    write(book / "a.crv", "A.\n\n{{ b.crv }}\n")
    write(book / "b.crv", "B.\n\n{{ a.crv }}\n")
    result = render(book, (book / "a.crv").read_text(), source_path="a.crv")
    assert result["warnings"][0]["file"] == "a.crv"


def test_the_depth_limit_refuses_a_deeper_chain(book):
    result = render(
        book,
        (book / "main.crv").read_text(),
        source_path="main.crv",
        max_depth=0,
    )
    assert rules(result) == ["include-depth"]


def test_the_byte_budget_refuses_an_oversized_expansion(book):
    result = render(
        book,
        (book / "main.crv").read_text(),
        source_path="main.crv",
        max_bytes=1,
    )
    assert rules(result) == ["include-budget"]


def test_a_target_refused_by_the_byte_budget_was_still_read(book):
    # Section 19 charges the budget for what the resolver HANDED BACK. A target
    # is resolved before its size is known, so refusing before the read would
    # be a different rule than the one the spec states.
    result = render(
        book,
        (book / "main.crv").read_text(),
        source_path="main.crv",
        max_bytes=1,
    )
    assert result["dependencies"][0]["resolved"] is True


def test_the_resolver_call_limit_is_reported(book):
    source = "{{ shared/glossary.crv }}\n\n{{ chapters/one.crv }}\n"
    result = render(book, source, source_path="main.crv", max_resolver_calls=1)
    assert "include-call-limit" in rules(result)


def test_a_target_past_the_file_size_cap_is_denied(book):
    write(book / "big.crv", "x" * 500)
    result = render(book, "{{ big.crv }}\n", max_file_bytes=10)
    assert denials(result) == {"big.crv": "include-denied"}


def test_a_capped_warning_report_says_how_many_it_dropped(book):
    source = "".join("{{ missing-%d.crv }}\n\n" % n for n in range(5))
    result = render(book, source, max_warnings=1)
    assert result["suppressed_warnings"] == 4


def test_a_relative_include_root_is_refused(book):
    # The root reaches the resolver unchanged on purpose: canonicalizing a
    # relative spec here would root containment at the process working
    # directory, which PART 9 section 19 forbids.
    with pytest.raises(ValueError, match="absolute"):
        carve.render_with_includes("Text.\n", "relative/root")


def test_a_root_that_is_not_there_is_refused(tmp_path):
    with pytest.raises(ValueError, match="include root"):
        carve.render_with_includes("Text.\n", str(tmp_path / "absent"))


def test_the_string_entry_points_leave_a_directive_literal():
    # No root, no expansion: this is the behavior the conformance corpus pins,
    # and it is what keeps a string-only caller off the filesystem.
    assert carve.to_html("{{ chapters/one.crv }}\n") == "<p>{{ chapters/one.crv }}</p>"


def test_no_host_path_reaches_the_caller(book, tmp_path):
    write(book / "escape.crv", "")
    (book / "escape.crv").unlink()
    (book / "escape.crv").symlink_to(tmp_path / "outside" / "secret.crv")
    source = "{{ chapters/one.crv }}\n\n{{ escape.crv }}\n\n{{ nope.crv }}\n"
    result = render(book, source, source_path="main.crv")
    reported = json.dumps(
        {"warnings": result["warnings"], "dependencies": result["dependencies"]}
    )
    assert str(tmp_path) not in reported


def test_an_extension_reaches_an_included_child(book):
    write(book / "child.crv", "See [[Target]].\n")
    result = render(book, "{{ child.crv }}\n", extensions=["wikilinks"])
    assert "<a " in result["output"]


def test_a_non_html_target_expands_too(book):
    result = render(book, "{{ shared/glossary.crv }}\n", target="markdown")
    assert result["output"].strip() == "Glossary body."


def test_an_unknown_target_is_rejected(book):
    with pytest.raises(ValueError, match="unknown carve render target"):
        render(book, "Text.\n", target="carve")


def test_a_profile_violation_raises(book):
    with pytest.raises(ValueError):
        render(book, "x" * 120_000, profile="comment")


def test_the_root_document_needs_no_source_path(book):
    # Without one there is no identity to report, and none is invented.
    result = render(book, "{{ nope.crv }}\n")
    assert result["warnings"][0]["file"] is None


def test_the_stub_declares_the_new_entry_point():
    stub = pathlib.Path(__file__).resolve().parent.parent / "carve.pyi"
    assert "def render_with_includes(" in stub.read_text(encoding="utf-8")


def test_the_binding_exports_it():
    assert callable(carve.render_with_includes)
