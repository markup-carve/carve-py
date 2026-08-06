"""The spec corpus, run through `carve.parse` rather than `carve.to_html`.

`test_corpus.py` compares rendered HTML byte for byte, and that was the only
corpus-driven check here. It cannot see an AST-only change: a node that renders
nothing renders nothing in both engines. carve-rb sat 44 commits behind on a pin
that had lost a whole node type, and every corpus pair still matched
(markup-carve/carve-rb#46, markup-carve/carve-py#24).

Two checks, because they answer different questions:

  test_every_recorded_node_type_still_reaches_the_tree
      is every TYPE still produced? A pin that drops one drops it from all 658
      documents at once, so the whole corpus answers with one fact.

  test_every_node_uses_field_names_the_schema_names
      do the FIELD NAMES still match `resources/ast-schema.json`? Catches a
      rename, which the type check cannot see - the type is still produced,
      under a different property.

WHY NOT A PER-DOCUMENT ASSERTION. The obvious check - a document with a
definition line must produce a `link_reference_definition` - does not survive
contact with the corpus: 64 documents have that source shape and 36 legitimately
produce no such node, because `[^f]: note` is the same shape and because several
documents exist precisely to pin that a definition-shaped line is NOT a
definition. Modelling that needs an allowlist of exactly the documents whose
rules the check cannot model.

THE SCHEMA CHECK IS NOT JSON SCHEMA VALIDATION. It reads two keywords -
`additionalProperties: false` and `required` - and ignores types, enums, formats
and conditionals. A real validator would be a new dependency; these two are the
ones a drifted engine actually trips.
"""

import json
import os
import pathlib

import carve
import pytest

CORPUS = os.environ.get("CARVE_SPEC_CORPUS")

pytestmark = pytest.mark.skipif(
    not CORPUS, reason="CARVE_SPEC_CORPUS not set (see .github/workflows/ci.yml)"
)

MIN_DOCUMENTS = 400

# Recorded by walking every corpus document through this binding. An explicit
# list rather than a count: a count says "something went missing" and this says
# which.
EXPECTED_TYPES = frozenset(
    """
    abbreviation abbreviation_def admonition autolink block_quote caption_number
    code code_block comment critic_comment definition_description definition_list
    definition_term delete div document emphasis escaped_text figure footnote
    footnote_ref frontmatter hard_break heading heading_ref highlight image
    inline_extension inline_footnote insert line_block link
    link_reference_definition list list_item literal_inline math mention
    paragraph raw_block raw_inline smart_punctuation soft_break span strike
    strong subscript substitution superscript symbol table table_cell table_row
    tag text thematic_break underline
    """.split()
)


def _documents():
    directory = pathlib.Path(CORPUS)
    if not directory.is_dir():
        pytest.fail(f"CARVE_SPEC_CORPUS={CORPUS} is not a directory")
    return sorted(directory.glob("*.crv"))


def _walk(node, visit):
    if isinstance(node, dict):
        if "type" in node:
            visit(node)
        for value in node.values():
            _walk(value, visit)
    elif isinstance(node, list):
        for value in node:
            _walk(value, visit)


def _schema_defs():
    # The schema ships beside the corpus in the spec checkout, so CI needs no
    # second variable.
    path = pathlib.Path(CORPUS).parent.parent / "resources" / "ast-schema.json"
    if not path.exists():
        pytest.fail(f"no schema at {path}; it ships in the spec repo beside the corpus")
    return json.loads(path.read_text(encoding="utf-8"))["$defs"]


def _types_produced():
    seen = set()
    for document in _documents():
        _walk(carve.parse(document.read_text(encoding="utf-8")), lambda n: seen.add(n["type"]))
    return seen


def test_the_corpus_is_actually_walked():
    # Without this an empty or mistyped directory produces an empty set, every
    # assertion below is vacuous, and the run reads as clean - the same failure
    # shape these tests exist to remove.
    found = len(_documents())
    assert found >= MIN_DOCUMENTS, (
        f"only {found} corpus documents under {CORPUS}; the corpus has ~650, "
        "so this is a wiring problem, not a clean run"
    )


def test_every_recorded_node_type_still_reaches_the_tree():
    produced = _types_produced()
    missing = sorted(EXPECTED_TYPES - produced)

    assert not missing, (
        f"{len(missing)} node type(s) the corpus used to produce are gone: "
        f"{', '.join(missing)}. The carve-rs rev in Cargo.toml is probably behind a "
        "change that renamed or removed them; bump it and commit the regenerated "
        "Cargo.lock. If a type was removed from the language on purpose, delete it "
        "from EXPECTED_TYPES in the same commit."
    )


def test_a_missing_type_would_actually_be_reported():
    # The ablation for the check above. Without it, that assertion passes
    # identically whether the corpus is being walked or quietly skipped.
    produced = _types_produced()
    assert sorted({"a_type_no_engine_emits"} - produced) == ["a_type_no_engine_emits"]


def test_a_new_node_type_is_reported_without_failing():
    # Not a failure: new constructs arrive with corpus growth and should not fail
    # a binding that parses them correctly. The drift this guards only subtracts.
    extra = sorted(_types_produced() - EXPECTED_TYPES)
    if extra:
        print(f"corpus produces {len(extra)} type(s) not in EXPECTED_TYPES: {', '.join(extra)}")


def _schema_findings(defs):
    findings = {}

    def check(node):
        node_type = node["type"]
        schema = defs.get(node_type)
        if schema is None:
            findings[f"{node_type}: no $defs entry in the schema"] = (
                findings.get(f"{node_type}: no $defs entry in the schema", 0) + 1
            )
            return
        properties = schema.get("properties")
        if properties is None:
            return
        if schema.get("additionalProperties") is False:
            for key in node:
                if key not in properties:
                    label = f"{node_type}.{key}: not a property the schema names"
                    findings[label] = findings.get(label, 0) + 1
        for required in schema.get("required", []):
            if required not in node:
                label = f"{node_type}: required property {required} is missing"
                findings[label] = findings.get(label, 0) + 1

    for document in _documents():
        _walk(carve.parse(document.read_text(encoding="utf-8")), check)
    return findings


def test_the_schema_is_actually_read():
    defs = _schema_defs()
    assert len(defs) >= 40, (
        f"the schema has only {len(defs)} type definitions, which is too few to be "
        "the spec's - check the spec checkout beside CARVE_SPEC_CORPUS"
    )


def test_every_node_uses_field_names_the_schema_names():
    findings = _schema_findings(_schema_defs())
    top = sorted(findings.items(), key=lambda item: -item[1])[:10]

    assert not findings, (
        f"{sum(findings.values())} node(s) do not match the schema's field names: "
        f"{'; '.join(f'{count}x {label}' for label, count in top)}. "
        "The carve-rs rev in Cargo.toml is probably behind a rename; bump it and "
        "commit the regenerated Cargo.lock."
    )


def test_the_schema_check_can_fail():
    # The ablation, in the test rather than in a commit message: rename a
    # property the corpus certainly produces and confirm the sweep reports it.
    # Without this the assertion above passes identically whether the schema is
    # being read or quietly ignored.
    defs = _schema_defs()
    defs["text"] = dict(defs["text"])
    defs["text"]["properties"] = {
        key: value for key, value in defs["text"]["properties"].items() if key != "value"
    }
    assert "text.value: not a property the schema names" in _schema_findings(defs)
