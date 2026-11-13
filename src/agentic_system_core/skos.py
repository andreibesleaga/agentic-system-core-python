"""The SKOS view of the graph, the file ``export --skos`` writes (AGSC-05-36).

What: one Turtle file, with its own two-line prefix block (``dcterms``, ``skos``), that
states the SKOS structure the graph leaves implicit: the Bundle as a
``skos:ConceptScheme`` with its record (``site.title``, ``site.tagline``,
``site.author`` and the Bundle's licence), ``a skos:Concept`` for each concept and
lesson, ``a skos:Collection`` for each cluster, and ``skos:hasTopConcept`` /
``skos:topConceptOf`` for each concept with no ``skos:broader``. It copies the SKOS
triples of the graph whose two ends are in the view; an episode, a procedure and a gate
are not SKOS concepts, so they and every triple that names one are left out.

Why it reads the triples of ``graph.nq``: the view is "the triples of ``graph.nq``
whose predicate is ...", so it agrees with the graph by construction — the published
projection, the labels, the language tags and the escaping are the graph's own. The
engine reads the text of ``graph.nq``; this package hands over the same triples from
``graph.dataset`` (no N-Quads parser is needed for its own output). The file is written
by the one stable-Turtle writer the graph uses (``rdf.turtle``, AGSC-05-10 (c) to (e)).
The engine's ``src/knowledge/skos-export.js`` is the reference; ``graph-0040`` pins the
whole file.

Standard library only.
"""

from .rdf import ASC, DCTERMS, IRI, RDF_TYPE, SCHEMA, SKOS, Literal, turtle

#: The prefix block of the file: exactly these two lines, in this order (AGSC-05-36).
PREFIXES = (("dcterms", DCTERMS), ("skos", SKOS))
#: The predicates of ``graph.nq`` the view copies.
COPIED = frozenset(SKOS + name for name in ("prefLabel", "altLabel", "definition", "inScheme",
                                            "broader", "narrower", "related", "member"))
#: The SKOS class of each item class the view keeps (the axioms of AGSC-05-12).
SKOS_CLASS_OF = {ASC + "Concept": "Concept", ASC + "Lesson": "Concept",
                 ASC + "Cluster": "Collection"}
#: The scheme record: the dcterms property each value is written as, in this order.
RECORD_PROPERTIES = (("creator", DCTERMS + "creator"), ("description", DCTERMS + "description"),
                     ("title", DCTERMS + "title"), ("license", DCTERMS + "license"))


def scheme_record(config):
    """``site.title``, ``site.tagline`` and ``site.author`` where present (AGSC-05-36)."""
    site = (config or {}).get("site") or {}
    record = {"creator": site.get("author"), "description": site.get("tagline"),
              "title": site.get("title")}
    return dict((name, value) for name, value in record.items() if value is not None)


def _kinds(triples):
    """{subject IRI: "Concept" or "Collection"} for the items the view keeps."""
    return dict((subject.value, SKOS_CLASS_OF[obj.value]) for subject, predicate, obj in triples
                if predicate.value == RDF_TYPE and isinstance(obj, IRI)
                and obj.value in SKOS_CLASS_OF)


def _scheme(triples):
    """(Bundle IRI, its licence or None), or None when the graph has no Bundle node."""
    bundles = sorted(subject.value for subject, predicate, obj in triples
                     if predicate.value == RDF_TYPE and obj == IRI(ASC + "Bundle"))
    if not bundles:
        return None
    licences = sorted(obj.value for subject, predicate, obj in triples
                      if subject.value == bundles[0] and predicate.value == SCHEMA + "license")
    return bundles[0], (licences[0] if licences else None)


def _copied(triples, kinds, scheme):
    def belongs(term):
        return not isinstance(term, IRI) or term.value in kinds or (
            scheme is not None and term.value == scheme[0])
    return [(subject, predicate, Literal(obj.value, lang=obj.lang) if isinstance(obj, Literal)
             else obj)
            for subject, predicate, obj in triples
            if predicate.value in COPIED and subject.value in kinds and belongs(obj)]


def _scheme_triples(scheme, record, kinds, copied):
    iri, licence = scheme
    node = IRI(iri)
    out = [(node, IRI(RDF_TYPE), IRI(SKOS + "ConceptScheme"))]
    values = dict(record, license=licence)
    for name, prop in RECORD_PROPERTIES:
        if values.get(name) is not None:
            out.append((node, IRI(prop), Literal(str(values[name]))))
    if values.get("title") is not None:
        out.append((node, IRI(SKOS + "prefLabel"), Literal(str(values["title"]))))
    narrower = set(subject.value for subject, predicate, _ in copied
                   if predicate.value == SKOS + "broader")
    for top in sorted(subject for subject, kind in kinds.items()
                      if kind == "Concept" and subject not in narrower):
        out.append((node, IRI(SKOS + "hasTopConcept"), IRI(top)))
        out.append((IRI(top), IRI(SKOS + "topConceptOf"), node))
    return out


def skos_view(triples, record=None):
    """The Turtle text of ``skos.ttl`` for the triples of ``graph.nq`` and a scheme record."""
    kinds = _kinds(triples)
    scheme = _scheme(triples)
    copied = _copied(triples, kinds, scheme)
    types = [(IRI(subject), IRI(RDF_TYPE), IRI(SKOS + kind)) for subject, kind in kinds.items()]
    own = [] if scheme is None else _scheme_triples(scheme, record or {}, kinds, copied)
    return turtle(copied + types + own, PREFIXES)
