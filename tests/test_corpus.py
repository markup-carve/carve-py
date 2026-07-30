"""The mandatory spec corpus, run through this binding.

Every implementation is held to byte-identical HTML for these inputs. This
binding pins carve-rs and builds it from source, so it cannot ship a stale
prebuilt artifact -- but it can sit on a pinned revision whose output no longer
matches the spec, and the rest of the suite asserts hand-written expectations
that a drifted engine satisfies happily. That is how the pin came to sit months
behind with CI green (see the note in .github/workflows/ci.yml).

The corpus path comes from CARVE_SPEC_CORPUS. Unset, these tests skip, so a plain
`pytest` works in a checkout without the spec repo. CI always sets it, and the
guard below turns "the corpus was not really there" into a failure rather than a
pass -- an empty directory otherwise reports zero mismatches and looks clean,
which is the same shape of check the gate exists to replace.
"""

import os
import pathlib

import carve
import pytest

CORPUS = os.environ.get("CARVE_SPEC_CORPUS")

pytestmark = pytest.mark.skipif(
    not CORPUS, reason="CARVE_SPEC_CORPUS not set (see .github/workflows/ci.yml)"
)

# The corpus has ~500 pairs. Anything far below that means the path is wrong
# rather than that the run was clean.
MIN_PAIRS = 400


def _pairs():
    directory = pathlib.Path(CORPUS)
    if not directory.is_dir():
        pytest.fail(f"CARVE_SPEC_CORPUS={CORPUS} is not a directory")
    found = []
    for crv in sorted(directory.glob("*.crv")):
        html = crv.with_suffix(".html")
        if html.exists():
            found.append((crv, html))
    return found


def test_corpus_is_actually_present():
    pairs = _pairs()
    assert len(pairs) >= MIN_PAIRS, (
        f"only {len(pairs)} corpus pairs under {CORPUS}; the corpus has ~500, "
        "so this is a wiring problem, not a clean run"
    )


def test_corpus_renders_byte_identically():
    mismatches = []
    pairs = _pairs()
    for crv, html in pairs:
        want = html.read_text(encoding="utf-8").rstrip("\n")
        got = carve.to_html(crv.read_text(encoding="utf-8")).rstrip("\n")
        if got != want:
            mismatches.append(crv.stem)

    assert not mismatches, (
        f"{len(mismatches)} of {len(pairs)} corpus cases diverge from the spec: "
        f"{', '.join(mismatches[:20])}"
        f"{' ...' if len(mismatches) > 20 else ''}. "
        "The carve-rs pin is probably behind; bump it with `cargo update -p carve-lang`."
    )
