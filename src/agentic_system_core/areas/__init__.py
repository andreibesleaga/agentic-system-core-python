"""The conformance areas this package runs natively, and why it runs no others.

Seven areas run with nothing but the standard library, each derived from the
rule text of the specification:

* ``frontmatter`` — the closed YAML subset, failsafe scalars, the item checks
  of spec/02 and adoption.
* ``slug`` — the slug grammar and uniqueness.
* ``jcs`` — RFC 8785 canonical JSON, NFC before sorting.
* ``links`` — Link keys, inverses, cycles, the cluster tree, anchors and
  inline-link resolution over a small CommonMark scanner.
* ``graph`` — the RDF dataset, canonical N-Quads, the stable-Turtle profile and
  the JSON-LD context.
* ``build`` — the search index and tokenizer, fragments, headers,
  ``security.txt`` and the content version.
* ``discovery`` — ``/llms.txt``, ``/llms-full.txt``, reachability, sitemap and
  robots facts, and the link set.

Every other area needs something this package does not carry: a Bundle build,
the engine's composition, governance, ledger or boundary modules, or its
command-line surface.  Each one is named below with its reason, and the runner
reports it as not run — never as a silent pass and never as a skip that a
reader could mistake for one.
"""

from .build_area import run as _run_build
from .discovery_area import run as _run_discovery
from .frontmatter_area import run as _run_frontmatter
from .graph_area import run as _run_graph
from .jcs_area import run as _run_jcs
from .links_area import run as _run_links
from .slug_area import run as _run_slug

#: area name -> callable(vector) -> {"status": "pass"|"fail", "detail": str}
AREA_RUNNERS = {
    "build": _run_build,
    "discovery": _run_discovery,
    "frontmatter": _run_frontmatter,
    "graph": _run_graph,
    "jcs": _run_jcs,
    "links": _run_links,
    "slug": _run_slug,
}

#: area name -> why this package does not run it.
NOT_RUN_REASONS = {
    "adapters": "needs the engine's adapters; not implemented by this package",
    "adopt": "needs the init verb and a Bundle on disk",
    "boards": "needs the live-board writer of a full build",
    "boundary": "needs the federation, visibility and surface modules of the engine",
    "bundle": "needs the Bundle loader and the configuration schema",
    "channels": "needs the governance channels of the engine",
    "chunks": "needs the chunk writer of a full build",
    "cli": "needs the engine's command-line surface",
    "compose": "needs the composition closure of the engine",
    "conform": "needs the engine's conformance report builder",
    "export": "needs the export writers of a full build",
    "harness": "needs the Harness emitters of the engine",
    "import": "needs the import readers of the engine",
    "ledger": "needs the ledger writer of the engine",
    "lint": "needs the lint rules of a full build",
    "prov": "needs the provenance and gate rules of the engine",
    "run": "needs the runnable Harness surface of the engine",
    "skills": "needs the skills writer of a full build",
}

__all__ = ["AREA_RUNNERS", "NOT_RUN_REASONS"]
