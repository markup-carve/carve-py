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

3. IT ASSERTS THE POPULATION, DERIVED. A runner that finds 3 cases and
   matches 3 of them prints a clean verdict. The conformance files must be
   byte-identical to the copy the pinned carve-rs vendors in
   `spec-conformance/`, so a truncated or stale spec checkout fails rather than
   certifying the subset it still holds.

4. IT IS ABLATED. See the pull request that introduced it for the output with a
   diverging engine, a truncated corpus and a substituted wheel.
"""

import argparse
import hashlib
import importlib.util
import json
import pathlib
import site
import subprocess
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


CONFORMANCE_FILES = ("examples.json", "clause-cases.json")


def pinned_revision(engine, manifest, lock):
    """The carve-rs commit the lock resolved."""
    path = REPO_ROOT / "scripts" / "pinned-spec-commit.py"
    spec = importlib.util.spec_from_file_location("pinned_spec_commit", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    pin = module.lock_pin(pathlib.Path(lock))
    if module.manifest_pin(pathlib.Path(manifest)) != pin:
        fail(f"{manifest} and {lock} pin different engines.")
    return module.resolve_pin(pathlib.Path(engine), pin)


def check_the_corpus_is_the_engines(conformance, engine, revision):
    """The spec checkout must hold exactly the conformance files the pinned engine vendors."""
    for name in CONFORMANCE_FILES:
        local = conformance / name
        if not local.is_file():
            fail(f"{local} is missing. An absent corpus must not certify a publish.")
        vendored = subprocess.run(
            ["git", "-C", str(engine), "show", f"{revision}:spec-conformance/{name}"],
            capture_output=True, check=False,
        )
        if vendored.returncode != 0:
            fail(f"carve-rs {revision[:12]} has no spec-conformance/{name}; it is not a 0.2 engine.")
        if local.read_bytes() != vendored.stdout:
            fail(
                f"{local} differs from spec-conformance/{name} at carve-rs {revision[:12]}. "
                "The spec checkout is not the corpus the pinned engine was written against."
            )


def run_conformance(carve, conformance):
    """Verified render examples (HTML and tree) and source-only lint clause cases."""
    examples = json.loads((conformance / "examples.json").read_text(encoding="utf-8"))["examples"]
    catalog = json.loads((conformance.parent / "data" / "options.json").read_text(encoding="utf-8"))
    parse_keys = {
        option["name"] for option in catalog["options"]
        if ({option["read_by"]} if isinstance(option["read_by"], str) else set(option["read_by"]))
        & {"parse", "resolve"}
    }
    renders = [
        row for row in examples
        if row.get("kind") == "render"
        and row.get("status") == "verified"
        and isinstance(row.get("expected", {}).get("html"), str)
    ]
    cases = json.loads((conformance / "clause-cases.json").read_text(encoding="utf-8"))["cases"]
    lints = [
        row for row in cases
        if row.get("kind") == "lint" and isinstance(row.get("input"), str)
        and not row.get("files") and not row.get("options")
    ]
    print(f"population  : {len(renders)} verified render examples, {len(lints)} lint clause cases")
    if not renders or not lints:
        fail("the conformance corpus selected no cases; it must not certify a publish.")

    mismatches = []
    for row in renders:
        options = row.get("options") or {}
        try:
            if carve.render(row["input"], options)["html"] != row["expected"]["html"]:
                mismatches.append(f"{row['id']} (html)")
                continue
            tree = row["expected"].get("tree")
            if isinstance(tree, dict):
                parse_options = {key: value for key, value in options.items() if key in parse_keys}
                if carve.parse(row["input"], parse_options)["tree"]["children"] != tree["children"]:
                    mismatches.append(f"{row['id']} (tree)")
        except carve.EnginePanicError as panic:
            # A panic is one more divergence; aborting would leave the rest unmeasured.
            mismatches.append(f"{row['id']} (engine panic: {str(panic).splitlines()[0]})")
    for row in lints:
        try:
            actual = [entry["code"] for entry in carve.lint(row["input"])["diagnostics"]]
        except carve.EnginePanicError as panic:
            mismatches.append(f"{row['id']} (engine panic: {str(panic).splitlines()[0]})")
            continue
        expected = [
            entry if isinstance(entry, str) else entry["code"]
            for entry in row["expected"].get("diagnostics", [])
        ]
        if not all(code in actual for code in expected):
            mismatches.append(f"{row['id']} (lint)")
    return len(renders) + len(lints), mismatches


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wheel", required=True, help="the wheel this release would publish")
    parser.add_argument("--conformance", required=True, help="<spec>/spec/0.2/conformance")
    parser.add_argument("--engine", required=True, help="a full carve-rs checkout")
    parser.add_argument("--manifest", default=str(REPO_ROOT / "Cargo.toml"))
    parser.add_argument("--lock", default=str(REPO_ROOT / "Cargo.lock"))
    arguments = parser.parse_args()

    carve, installed_dir = import_carve()
    print(f"import      : {carve.__file__} (version {carve.__version__})")
    check_the_import_is_the_wheel(arguments.wheel, installed_dir)

    conformance = pathlib.Path(arguments.conformance)
    if not conformance.is_dir():
        fail(f"--conformance {conformance} is not a directory. An absent corpus must not certify a publish.")
    revision = pinned_revision(arguments.engine, arguments.manifest, arguments.lock)
    check_the_corpus_is_the_engines(conformance, pathlib.Path(arguments.engine), revision)
    print(f"corpus      : {conformance} matches the copy carve-rs {revision[:12]} vendors")

    total, mismatches = run_conformance(carve, conformance)
    if mismatches:
        listed = "\n  ".join(mismatches[:25])
        more = f"\n  ... and {len(mismatches) - 25} more" if len(mismatches) > 25 else ""
        fail(
            f"{len(mismatches)} of {total} conformance cases differ through this wheel:\n  "
            f"{listed}{more}\n"
            "This artifact must not be published. The carve-rs rev in Cargo.toml is the usual "
            "cause; bump it, commit the regenerated Cargo.lock, and retag."
        )

    print(f"conformance : {total}/{total} cases pass through the wheel")
    print("release corpus gate: PASS")


if __name__ == "__main__":
    main()
