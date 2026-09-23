"""The conformance areas this package runs natively, and why it runs no others.

A Python consumer with no Node engine can run the areas whose expected output
follows from the vector's own input by a rule alone.  Two areas are like that:

* ``jcs`` — canonical JSON.  The case is a value and the expected bytes; the
  rule is RFC 8785 plus the NFC-before-sort rule, and nothing else is needed.
* ``slug`` — the slug grammar and uniqueness.  The case is a list of candidate
  strings and the expected verdicts.

Every other area needs something this package does not carry: a Bundle build,
a YAML frontmatter reader with the three JSON Schemas, a CommonMark parser, an
RDF writer, or the engine's own builders.  Each one is named below with its
reason, and the runner reports it as not run — never as a silent pass and never
as a skip that a reader could mistake for one.
"""

from .jcs_area import run as _run_jcs
from .slug_area import run as _run_slug

#: area name -> callable(vector) -> {"status": "pass"|"fail", "detail": str}
AREA_RUNNERS = {
    "jcs": _run_jcs,
    "slug": _run_slug,
}

#: area name -> why this package does not run it.
NOT_RUN_REASONS = {
    "adapters": "needs the engine's adapters; not implemented by this package",
    "adopt": "needs the Markdown and frontmatter reader of a full build",
    "boards": "needs the live-board writer of a full build",
    "boundary": "needs the federation, visibility and surface modules of the engine",
    "build": "needs a full site build",
    "bundle": "needs the Bundle loader and the three JSON Schemas",
    "channels": "needs the governance channels of the engine",
    "chunks": "needs the chunk writer of a full build",
    "cli": "needs the engine's command-line surface",
    "compose": "needs the composition closure of the engine",
    "conform": "needs the engine's conformance report builder",
    "discovery": "needs the engine's discovery, index and llms.txt writers",
    "export": "needs the export writers of a full build",
    "frontmatter": "needs a YAML reader and the three JSON Schemas",
    "graph": "needs the RDF writers of a full build",
    "harness": "needs the Harness emitters of the engine",
    "import": "needs the import readers of the engine",
    "ledger": "needs the ledger writer of the engine",
    "links": "needs a CommonMark parser for the body and anchor rules",
    "lint": "needs the lint rules of a full build",
    "prov": "needs the provenance and gate rules of the engine",
    "run": "needs the runnable Harness surface of the engine",
    "skills": "needs the skills writer of a full build",
}

__all__ = ["AREA_RUNNERS", "NOT_RUN_REASONS"]
