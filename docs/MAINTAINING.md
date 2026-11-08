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

Inside the seven areas, a case is reported as not run, with its reason, when it needs
a whole build (the query page of `build-0029` and `build-0030` among them), a writer
this package does not carry (HTML pages, the chunk files, the closure file of
`export --closure`), or the domain layer, which only the engine checks in 1.1; the
reason of the last is `domain layer: engine only in 1.1`. The web connection of a node
(the Signposting links and the Dataset block of `/`, the two catalogue files, the A2A
agent card) is written here as data and bytes, though no page is, so its cases
(`disc-0026` to `disc-0031`) run. The cases and reasons are in
`src/agentic_system_core/areas/__init__.py` (`CASES_NOT_RUN`) and the handlers, and
the README lists them by name; `tests/test_readme_counts.py` keeps the two in step.

## The equivalence proof

`tests/test_equivalence.py` runs this package's discovery-file checker and the engine's
`tools/validate-wellknown` over the same documents, at every Level, with and without a
peer, and compares the status, the counts and each finding's position and code. The
documents are every case under `tests/fixtures/wellknown/`, the built files of the two
sites when they are here, and two nodes the engine builds for the run with
`SOURCE_DATE_EPOCH=1767225600`: its own `tests/fixtures/minimal` and, when it is checked
out beside this repository, `../agsc-demo-node` (copied with its git history, so the
build writes the ledger and the chunk and ledger facts of AGSC-06-44 that both checkers
recompute). The fixture cases of the 1.1 checks (`chunks-*`, `ledger-length-wrong`,
`card-*`) are the documents and files of vector disc-0033, and variants of them with one
fact changed; the checks of a URL alone (the `Link` header of `/`, the response headers,
the request budget) are stated by `tests/test_wellknown_facts.py` and
`tests/test_wellknown.py` with an injected fetcher, because the proof opens no
connection. The
cross-runner test (`tests/test_vector_equivalence.py`) runs the engine's vector runner
over its live set and requires both runners to agree on every vector of the seven areas.
Both need the engine checked out beside this repository at `../agentic-system-core` and
Node 22.13 or later; without them they are skipped with a message. The tests that read
the built discovery files of the two sites use the checkouts beside this repository, at
`../AgenticSystemCore.com` and `../AgenticSystemCore-Patterns`, and skip a site that is
absent. `../AgenticSystemCore-Patterns` is the maintainer's private working copy of the
demo node (its built `www/` is committed there; the public `agsc-demo-node` does not
commit `www/`), so CI checks out only the main site and the patterns node's discovery
file is read on the maintainer's machine.

To compare with another engine checkout (a second worktree of a release branch, say),
set `AGSC_ENGINE_DIR` to its path; unset or empty, the suite uses
`../agentic-system-core`. Every test that runs the engine reads it from there
(`tests/conftest.py`, `engine_dir`):

```bash
AGSC_ENGINE_DIR=../agentic-system-core-1.1 .venv/bin/python -m pytest
```

On the `next-1.1` branch the vector copies, the rule index and the relation table are
the 1.1 engine's, so the suite agrees with a 1.1 engine checkout; run it with
`AGSC_ENGINE_DIR` naming one. Against a 1.0 checkout the drift tests and the
equivalence proof fail, as they should: they compare with another version.

`tests/test_link_parity.py` is a property test against the same checkout: a seeded
generator (the same 120 item sets on every run) draws Link graphs, and the engine's
`links.resolve`, `derive.readings` and `questions.answer` must give what this package's
`links.link_warnings`, `derive.readings` and `questions.answer` give.

Two more proofs need the same checkout and Node, and are skipped with a message without
them. `tests/test_graph_jsonld.py` checks that the shipped context is the one the
engine derives and that this package's `graph.jsonld` and per-item files equal the
engine's for every graph vector that states a dataset. `tests/test_build_cross_check.py`
has the engine build the Bundle of each of `build-0020` to `build-0028`, the way the
engine's own handler does, and `agentic_system_core/areas/build_tree.py` checks every
expectation of the vector against the files written. `run-vectors` still reports those
nine cases as not run, because this package writes no site.

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
ENGINE="${AGSC_ENGINE_DIR:-../agentic-system-core}"
PYTHONPATH=src python3 -c "import json, sys; from agentic_system_core import vectors; open('src/agentic_system_core/data/spec-index.json', 'w').write(json.dumps(vectors.spec_index_from(sys.argv[1] + '/spec'), sort_keys=True) + '\n')" "$ENGINE"
```

The higher-Level case table of AGSC-10-15 (`HIGHER_LEVEL_CASES` in
`src/agentic_system_core/vectors.py`) is the table of `spec/10-implementation-profiles.md`;
`tests/test_vectors.py` reads the specification's table and fails when the two differ.

The relation table of AGSC-03-01 (`src/agentic_system_core/data/relations.json`: the
fourteen Link keys, their inverses, RDF properties, self-link readings and Expected
target kinds) is the engine's `src/knowledge/relations.js`, written out by Node, never
typed. `links.py`, `graph.py`, `derive.py` and `questions.py` read it through
`relations.py`; the suite fails when it drifts, and a fitness test fails when a module
spells out a computed inverse name instead of reading the table:

```bash
ENGINE="${AGSC_ENGINE_DIR:-../agentic-system-core}"
node -e "const r = require(require('node:path').resolve(process.argv[1], 'src/knowledge/relations.js')); process.stdout.write(JSON.stringify({ relations: r.RELATIONS }, null, 2) + '\n');" "$ENGINE" > src/agentic_system_core/data/relations.json
```

The vector copies under `tests/fixtures/vectors/` are byte-for-byte copies of the
engine's `tests/vectors/<area>/` for the seven areas; the suite fails when they drift,
and the fix is to copy the files again, never to edit them:

```bash
ENGINE="${AGSC_ENGINE_DIR:-../agentic-system-core}"
for area in build discovery frontmatter graph jcs links slug; do
  rm -r "tests/fixtures/vectors/$area" && cp -R "$ENGINE/tests/vectors/$area" tests/fixtures/vectors/
done
```

The published JSON-LD context (`src/agentic_system_core/data/context.jsonld`, the bytes
a node serves at `/ns/context.jsonld`) is the engine's `tools/gen-ns` output, never
typed; `graph.jsonld` is compacted with it, and the suite fails when it drifts:

```bash
ENGINE="${AGSC_ENGINE_DIR:-../agentic-system-core}"
out="$(mktemp -d)" && node "$ENGINE/tools/gen-ns" --quiet --out "$out" \
  && cp "$out/context.jsonld" src/agentic_system_core/data/context.jsonld && rm -r "$out"
```

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

To roll back a bad release, yank that version on PyPI (project page, "Manage",
the release, "Options", "Yank"): pip then stops choosing it, but anyone who pins it still gets it. Never
delete it. Fix the cause and release the next patch version through the same lane
(for example `1.0.2` after a bad `1.0.1`), and add a line to `CHANGELOG.md` under the
new version that names the yanked one and why.

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
