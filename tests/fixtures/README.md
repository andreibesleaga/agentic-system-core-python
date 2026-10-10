# `tests/fixtures/` — the fixed inputs of the suite

**Summary.** The files the tests read. Nothing here is generated at test time, and the
sub-folders carry no README of their own, because a README inside them would become
part of the input the tests read or would make a copy differ from its original.

**Read after:** [tests/README.md](../README.md).

| Path | What it holds |
|---|---|
| `vectors/<area>/` | byte-identical copies of the engine's `tests/vectors/<area>/` for the seven areas this package runs (`build`, `discovery`, `frontmatter`, `graph`, `jcs`, `links`, `slug`); a test fails when they drift from the engine beside this repository, and the fix is to copy them again, never to edit them |
| `conformance/pending.json` | the pending list beside the vectors, in the engine's layout (`tests/conformance/pending.json`), which the runner reads by default; it is empty |
| `wellknown/<case>/` | one discovery-file case per folder: its `.well-known/knowledge-linkset` (or, for a document outside such a folder, `plain/knowledge-linkset`) and, where the case needs them, the targets it links to, such as `llms.txt`, `graph.jsonld`, `ledger.jsonl` and `legal/index.html` |
