"""The version this binding reports is the version that was packaged.

A version constant is read by people who cannot see the build: an embedder
quotes ``carve.__version__`` in a bug report, and a provenance stamp writes a
version into a document. When it names a release that is not the one running,
every conclusion drawn from it is wrong and the reader has no way to notice -
they suspect their own build first. carve-js shipped ``LIB_VERSION = '0.1.0'``
through three releases while its package was at 0.1.3, found by an outside
embedder (markup-carve/carve-js#1074). The comment guarding it said "keep in
sync with package.json on release", which is an instruction, not a check.

This binding states its release version in two hand-written places, and the two
feed different consumers:

- ``pyproject.toml`` ``[project] version`` is what PyPI and ``pip show`` report,
  and it is the only side the release workflow's tag guard reads;
- ``Cargo.toml`` ``[package] version`` is what ``carve.__version__`` reports,
  because the module exposes ``CARGO_PKG_VERSION``.

So bumping only the first - which is what a release did until the check below
existed - publishes a wheel that names itself one version and reports another.
The third side is the newest cut ``CHANGELOG.md`` section.

Every assertion reads BOTH of its sides at run time. No version literal appears
in this file: a literal would have to be edited on release too, which is the
defect rather than the fix.
"""

import pathlib
import re

import carve

ROOT = pathlib.Path(__file__).resolve().parent.parent


def _read(relative):
    path = ROOT / relative
    assert path.is_file(), (
        f"cannot read {path}; this gate compares two files against each other, "
        f"so a missing side means the comparison did not happen"
    )
    return path.read_text(encoding="utf-8")


def _table_version(relative, table):
    """The ``version`` key of one TOML table, read out of the file itself.

    Parsed by hand rather than with ``tomllib`` so the gate runs identically on
    every Python this package supports (``tomllib`` is 3.11+, the wheel is
    abi3-py38). Both manifests state the key on its own line.
    """
    in_table = False
    for line in _read(relative).splitlines():
        stripped = line.strip()
        if stripped.startswith("["):
            in_table = stripped == f"[{table}]"
            continue
        if not in_table:
            continue
        match = re.match(r'version\s*=\s*"([^"]+)"', stripped)
        if match:
            return match.group(1)
    raise AssertionError(f"{relative} has no [{table}] version field")


def _newest_released_changelog_version():
    """The newest CUT changelog section, skipping an open ``## [Unreleased]``.

    That heading is what the release process writes when it cuts a release, so
    it is an independently maintained record of the version this repo shipped.
    """
    for line in _read("CHANGELOG.md").splitlines():
        match = re.match(r"## \[?(\d[^\]\s]*)", line)
        if match:
            return match.group(1)
    raise AssertionError("CHANGELOG.md has no cut '## X.Y.Z' section")


def test_the_module_reports_the_packaged_version():
    packaged = _table_version("pyproject.toml", "project")

    assert carve.__version__ == packaged, (
        f"the installed module reports {carve.__version__}, but this tree "
        f"packages {packaged}. __version__ comes from Cargo.toml and the "
        f"distribution version from pyproject.toml, so an embedder reading "
        f"__version__ would name a release that is not the one running."
    )


def test_the_crate_version_is_the_packaged_version():
    crate = _table_version("Cargo.toml", "package")
    packaged = _table_version("pyproject.toml", "project")

    assert crate == packaged, (
        f"Cargo.toml is at {crate} and pyproject.toml at {packaged}. They are "
        f"two hand-written copies of one release number: the first is what "
        f"carve.__version__ reports, the second is what PyPI publishes and "
        f"what the release workflow's tag guard checks."
    )


def test_the_packaged_version_is_the_newest_released_changelog_section():
    packaged = _table_version("pyproject.toml", "project")
    changelog = _newest_released_changelog_version()

    assert packaged == changelog, (
        f"pyproject.toml packages {packaged}, but the newest cut CHANGELOG "
        f"section is {changelog}. Either the release bumped the version "
        f"without cutting the changelog, or it cut the changelog without "
        f"bumping the version."
    )
