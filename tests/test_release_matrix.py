"""Every wheel the release builds is gated, and nothing gates a wheel twice.

The release workflow builds one wheel per platform and runs the spec corpus
through each one before `publish` can start. That only holds while the two
matrices agree: an entry added to the build matrix and forgotten in a gate
matrix produces a wheel that is uploaded without the corpus ever touching it,
and nothing in the workflow would say so - the run is green either way.

That is the "check that cannot fail" of markup-carve/carve#755 arriving through
a gap rather than through a weak assertion, on the one path that cannot be
undone. So the agreement is a test rather than a habit.

Parsed with a regex rather than a YAML library on purpose: the test environment
installs pytest and the wheel, nothing else, and a test that needs a dependency
CI does not have is a test CI does not run.
"""

from __future__ import annotations

import re
from pathlib import Path

WORKFLOW = Path(__file__).resolve().parent.parent / ".github" / "workflows" / "release.yml"

_JOB = re.compile(r"^  (?P<name>[a-z0-9-]+):$", re.MULTILINE)
# A matrix entry's name is one token. A step's `- name:` is a sentence, and sits
# at a different indent; both differences are checked so neither alone carries it.
_MATRIX_ENTRY = re.compile(r"^ {10}- name: (?P<name>[A-Za-z0-9._-]+)$", re.MULTILINE)


def _jobs() -> dict[str, str]:
    text = WORKFLOW.read_text(encoding="utf-8")
    starts = [(m.group("name"), m.start()) for m in _JOB.finditer(text)]
    assert starts, f"{WORKFLOW} has no jobs"
    bounds = starts + [("", len(text))]
    return {
        name: text[start : bounds[index + 1][1]]
        for index, (name, start) in enumerate(starts)
    }


def _entries(job: str) -> list[str]:
    jobs = _jobs()
    assert job in jobs, f"{WORKFLOW} has no job named {job}; it has {sorted(jobs)}"
    return [match.group("name") for match in _MATRIX_ENTRY.finditer(jobs[job])]


def test_every_built_wheel_is_gated():
    built = _entries("build-wheels")
    gated = _entries("corpus-gate") + _entries("corpus-gate-musl")

    assert built, "the build matrix is empty"
    assert sorted(built) == sorted(gated), (
        f"the release builds {sorted(built)} and gates {sorted(gated)}. A wheel "
        f"that is built and not gated is uploaded without the spec corpus ever "
        f"running through it."
    )


def test_no_wheel_is_gated_twice():
    gated = _entries("corpus-gate") + _entries("corpus-gate-musl")

    assert len(gated) == len(set(gated)), (
        f"two gate jobs claim the same wheel: {sorted(gated)}. Both would "
        f"download the same artifact, and one of them is measuring the wrong "
        f"platform."
    )


def test_publish_waits_for_both_gates():
    jobs = _jobs()
    needs = re.search(r"^    needs: \[(?P<list>[^\]]*)\]$", jobs["publish"], re.MULTILINE)

    assert needs, "the publish job declares no needs"
    required = {item.strip() for item in needs.group("list").split(",")}
    assert {"corpus-gate", "corpus-gate-musl"} <= required, (
        f"publish needs {sorted(required)}. A gate the upload does not wait for "
        f"is a gate that cannot stop it."
    )
