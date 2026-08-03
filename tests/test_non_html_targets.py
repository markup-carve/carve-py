"""The targets the HTML gates cannot see.

`test_corpus.py` and `test_byte_identical.py` both read `to_html`. This binding
also exposes `to_markdown`, `to_plain_text`, `to_ansi` and `parse`, and nothing
measured any of them - which is how the engine pin sat 65 commits behind while
CI stayed green, shipping a Markdown renderer that emitted a link inside a link
(carve-rs#437) and a `parse` that published adjacent text runs (carve-rs#441).

What these tests can and cannot do is worth being precise about. There are no
expected-output fixtures for the non-HTML targets - agreement there is measured
ENGINE AGAINST ENGINE, in the spec repo's `compare:impls`. So this file cannot
detect drift on its own. It pins the specific regressions the drift shipped, and
checks that every target survives the whole corpus, which is the part a stale
pin can break outright.
"""

import os
import pathlib

import carve
import pytest

CORPUS = os.environ.get("CARVE_SPEC_CORPUS")

pytestmark = pytest.mark.skipif(
    not CORPUS, reason="CARVE_SPEC_CORPUS not set (see .github/workflows/ci.yml)"
)

MIN_PAIRS = 400

TARGETS = {
    "to_markdown": carve.to_markdown,
    "to_plain_text": carve.to_plain_text,
    "to_ansi": carve.to_ansi,
}


def _sources():
    directory = pathlib.Path(CORPUS)
    if not directory.is_dir():
        pytest.fail(f"CARVE_SPEC_CORPUS={CORPUS} is not a directory")
    return sorted(directory.glob("*.crv"))


def test_every_target_survives_the_corpus():
    sources = _sources()
    assert len(sources) >= MIN_PAIRS, (
        f"only {len(sources)} corpus inputs under {CORPUS}; that is a wiring "
        "problem, not a clean run"
    )

    failures = []
    for name, render in TARGETS.items():
        for crv in sources:
            source = crv.read_text(encoding="utf-8")
            try:
                render(source)
            except Exception as exc:  # noqa: BLE001 - the point is that nothing raises
                failures.append(f"{name} raised on {crv.stem}: {exc!r}")

    assert not failures, "\n".join(failures[:20])


def test_a_crossref_in_a_link_label_does_not_nest_in_markdown():
    # carve-rs#437. A link inside a link is not valid Markdown: a consumer
    # reparsing this gets something other than what the document says. The
    # pinned engine emitted `[see [H](#H)](/outer)` for 65 commits.
    assert carve.to_markdown("# H\n\n[see </#H>](/outer)\n") == "# H\n\n[see H](/outer)\n"


def test_a_crossref_in_a_link_label_does_not_nest_in_ansi():
    # Same fix, other target: a nested link sequence ends with its own reset,
    # which closes the outer link's styling early.
    ansi = carve.to_ansi("# H\n\n[see </#H>](/outer)\n")
    assert ansi.count("\x1b[4m") == 1, repr(ansi)


def test_adjacent_text_runs_are_coalesced():
    # PART 12 section 1a, carve-rs#441. The pinned engine published several text
    # nodes wherever a construct reverted to literal source, so a consumer could
    # not compare this binding's tree with another engine's node for node.
    children = carve.parse("A [missing][nope] ref stays literal.\n")["children"][0]["children"]
    values = [c["value"] for c in children if c["type"] == "text"]

    assert values == ["A [missing][nope] ref stays literal."]
