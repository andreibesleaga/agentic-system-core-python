"""The versioned context address this package writes (AGSC-05-09, AGSC-05-25).

AGSC-05-09 names one persistent context address,
``https://w3id.org/agentic-system-core/ns/<version>/context.jsonld``.  As amended for
1.1, the version in it is a constant ``1.0.0`` at every version 1.x and no longer the
ontology version that AGSC-05-25 takes from ``owl:versionIRI`` (vector graph-0043):
raising the ontology version changes no byte of any ``graph.jsonld``.  The engine holds
the constant as ``CONTEXT_VERSION`` in ``src/knowledge/jsonld.js``; this package as
``context.CONTEXT_VERSION``.  When the engine is beside this repository, the two are
compared.

No network, no clock: the test reads one file of the engine checkout.
"""

import re

import pytest

from agentic_system_core import context
from agentic_system_core.rdf import IRI, RDF_TYPE
from conftest import ENGINE

JSONLD = ENGINE / "src" / "knowledge" / "jsonld.js"
NAMESPACE = "https://w3id.org/agentic-system-core/ns"


def _engine_context_version():
    text = JSONLD.read_text(encoding="utf-8")
    found = re.findall(r"^const CONTEXT_VERSION = '([^']+)';$", text, re.M)
    assert len(found) == 1, "the engine's jsonld.js states CONTEXT_VERSION %d times" % len(found)
    return found[0]


@pytest.mark.skipif(not JSONLD.is_file(), reason="the engine is not beside this repository")
def test_the_context_address_names_the_engines_context_version():
    assert context.CONTEXT_VERSION == _engine_context_version()
    assert context.CONTEXT_URL == "%s/%s/context.jsonld" % (NAMESPACE, context.CONTEXT_VERSION)


def test_the_context_version_is_the_constant_of_every_1x_version():
    assert context.CONTEXT_VERSION == "1.0.0"


def test_the_address_is_the_persistent_form_of_the_rule():
    assert re.fullmatch(re.escape(NAMESPACE) + r"/[0-9A-Za-z.+-]+/context\.jsonld", context.CONTEXT_URL)


def test_a_compacted_document_names_that_address():
    subject = IRI("https://a.example/concepts/sample/")
    triples = {(subject, IRI(RDF_TYPE), IRI(context.ASC + "Concept"))}
    built = context.build([{"kind": "object", "term": "uses"}], ["skos:prefLabel"])
    document = context.compact(triples, built)
    assert document["@context"] == context.CONTEXT_URL
