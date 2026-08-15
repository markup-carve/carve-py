# Releasing

Wheels and the sdist are published to PyPI as `carve-lang` by
`.github/workflows/release.yml`, which runs on a pushed `v*` tag. The import
name stays `carve`; only the distribution name differs.

The publish job prefers a `PYPI_API_TOKEN` secret when one is set and otherwise
uploads through Trusted Publishing, which stores no credential at all.

## One-time setup

All of it happens outside this repository's files.

1. In the repository settings, create an environment named `pypi`. The publish
   job is bound to it, so restricting who may approve it also restricts who may
   release.
2. Give the first release a credential, either way round:
   - **Trusted Publishing, no secret.** On PyPI, add a *pending* publisher for
     the project name `carve-lang`: owner `markup-carve`, repository
     `carve-py`, workflow `release.yml`, environment `pypi`. PyPI supports
     pending publishers precisely so a name that does not exist yet can be
     claimed this way.
   - **API token.** Set `PYPI_API_TOKEN` as a repository secret. A token for a
     project that does not exist yet has to be account-scoped, because
     project-scoped tokens cannot be minted before the project does. Treat that
     as a bootstrap credential: after the first upload, add a trusted publisher
     on the now-existing PyPI project and `gh secret delete PYPI_API_TOKEN`, so
     the broad credential stops living in the repository.

## Per release

1. Move the entries under a version heading in `CHANGELOG.md` and set its date.
2. Set the version in **both** manifests: `project.version` in `pyproject.toml`
   and `package.version` in `Cargo.toml`. They feed different readers - PyPI and
   `pip show` report the first, `carve.__version__` reports the second, because
   the module exposes `CARGO_PKG_VERSION`. Bumping only `pyproject.toml`
   publishes a wheel that names itself one version and reports another, which is
   how carve-js shipped an exported constant reading 0.1.0 across three releases
   (`markup-carve/carve-js#1074`).
3. Tag `vX.Y.Z` and push the tag. The workflow matches `v*` - a bare `0.1.0`
   tag lands but fires nothing, which is a silent no-op rather than an error.

Steps 1 and 2 are checked rather than remembered: `tests/test_release_version.py`
compares the two manifests and the changelog against each other and against the
installed module on every CI run, and the release workflow's `guard` job refuses
a tag that disagrees with either manifest.

## What the wheel embeds

The engine is carve-rs, built from the revision recorded in `Cargo.lock`. That
revision is what a release ships, so treat an engine bump as a release-worthy
change: the same Python code renders differently underneath.
