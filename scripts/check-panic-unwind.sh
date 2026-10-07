#!/usr/bin/env bash
#
# check-panic-unwind.sh
#
# Regression guard for the FFI panic-safety net.
#
# A Rust panic in this extension unwinds, is caught, and is raised to Python as
# `carve.EnginePanicError` - an Exception subclass a host can handle. Two
# separate pieces produce that, and this script guards the first:
#
#   1. `panic = "unwind"` (the Cargo default) makes the panic unwindable at all,
#      so catch_unwind can run and the panic report keeps its location and any
#      RUST_BACKTRACE output.
#   2. `guard` in src/lib.rs catches that unwind and converts it. Without it the
#      panic still reaches Python - PyO3 catches it too - but as
#      `PanicException`, which derives from `BaseException` and therefore
#      escapes `except Exception` (markup-carve/carve-py#94).
#      tests/test_panic_unwind.py covers that half.
#
# If anyone later adds `panic = "abort"` to a tracked Cargo.toml (this crate or
# an inherited workspace profile), the unwind is silently removed: there is
# nothing left to catch or convert, and a panic would abort the Python
# interpreter.
#
# This script fails if any tracked Cargo.toml sets `panic = "abort"`.
# It is intentionally cheap so it can gate every CI run.
set -euo pipefail

cd "$(dirname "$0")/.."

# Only inspect git-tracked Cargo.toml files, so vendored/dependency copies
# under target/ or other ignored paths cannot trip (or defeat) the guard.
#
# Read with a while loop rather than `mapfile`: that is a bash 4 builtin, and
# macOS ships bash 3.2. On a macOS runner `mapfile` is simply not found, and
# because this script runs under `set -e` the guard failed the whole job - which
# is how the 0.1.0 release lost its macOS wheel and skipped publishing.
cargo_tomls=()
while IFS= read -r path; do
  cargo_tomls+=("$path")
done < <(git ls-files '*Cargo.toml' 'Cargo.toml')

if [ "${#cargo_tomls[@]}" -eq 0 ]; then
  echo "check-panic-unwind: no tracked Cargo.toml found" >&2
  exit 1
fi

# Match only an actual setting: `panic = "abort"` at the start of a line
# (optional leading whitespace). Lines beginning with `#` are comments (such as
# the explanatory note in Cargo.toml) and are intentionally NOT matched.
if grep -nE '^[[:space:]]*panic[[:space:]]*=[[:space:]]*"abort"' "${cargo_tomls[@]}"; then
  echo >&2
  echo "ERROR: 'panic = \"abort\"' found in a tracked Cargo.toml." >&2
  echo "This extension relies on catch_unwind (panic = \"unwind\") to convert a" >&2
  echo "Rust panic into a catchable carve.EnginePanicError; 'abort' removes the" >&2
  echo "unwind entirely and would let a panic kill the host." >&2
  echo "Remove the 'panic = \"abort\"' setting." >&2
  exit 1
fi

echo "check-panic-unwind: OK (no panic = \"abort\" in tracked Cargo.toml)"
