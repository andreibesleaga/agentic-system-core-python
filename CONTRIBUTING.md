# Contributing

This package is the Python side of AgenticSystemCore: two standalone checkers, a vector
runner and a reading API that must agree with the Node engine on every case they
share. A change here is one of two kinds.

- **A rule, a conformance vector or the engine is wrong.** The specification, the
  vectors and the engine live in the
  [engine repository](https://github.com/andreibesleaga/agentic-system-core). Propose
  the change there, as its
  [CONTRIBUTING.md](https://github.com/andreibesleaga/agentic-system-core/blob/main/CONTRIBUTING.md)
  describes; this package follows in its next release.
- **This package is wrong, or could be better.** A normal pull request against this
  repository. For anything larger than a small fix, describe the problem in an issue
  first.

## Before you open a pull request

```bash
python -m venv .venv && .venv/bin/pip install -e ".[test]"
.venv/bin/python -m pytest       # with the engine checked out beside this repository
.venv/bin/pip install ruff==0.16.9 mypy==2.3.1
.venv/bin/ruff check . && .venv/bin/mypy src/agentic_system_core tests
```

All of these must pass, and the test comes first: write the failing test, then the
smallest change that makes it pass. Every test is deterministic: no clock, no network.
The vector copies under `tests/fixtures/vectors/` are never edited; they are copied
again from the engine. [docs/MAINTAINING.md](docs/MAINTAINING.md) explains the
equivalence tests and what is copied from the specification.

## Signing off

An outside contribution, a commit from anyone other than the maintainer, signs off
under the contributor agreement `CA-v1`, the file
[`CONTRIBUTOR-AGREEMENT`](https://github.com/andreibesleaga/agentic-system-core/blob/main/CONTRIBUTOR-AGREEMENT)
in the engine repository. Read it before your first commit. Each commit message ends
with a line of this shape:

```
Signed-off-by: Ada Lovelace <ada@example.org> (CA-v1)
```

`git commit -s` writes the first part of that line; add ` (CA-v1)` at its end. The
maintainer's own commits are exempt. The engine's CONTRIBUTING.md, "Signing off",
says what the agreement means. The code here is Apache-2.0 (`LICENSE`).

Your name, the address you commit under and your sign-off become part of this
repository's public history. If you would rather not publish an address, GitHub's
`users.noreply.github.com` address works.

## Conduct and security

The [code of conduct](CODE_OF_CONDUCT.md) applies everywhere the project is
represented. A security problem is never an issue or a pull request: report it
privately, as [SECURITY.md](SECURITY.md) says.
