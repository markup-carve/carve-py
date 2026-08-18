"""The corpus gate has to be REACHED, not merely present.

``test_corpus.py``, ``test_corpus_ast.py`` and ``test_non_html_targets.py`` all
hang off one environment variable, and every one of them declares

    pytestmark = pytest.mark.skipif(not CORPUS, reason=...)

That skip is a convenience for a plain checkout without the spec repo, and it is
a hole in CI. All three modules are reached through a single ``env:`` block in
``.github/workflows/ci.yml``; delete it, rename the variable, or move the pytest
step to a job that never checks the spec out, and every corpus assertion stops
running while ``pytest -q`` still exits 0. The build goes green having compared
nothing - the variant-1 dead check catalogued in markup-carve/carve#755, and the
shape hugo-carve shipped, where ci.yml skipped the corpus test in silence.

Measured on this package before this file existed: with CARVE_SPEC_CORPUS unset,
``pytest -q tests/test_corpus.py tests/test_corpus_ast.py
tests/test_non_html_targets.py`` printed ``16 skipped`` and exited 0, over an
engine pin that was diverging on 75 of the spec's 1239 documents at the time.

So the skip is kept exactly where it is useful and refused where it is
dangerous. This test carries no skipif of its own: a CI runner that gets here
without a corpus is a wiring failure, and it fails rather than reporting a pass.
"""

import os
import pathlib

CORPUS = os.environ.get("CARVE_SPEC_CORPUS")

# GitHub Actions sets both; `CI` alone covers other runners.
IN_CI = os.environ.get("GITHUB_ACTIONS") == "true" or os.environ.get("CI") == "true"


def test_ci_always_has_the_corpus_wired_up():
    if not IN_CI:
        # Local runs legitimately have no spec checkout. Asserting here would
        # make `pytest` unrunnable outside CI, which is how a guard gets
        # deleted rather than fixed.
        return
    assert CORPUS, (
        "CARVE_SPEC_CORPUS is unset in a CI run. The corpus tests are the only checks that "
        "measure this binding against the spec, and unset they skip and report success. Set it "
        'from the spec checkout (see the "Check out the spec corpus" step in '
        ".github/workflows/ci.yml); do not let this run report success."
    )
    assert pathlib.Path(CORPUS).is_dir(), (
        f"CARVE_SPEC_CORPUS={CORPUS} is set in a CI run but is not a directory, so every corpus "
        "test below it fails at collection or skips. The spec checkout step is misconfigured."
    )
