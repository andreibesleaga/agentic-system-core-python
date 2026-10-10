<!--
Thank you. CONTRIBUTING.md says how a change is proposed; a change to a rule starts in the engine repository.
-->

## What this changes and why

## How it was checked

- [ ] `python -m pytest` passes with the engine beside this repository, and the test came first
- [ ] `ruff check .` and `mypy src/agentic_system_core tests` are clean

## Sign-off (outside contributions)

An outside contribution signs off every commit under the contributor agreement (`CONTRIBUTOR-AGREEMENT` in the engine repository), with a last line of this shape:

```
Signed-off-by: Your Name <you@example.org> (CA-v1)
```

`git commit -s` writes the first part of that line; add ` (CA-v1)` at its end. The maintainer's own commits are exempt.
