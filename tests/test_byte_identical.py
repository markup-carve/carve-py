"""Byte-identical parity check: the Python binding must not diverge from the
carve-rs engine it wraps.

For each sample, we run the carve-rs CLI binary (built in the carve-rs repo)
and compare its stdout to `carve.to_html`. The CLI appends a trailing newline
when the output lacks one, so we normalize a single trailing newline before
comparing.

If the CLI binary is not present, the test is skipped (the binding still works;
this is purely an engine-parity cross-check).
"""

import os
import subprocess

import carve
import pytest

CARVE_BIN = "/media/mark/data/work/git/carve-rs/target/release/carve"

SAMPLES = [
    "# Hello *world*\n",
    "- one\n- two\n\nA /italic/ and `code` line.\n",
    "| a | b |\n|---|---|\n| 1 | 2 |\n",
]


def _cli_html(src: str) -> str:
    res = subprocess.run(
        [CARVE_BIN, "--html"],
        input=src.encode("utf-8"),
        capture_output=True,
        check=True,
    )
    return res.stdout.decode("utf-8")


@pytest.mark.skipif(
    not os.path.exists(CARVE_BIN),
    reason="carve-rs CLI binary not built",
)
@pytest.mark.parametrize("src", SAMPLES)
def test_byte_identical_to_cli(src):
    py = carve.to_html(src)
    cli = _cli_html(src)
    # The CLI guarantees exactly one trailing newline; normalize both sides to
    # a single trailing newline so we compare the rendered body byte-for-byte.
    assert py.rstrip("\n") + "\n" == cli.rstrip("\n") + "\n"
