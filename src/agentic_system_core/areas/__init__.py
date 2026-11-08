"""The conformance areas this package runs natively, and why it runs no others.

Seven areas run with nothing but the standard library, each derived from the
rule text of the specification:

* ``frontmatter`` — the closed YAML subset, failsafe scalars, the item checks
  of spec/02, the 64-level nesting bound and adoption.
* ``slug`` — the slug grammar and uniqueness.
* ``jcs`` — RFC 8785 canonical JSON, NFC before sorting.
* ``links`` — Link keys, inverses, cycles, the cluster tree, the four Link
  warnings of AGSC-03-23 to 03-26, anchors and inline-link resolution over a small
  CommonMark scanner.
* ``graph`` — the RDF dataset, canonical N-Quads, the stable-Turtle profile,
  ``graph.jsonld`` with the per-item files, the JSON-LD context, the readings and
  the ten questions of the Link graph, and the SKOS view.
* ``build`` — the search index and tokenizer, fragments, headers,
  ``security.txt``, the content version and the ``/now/`` line.
* ``discovery`` — ``/llms.txt``, ``/llms-full.txt``, reachability, sitemap and
  robots facts, and the link set.

``build_tree`` is not an area runner: it checks the nine ``build`` cases that need a
whole build (build-0020 to build-0028) against the files another writer built.

Every other area needs something this package does not carry: a Bundle build,
the engine's composition, governance, ledger or boundary modules, or its
command-line surface.  Each one is named below with its reason, and the runner
reports it as not run — never as a silent pass and never as a skip that a
reader could mistake for one.  Inside the seven areas, a case whose input is a
whole Bundle is reported not run by its handler; ``CASES_NOT_RUN`` names the other
cases this package cannot run (a writer it does not carry, or the domain layer,
which the engine alone checks in 1.1), each with its reason, and the few cases of
an area not run here whose reason is narrower than the area's.
"""

from .build_area import run as _run_build
from .discovery_area import run as _run_discovery
from .frontmatter_area import run as _run_frontmatter
from .graph_area import run as _run_graph
from .jcs_area import run as _run_jcs
from .links_area import run as _run_links
from .slug_area import run as _run_slug

#: The reason every domain-layer case gives (site vocabulary, domain keys, warrants,
#: contexts, crosswalks, SHACL): the engine checks the domain layer, this package not yet.
DOMAIN_LAYER = "domain layer: engine only in 1.1"
_NO_HTML = "needs the HTML page writer of a full build (AGSC-06-38); this package writes no HTML"
_QUERY_PAGE = "needs the engine's build and the query page (Level 3)"

#: vector id -> why this package does not run it: cases of the seven areas whose input
#: shape the handler could read but whose subject is a writer or a layer this package
#: does not carry, and cases of an area it does not run whose reason is narrower than
#: the area's own (the diagram compiler of bundle-0018 and bundle-0019).
CASES_NOT_RUN = {
    "bundle-0018": "needs the diagram compiler (Level 3)",
    "bundle-0019": "needs the diagram compiler (Level 3)",
    "build-0029": _QUERY_PAGE,
    "build-0030": _QUERY_PAGE,
    "build-0031": _NO_HTML,
    "build-0032": _NO_HTML,
    "build-0037": "needs the chunk writer of a full build (/chunks.jsonl, /chunks-index.toon)",
    "disc-0032": ("needs a whole build of the minimal fixture: it reads every file the engine "
                  "writes, the HTML home page among them, for the PROV-O terms (AGSC-06-41); "
                  "this package writes no HTML"),
    "fm-0022": DOMAIN_LAYER,
    "fm-0023": DOMAIN_LAYER,
    "fm-0024": DOMAIN_LAYER,
    "fm-0025": DOMAIN_LAYER,
    "fm-0027": DOMAIN_LAYER,
    "graph-0041": ("needs export --closure: a Turtle reader of the engine's ontology/agsc.ttl "
                   "and the OWL 2 RL rules of AGSC-05-37 (the engine runs them with the n3 "
                   "Reasoner); this package carries no export verb and no reasoner"),
    "graph-0042": DOMAIN_LAYER,
    "graph-0044": DOMAIN_LAYER,
    "graph-0045": DOMAIN_LAYER,
    "graph-0046": DOMAIN_LAYER,
    "links-0018": DOMAIN_LAYER,
    "links-0019": DOMAIN_LAYER,
}


def _unless_not_run(runner):
    """The area runner, behind the ``CASES_NOT_RUN`` table."""
    def run(vector):
        reason = CASES_NOT_RUN.get(vector.get("id"))
        if reason is not None:
            return {"status": "not-run", "detail": reason}
        return runner(vector)
    return run


#: area name -> callable(vector) -> {"status": "pass"|"fail"|"not-run", "detail": str}
AREA_RUNNERS = dict((name, _unless_not_run(runner)) for name, runner in (
    ("build", _run_build),
    ("discovery", _run_discovery),
    ("frontmatter", _run_frontmatter),
    ("graph", _run_graph),
    ("jcs", _run_jcs),
    ("links", _run_links),
    ("slug", _run_slug),
))

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

__all__ = ["AREA_RUNNERS", "CASES_NOT_RUN", "DOMAIN_LAYER", "NOT_RUN_REASONS"]
