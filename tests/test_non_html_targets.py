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

import json
import os
import pathlib
import re

import carve
import pytest

from corpus_population import require_whole_corpus

CORPUS = os.environ.get("CARVE_SPEC_CORPUS")

pytestmark = pytest.mark.skipif(
    not CORPUS, reason="CARVE_SPEC_CORPUS not set (see .github/workflows/ci.yml)"
)

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
    # "Every target survives the whole corpus" is a claim about the WHOLE
    # corpus, so the population is checked for equality rather than a floor.
    require_whole_corpus(CORPUS, len(sources), "corpus inputs found")

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
    #
    # The assertion is the PROPERTY - no two text nodes are adjacent - not a
    # fixed node list. An unresolved reference is a `link` node now rather than
    # reverted text (carve-rs#474), so the old expectation of one text run for
    # the whole paragraph described an engine that no longer exists. carve-js
    # publishes the same three nodes for this input.
    children = carve.parse("A [missing][nope] ref stays literal.\n")["children"][0]["children"]
    types = [c["type"] for c in children]

    assert types == ["text", "link", "text"], types
    adjacent = [
        (a, b) for a, b in zip(types, types[1:]) if a == "text" and b == "text"
    ]
    assert adjacent == [], f"adjacent text runs were not coalesced: {children}"


# --- corpus-wide sweeps -----------------------------------------------------
#
# The three checks above pin ONE input each, which is the right shape for
# naming a specific regression. It is the wrong shape for noticing the next
# one: a construct nobody thought to write down drifts silently. These run the
# same properties over every corpus document, so a new occurrence has somewhere
# to fail.


def _has_nested_link(markdown):
    r"""Whether any link label in `markdown` contains a complete link.

    A bracket walk rather than a regex. The obvious pattern -
    `\[([^\[\]]*)\]\(` - forbids `[` inside the label, so on
    `[see [H](#H)](/outer)` it skips the outer label entirely and matches the
    INNER link, whose label holds nothing: the check would pass on exactly the
    input it exists to catch.
    """
    # Each entry records whether the bracket belongs to an image and whether a
    # real link has closed inside it. Markdown images use the same `](` suffix
    # as links and are valid inside a link, so counting them as nested links
    # produces a false positive for `[![alt](/i)](/outer)`.
    open_labels = []
    escaped = False
    for i, ch in enumerate(markdown):
        if escaped:
            escaped = False
            continue
        if ch == "\\":
            escaped = True
        elif ch == "[":
            open_labels.append(
                {"image": i > 0 and markdown[i - 1] == "!", "link": False}
            )
        elif ch == "]" and open_labels:
            closed = open_labels.pop()
            closed_a_link = markdown[i + 1 : i + 2] == "(" and not closed["image"]
            if closed_a_link and closed["link"]:
                return True
            if closed_a_link and open_labels:
                open_labels[-1]["link"] = True
    return False


def test_no_document_in_the_corpus_emits_a_nested_link():
    nested = [
        crv.stem
        for crv in _sources()
        if _has_nested_link(carve.to_markdown(crv.read_text(encoding="utf-8")))
    ]

    assert nested == [], f"{len(nested)} document(s) emit a nested link: {nested[:5]}"


def _adjacent_text_runs(node, hits):
    if not isinstance(node, dict):
        return
    for value in node.values():
        if isinstance(value, list):
            previous = None
            for child in value:
                if isinstance(child, dict):
                    if previous == "text" and child.get("type") == "text":
                        hits.append(1)
                    previous = child.get("type")
                    _adjacent_text_runs(child, hits)
        elif isinstance(value, dict):
            _adjacent_text_runs(value, hits)


def test_no_document_in_the_corpus_publishes_an_adjacent_text_run():
    # Against the pin this repo shipped before #17, EIGHT documents did - the
    # single-input check above catches one of the eight.
    offenders = []
    for crv in _sources():
        hits = []
        _adjacent_text_runs(json.loads(carve.parse_json(crv.read_text(encoding="utf-8"))), hits)
        if hits:
            offenders.append(f"{crv.stem} ({len(hits)})")

    assert offenders == [], (
        f"{len(offenders)} document(s) publish adjacent text runs: {offenders[:8]}"
    )


# U+E000..U+E003 are the engine's internal sentinels (the no-break-space
# placeholder and the writer's verbatim marks). Every renderer resolves its own;
# one reaching a caller is a rendering bug wearing a private-use codepoint, and
# it is invisible in a terminal - which is exactly why it wants a check rather
# than an eye.
SENTINELS = re.compile("[\ue000-\ue003]")


def test_no_target_leaks_an_internal_sentinel():
    leaks = []
    for crv in _sources():
        source = crv.read_text(encoding="utf-8")
        for name, render in TARGETS.items():
            if SENTINELS.search(render(source)):
                leaks.append(f"{crv.stem} [{name}]")

    assert leaks == [], f"{len(leaks)} document(s) leak a private-use sentinel: {leaks[:5]}"
