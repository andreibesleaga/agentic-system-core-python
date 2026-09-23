"""Discovery surfaces: ``/llms.txt``, ``/llms-full.txt``, reachability, the
sitemap facts, the robots groups and the link-set writer.

Derived from the rule text:

* AGSC-06-13a / 06-15 — the byte layout of both agent-facing files, the
  provenance header and the ``-->`` neutralisation.
* AGSC-06-14 — every published item is reachable from ``/llms.txt``.
* AGSC-06-19 — ``sitemap.xml``: every published route, by URL, ``lastmod`` the
  build instant.
* AGSC-06-18 — one robots group per ``site.tdm_crawlers[]`` token, before the
  ``*`` group; an empty list beside ``tdm-reservation: 1`` is ``AGSC-E202``.
* AGSC-06-08 / 06-08a / 06-10 / 11-20 — the one link context of
  ``/.well-known/knowledge-linkset`` and what each Level carries.
"""

import base64
import hashlib

from . import REL_BASE
from .graph import CONTENT_USE_TERMS
from .jcs import canonicalize
from .links import TYPE_PLURAL

#: AGSC-06-15: the AI-assistance statement, a constant of the specification.
ASSISTANCE = ("content may be AI-assisted; each item states its origin in prov.origin and "
              "each accepted contribution carries an Assisted-by: trailer")
#: AGSC-06-19: the closed set of schema.org types embedded in item and index pages.
JSONLD_PAGE_TYPES = ("Dataset", "DefinedTerm", "TechArticle")
UNPUBLISHED_STATUSES = ("draft", "retired")


def _base(base):
    return base.rstrip("/")


def item_iri(base, item):
    return "%s/%s/%s/" % (_base(base), TYPE_PLURAL[item.get("type") or "concept"], item["slug"])


def published(items):
    """AGSC-06-30: draft and retired items appear in no agent-facing export."""
    return [one for one in items if one.get("status") not in UNPUBLISHED_STATUSES]


def _neutral(value):
    """AGSC-06-13a: no interpolated value may close the comment early."""
    return str(value).replace("-->", "--&gt;")


def _one_line(text):
    return " ".join(str(text).replace("\r\n", "\n").split("\n"))


def _cluster_titles(items, clusters):
    titles = dict((one["slug"], one.get("title", one["slug"])) for one in clusters or [])
    for item in items:
        if item.get("type") == "cluster":
            titles.setdefault(item["slug"], item.get("title", item["slug"]))
    return titles


def sections(items, clusters=None):
    """[(section title, [items by slug])]: cluster sections by cluster slug, then Other."""
    titles = _cluster_titles(items, clusters)
    grouped, other = {}, []
    for item in sorted(published(items), key=lambda one: one["slug"]):
        if item.get("type") == "cluster":
            continue
        primary = (item.get("clusters") or [None])[0]
        if primary in titles:
            grouped.setdefault(primary, []).append(item)
        else:
            other.append(item)
    out = [(titles[slug], grouped[slug]) for slug in sorted(grouped)]
    if other:
        out.append(("Other", other))
    return out


def _header(bundle, spec_version, bundle_version, generated_at):
    lines = [
        "<!-- agsc:provenance",
        "bundle: %s" % _neutral(_base(bundle["base"]) + "/"),
        "license: %s" % _neutral(bundle.get("license_prose", CONTENT_USE_TERMS)),
        "terms: %s" % CONTENT_USE_TERMS,
        "spec_version: %s" % _neutral(spec_version),
        "bundle_version: %s" % _neutral(bundle_version),
        "generated_at: %s" % _neutral(generated_at),
        "assistance: %s" % ASSISTANCE,
        "-->",
    ]
    return "\n".join(lines)


def _index_blocks(bundle, items, clusters, spec_version, bundle_version, generated_at):
    blocks = ["# %s" % _one_line(bundle["title"]),
              _header(bundle, spec_version, bundle_version, generated_at),
              "> %s" % _one_line(bundle.get("description", ""))]
    order = []
    for title, members in sections(items, clusters):
        lines = ["## %s" % _one_line(title), ""]
        for item in members:
            order.append(item)
            label = _one_line(item.get("description") or item.get("title", ""))
            lines.append("- [%s](%s): %s" % (_one_line(item.get("title", "")),
                                             item_iri(bundle["base"], item), label))
        blocks.append("\n".join(lines))
    return blocks, order


def llms_txt(bundle, items, clusters=None, spec_version="", bundle_version="",
             generated_at=""):
    blocks, _ = _index_blocks(bundle, items, clusters, spec_version, bundle_version,
                              generated_at)
    return "\n\n".join(blocks) + "\n"


def llms_full_txt(bundle, items, clusters=None, spec_version="", bundle_version="",
                  generated_at=""):
    blocks, order = _index_blocks(bundle, items, clusters, spec_version, bundle_version,
                                  generated_at)
    for item in order:
        body = (item.get("body") or "").rstrip("\n") + "\n"
        blocks.append("## %s\n<!-- agsc:item %s -->\n```text agsc-content\n%s```"
                      % (_one_line(item.get("title", "")), item_iri(bundle["base"], item), body))
    return "\n\n".join(blocks) + "\n"


def reachability(text):
    """{item IRI: section title} read back from an llms file's index blocks."""
    out = {}
    section = None
    for line in text.split("\n"):
        if line.startswith("## "):
            section = line[3:]
        elif line.startswith("- [") and section is not None:
            target = line.split("](", 1)[1].split("): ", 1)[0]
            out.setdefault(target, section)
    return out


# --- sitemap (AGSC-06-19) ------------------------------------------------------

def sitemap_entries(base, routes, build_instant):
    """[(url, lastmod)] ordered by URL (code point), one lastmod: the build instant."""
    urls = sorted(set(_base(base) + route for route in routes))
    return [(url, build_instant) for url in urls]


def sitemap_xml(base, routes, build_instant):
    """One rendering of the sitemap; no rule pins these bytes (AGSC-06-19)."""
    def escape(text):
        return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    rows = "".join("  <url><loc>%s</loc><lastmod>%s</lastmod></url>\n" % (escape(url), when)
                   for url, when in sitemap_entries(base, routes, build_instant))
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n%s</urlset>\n' % rows)


# --- robots (AGSC-06-18) -------------------------------------------------------

def robots_groups(tdm_crawlers, tdm_reservation):
    """(groups, findings): one Disallow group per token, in order, then ``*``."""
    findings = []
    if tdm_reservation == 1 and not tdm_crawlers:
        findings.append({"code": "AGSC-E202", "severity": "error",
                         "message": "tdm-reservation 1 with an empty site.tdm_crawlers[]"})
    groups = [{"disallow": ["/"], "user_agent": token} for token in tdm_crawlers]
    groups.append({"allow": ["/"], "disallow": [], "user_agent": "*"})
    return groups, findings


def robots_txt(groups):
    """One rendering of the groups; no rule pins the file's bytes."""
    out = []
    for group in groups:
        lines = ["User-agent: %s" % group["user_agent"]]
        lines.extend("Allow: %s" % one for one in group.get("allow", []))
        lines.extend("Disallow: %s" % one for one in group.get("disallow", []))
        out.append("\n".join(lines))
    return "\n\n".join(out) + "\n"


# --- the link set (AGSC-06-08) ------------------------------------------------

def digest(data):
    """RFC 9530 ``sha-256`` as an RFC 9651 Byte Sequence."""
    raw = data.encode("utf-8") if isinstance(data, str) else data
    return "sha-256=:%s:" % base64.b64encode(hashlib.sha256(raw).digest()).decode("ascii")


def linkset(base, level=2, artefacts=None, facts=None, peers=(), restricted=False):
    """The discovery document for one node, as a value.

    ``artefacts`` maps a route (``/graph.jsonld`` …) to its bytes; ``facts`` holds
    ``spec_version``, ``generated_at``, ``counts``, ``bundle_hash``,
    ``bundle_version`` and ``ledger_head``.  Level 0 omits every digest and every
    ``agsc-*`` attribute (AGSC-06-08a); a restricted node omits the four of
    AGSC-11-20 and carries ``agsc-visibility``.
    """
    root = _base(base)
    artefacts = artefacts or {}
    facts = facts or {}
    full = level >= 2

    def target(route, media_type, attributes=None):
        link = {"href": root + route, "type": media_type}
        if full and not restricted:
            link["digest"] = [digest(artefacts.get(route, b""))]
        for name, value in (attributes or {}).items():
            if value is not None:
                link[name] = value if isinstance(value, list) else [value]
        return link

    described = {}
    if full:
        described = {"agsc-generated-at": facts.get("generated_at"),
                     "agsc-spec-version": facts.get("spec_version")}
        if not restricted:
            described.update({"agsc-bundle-hash": facts.get("bundle_hash"),
                              "agsc-bundle-version": facts.get("bundle_version"),
                              "agsc-counts": facts.get("counts")})
    if restricted:
        described["agsc-visibility"] = "restricted"
    context = {
        "alternate": [target("/llms.txt", "text/plain")],
        "anchor": root + "/",
        "describedby": [target("/graph.jsonld", "application/ld+json", described)],
        "license": [{"href": root + "/legal/"}],
        "service-doc": [{"href": root + "/specs/"}],
        REL_BASE + "graph": [target("/graph.nq", "application/n-quads"),
                             target("/graph.ttl", "text/turtle")],
    }
    if full:
        ledger = {"href": root + "/ledger.jsonl", "type": "application/jsonl"}
        if not restricted:
            ledger["digest"] = [digest(artefacts.get("/ledger.jsonl", b""))]
            ledger["agsc-ledger-head"] = [facts.get("ledger_head")]
        context[REL_BASE + "ledger"] = [ledger]
    if peers:
        context[REL_BASE + "peer"] = [{"href": one} for one in sorted(peers)]
    return {"linkset": [context]}


def linkset_bytes(document):
    """JCS plus one LF (AGSC-04-04)."""
    return canonicalize(document) + "\n"
