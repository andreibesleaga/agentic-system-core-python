"""The two AI-catalogue files a node may write, opt-in (AGSC-06-42).

The twin of the engine's ``src/distribution/ai-catalog.js``: ``/.well-known/ard.json``
and ``/.well-known/ai-catalog.json``, written only when ``discovery.ai_catalog`` is
``true``, with one entry for the discovery document and, when the node publishes one,
one for the agent card.  Each entry carries the SHA-256 of the exact bytes served at
its ``url``, and its identifier is a ``urn:air`` name built from the host of
``site.base``, which must be a fully qualified domain name (vectors disc-0028,
disc-0029).

Both formats are proposals (the Agentic Resource Discovery manifest 0.91 and the AI
Catalog draft ``specVersion`` "1.0"); no library on PyPI writes either, as none does on
npm, so the entries are plain data and the bytes are this package's JCS writer.
Pure: data in, text out.  Standard library only.
"""

import hashlib
import re
from urllib.parse import urlsplit

from . import MEDIA_TYPE, PROFILE_URI, WELLKNOWN_PATH
from .diagnostics import finding
from .jcs import canonicalize
from .signposting import href

ARD_PATH = "/.well-known/ard.json"
AI_CATALOG_PATH = "/.well-known/ai-catalog.json"
#: AGSC-06-42: the media types the two files are served with.
ARD_MEDIA_TYPE = "application/json"
AI_CATALOG_MEDIA_TYPE = "application/ai-catalog+json"
#: AGSC-06-42: the ``specVersion`` of the AI Catalog draft.
AI_CATALOG_SPEC_VERSION = "1.0"
#: AGSC-06-34: the agent card's route and media type (the engine's ``surfaces.js``).
A2A_CARD_ROUTE = "/.well-known/agent-card.json"
A2A_CARD_MEDIA_TYPE = "application/a2a-agent-card+json"

#: WHATWG URL: a host whose last label is a number is an IPv4 address (decimal, octal or
#: hexadecimal parts), which the engine's URL parser writes as four decimals.
_NUMERIC_LABEL = re.compile(r"^(?:\d+|0[xX][0-9A-Fa-f]*)$")


def hex_digest(text):
    """AGSC-06-42: ``sha256:`` and the lowercase hexadecimal SHA-256 of the served bytes."""
    return "sha256:" + hashlib.sha256(str(text).encode("utf-8")).hexdigest()


def domain_name(base):
    """AGSC-06-42: the host of ``site.base``, lower case and without a port, when it is
    a fully qualified domain name (at least one ``.``, not an IP literal, not under
    ``.local``); else None."""
    try:
        parts = urlsplit(str(base))
        host = (parts.hostname or "").lower()
    except ValueError:
        return None
    if parts.scheme == "" or host == "" or "[" in parts.netloc:
        return None
    bare = host[:-1] if host.endswith(".") else host
    if "." not in bare or _NUMERIC_LABEL.match(bare.rsplit(".", 1)[-1]) or bare.endswith(".local"):
        return None
    return host


def _entry(fields, digest_member):
    out = {"displayName": fields["displayName"], "identifier": fields["identifier"],
           "type": fields["type"], "url": fields["url"]}
    description = fields.get("description")
    if isinstance(description, str) and description != "":
        out["description"] = description
    # AGSC-06-42: `digest` in the AI Catalog draft's form; ARD names it in `metadata`.
    if digest_member == "digest":
        out["digest"] = fields["digest"]
    else:
        out["metadata"] = {"digest": fields["digest"]}
    return out


def _refused(code, message):
    return {}, [finding(code, "agsc.config.json", message)]


def catalogue_files(config, discovery_bytes, card_bytes=None, description=None):
    """The two catalogue files of AGSC-06-42 as (route -> text, findings): none when the
    switch is off, and none when a finding refuses them.  ``discovery_bytes`` and
    ``card_bytes`` are the exact texts served at the two entries' ``url``."""
    if (config.get("discovery") or {}).get("ai_catalog") is not True:
        return {}, []
    site = config.get("site") or {}
    host = domain_name(site.get("base"))
    identifier = (config.get("bundle") or {}).get("id")
    if host is None:
        return _refused("AGSC-E209", "discovery.ai_catalog is true, but the host of site.base %s "
                                     "is not a fully qualified domain name, which a urn:air "
                                     "identifier needs; no catalogue file is written (AGSC-06-42)"
                        % canonicalize(str(site.get("base"))))
    if not isinstance(identifier, str) or identifier == "":
        return _refused("AGSC-E202", "discovery.ai_catalog is true, but bundle.id is not set; no "
                                     "catalogue file is written (AGSC-06-42)")
    common = {"description": description, "displayName": site.get("title")}
    listed = [dict(common, digest=hex_digest(discovery_bytes),
                   identifier="urn:air:%s:knowledge:%s" % (host, identifier),
                   type='%s; profile="%s"' % (MEDIA_TYPE, PROFILE_URI),
                   url=href(site.get("base"), WELLKNOWN_PATH))]
    if isinstance(card_bytes, str):
        listed.append(dict(common, digest=hex_digest(card_bytes),
                           identifier="urn:air:%s:a2a:%s" % (host, identifier),
                           type=A2A_CARD_MEDIA_TYPE, url=href(site.get("base"), A2A_CARD_ROUTE)))
    listed.sort(key=lambda one: one["identifier"])  # code-point order, as the engine sorts
    # AGSC-06-42: `representativeQueries` is never written; it would have to be invented.
    ard = canonicalize({"entries": [_entry(one, "metadata") for one in listed]}) + "\n"
    catalogue = canonicalize({"entries": [_entry(one, "digest") for one in listed],
                              "specVersion": AI_CATALOG_SPEC_VERSION}) + "\n"
    return {ARD_PATH: ard, AI_CATALOG_PATH: catalogue}, []
