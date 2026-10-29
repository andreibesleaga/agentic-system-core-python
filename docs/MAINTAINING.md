# Maintaining the Python package

**Summary.** How the package is arranged, what it runs natively and what it hands to
the Node engine, how the equivalence with the engine is proved, how to run the tests,
how to refresh what it copies from the specification, and how a release happens. It is
for a maintainer or a contributor; a user wants the [README](../README.md).

**Read after:** the [README](../README.md) and
[src/agentic_system_core/README.md](../src/agentic_system_core/README.md).

## What runs natively, and what is forwarded

Native, in the standard library: `agsc validate-wellknown`, `agsc validate-vectors`,
`agsc run-vectors` (seven areas: `build`, `discovery`, `frontmatter`, `graph`, `jcs`,
`links`, `slug`) and the reading API. Forwarded, exactly as typed and without a shell:
the sixteen engine verbs, to the npm package's `agsc` when it is on the `PATH`. The
README's "What runs here" and "What forwards to Node" sections are the detail.
[ARCHITECTURE.md](ARCHITECTURE.md) draws the parts and how they call each other.

## The equivalence proof

`tests/test_equivalence.py` runs this package's discovery-file checker and the engine's
`tools/validate-wellknown` over the same documents, at every Level, with and without a
peer, and compares the status, the counts and each finding's position and code. The
cross-runner test (`tests/test_vector_equivalence.py`) runs the engine's vector runner
over its live set and requires both runners to agree on every vector of the seven areas.
Both need the engine checked out beside this repository at `../agentic-system-core` and
Node 22.13 or later; without them they are skipped with a message. The tests that read
the built discovery files of the two sites use the checkouts beside this repository, at
`../AgenticSystemCore.com` and `../AgenticSystemCore-Patterns`, and skip a site that is
absent.

## Tests

```bash
python -m venv .venv && .venv/bin/pip install -e ".[test]"
.venv/bin/python -m pytest          # pyproject already passes -q; do not add another
```

The static checks, `ruff` and `mypy`, are installed and run as
[CONTRIBUTING.md](../CONTRIBUTING.md) shows.

## Continuous integration

`.github/workflows/test.yml` runs on every push and pull request, by hand
(`workflow_dispatch`) and as the test stage of a release; its header comment is the full
description. In short:

- `tests (Python 3.9)`, `tests (Python 3.13)` and `tests (Python 3.14)` run `pytest`
  under `coverage` (the report fails below the floor in `pyproject.toml`) with the engine
  and the main site checked out beside this repository, then the engine's persona-l and
  persona-o scenarios, and fail if either was skipped.
- `ruff and mypy (Python 3.13)` runs `ruff check --select E4,E7,E9,F src tests` and
  `mypy src/agentic_system_core tests` at exact pins.
- The engine is taken at `ENGINE_REF` (`main`) unless a manual run names another ref.
- The required checks on `main` are the 3.9 and 3.13 test legs and the ruff and mypy job;
  the 3.14 leg is not required, but a release waits for it.
- `.github/dependabot.yml` opens one monthly pull request for the pinned actions.

## Refreshing what is copied from the specification

The rule index (`src/agentic_system_core/data/spec-index.json`) is derived, never
typed. From this repository's root, with the engine beside it:

```bash
PYTHONPATH=src python3 -c "import json; from agentic_system_core import vectors; open('src/agentic_system_core/data/spec-index.json', 'w').write(json.dumps(vectors.spec_index_from('../agentic-system-core/spec'), sort_keys=True) + '\n')"
```

The vector copies under `tests/fixtures/vectors/` are byte-for-byte copies of the
engine's `tests/vectors/<area>/` for the seven areas; the suite fails when they drift,
and the fix is to copy the files again, never to edit them.

## Releases

A release is a tag `v<version>` (PEP 440 spelling, for example `v1.0.0`) pushed by
the maintainer. `.github/workflows/release.yml` checks that the tag is the version and
that the tagged commit is on `main`, runs the whole test lane (`test.yml`, the same
legs, scenarios and static checks as a pull request) with the engine checked out at its
package tag of the same version (a release candidate `X.Y.ZrcN` tests against `vX.Y.Z-rc.N`,
`1.0.0` and `1.0.0.post1` against `v1.0.0`, `1.0.1` against `v1.0.1`), builds once, and
publishes through PyPI trusted publishing: no token is stored in the repository, and
every action is pinned to a commit. The publish job runs in the GitHub environment
`pypi`, which has required reviewers, so the upload waits for an approval. The engine's package tag `v<version>` must therefore exist
before this package's tag is pushed; it exists for every engine release, while a
specification tag exists only when the specification moved. The version in `pyproject.toml` must be the engine's version in PEP 440
spelling; the engine's `tools/release` checks that the two agree.

Before tagging, write the new version in every place that carries it: `pyproject.toml`,
`__version__` and `SEMVER_VERSION` in `src/agentic_system_core/__init__.py`, the
"Version" section of the README, and a heading in `CHANGELOG.md`. `tests/test_cli.py`
also names the version and fails until it is updated. To check the build before tagging,
run what the release lane's build job runs:

```bash
.venv/bin/pip install build==1.6.1 twine==7.0.0
.venv/bin/python -m build
.venv/bin/python -m twine check --strict dist/*
```

`build/` and `dist/` are ignored by git.
