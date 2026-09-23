"""The JSON-LD context file and the compaction it round-trips (AGSC-06-32, AGSC-05-09).

AGSC-06-32 fixes the mapping: every ``asc:`` term becomes a term definition whose
``@id`` is its IRI, object properties carry ``@type: @id``, datatype properties
carry the ``@type`` of their declared range; the prefixes ``dcterms``, ``prov``,
``rdfs``, ``schema``, ``skos`` and ``xsd`` are always defined; every external
property a rule emits gets a typed term definition; no term is ever ``null``;
``@version`` 1.1 and ``@protected`` true are set; members are in JCS order.
A term is named by its local name, or by its compact IRI where that local name
is also an ``asc:`` term name or is shared by two external properties.

The round-trip obligation — expand ``graph.jsonld`` with the context, re-compact,
serialise canonically, and get the same bytes — is discharged here by a
compactor and an expander restricted to exactly the term definitions this
context can contain (string-valued, typed, ``@id``-typed and untyped terms, with
language-tagged values).  This is not a JSON-LD processor (AGSC-05-11); it is
the part of one that this profile's own documents exercise.
"""

import json

from .jcs import canonicalize
from .rdf import (ASC, DCTERMS, IRI, PREFIXES, PROV, RDF_TYPE, RDFS, SCHEMA, SKOS, XSD,
                  Literal)

#: AGSC-05-09: the specification's persistent versioned context URL.
ONTOLOGY_VERSION = "1.0.0-draft.1"
CONTEXT_URL = "https://w3id.org/agentic-system-core/ns/%s/context.jsonld" % ONTOLOGY_VERSION

_NAMESPACES = dict(PREFIXES)

#: External properties a rule of spec/05, 06 or 11 emits, with the @type the
#: emitting rule fixes (None: language-tagged, no @type).
EXTERNAL_PROPERTIES = (
    ("dcterms:created", XSD + "dateTime"),
    ("dcterms:creator", XSD + "string"),
    ("dcterms:date", XSD + "string"),
    ("dcterms:format", XSD + "string"),
    ("dcterms:isReplacedBy", "@id"),
    ("dcterms:isRequiredBy", "@id"),
    ("dcterms:license", XSD + "string"),
    ("dcterms:modified", XSD + "dateTime"),
    ("dcterms:replaces", "@id"),
    ("dcterms:requires", "@id"),
    ("dcterms:source", XSD + "string"),
    ("dcterms:title", XSD + "string"),
    ("prov:wasDerivedFrom", "@id"),
    ("rdfs:seeAlso", "@id"),
    ("schema:license", XSD + "string"),
    ("schema:usageInfo", XSD + "string"),
    ("skos:altLabel", None),
    ("skos:broader", "@id"),
    ("skos:definition", None),
    ("skos:inScheme", "@id"),
    ("skos:member", "@id"),
    ("skos:narrower", "@id"),
    ("skos:prefLabel", None),
    ("skos:related", "@id"),
)
_EXTERNAL_TYPES = dict(EXTERNAL_PROPERTIES)


def expand_curie(value):
    """``prefix:local`` -> IRI when the prefix is one of the constant block, else unchanged."""
    if ":" in value:
        prefix, local = value.split(":", 1)
        if prefix in _NAMESPACES and not local.startswith("//"):
            return _NAMESPACES[prefix] + local
    return value


def term_names(ontology_terms, external):
    """AGSC-06-32 naming: compact IRI -> term name."""
    asc_names = set(term["term"] for term in ontology_terms)
    locals_seen = {}
    for prop in external:
        local = prop.split(":", 1)[1]
        locals_seen[local] = locals_seen.get(local, 0) + 1
    names = {}
    for term in ontology_terms:
        names["asc:" + term["term"]] = term["term"]
    for prop in external:
        local = prop.split(":", 1)[1]
        names[prop] = prop if local in asc_names or locals_seen[local] > 1 else local
    return names


def build(ontology_terms, external_properties):
    """The context document ``{"@context": {...}}``.

    ``ontology_terms``: [{term, kind: object|datatype, range?}].
    ``external_properties``: [{property, type}] (type None: no @type), or a list of
    compact IRIs whose type is taken from :data:`EXTERNAL_PROPERTIES`.
    """
    external = []
    for one in external_properties:
        if isinstance(one, str):
            external.append((one, _EXTERNAL_TYPES[one]))
        else:
            external.append((one["property"], one.get("type")))
    names = term_names(ontology_terms, [prop for prop, _ in external])
    body = {"@protected": True, "@version": 1.1}
    for prefix, namespace in PREFIXES:
        body[prefix] = namespace
    for term in ontology_terms:
        definition = {"@id": "asc:" + term["term"]}
        if term["kind"] == "object":
            definition["@type"] = "@id"
        elif term.get("range"):
            definition["@type"] = expand_curie(term["range"])
        body[names["asc:" + term["term"]]] = definition
    for prop, kind in external:
        definition = {"@id": prop}
        if kind is not None:
            definition["@type"] = kind
        body[names[prop]] = definition
    return {"@context": body}


# --- compaction and expansion over this profile -------------------------------

def _definitions(context):
    """term name -> (predicate IRI, @type or None)."""
    out = {}
    for name, value in context["@context"].items():
        if isinstance(value, dict):
            out[name] = (expand_curie(value["@id"]), value.get("@type"))
    return out


def _compact_iri(value):
    for prefix, namespace in PREFIXES:
        local = value[len(namespace):]
        if value.startswith(namespace) and local and "/" not in local and "#" not in local:
            return "%s:%s" % (prefix, local)
    return value


def compact(triples, context):
    """``graph.jsonld`` for a set of triples: nodes by @id, members in JCS order."""
    definitions = _definitions(context)
    by_predicate = {}
    for name, (iri, kind) in definitions.items():
        by_predicate.setdefault(iri, []).append((name, kind))
    nodes = {}
    for subject, predicate, obj in triples:
        node = nodes.setdefault(subject.value, {"@id": subject.value})
        if predicate.value == RDF_TYPE and isinstance(obj, IRI):
            node.setdefault("@type", []).append(_compact_iri(obj.value))
            continue
        key, value = None, None
        for name, kind in sorted(by_predicate.get(predicate.value, [])):
            if kind == "@id" and isinstance(obj, IRI):
                key, value = name, obj.value
            elif isinstance(obj, Literal) and obj.lang is None and kind is not None \
                    and kind != "@id" and kind == (obj.datatype or XSD + "string"):
                key, value = name, obj.value
            elif isinstance(obj, Literal) and obj.lang is not None and kind is None:
                key, value = name, {"@language": obj.lang, "@value": obj.value}
            if key is not None:
                break
        if key is None:
            key = _compact_iri(predicate.value)
            if isinstance(obj, IRI):
                value = {"@id": obj.value}
            elif obj.lang is not None:
                value = {"@language": obj.lang, "@value": obj.value}
            else:
                value = {"@type": obj.datatype or XSD + "string", "@value": obj.value}
        node.setdefault(key, []).append(value)
    graph = []
    for subject in sorted(nodes):
        node = nodes[subject]
        for key in list(node):
            if isinstance(node[key], list):
                values = sorted(node[key], key=canonicalize)
                node[key] = values[0] if len(values) == 1 else values
        graph.append(node)
    return {"@context": CONTEXT_URL, "@graph": graph}


def expand(document, context):
    """The triples of a document written by :func:`compact`, read with ``context``."""
    definitions = _definitions(context)
    triples = set()
    for node in document["@graph"]:
        subject = IRI(node["@id"])
        for key, raw in node.items():
            if key == "@id":
                continue
            values = raw if isinstance(raw, list) else [raw]
            if key == "@type":
                for value in values:
                    triples.add((subject, IRI(RDF_TYPE), IRI(expand_curie(value))))
                continue
            predicate, kind = definitions.get(key, (expand_curie(key), None))
            for value in values:
                if isinstance(value, dict):
                    if "@id" in value:
                        obj = IRI(value["@id"])
                    elif "@language" in value:
                        obj = Literal(value["@value"], lang=value["@language"])
                    else:
                        obj = Literal(value["@value"], datatype=value.get("@type"))
                elif kind == "@id":
                    obj = IRI(expand_curie(value))
                else:
                    obj = Literal(value, datatype=kind)
                triples.add((subject, IRI(predicate), obj))
    return triples


def roundtrip_bytes(triples, context):
    """(first bytes, bytes after expand + re-compact): equal when the context round-trips."""
    first = canonicalize(compact(triples, context))
    again = canonicalize(compact(expand(json.loads(first), context), context))
    return first, again


def sample_triples(context):
    """One subject using every term of a context, so a round trip exercises each one."""
    subject = IRI("https://a.example/concepts/sample/")
    triples = {(subject, IRI(RDF_TYPE), IRI(ASC + "Concept"))}
    for name, (iri, kind) in sorted(_definitions(context).items()):
        if kind == "@id":
            obj = IRI("https://a.example/concepts/%s/" % name.replace(":", "-").lower())
        elif kind is None:
            obj = Literal("Label of " + name, lang="en")
        elif kind == XSD + "dateTime":
            obj = Literal("2026-01-01T00:00:00Z", datatype=kind)
        else:
            obj = Literal("value of " + name, datatype=kind)
        triples.add((subject, IRI(iri), obj))
    return triples


__all__ = ["CONTEXT_URL", "EXTERNAL_PROPERTIES", "build", "compact", "expand",
           "roundtrip_bytes", "sample_triples", "term_names", "ASC", "DCTERMS", "PROV",
           "RDFS", "SCHEMA", "SKOS"]
