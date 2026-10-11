# Changelog

All notable changes to the Python package `agentic-system-core`: the two standalone
checkers, the reading API and the `agsc` command. The specification and the Node engine
keep their own change log, in the engine repository's `CHANGELOG.md`; this package
follows the specification version of the same number.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Versions use
PEP 440 spelling: a release is spelled as in SemVer (`1.0.0`), a release candidate
differently (SemVer's `1.0.0-rc.7` is `1.0.0rc7` here).

## [Unreleased]

## [1.0.0] - 2026-10-14

### Upgrading from 1.0.0rc7

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

### Changed

- The release lane runs the whole test lane of a pull request, with the engine checked out
  at the specification tag of the package version, and refuses a tag whose commit is not on
  `main`. A Python 3.14 leg runs on every pull request.
- The per-response deadline of `validate-wellknown` is injectable for tests; the default
  stays 10 seconds.
- The usage text no longer shows the directory of `validate-vectors` and `run-vectors` as
  optional.
- Dependabot keeps the pinned actions up to date.

### Fixed

- The main-site test looked for the site's discovery document in a removed folder and
  always skipped; it runs again when the site is checked out beside the package.
