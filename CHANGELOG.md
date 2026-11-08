# Changelog

All notable changes to the Python package `agentic-system-core`: the two standalone
checkers, the reading API and the `agsc` command. The specification and the Node engine
keep their own change log, in the engine repository's `CHANGELOG.md`; this package
carries the engine package's version number and names the specification version it
implements (`SPEC_VERSION`; README, "Version").

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Versions use
PEP 440 spelling: a release is spelled as in SemVer (`1.0.0`), a release candidate
differently (SemVer's `1.1.0-rc.1` is `1.1.0rc1` here).

## [Unreleased]

- Docs: README, `docs/MAINTAINING.md` corrected and extended (tests, CI jobs, release steps); `AGENTS.md` and `docs/ARCHITECTURE.md` added.
- Added: `graph.to_jsonld` and `graph.restrict_to` write `graph.jsonld` and the per-item `/pages/<slug>.jsonld` files (AGSC-05-09, AGSC-06-02) from the same triples as `graph.nq`, as the engine's `src/knowledge/jsonld.js` does; `run-vectors` now runs `graph-0028` (on the shipped copies: 79 pass, 13 not run).
- Added: `data/context.jsonld`, the published context (AGSC-06-32) as the engine's `tools/gen-ns` derives it, read by `context.published()`; the suite fails when it drifts from the engine's.
- Added: `areas/build_tree.py` checks the files a whole build wrote against `build-0020` to `build-0028` (AGSC-00-05, AGSC-01-19, AGSC-01-20, AGSC-05-07, AGSC-06-01, AGSC-06-18, AGSC-07-19, AGSC-07-20), member for member as the engine's handler does; the suite runs it over the engine's build of each case. `run-vectors` still reports the nine as not run.
- Changed: the source distribution ships `SECURITY.md` and `data/context.jsonld`.
- Tests: the environment variable `AGSC_ENGINE_DIR` names the engine checkout the suite compares with; unset, it is `../agentic-system-core` as before.
- Tests: two fitness functions: the package imports only the standard library, and only `cli.py` starts a process.
- Changed: the vector copies under `tests/fixtures/vectors/` are the 1.1 engine's seven areas (151 files; `disc-0013`, `disc-0014`, `disc-0019` and `build-0024` are withdrawn there), and the drift test also fails when a file is missing or extra (AGSC-09-04; EARS row PRD-010).
- Changed: `data/spec-index.json` is regenerated from the 1.1 specification: 385 rules and 105 registered codes, among them AGSC-E005, AGSC-E313 to E317, AGSC-E417 to E423 and AGSC-E512 (AGSC-09-15; PRD-010); the declared version stays the one constant `SPEC_VERSION`.
- Changed: `HIGHER_LEVEL_CASES` is the AGSC-10-15 table as amended for 1.1.0 (72 cases; PRD-010).
- Added: `relations.py` and `data/relations.json`, the relation table of AGSC-03-01 as the engine's `src/knowledge/relations.js` holds it; `links.py` and `graph.py` read their key lists, inverses and RDF properties from it instead of their own copies (AGSC-03-01, AGSC-05-16; PRD-002).
- Added: `links.link_warnings`, the warnings AGSC-E313 (a self-link, AGSC-03-23), AGSC-E314 (two relations a pair cannot both hold, AGSC-03-24), AGSC-E315 (a target of an unexpected kind, AGSC-03-25) and AGSC-E316 (superseding a stable item, AGSC-03-26); `run-vectors` passes `links-0010` to `links-0017` (PRD-003).
- Added: `derive.readings`, the readings of the Link graph with their reasons (AGSC-05-33, `graph-0029`), as the engine's `src/knowledge/derive.js` gives them (PRD-023; the 1.1 EARS row comes with the engine's B12 requirements pass).
- Added: `questions.answer`, the ten questions of AGSC-05-34 (`graph-0030` to `graph-0039`), as the engine's `src/knowledge/questions.js` answers them (PRD-023; 1.1 EARS row as above).
- Added: `skos.skos_view` and `skos.scheme_record`, the SKOS view `export --skos` writes, byte for byte (AGSC-05-36, `graph-0040`; PRD-060); `rdf.turtle` takes the prefix block it writes.
- Added: a frontmatter nested deeper than 64 levels is the warning AGSC-E105 and is still read (AGSC-02-02 as amended for 1.1, `fm-0021`, `fm-0026`; PRD-003); `yamlsubset.depth` counts block nesting.
- Changed: `/llms.txt` and `/llms-full.txt` follow the 1.1 layout: the blockquote straight after the H1, then the provenance comment, the backslash, `[`, `]` and `(` of a link line escaped, and no `bundle_version` line on a restricted node (AGSC-06-13a as amended for 1.1, AGSC-11-20; `disc-0024`, `disc-0025`, `disc-0034`; PRD-060).
- Added: `site.security_txt(..., policy=)` writes the declared disclosure page as `Policy` (AGSC-06-36 as amended for 1.1, `build-0035`; PRD-047), and `site.now_line(..., visibility=)` gives a restricted node's line without the content version and the fingerprint (AGSC-06-22 with AGSC-11-20, `build-0036`; PRD-010).
- Changed: `run-vectors` reports as not run, each with its reason, the cases it cannot run: `build-0031` and `build-0032` (it writes no HTML), `build-0037` (it has no chunk writer), and the domain-layer cases `fm-0022` to `fm-0025`, `fm-0027`, `graph-0042`, `graph-0044` to `graph-0046`, `links-0018`, `links-0019` ("domain layer: engine only in 1.1"), 31 by name with the whole-build cases (AGSC-09-02; PRD-010).
- Changed: `bundle-0018` and `bundle-0019` (the `.diagram` grammar, AGSC-01-42) are reported not run with the reason "needs the diagram compiler (Level 3)"; the `bundle` area keeps its own reason (PRD-010).
- Tests: `test_link_parity.py` compares the Link warnings, the readings and the ten answers with the engine's on 120 seeded generated graphs; a fitness function keeps one source for the relation table.

## [1.0.1] - 2026-10-21

A patch of the package. Specification `1.0.0` is unchanged (README, "Version").

### Fixed

- The discovery-document checker now asks a restricted node for everything AGSC-11-20
  already requires of it, as the engine's `tools/validate-wellknown` does, with the same
  codes and words: the `…/rel#access` link carries `agsc-access` `credential` (missing is
  `AGSC-E202`, another value `AGSC-E210`), and `agsc-generated-at` and
  `agsc-spec-version` are present at Levels 0 and 1 (missing is `AGSC-E202`).
- `discovery.linkset` writes `agsc-generated-at` and `agsc-spec-version` on a restricted
  node at every Level, as AGSC-11-20 requires. A public node's output is unchanged.
- `agsc --version` printed the package version where the specification version
  belongs; it now prints `agsc 1.0.1 (Python package; specification 1.0.0)`.

### Changed

- The release lane tests the package against the engine's package tag (`v<version>`,
  which exists for every engine release) instead of the engine's specification tag,
  which a package-only patch does not create.

## [1.0.0] - 2026-10-14

### Changes in 1.0.0

The package follows specification `1.0.0`. `pip install agentic-system-core` installs it
without `--pre`, and `agsc --version` prints `agsc 1.0.0 (Python package; specification
1.0.0)`. The trove classifier is "Development Status :: 5 - Production/Stable". Python 3.9
or newer is still supported; every release is tested on 3.9, 3.13 and 3.14.

**What the checker may now report** (each was already outside a rule of the
specification):

- `validate-wellknown`: a discovery document served as anything but
  `application/linkset+json` fails, whether the profile is carried by the `profile`
  parameter or by a `Link: …; rel="profile"` header (AGSC-06-07, AGSC-09-93).
- `validate-wellknown`: a restricted node must carry exactly one access link: none is
  `AGSC-E202`, more than one is one `AGSC-E210` (AGSC-11-20). The check applies at every
  Level.
- The actor pattern admits `process:<id>/<version>`, the form of the ledger's trailing
  build entry (AGSC-02-09).

### Added

- The vector copies of the seven areas this package runs follow the engine's new cases,
  among them `slug-0007`, the new build, front-matter and links cases, and `disc-0022`.
- The links area reports orphan items.
- `SECURITY.md`, `CONTRIBUTING.md` and `CODE_OF_CONDUCT.md`.
- The change log is linked from the package page on PyPI (a `Changelog` project link and a
  link in the README) and ships in the source distribution.

### Changed

- The release lane runs the whole test lane of a pull request, with the engine checked out
  at the specification tag of the package version, and refuses a tag whose commit is not on
  `main`. A Python 3.14 leg runs on every pull request.
- The per-response deadline of `validate-wellknown` is injectable for tests; the default
  stays 10 seconds.
- The usage text no longer shows the directory of `validate-vectors` and `run-vectors` as
  optional.
- Dependabot keeps the pinned actions up to date.
- CI: the engine's restricted-publisher scenario, in which both checkers flag a restricted
  node without an access link, runs on every leg with this package beside the engine, next
  to the port implementer's scenarios; a skipped scenario fails the leg.
- The cross-runner proof reads the specification version of a release, not only of a
  candidate, and two area handlers assert what the engine's assert.

### Fixed

- The main-site test looked for the site's discovery document in a removed folder and
  always skipped; it runs again when the site is checked out beside the package.
- The JSON-LD context address that `context.compact()` writes names the vocabulary version
  `1.0.0` (`https://w3id.org/agentic-system-core/ns/1.0.0/context.jsonld`), the address the
  engine derives from the vocabulary's `owl:versionIRI` (AGSC-05-09, AGSC-05-25); it named
  the pre-release `/ns/1.0.0-draft.1/`. A test compares it with the engine's vocabulary
  when the engine is beside this repository.
- A verb outside the sixteen of the specification is refused with `AGSC-E001` when no
  engine is installed (it was answered with the install sentence alone).
- A discovery document nested too deep for the reader is reported as `AGSC-E201`, as the
  Node checker reports it (it was a traceback).
