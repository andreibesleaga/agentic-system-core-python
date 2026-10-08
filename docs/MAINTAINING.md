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

## The equivalence proof

`tests/test_equivalence.py` runs this package's discovery-file checker and the engine's
`tools/validate-wellknown` over the same documents, at every Level, with and without a
peer, and compares the status, the counts and each finding's position and code. The
cross-runner test runs the engine's vector runner over its live set and requires both
runners to agree on every vector of the seven areas. Both need the engine checked out
beside this repository at `../agentic-system-core` and Node 22.13 or later.

## Tests

```bash
python -m venv .venv && .venv/bin/pip install -e ".[test]"
.venv/bin/python -m pytest          # pyproject already passes -q; do not add another
```

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

A release is a tag `v<version>` (PEP 440 spelling, for example `v1.0.0rc7`) pushed by
the maintainer. `.github/workflows/release.yml` runs the tests on the oldest and newest
supported Python, builds once, and publishes through PyPI trusted publishing: no token
is stored in the repository, and every action is pinned to a commit. The version in
`pyproject.toml` must be the engine's version in PEP 440 spelling; the engine's
`tools/release` checks that the two agree.
