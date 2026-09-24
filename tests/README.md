# `tests/` — the Python test suite

**Summary.** The tests of the package: each module on fixed data, the command line, the
seven vector areas over byte-identical copies of the engine's vectors, and the
equivalence of the discovery-file checker with the engine's own. Deterministic: no
clock, no network; the only subprocess is the Node checker in the equivalence test,
which is skipped with a message when Node or the engine checkout is absent.

**Read after:** the repository [README](../README.md), "Tests".

```bash
python -m venv .venv && .venv/bin/pip install -e ".[test]"
.venv/bin/python -m pytest
```

| Path | What it holds |
|---|---|
| `test_*.py` | one file per module or concern; `test_equivalence.py` compares the two checkers, `test_area_handlers.py` runs the vector areas |
| `fixtures/vectors/` | copies of the engine's vectors for the seven areas; a test fails if they drift from the engine beside this repository |
| `fixtures/wellknown/`, `fixtures/conformance/` | discovery documents and conformance inputs |
