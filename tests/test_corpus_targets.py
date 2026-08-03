"""The corpus through the targets nothing else reads.

`test_corpus.py` and `test_byte_identical.py` are both `to_html` only, and HTML
is the target where the engines have been in agreement all along -- which is
exactly why cross-engine divergences kept landing elsewhere. This binding also
exposes `to_markdown`, `to_ansi`, `to_plain_text` and `parse_json`, and nothing
measured any of them, so a stale engine pin could and did sit here with a green
suite (issue #16).

These are PROPERTIES rather than fixtures on purpose. The corpus ships expected
HTML and nothing else, so there is no golden to compare the other targets
against -- but the failures the stale pin actually shipped are all expressible
as invariants that need no oracle, and an invariant does not go stale when the
corpus grows.
"""

import glob
import json
import os
import pathlib
import re

import carve
import pytest

CORPUS = os.environ.get("CARVE_SPEC_CORPUS")

pytestmark = pytest.mark.skipif(
    not CORPUS, reason="CARVE_SPEC_CORPUS not set (see .github/workflows/ci.yml)"
)

# The corpus has ~500 documents. Far below that means the path is wrong rather
# than that the run was clean.
MIN_DOCUMENTS = 400

# U+E000..U+E003 are the engine's internal sentinels (the no-break-space
# placeholder and the writer's verbatim marks). Every renderer resolves its own;
# one reaching a caller is a rendering bug wearing a private-use codepoint.
SENTINELS = re.compile("[-]")

TARGETS = {
    "html": carve.to_html,
    "markdown": carve.to_markdown,
    "ansi": carve.to_ansi,
    "plain": carve.to_plain_text,
}


def _documents():
    directory = pathlib.Path(CORPUS)
    if not directory.is_dir():
        pytest.fail(f"CARVE_SPEC_CORPUS={CORPUS} is not a directory")
    found = sorted(glob.glob(str(directory / "*.crv")))
    assert len(found) >= MIN_DOCUMENTS, (
        f"only {len(found)} corpus documents under {CORPUS}; the corpus has ~500, "
        "so this is a wiring problem, not a clean run"
    )
    return [(pathlib.Path(f).name, pathlib.Path(f).read_text(encoding="utf-8")) for f in found]


def test_every_target_renders_every_document():
    """A target that raises on a corpus document is a hard failure.

    `to_html` was the only one anything called, so a panic converted to an
    exception in any other renderer would have surfaced to a user first.
    """
    failures = []
    for name, source in _documents():
        for target, render in TARGETS.items():
            try:
                render(source)
            except Exception as error:  # noqa: BLE001 - the point is to name it
                failures.append(f"{name} [{target}]: {type(error).__name__}: {error}")
    assert failures == [], f"{len(failures)} render failure(s): {failures[:5]}"


def test_no_target_leaks_an_internal_sentinel():
    leaks = []
    for name, source in _documents():
        for target, render in TARGETS.items():
            output = render(source)
            if SENTINELS.search(output):
                leaks.append(f"{name} [{target}]")
    assert leaks == [], f"{len(leaks)} document(s) leak a private-use sentinel: {leaks[:5]}"


def test_markdown_emits_no_nested_link():
    """A link inside a link is not valid Markdown.

    Carve's no-nested-links rule was applied in the HTML renderer before the
    Markdown and ANSI ones (carve-rs#437), so `to_markdown` published
    `[see [H](#H)](/outer)` -- a consumer reparsing that gets a different
    document from the one Carve describes.
    """
    nested = [name for name, source in _documents() if _has_nested_link(carve.to_markdown(source))]
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


def test_parse_publishes_no_adjacent_text_runs():
    """PART 12 section 1a: a published node's children hold no two adjacent
    `text` nodes, and the merge belongs to `parse(x)`.

    This is the invariant the stale pin actually broke: against the engine this
    binding shipped before the bump, 8 corpus documents published runs, so a
    consumer comparing this tree against carve-js got a different tree for the
    same characters.
    """
    offenders = []
    for name, source in _documents():
        hits = []
        _adjacent_text_runs(json.loads(carve.parse_json(source)), hits)
        if hits:
            offenders.append(f"{name} ({len(hits)})")
    assert offenders == [], (
        f"{len(offenders)} document(s) publish adjacent text runs: {offenders[:8]}"
    )


def _has_nested_link(markdown):
    r"""Whether any link label in `markdown` contains a complete link.

    Written as a bracket walk rather than a regex. The obvious pattern -
    `\[([^\[\]]*)\]\(` - forbids `[` inside the label, so on
    `[see [H](#H)](/outer)` it skips the outer label entirely and matches the
    INNER link, whose label holds nothing: the check would pass on exactly the
    input it exists to catch.
    """
    depth = 0
    # Offset of the `[` that opened each currently-open label, and whether a
    # complete `](` has been seen since it opened.
    open_labels = []
    escaped = False
    for i, ch in enumerate(markdown):
        if escaped:
            escaped = False
            continue
        if ch == "\\":
            escaped = True
        elif ch == "[":
            depth += 1
            open_labels.append(False)
        elif ch == "]" and depth:
            depth -= 1
            closed_a_link = markdown[i + 1 : i + 2] == "("
            inner_saw_link = open_labels.pop()
            if closed_a_link and inner_saw_link:
                return True
            if closed_a_link and open_labels:
                open_labels[-1] = True
    return False
