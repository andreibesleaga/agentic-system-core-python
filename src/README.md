# `src/` — the source folder

**Summary.** The source layout of the package: `src/` holds the one importable package,
so the tests always run against the installed package and never against a folder that
happens to be on the import path.

**Read after:** the repository [README](../README.md). **Read next:**
[agentic_system_core/README.md](agentic_system_core/README.md).

| Path | What it holds |
|---|---|
| `agentic_system_core/` | the package: the two checkers, the vector runner, the reading API and the `agsc` command; its README lists every module, the `areas/` handlers and the `data/` index |

An `*.egg-info/` folder beside it is written by `pip install -e .`; it is build output,
ignored by git, and never edited.
