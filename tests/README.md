# `tests/` — the Python test suite

**Summary.** The tests of the package: each module on fixed data, the command line, the
seven vector areas over byte-identical copies of the engine's vectors, the equivalence
of the discovery-file checker with the engine's own, and the two CI workflows.
Deterministic: no clock, no network. The subprocesses are the engine's Node checker,
vector runner, JSON-LD writer and build in the equivalence and cross-check tests,
skipped with a message when Node or the engine checkout is absent (the checkout is
`../agentic-system-core`, or the one `AGSC_ENGINE_DIR` names), and the workflow steps that `test_ci_workflows.py` runs as
written on scratch input (Python, bash, and git on a scratch repository with fixed
dates).

**Read after:** the repository [README](../README.md), "Tests".

```bash
python -m venv .venv && .venv/bin/pip install -e ".[test]"
.venv/bin/python -m pytest
```

| Path | What it holds |
|---|---|
| `test_*.py` | one file per module or concern; `test_equivalence.py` compares the two checkers, `test_area_handlers.py` runs the vector areas, `test_graph_jsonld.py` compares the `graph.jsonld` writer with the engine's, `test_build_cross_check.py` checks the engine's build of `build-0020` to `build-0028`, `test_architecture.py` holds the package's shape (standard library only, one process starter), `test_ci_workflows.py` checks the test and release workflows |
| `fixtures/vectors/` | copies of the engine's vectors for the seven areas; a test fails if they drift from the engine beside this repository |
| `fixtures/wellknown/`, `fixtures/conformance/` | discovery documents and conformance inputs |
