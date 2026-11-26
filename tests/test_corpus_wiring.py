"""Keep the 0.2 conformance test reachable in CI."""

import os
import pathlib


EXAMPLES = os.environ.get("CARVE_SPEC2_EXAMPLES")
IN_CI = os.environ.get("GITHUB_ACTIONS") == "true" or os.environ.get("CI") == "true"


def test_ci_always_has_the_corpus_wired_up_c2_t005():
    if not IN_CI:
        return
    # C2-T-005: the 0.2 calls are checked against the 0.2 JSON conformance
    # examples and clause cases. The 0.1 source/HTML pair directory is retired.
    assert EXAMPLES, "CARVE_SPEC2_EXAMPLES is unset in CI, so the 0.2 conformance suite would skip"
    path = pathlib.Path(EXAMPLES)
    assert path.is_file(), f"CARVE_SPEC2_EXAMPLES={EXAMPLES} is not a file"
    assert path.with_name("clause-cases.json").is_file(), "0.2 lint clause cases are missing"
