"""How many documents the spec corpus should hold, derived rather than recorded.

ONE spelling of "a corpus runner must not report success over an empty or short
population" (the variant-2 defect catalogued in markup-carve/carve#755). This
package had THREE of them, each with its own literal and its own wrong number:
``test_corpus.py`` and ``test_non_html_targets.py`` said "the corpus has ~500",
``test_corpus_ast.py`` said "~650", and all three let a run through at 400
documents against a corpus of 1124.

That gap is not theoretical. Measured on the sibling binding with the identical
floor, a corpus cut to 420 documents printed
``corpus: 420/420 documents byte-identical`` - a clean verdict over 37 percent
of the corpus, with every then-diverging document simply absent
(markup-carve/carve-py#43).

THE COMPARISON HAS TO BE AGAINST SOMETHING THE RUNNER DOES NOT ITSELF READ AS
THE POPULATION. Deriving "how many documents should there be" from the corpus
directory would be a check that reads its own input hiding inside a fix for a
check that cannot fail: emptying the directory would move both sides and the
guard would still pass.

So the reference is the corpus's SOURCE, not the corpus. ``tests/corpus`` is
generated from the ``::: compare`` blocks in
``resources/examples/{core,extensions,edge-cases}.md`` (see
``scripts/generate-corpus.mjs`` in the spec repository), and the generator
refuses to write a corpus where the two disagree. Both live in the same spec
checkout CI already clones, one directory away from ``CARVE_SPEC_CORPUS`` - the
same route ``test_corpus_ast.py`` already takes to ``resources/ast-schema.json``.

Counting the source rather than recording a number also means there is no
literal left to go stale: adding an example upstream moves the expectation on
the next spec checkout, without anyone editing these files. A hardcoded 1124
would be this same defect with a bigger number.
"""

import pathlib
import re

import pytest

# The pages the corpus is generated from, in the order the generator reads them.
# Order is irrelevant to a count; the list is the generator's.
EXAMPLE_PAGES = ("core.md", "extensions.md", "edge-cases.md")

# Mirrors the generator: `::: compare`, or a longer colon run, with optional
# modifiers such as `::: compare no-render`.
_COMPARE_OPEN = re.compile(r"^:{3,}\s+compare(\s+\S.*)?$")
_MARKER_RUN = re.compile(r"^:{3,}")


def declared_corpus_size(corpus_dir):
    """Count the example pairs the spec DECLARES.

    ``corpus_dir`` is ``CARVE_SPEC_CORPUS``, i.e. ``<spec>/tests/corpus``.

    Count Carve and HTML fences independently of generated files. Each
    compare block must contain equal, nonzero counts. Literal fenced content
    cannot open or close a compare block.
    """
    examples_dir = pathlib.Path(corpus_dir).parent.parent / "resources" / "examples"
    declared = 0
    for page in EXAMPLE_PAGES:
        path = examples_dir / page
        if not path.exists():
            # Not a soft skip. Without this file there is no independent
            # statement of how big the corpus should be, and a corpus check with
            # nothing to compare against is the failure shape this helper exists
            # to remove.
            pytest.fail(
                f"no corpus source page at {path}. tests/corpus is generated from these "
                "pages; if the spec moved them, this helper has to move with them"
            )
        marker = None
        fence = None
        counts = {"carve": 0, "html": 0}
        for line in path.read_text(encoding="utf-8").split("\n"):
            if fence is not None:
                if line.startswith(fence) and not line[len(fence):].strip():
                    fence = None
                continue
            opening = re.match(r"^(`{3,})(.*)$", line)
            if opening:
                fence = opening.group(1)
                language = opening.group(2).strip()
                if marker is not None and language in counts:
                    counts[language] += 1
                continue
            trimmed = line.strip()
            if marker is not None:
                if trimmed == marker:
                    assert counts["carve"] == counts["html"] and counts["carve"] > 0, (
                        f"unpaired or empty compare block in {path}: {counts}"
                    )
                    declared += counts["carve"]
                    marker = None
                continue
            if _COMPARE_OPEN.match(trimmed):
                marker = _MARKER_RUN.match(trimmed).group(0)
                counts = {"carve": 0, "html": 0}
        assert marker is None and fence is None, f"unclosed compare block or fence in {path}"
    if declared == 0:
        pytest.fail(
            f"the corpus source pages under {examples_dir} declare no ::: compare blocks "
            "at all; this is a wiring problem, not a corpus of size zero"
        )
    return declared


def require_whole_corpus(corpus_dir, got, what):
    """The only place this package decides whether a population is whole.

    ``got`` is what the caller actually processed; ``what`` names it for the
    failure message.

    Equality rather than a floor, deliberately. A floor is what went stale three
    times here, and it answers the wrong question: "at least 400" cannot tell a
    whole corpus from a truncated checkout, and truncation is the failure being
    guarded against.
    """
    declared = declared_corpus_size(corpus_dir)
    assert got == declared, (
        f"{what}: {got}, but the spec's example pages declare {declared}. Every "
        "::: compare block in resources/examples/{core,extensions,edge-cases}.md becomes "
        f"its declared fence pairs, so a difference means the corpus at {corpus_dir} is not the one "
        "those pages describe - a truncated or stale checkout, a wrong CARVE_SPEC_CORPUS, "
        "or a corpus that needs regenerating (npm run corpus:build in the spec repository). "
        "It does not mean this run was clean."
    )
