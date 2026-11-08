"""The ``graph.jsonld`` writer and the per-item files (AGSC-05-09, AGSC-05-06, AGSC-06-02).

Three proofs. On fixed data, each compaction form of AGSC-05-31 the writer can meet.
Against the engine, when it is beside this repository with Node: the published context
this package ships is the bytes the engine's ``tools/gen-ns`` derives from
``ontology/agsc.ttl``, and for every graph vector that states a dataset the writer's
documents are the engine's ``toJsonLd`` and ``restrictTo``, after JCS. No network.
"""

import json
import subprocess

import pytest

from agentic_system_core import context, graph
from agentic_system_core.areas import CASES_NOT_RUN
from agentic_system_core.jcs import canonicalize
from agentic_system_core.rdf import ASC, DCTERMS, IRI, RDFS, SKOS, XSD_DATETIME, Literal
from conftest import ENGINE, VECTORS, engine_available

BASE = "https://a.example/"
ITEM = {"slug": "alpha", "type": "concept", "title": "Alpha", "lang": "en"}


def _node(document, iri):
    return next(one for one in document["@graph"] if one["@id"] == iri)


# --- on fixed data --------------------------------------------------------------

def test_the_published_context_is_one_jcs_object_with_one_lf():
    raw = context.published_bytes()
    assert raw.endswith(b"\n") and not raw.endswith(b"\n\n")
    assert canonicalize(json.loads(raw)) + "\n" == raw.decode("utf-8")
    assert context.published()["@context"]["@version"] == 1.1


def test_one_value_is_bare_and_several_are_sorted():
    items = [dict(ITEM, aliases=["Zeta", "Beta"]), {"slug": "beta", "type": "concept",
                                                   "title": "Beta", "related": ["alpha"]}]
    node = _node(graph.to_jsonld(items, BASE), BASE + "concepts/alpha/")
    assert node["@type"] == "Concept"
    assert node["inScheme"] == BASE
    assert node["related"] == BASE + "concepts/beta/"
    assert node["altLabel"] == [{"@language": "en", "@value": "Beta"},
                                {"@language": "en", "@value": "Zeta"}]


def test_a_document_without_a_context_url_names_none():
    document = graph.to_jsonld([ITEM], BASE)
    assert "@context" not in document
    named = graph.to_jsonld([ITEM], BASE, context_url=context.CONTEXT_URL)
    assert named["@context"] == context.CONTEXT_URL


def test_a_typed_literal_under_its_own_datatype_is_its_lexical_form():
    node = _node(graph.to_jsonld([dict(ITEM, date="2026-01-01")], BASE), BASE + "concepts/alpha/")
    assert node["created"] == "2026-01-01T00:00:00Z"


def test_each_compaction_form_without_a_term():
    table = graph.compaction_table(context.published())
    assert graph.compact_name(ASC + "warrant", table) == "asc:warrant"
    assert graph.compact_name("https://site.example/ns#thing", table) == "https://site.example/ns#thing"
    assert graph.compact_name(SKOS + "prefLabel", table) == "prefLabel"
    term = table["terms"][SKOS + "related"]
    assert graph.json_value(IRI(RDFS + "Class"), term, table) == "rdfs:Class"
    assert graph.json_value(IRI(BASE), None, table) == {"@id": BASE}
    assert graph.json_value(Literal("x", datatype=XSD_DATETIME), term, table) == \
        {"@type": "xsd:dateTime", "@value": "x"}
    untyped = table["terms"][DCTERMS + "title"]
    assert graph.json_value(Literal("x", datatype=XSD_DATETIME), untyped, table) == \
        {"@type": "xsd:dateTime", "@value": "x"}
    assert graph.json_value(Literal("x"), untyped, table) == "x"
    assert graph.json_value(Literal("x", lang="en"), untyped, table) == \
        {"@language": "en", "@value": "x"}


def test_a_per_item_file_takes_each_node_from_the_whole_graph():
    items = [ITEM, {"slug": "beta", "type": "concept", "title": "Beta", "requires": ["alpha"]}]
    whole = graph.to_jsonld(items, BASE)
    single = graph.to_jsonld([ITEM], BASE)
    one = graph.restrict_to(whole, single)
    assert [node["@id"] for node in one["@graph"]] == [BASE + "concepts/alpha/"]
    assert one["@graph"][0]["isRequiredBy"] == BASE + "concepts/beta/"
    lone = {"@graph": [{"@id": "https://b.example/"}]}
    assert graph.restrict_to(whole, lone) == lone


# --- against the engine -----------------------------------------------------------

needs_engine = pytest.mark.skipif(
    not (engine_available() and (ENGINE / "tools" / "gen-ns").is_file()
         and (ENGINE / "src" / "knowledge" / "jsonld.js").is_file()),
    reason="the JSON-LD parity proof needs Node and the engine checkout beside this one",
)

def _states_a_dataset(vector):
    """Items and a base, and not a domain-layer case (a site vocabulary or a warrant
    adds triples the engine alone writes in 1.1, CASES_NOT_RUN)."""
    given = vector["input"]
    base = (given.get("site") or {}).get("base") or given.get("base")
    return isinstance(given.get("items"), list) and base is not None \
        and vector["id"] not in CASES_NOT_RUN


#: The graph vectors that state a dataset.
DATASETS = sorted(one for one in (VECTORS / "graph").glob("*.json")
                  if _states_a_dataset(json.loads(one.read_bytes())))

_SCRIPT = r"""
const path = require('node:path');
const fs = require('node:fs');
const crypto = require('node:crypto');
const ROOT = process.argv[1];
const jsonld = require(path.join(ROOT, 'src/knowledge/jsonld.js'));
const turtle = require(path.join(ROOT, 'src/knowledge/turtle.js'));
const jcs = require(path.join(ROOT, 'src/knowledge/jcs.js'));
const links = require(path.join(ROOT, 'src/knowledge/links.js'));
const input = JSON.parse(fs.readFileSync(process.argv[2], 'utf8')).input;
const context = jsonld.context(
  turtle.ontologyTerms(fs.readFileSync(path.join(ROOT, 'ontology', 'agsc.ttl'), 'utf8')),
  jsonld.allExternalProperties());
// The inline-link edges are resolved by the Links module and injected, as the build does.
const mentions = links.resolve(input.items.map((item) => ({ ...item, path: `content/concepts/${item.slug}.md` })))
  .edges.filter((edge) => edge.key === 'mentions' && edge.source !== edge.target)
  .map((edge) => ({ source: edge.source, target: edge.target }));
const options = { mentions, base: (input.site && input.site.base) || input.base, context,
  contextUrl: input.context_url,
  sha256: (bytes) => crypto.createHash('sha256').update(bytes).digest('hex'),
  ...(input.bundle ? { bundle: input.bundle } : {}),
  ...(input.attachment_bytes ? { attachmentBytes: input.attachment_bytes } : {}) };
const whole = jsonld.toJsonLd(input.items, options);
const out = { whole: jcs.canonicalize(whole), per_item: {} };
for (const item of input.items) {
  out.per_item[item.slug] = jcs.canonicalize(jsonld.restrictTo(whole, jsonld.toJsonLd([item], options)));
}
process.stdout.write(JSON.stringify(out));
"""


@needs_engine
def test_the_shipped_context_is_the_one_the_engine_derives(tmp_path):
    done = subprocess.run(["node", str(ENGINE / "tools" / "gen-ns"), "--quiet", "--out",
                           str(tmp_path)], capture_output=True, cwd=str(ENGINE))
    assert done.returncode == 0, done.stderr[-2000:]
    assert (tmp_path / "context.jsonld").read_bytes() == context.published_bytes()


@needs_engine
@pytest.mark.parametrize("path", DATASETS, ids=[one.stem for one in DATASETS])
def test_the_writer_agrees_with_the_engine(path):
    done = subprocess.run(["node", "-e", _SCRIPT, str(ENGINE), str(path)],
                          capture_output=True, text=True, cwd=str(ENGINE))
    assert done.returncode == 0, done.stderr[-2000:]
    theirs = json.loads(done.stdout)
    given = json.loads(path.read_bytes())["input"]
    base = (given.get("site") or {}).get("base") or given.get("base")
    arguments = (base, given.get("bundle"), given.get("attachment_bytes"))
    whole = graph.to_jsonld(given["items"], *arguments, context_url=given.get("context_url"))
    assert canonicalize(whole) == theirs["whole"]
    for item in given["items"]:
        single = graph.to_jsonld([item], *arguments, context_url=given.get("context_url"))
        assert canonicalize(graph.restrict_to(whole, single)) == theirs["per_item"][item["slug"]]
