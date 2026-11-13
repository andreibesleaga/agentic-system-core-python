"""The home page's machine-readable parts: its Signposting links and its Dataset block.

The twin of the engine's ``headers.homeLinks`` (``src/distribution/headers.js``), its
``licenseUrl`` (``src/knowledge/chunks.js``) and its ``datasetBlock`` and
``creatorOf`` (``src/distribution/front-page.js``):

* ``home_links`` — the typed links FAIR Signposting Level 1 asks of a landing page, in
  the ``Link`` field of ``/`` after the ``describedby`` link of AGSC-11-05 (AGSC-06-40;
  vector disc-0026);
* ``license_url`` — the licence URL of a node (AGSC-06-44);
* ``dataset_block`` — the Schema.org ``Dataset`` of the home page with the licence URL,
  the creator, free access, one ``DataDownload`` per machine file served and the two
  PROV-O terms (AGSC-06-19, AGSC-06-41; vector disc-0027).

This package writes no HTML page and no ``_headers`` file; these functions give the
data those files carry, so that the vectors that pin it are run here and compared with
the engine.  Pure: data in, data out.  Standard library only.
"""

from . import MEDIA_TYPE, WELLKNOWN_PATH

#: AGSC-06-18: the identifier of the Content Use Terms, the default prose licence.
CONTENT_USE_TERMS = "LicenseRef-AgenticSystemCore-Content-Use-1.0"
#: AGSC-06-40: the files an ``item`` link names, in order, with the type each is served with.
SIGNPOSTED_ITEMS = (
    ("/graph.nq", "application/n-quads"),
    ("/graph.ttl", "text/turtle"),
    ("/chunks.jsonl", "application/jsonl"),
)
#: AGSC-06-41: the PROV-O namespace (W3C Recommendation, 30 April 2013), prefix ``prov``.
PROV = "http://www.w3.org/ns/prov#"
XSD_DATE_TIME = "http://www.w3.org/2001/XMLSchema#dateTime"
#: AGSC-06-41: the machine files a ``DataDownload`` names, in order, with their types.
DOWNLOADS = (
    ("/graph.jsonld", "application/ld+json"),
    ("/graph.ttl", "text/turtle"),
    ("/graph.nq", "application/n-quads"),
    ("/chunks.jsonl", "application/jsonl"),
    (WELLKNOWN_PATH, MEDIA_TYPE),
)


def href(base, route):
    """A route on the node: its base without trailing slashes, then the route."""
    return str(base).rstrip("/") + route


def license_url(config, legal=False):
    """AGSC-06-44: ``bundle.license_url``; else, when the prose licence is the Content Use
    Terms (or absent, which defaults to them) and the build writes ``/legal/``, the
    node's ``/legal/`` page; else None."""
    bundle = config.get("bundle") or {}
    named = bundle.get("license_url")
    if isinstance(named, str) and named != "":
        return named
    prose = bundle.get("license_prose")
    if not legal or (prose is not None and str(prose) != CONTENT_USE_TERMS):
        return None
    return href((config.get("site") or {}).get("base") or "", "/legal/")


def _cite_as(config):
    """The first ``related[]`` entry of relation ``cite-as`` in ``href`` order, or None.
    The entries are taken as the configuration schema admitted them."""
    hrefs = sorted(str(one["href"]) for one in config.get("related") or []
                   if one.get("rel") == "cite-as")
    return hrefs[0] if hrefs else None


def home_links(config, routes):
    """AGSC-06-40: the links of the ``Link`` field of ``/`` as ``{href, rel[, type]}``, the
    ``describedby`` link of AGSC-11-05 first.  Only a node that writes a home page sends
    the Signposting links: ``cite-as`` (else the Bundle IRI), the two ``type`` links,
    ``describedby`` for ``/graph.jsonld``, an ``item`` for each graph file and the chunks
    it serves (none on a restricted node), ``license`` when it has a licence URL, and
    ``linkset``.  Targets on the node are root-relative; ``cite-as`` and ``license`` are
    absolute."""
    emitted = set(routes)
    out = [{"href": WELLKNOWN_PATH, "rel": "describedby", "type": MEDIA_TYPE}]
    if "/index.html" not in emitted:
        return out
    base = str((config.get("site") or {}).get("base") or "").rstrip("/")
    cite = _cite_as(config)
    out.append({"href": base + "/" if cite is None else cite, "rel": "cite-as"})
    out.append({"href": "https://schema.org/Dataset", "rel": "type"})
    out.append({"href": "https://schema.org/AboutPage", "rel": "type"})
    if "/graph.jsonld" in emitted:
        out.append({"href": "/graph.jsonld", "rel": "describedby", "type": "application/ld+json"})
    if config.get("visibility") != "restricted":
        out.extend({"href": route, "rel": "item", "type": kind}
                   for route, kind in SIGNPOSTED_ITEMS if route in emitted)
    licence = license_url(config, legal="/legal/index.html" in emitted)
    if licence is not None:
        out.append({"href": licence, "rel": "license"})
    out.append({"href": WELLKNOWN_PATH, "rel": "linkset", "type": MEDIA_TYPE})
    return out


def creator_of(config, base):
    """AGSC-06-41: the creator, a ``Person`` with a ``name`` and, where an ORCID iD is
    configured, a ``sameAs`` naming it: from ``bundle.creator`` (name, optional orcid),
    else from ``site.author`` with ``site.author_orcid`` (AGSC-01-18); None when
    neither is configured.  As amended 2026-11-10 the Person is a named node: ``@id``
    is the ORCID iD URL, else ``<site.base>#creator``."""
    creator = (config.get("bundle") or {}).get("creator")
    site = config.get("site") or {}
    if isinstance(creator, dict) and isinstance(creator.get("name"), str):
        name, orcid = creator["name"], creator.get("orcid")
    elif isinstance(site.get("author"), str) and site["author"] != "":
        name, orcid = site["author"], site.get("author_orcid")
    else:
        return None
    iri = "https://orcid.org/" + orcid if isinstance(orcid, str) and orcid != "" else None
    person = {"@id": base + "#creator" if iri is None else iri, "@type": "Person", "name": name}
    if iri is not None:
        person["sameAs"] = iri
    return person


def dataset_block(config, instant, served, description=None, name=None, legal=False):
    """AGSC-06-19 with AGSC-06-41: the ``Dataset`` block of the home page, as data.

    ``served``: the routes the build emits; ``legal``: it emits ``/legal/``.  The files
    of a restricted node are gated, so it names none and claims no free access."""
    base = (config.get("site") or {}).get("base") or ""
    block = {
        "@context": ["https://schema.org", {"prov": PROV}], "@id": href(base, "/"),
        "@type": "Dataset",
        "description": "" if description is None else description,
        "name": "" if name is None else name,
        "prov:generatedAtTime": {"@type": XSD_DATE_TIME, "@value": str(instant)},
        "url": href(base, "/"),
    }
    licence = license_url(config, legal=legal)
    if licence is not None:
        block["license"] = licence
    creator = creator_of(config, href(base, "/"))
    if creator is not None:
        block["creator"] = creator
        block["prov:wasAttributedTo"] = {"@id": creator["@id"]}
    if config.get("visibility") != "restricted":
        block["isAccessibleForFree"] = True
        downloads = [{"@type": "DataDownload", "contentUrl": href(base, route),
                      "encodingFormat": kind} for route, kind in DOWNLOADS if route in served]
        if downloads:
            block["distribution"] = downloads
    return block


#: AGSC-06-41: the namespaces of the DCAT 3 catalogue block, and the IANA media type registry.
DCAT = "http://www.w3.org/ns/dcat#"
DCTERMS = "http://purl.org/dc/terms/"
IANA_MEDIA_TYPES = "https://www.iana.org/assignments/media-types/"


def catalog_block(config, instant, served, description=None, name=None, legal=False):
    """AGSC-06-41 as amended 2026-11-10: the DCAT 3 catalogue block a node writes beside
    the Dataset block when ``discovery.dcat`` is true, or None (the engine's
    ``front-page.js#catalogBlock``)."""
    if (config.get("discovery") or {}).get("dcat") is not True:
        return None
    dataset = dataset_block(config, instant, served, description, name, legal)
    described = {"@id": dataset["@id"], "@type": "dcat:Dataset",
                 "dcterms:description": dataset["description"],
                 "dcterms:modified": dataset["prov:generatedAtTime"],
                 "dcterms:title": dataset["name"]}
    if "license" in dataset:
        described["dcterms:license"] = {"@id": dataset["license"]}
    if "creator" in dataset:
        described["dcterms:creator"] = {"@id": dataset["creator"]["@id"]}
    if "distribution" in dataset:
        described["dcat:distribution"] = [dict(
            {"@type": "dcat:Distribution", "dcat:downloadURL": {"@id": one["contentUrl"]}},
            **({"dcterms:format": kind} if kind == "application/jsonl"
               else {"dcat:mediaType": {"@id": IANA_MEDIA_TYPES + kind}}))
            for one in dataset["distribution"] for kind in [one["encodingFormat"].split(";")[0]]]
    return {"@context": {"dcat": DCAT, "dcterms": DCTERMS}, "@id": dataset["@id"] + "#catalog",
            "@type": "dcat:Catalog", "dcat:dataset": described, "dcterms:title": dataset["name"]}
