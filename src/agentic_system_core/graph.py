"""The Bundle's RDF dataset: IRIs, classes, the frontmatter-to-property mapping.

Derived from the rule text of spec/05 (and AGSC-11-22 for ``asc:retiredAt``):

* AGSC-05-01 / 05-03 — item IRI ``<site.base>/<type-plural>/<slug>/``, Bundle
  IRI ``<site.base>/``.
* AGSC-05-12 — the type-to-class table; the Bundle is ``asc:Bundle``.
* AGSC-05-14 / 05-15 / 05-29 — Sources, Reviews and Attachments as fragment
  IRIs ``#source-<n>``, ``#review-<n>``, ``#attachment-<n>``, each reachable from
  its item.
* AGSC-05-16 / 05-18 / 05-19 / 05-20 — the Link-key properties with their
  materialised inverses (AGSC-05-23), cluster membership and nesting as
  ``skos:member``, and no Collection in a semantic relation.
* AGSC-05-17 / 05-26 / 05-27 / 05-30 / 05-31 — labels, the datatype-property
  table, ports and task state, and the three literal forms.
* AGSC-05-04 / 05-04b — ``memory://`` is resolved locally and never emitted.

The Bundle node and the two licence rows are emitted when the Bundle's
configuration is given (``bundle``).  Every line of ``graph.nq`` is a quad
whose graph name is the Bundle IRI (AGSC-04-15).

``graph.jsonld`` (AGSC-05-09) is written from the same triples, so the views
cannot drift (AGSC-05-06): one node per subject in code-point order of ``@id``,
each predicate under the term name of the published context (AGSC-06-32), one
value bare and several as a sorted array.  ``/pages/<slug>.jsonld`` (AGSC-06-02)
is the one-item view with each node taken from the whole graph.  The writer
follows the engine's ``src/knowledge/jsonld.js`` (``toJsonLd``, ``restrictTo``);
it is a JSON writer, not a JSON-LD processor (AGSC-05-11).
"""

import hashlib
import re

from . import context as context_module
from . import links as links_module
from . import relations
from .jcs import canonicalize
from .rdf import (ASC, DCTERMS, IRI, RDF_TYPE, SCHEMA, SKOS, XSD_DATETIME, XSD_STRING,
                  Literal, nquads, turtle)

TYPE_CLASS = {
    "concept": ASC + "Concept", "lesson": ASC + "Lesson", "episode": ASC + "Episode",
    "procedure": ASC + "Procedure", "cluster": ASC + "Cluster", "gate": ASC + "Gate",
}
#: The item types whose class is a subclass of skos:Concept (AGSC-05-12, AGSC-05-17).
CONCEPT_TYPES = ("concept", "lesson")
#: AGSC-06-18: the Content Use Terms identifier, a constant of the specification.
CONTENT_USE_TERMS = "LicenseRef-AgenticSystemCore-Content-Use-1.0"


def terms_for(license_prose):
    """AGSC-06-18: the Content Use Terms identifier where the node
    adopted the terms, else the node's own prose licence in its place."""
    if license_prose is None or str(license_prose) == CONTENT_USE_TERMS:
        return CONTENT_USE_TERMS
    return str(license_prose)

#: Link key -> (forward property, inverse property or None): the relation table of
#: AGSC-03-01 (AGSC-05-16, AGSC-05-23), read from ``relations.py``.
LINK_PROPERTIES = relations.LINK_PROPERTIES
_SEMANTIC = (SKOS + "related", SKOS + "broader", SKOS + "narrower")

#: AGSC-05-26 rows read straight from an item key: key -> (property, types or None, datatype).
_ITEM_ROWS = (
    ("status", ASC + "status", None, None),
    ("kind", ASC + "kind", ("concept",), None),
    ("stale_after", ASC + "staleAfter", None, XSD_DATETIME),
    ("date", DCTERMS + "created", None, XSD_DATETIME),
    ("modified", DCTERMS + "modified", None, XSD_DATETIME),
    ("level", ASC + "level", ("gate",), None),
    ("severity", ASC + "severity", ("lesson",), None),
    ("outcome", ASC + "outcome", ("episode",), None),
    ("task_state", ASC + "taskState", None, None),
)
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class GraphError(ValueError):
    def __init__(self, code, message):
        ValueError.__init__(self, message)
        self.code = code


def base_of(site_base):
    return site_base.rstrip("/")


def bundle_iri(site_base):
    """AGSC-05-03."""
    return base_of(site_base) + "/"


def item_iri(site_base, item):
    """AGSC-05-01."""
    return "%s/%s/%s/" % (base_of(site_base), links_module.TYPE_PLURAL[item["type"]],
                          item["slug"])


def instant(value):
    """AGSC-04-10 / AGSC-05-14: a date becomes its midnight instant; an instant is kept."""
    value = str(value)
    if _DATE.match(value):
        return value + "T00:00:00Z"
    return value


def resolve_memory(value, bundle_id):
    """AGSC-05-04b: ``memory://<bundle-id>/<slug>`` -> slug, or ``AGSC-E309`` when foreign."""
    if not value.startswith("memory://"):
        return value
    rest = value[len("memory://"):]
    owner, _, slug = rest.partition("/")
    if owner != bundle_id:
        raise GraphError("AGSC-E309", "foreign bundle: use the https:// IRI")
    return slug


def dataset(items, site_base, bundle=None, attachment_bytes=None):
    """Every triple of the Bundle's graph, as a set of (IRI, IRI, term)."""
    triples = set()
    scheme = IRI(bundle_iri(site_base))

    def add(subject, predicate, obj):
        triples.add((IRI(subject) if isinstance(subject, str) else subject,
                     IRI(predicate), obj))

    if bundle is not None:
        add(scheme, RDF_TYPE, IRI(ASC + "Bundle"))
        if bundle.get("spec_version") is not None:
            add(scheme, ASC + "specVersion", Literal(bundle["spec_version"]))
        licence = bundle.get("license_prose", CONTENT_USE_TERMS)
        add(scheme, SCHEMA + "license", Literal(licence))
        add(scheme, SCHEMA + "usageInfo", Literal(terms_for(licence)))

    by_slug = dict((item["slug"], item) for item in items)
    for item in items:
        iri = item_iri(site_base, item)
        kind = item["type"]
        lang = item.get("lang") or "en"
        add(iri, RDF_TYPE, IRI(TYPE_CLASS[kind]))
        if kind in CONCEPT_TYPES:
            add(iri, SKOS + "inScheme", scheme)
        if item.get("title") is not None:
            add(iri, SKOS + "prefLabel", Literal(item["title"], lang=lang))
        if item.get("description") is not None:
            add(iri, SKOS + "definition", Literal(item["description"], lang=lang))
        for alias in item.get("aliases") or []:
            add(iri, SKOS + "altLabel", Literal(alias, lang=lang))
        for key, prop, types, datatype in _ITEM_ROWS:
            if item.get(key) is None or (types is not None and kind not in types):
                continue
            value = instant(item[key]) if datatype else str(item[key])
            add(iri, prop, Literal(value, datatype=datatype))
        if item.get("status") == "retired":  # AGSC-11-22
            when = item.get("modified") or item.get("date")
            if when is not None:
                add(iri, ASC + "retiredAt", Literal(instant(when), datatype=XSD_DATETIME))
        prov = item.get("prov") or {}
        for key, prop in (("origin", "origin"), ("operator", "operator"), ("model", "model")):
            if prov.get(key) is not None:
                add(iri, ASC + prop, Literal(str(prov[key])))
        generated = item.get("generated") or {}
        if generated.get("by") is not None:
            add(iri, ASC + "generatedBy", Literal(str(generated["by"])))
        if generated.get("at") is not None:
            add(iri, ASC + "generatedAt", Literal(instant(generated["at"]),
                                                  datatype=XSD_DATETIME))
        for name in item.get("produces") or []:
            add(iri, ASC + "produces", Literal(name))
        for name in item.get("consumes") or []:
            add(iri, ASC + "consumes", Literal(name))
        if bundle is not None:
            add(iri, SCHEMA + "license", Literal(bundle.get("license_prose", CONTENT_USE_TERMS)))
            add(iri, SCHEMA + "usageInfo", Literal(terms_for(bundle.get("license_prose", CONTENT_USE_TERMS))))

        for index, source in enumerate(item.get("sources") or [], 1):
            node = "%s#source-%d" % (iri, index)
            add(iri, ASC + "source", IRI(node))
            add(node, RDF_TYPE, IRI(ASC + "Source"))
            for key, prop in (("resource", "source"), ("title", "title"),
                              ("author", "creator"), ("year", "date")):
                if source.get(key) is not None:
                    add(node, DCTERMS + prop, Literal(str(source[key])))
            if source.get("verified") is not None:
                add(node, ASC + "verifiedOn", Literal(instant(source["verified"]),
                                                      datatype=XSD_DATETIME))
            if source.get("grade") is not None:
                add(node, ASC + "grade", Literal(str(source["grade"])))
        for index, review in enumerate(item.get("verified") or [], 1):
            node = "%s#review-%d" % (iri, index)
            add(iri, ASC + "review", IRI(node))
            add(node, RDF_TYPE, IRI(ASC + "Review"))
            if review.get("by") is not None:
                add(node, ASC + "verifiedBy", Literal(str(review["by"])))
            if review.get("at") is not None:
                add(node, ASC + "verifiedAt", Literal(instant(review["at"]),
                                                      datatype=XSD_DATETIME))
        for index, attachment in enumerate(item.get("attachments") or [], 1):
            node = "%s#attachment-%d" % (iri, index)
            add(iri, ASC + "hasAttachment", IRI(node))
            add(node, RDF_TYPE, IRI(ASC + "Attachment"))
            add(node, DCTERMS + "format", Literal(attachment["media_type"]))
            data = (attachment_bytes or {}).get(attachment["file"])
            if data is not None:
                raw = data.encode("utf-8") if isinstance(data, str) else data
                add(node, ASC + "sha256", Literal(hashlib.sha256(raw).hexdigest()))
            add(node, DCTERMS + "title", Literal(attachment["alt"]))
            licence = attachment.get("license") or (bundle or {}).get(
                "license_prose", CONTENT_USE_TERMS)
            add(node, DCTERMS + "license", Literal(licence))
            add(node, DCTERMS + "source", Literal(attachment["file"]))

        for cluster in item.get("clusters") or []:
            target = by_slug.get(links_module.target_slug(cluster)[0])
            if target is not None:
                add(item_iri(site_base, target), SKOS + "member", IRI(iri))

        for key, values in links_module.authored_links(item):
            forward, inverse = LINK_PROPERTIES[key]
            for value in values:
                target = by_slug.get(links_module.target_slug(value)[0])
                if target is None:
                    continue
                other = item_iri(site_base, target)
                clusters = (kind == "cluster", target["type"] == "cluster")
                if key in ("broader", "narrower") and clusters == (True, True):
                    parent, child = (other, iri) if key == "broader" else (iri, other)
                    add(parent, SKOS + "member", IRI(child))  # AGSC-05-19
                    continue
                if forward in _SEMANTIC and any(clusters):
                    continue  # AGSC-05-20: no Collection in a semantic relation
                add(iri, forward, IRI(other))
                if inverse is not None:
                    add(other, inverse, IRI(iri))

    for source, target in links_module.mentions(items):
        add(item_iri(site_base, by_slug[source]), ASC + "mentions",
            IRI(item_iri(site_base, by_slug[target])))
    return triples


def to_nquads(items, site_base, bundle=None, attachment_bytes=None):
    """``graph.nq``: every line a quad named by the Bundle IRI (AGSC-04-15)."""
    return nquads(dataset(items, site_base, bundle, attachment_bytes),
                  graph=bundle_iri(site_base))


def to_turtle(items, site_base, bundle=None, attachment_bytes=None):
    return turtle(dataset(items, site_base, bundle, attachment_bytes))


# --- graph.jsonld (AGSC-05-09) ------------------------------------------------------

def compaction_table(context_document):
    """What the writer compacts with: ``terms``, IRI -> {"name", "type"} of its term
    definition, and ``prefixes``, the (name, namespace) pairs of the plain string
    definitions (``asc``, ``dcterms``, ... in a context of AGSC-06-32)."""
    terms, prefixes = {}, []
    for name, definition in context_document.get("@context", {}).items():
        if isinstance(definition, str) and not name.startswith("@"):
            prefixes.append((name, definition))
        elif isinstance(definition, dict) and definition.get("@id"):
            terms[context_module.expand_curie(definition["@id"])] = {
                "name": name, "type": definition.get("@type")}
    return {"terms": terms, "prefixes": prefixes}


def prefixed(value, table):
    """An IRI under a prefix of the context as its compact IRI (``asc:warrant``), else
    itself: the form a JSON-LD processor's re-compaction writes (AGSC-06-32)."""
    for prefix, namespace in table["prefixes"]:
        if len(value) > len(namespace) and value.startswith(namespace):
            return "%s:%s" % (prefix, value[len(namespace):])
    return value


def compact_name(value, table):
    """A member name, a class or a datatype: its term name, else :func:`prefixed`."""
    term = table["terms"].get(value)
    return term["name"] if term else prefixed(value, table)


def json_value(obj, definition, table):
    """One object in the most compact form its term definition allows (AGSC-05-31)."""
    selects_iris = definition is not None and definition["type"] == "@id"
    if isinstance(obj, IRI):
        value = prefixed(obj.value, table)
        return value if selects_iris else {"@id": value}
    if obj.lang is not None:
        return {"@language": obj.lang, "@value": obj.value}
    datatype = obj.datatype or XSD_STRING
    if selects_iris:
        # A bare string under an @id term would be read as an IRI.
        return {"@type": compact_name(datatype, table), "@value": obj.value}
    if (definition is not None and definition["type"] == datatype) or datatype == XSD_STRING:
        return obj.value
    return {"@type": compact_name(datatype, table), "@value": obj.value}


def _value_key(value):
    if isinstance(value, str):
        return value
    return value.get("@id") or value.get("@value") or ""


def _members(objects, definition, table):
    """The values of one predicate: sorted, one per key, bare when there is one."""
    values = sorted((json_value(obj, definition, table) for obj in objects),
                    key=lambda value: (_value_key(value), canonicalize(value)))
    unique, seen = [], set()
    for value in values:
        if _value_key(value) not in seen:
            seen.add(_value_key(value))
            unique.append(value)
    return unique[0] if len(unique) == 1 else unique


def to_jsonld(items, site_base, bundle=None, attachment_bytes=None, context_document=None,
              context_url=None):
    """``graph.jsonld`` as a document (serialise it with JCS and one LF, AGSC-04-04).

    ``context_document`` fixes the term names (default: the published context);
    ``context_url`` is the ``@context`` the document names, none when it is None.
    """
    table = compaction_table(context_document or context_module.published())
    by_subject = {}
    for subject, predicate, obj in dataset(items, site_base, bundle, attachment_bytes):
        by_subject.setdefault(subject.value, {}).setdefault(predicate.value, []).append(obj)
    nodes = []
    for subject in sorted(by_subject):
        properties = by_subject[subject]
        node = {"@id": prefixed(subject, table)}
        types = [compact_name(value, table)
                 for value in sorted(obj.value for obj in properties.pop(RDF_TYPE, []))]
        if types:
            node["@type"] = types[0] if len(types) == 1 else types
        for predicate, objects in properties.items():
            node[compact_name(predicate, table)] = _members(
                objects, table["terms"].get(predicate), table)
        nodes.append(node)
    document = {}
    if context_url:
        document["@context"] = context_url
    document["@graph"] = nodes
    return document


def restrict_to(whole, single):
    """``/pages/<slug>.jsonld`` (AGSC-06-02): the nodes of the one-item document
    ``single``, each replaced by its node in the whole graph's document."""
    by_id = dict((node["@id"], node) for node in whole.get("@graph", []))
    restricted = dict(single)
    restricted["@graph"] = [by_id.get(node["@id"], node) for node in single.get("@graph", [])]
    return restricted
