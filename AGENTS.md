# AGENTS.md — orientation for AI agents and coding assistants

This file is for an agent working in this repository. People may read it too; the human
front door is [README.md](README.md) and the maintainer guide is
[docs/MAINTAINING.md](docs/MAINTAINING.md).

## What this repository is

The Python package `agentic-system-core` (PyPI): two standalone checkers
(`validate-wellknown`, `validate-vectors`), a vector runner (`run-vectors`) for seven
areas, a small reading API, and an `agsc` command that hands every other verb to the Node
engine. Standard library only. It is not a second implementation of the engine, and it
must agree with the engine on every case they share. The specification, the vectors and
the engine live in the [engine repository](https://github.com/andreibesleaga/agentic-system-core).

| Path | What it holds |
|---|---|
| `src/agentic_system_core/` | the package; [its README](src/agentic_system_core/README.md) lists every module |
| `tests/` | the suite; `tests/fixtures/vectors/` are copies of the engine's vectors |
| `docs/` | [MAINTAINING.md](docs/MAINTAINING.md) (tests, CI, releases) and [ARCHITECTURE.md](docs/ARCHITECTURE.md) (diagrams) |
| `.github/workflows/` | `test.yml` (every push and pull request) and `release.yml` (a `v*` tag) |

## How to check your work

Run from the repository root, with the engine checked out beside it at
`../agentic-system-core` and Node 22.13 or later (without them the equivalence tests are
skipped):

```bash
python -m venv .venv && .venv/bin/pip install -e ".[test]"
.venv/bin/python -m pytest
.venv/bin/pip install ruff==0.16.9 mypy==2.3.1
.venv/bin/ruff check . && .venv/bin/mypy src/agentic_system_core tests
```

Tests are deterministic: fixed data, no clock, no network. Write the failing test first.

## What you may change, and what you may not

- **Do not edit** the vector copies under `tests/fixtures/vectors/`; copy them again from
  the engine. Do not type `src/agentic_system_core/data/spec-index.json`; derive it with
  the command in [docs/MAINTAINING.md](docs/MAINTAINING.md).
- **A rule, a vector or the engine is wrong:** propose the change in the engine
  repository; this package follows in its next release.
- **Do not add a runtime dependency.** `pyproject.toml` has `dependencies = []` and the
  package keeps it so.
- **Keep the README free of relative links:** it is the PyPI page, and a test checks it.
- **Keep the version in step:** the places that carry it are listed in
  [docs/MAINTAINING.md](docs/MAINTAINING.md), "Releases".
- **Never** commit, tag, push or publish on your own; a person does that. A release is a
  tag the maintainer pushes.
- Cite rules by id (`AGSC-nn-nn`) and error codes as the specification registers them.
