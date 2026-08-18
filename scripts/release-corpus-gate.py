#!/usr/bin/env python3
"""The release's own corpus gate: the spec, run through the wheel about to be published.

WHY THIS EXISTS. `release.yml` built wheels, built an sdist and uploaded them to
PyPI without ever asking whether the artifact was correct. Every check it ran was
about the release's PAPERWORK - does the tag match the two manifests, does any
crate set `panic = "abort"` - and none of them about its OUTPUT. That is the
"check that cannot fail" class catalogued in markup-carve/carve#755, in the one
place where it is not recoverable: a publish is indexed by PyPI within minutes,
and a yank is itself a public event.

It is not hypothetical. The sibling binding carve-rb had a GREEN last `main` run
while the artifact built from that same `main` rendered 24 of 1241 corpus
documents wrongly, because nothing on the release path compared its output to
anything. This repository's own pin sat on 98de787 while rendering 75 of 1241
wrongly; a tag pushed in that window would have published it.

FOUR PROPERTIES, each of which some sibling gate is missing.

1. IT MEASURES THE ARTIFACT, NOT THE SOURCE TREE. The engine is a compiled
   `carve.abi3.so` inside the wheel, so "the tests pass" in a checkout says
   nothing about what the wheel carries: a rebuild, an editable install or a
   stale `target/` directory all render through a different binary. This script
   therefore refuses to run against an import that resolves inside the
   repository, and then compares every `carve/` member of the wheel byte for
   byte against the installed copy it just imported. A gate that measured
   something other than the upload would pass this file and then fail that
   comparison.

2. IT FAILS THE RELEASE RATHER THAN WARNING. It exits non-zero, and the workflow
   makes `publish` depend on the job that runs it, so the upload is not reachable
   when this refuses. `laravel-carve`, `symfony-carve` and `shopware-carve` each
   have a correct 1241-document comparison that runs on `schedule` only and
   reports divergence as a warning while exiting 0, so every required check is
   green while the shipped engine renders 15.5 percent of the corpus
   differently.

3. IT ASSERTS THE POPULATION, DERIVED. A runner that finds 3 documents and
   matches 3 of them prints a clean verdict. The expected count comes from
   `tests/corpus_population.py`, which counts the `::: compare` blocks the spec's
   example pages DECLARE - the corpus's source rather than the corpus, so
   emptying the corpus moves one side only. It is imported rather than
   reimplemented: this package already carried three hand-written floors that
   disagreed with each other, and a naive grep for the same blocks returns 1049
   where the real count is 1241.

4. IT IS ABLATED. See the pull request that introduced it for the output with a
   diverging engine, a truncated corpus and a substituted wheel.
"""

import argparse
import hashlib
import pathlib
import site
import sys
import sysconfig
import zipfile

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent


def _installed_library_roots():
    """Every directory a `pip install` of this interpreter can land a package in.

    `sysconfig` alone is not enough: outside a virtualenv, pip falls back to the
    user site, and CI installs into the runner's interpreter rather than a venv.
    Missing that would reject a correct configuration, which is how a guard gets
    deleted rather than fixed.
    """
    roots = [sysconfig.get_paths()[name] for name in ("purelib", "platlib")]
    roots.extend(site.getsitepackages())
    user_site = site.getusersitepackages()
    if user_site:
        roots.append(user_site)
    return roots


def _is_within(path, root):
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def fail(message):
    print(f"release corpus gate: FAIL: {message}", file=sys.stderr)
    raise SystemExit(1)


def import_carve():
    """Import the binding and refuse anything that is not an installed artifact."""
    try:
        import carve
    except Exception as error:  # noqa: BLE001 - any import failure is a release blocker
        fail(f"`import carve` failed: {error!r}. The wheel did not install, or it does not load.")

    location = pathlib.Path(carve.__file__).resolve()

    # An INSTALLED import lands in the running interpreter's site-packages. A
    # source-tree import and an editable install both resolve elsewhere - an
    # editable install's finder points `__file__` back at the project - so this
    # one question separates the artifact from every way of not measuring it.
    #
    # Deliberately not "outside the checkout": a virtualenv created inside the
    # workspace, which is what CI does, has its site-packages under the checkout
    # too, and rejecting that would reject the correct configuration.
    library_paths = {
        pathlib.Path(path).resolve()
        for path in _installed_library_roots()
    }
    if not any(_is_within(location, root) for root in library_paths):
        fail(
            f"`carve` imported from {location}, which is not inside this interpreter's "
            f"site-packages ({', '.join(str(root) for root in sorted(library_paths))}). "
            "The gate must measure the built wheel, not the source tree and not an editable "
            "install; run it from a virtualenv that has the wheel installed."
        )
    return carve, location.parent


def check_the_import_is_the_wheel(wheel_path, installed_dir):
    """Bind the imported module to the artifact, member by member.

    The engine is a compiled object. Comparing versions or import paths would
    pass over a wheel built from a different revision that happens to name the
    same version, which is exactly the drift this gate is for.
    """
    wheel = pathlib.Path(wheel_path)
    if not wheel.is_file():
        fail(f"no wheel at {wheel}. The gate has nothing to measure.")

    digest = hashlib.sha256(wheel.read_bytes()).hexdigest()
    compared = 0
    with zipfile.ZipFile(wheel) as archive:
        members = [name for name in archive.namelist() if name.startswith("carve/") and not name.endswith("/")]
        if not members:
            fail(f"{wheel.name} carries no `carve/` package members; it is not this project's wheel.")
        for name in members:
            installed = installed_dir / pathlib.PurePosixPath(name).relative_to("carve")
            if not installed.is_file():
                fail(f"{name} is in {wheel.name} but missing from the installed package at {installed}.")
            if installed.read_bytes() != archive.read(name):
                fail(
                    f"{name} differs between {wheel.name} and the installed copy at {installed}. "
                    "The module under test is NOT the artifact this job would publish."
                )
            compared += 1
    print(f"artifact    : {wheel.name} (sha256 {digest[:16]}), {compared} package members byte-identical to the import")


def declared_population(corpus_dir):
    """Reuse the package's ONE derivation of how big the corpus should be."""
    sys.path.insert(0, str(REPO_ROOT / "tests"))
    try:
        from corpus_population import declared_corpus_size
    except Exception as error:  # noqa: BLE001
        fail(f"could not import tests/corpus_population.py: {error!r}")
    try:
        return declared_corpus_size(corpus_dir)
    except Exception as error:  # noqa: BLE001 - it raises pytest.Failed on a missing source page
        fail(f"the corpus population could not be derived: {error}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wheel", required=True, help="the wheel this release would publish")
    parser.add_argument("--corpus", required=True, help="<spec>/tests/corpus")
    arguments = parser.parse_args()

    carve, installed_dir = import_carve()
    print(f"import      : {carve.__file__} (version {carve.__version__})")
    check_the_import_is_the_wheel(arguments.wheel, installed_dir)

    corpus = pathlib.Path(arguments.corpus)
    if not corpus.is_dir():
        fail(f"--corpus {corpus} is not a directory. An absent corpus must not certify a publish.")

    declared = declared_population(arguments.corpus)
    pairs = [(source, source.with_suffix(".html")) for source in sorted(corpus.glob("*.crv"))]
    pairs = [(source, expected) for source, expected in pairs if expected.is_file()]
    print(f"population  : {len(pairs)} pairs found, {declared} declared by the spec's example pages")
    if len(pairs) != declared:
        fail(
            f"the corpus at {corpus} holds {len(pairs)} document pairs where the spec's example "
            f"pages declare {declared}. A truncated or stale corpus renders cleanly over the "
            "subset it still contains; it must not certify a publish."
        )

    mismatches = []
    for source, expected in pairs:
        want = expected.read_text(encoding="utf-8").rstrip("\n")
        got = carve.to_html(source.read_text(encoding="utf-8")).rstrip("\n")
        if got != want:
            mismatches.append(source.stem)

    if mismatches:
        listed = "\n  ".join(mismatches[:25])
        more = f"\n  ... and {len(mismatches) - 25} more" if len(mismatches) > 25 else ""
        fail(
            f"{len(mismatches)} of {len(pairs)} corpus documents render differently through this "
            f"wheel:\n  {listed}{more}\n"
            "This artifact must not be published. The carve-rs rev in Cargo.toml is the usual "
            "cause; bump it, commit the regenerated Cargo.lock, and retag."
        )

    print(f"corpus      : {len(pairs)}/{len(pairs)} documents byte-identical")
    print("release corpus gate: PASS")


if __name__ == "__main__":
    main()
