import re
from pathlib import Path

import pytest

import carve

# A panic crossing the PyO3 boundary must arrive as an exception the handler
# hosts actually write catches. PyO3 already converts the unwind - that is why
# the interpreter survives one - but it raises `pyo3_runtime.PanicException`,
# built over `PyBaseException` (pyo3-0.27.2 src/panic.rs:11-16), so
# `except Exception` does not see it. Measured on the 0.1.7 source with a
# temporary probe:
#
#   1. except Exception MISSED; BaseException caught PanicException
#      MRO: ['PanicException', 'BaseException', 'object']
#
# (markup-carve/carve-py#94)
#
# `carve._panic_probe` is why this file tests the mechanism rather than one
# input's symptom. No Carve source panics the pinned engine - `to_html("|{.r}")`
# is fixed in carve-lang 0.1.8 - so an input-based test would be silently
# disarmed by the next engine fix.
LIB_RS = Path(__file__).resolve().parents[1] / "src" / "lib.rs"


def test_panic_probe_raises_engine_panic_error():
    with pytest.raises(carve.EnginePanicError) as excinfo:
        carve._panic_probe()
    assert "deliberate panic from the Carve extension panic probe" in str(excinfo.value)


def test_except_exception_catches_an_engine_panic():
    try:
        carve._panic_probe()
        outcome = "returned"
    except Exception as error:  # noqa: BLE001 - the point of the ticket
        outcome = type(error)
    assert outcome is carve.EnginePanicError


def test_engine_panic_error_is_an_exception_subclass():
    assert issubclass(carve.EnginePanicError, Exception)
    assert issubclass(carve.EnginePanicError, BaseException)


def test_message_carries_the_panic_location():
    with pytest.raises(carve.EnginePanicError) as excinfo:
        carve._panic_probe()
    assert re.search(r"panicked at \S+:\d+:\d+:", str(excinfo.value))


def test_rendering_still_works_after_a_panic():
    with pytest.raises(carve.EnginePanicError):
        carve._panic_probe()
    assert carve.to_html("ok").strip() == "<p>ok</p>"


def _body_after_signature(source: str, name: str) -> str:
    """The function body of `fn name`, found by brace rather than by regex."""
    match = re.search(r"\nfn " + re.escape(name) + r"\s*[(<]", source)
    assert match, f"no definition found for registered function {name}"
    start = match.start()
    depth = 0
    for index in range(start, len(source)):
        char = source[index]
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
        elif char == "{" and depth == 0:
            return source[index + 1 :]
    raise AssertionError(f"no body found for {name}")


def test_every_registered_function_runs_inside_the_guard():
    """One registration without the guard would restore `PanicException` on
    just that call, and no behavioral test would notice until it panicked."""
    source = LIB_RS.read_text(encoding="utf-8")
    registered = re.findall(r"wrap_pyfunction!\(\s*([A-Za-z0-9_]+)\s*,", source)
    assert registered

    unguarded = [
        name
        for name in registered
        if not _body_after_signature(source, name).lstrip().startswith("guard(")
    ]
    assert not unguarded, f"registered without a panic guard: {', '.join(unguarded)}"
