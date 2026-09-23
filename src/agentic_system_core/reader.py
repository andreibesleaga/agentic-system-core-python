"""A small reading API for a published node: the discovery file, its links, its
digests, its chunk export and its graph.

Three properties, on purpose:

* **It fetches nothing.**  Every call that would need a network takes a
  ``fetcher`` callable from you.  Nothing in this module opens a connection, so
  a program that never passes a fetcher can never make a request.
* **No RDF library.**  ``graph.jsonld`` is read as JSON, which is all a JSON-LD
  document is; turning it into triples is a job for a library you choose.
* **Digests are checked against bytes you already hold.**  A digest attribute is
  an RFC 9530 dictionary member.  RFC 9530 says of ``Content-Digest`` that each
  "value is a Byte Sequence (Section 3.3.5 of [STRUCTURED-FIELDS]) that conveys
  an encoded version of the byte output produced by the digest calculation"
  (https://www.rfc-editor.org/rfc/rfc9530.html), and RFC 9651 writes a Byte
  Sequence as base64 between two colons — which is why the value reads
  ``sha-256=:d435Qo+nKZ+gLcUHn7GQtQ72hiBVAgqoLsZnZPiTGPk=:``, the example that
  same document gives.

Standard library only.
"""

import base64
import binascii
import hashlib
import json
import os
import re

from . import REL_BASE, WELLKNOWN_SUFFIX
from .jcs import parse_ijson
from .urls import resolve

_DIGEST = re.compile(r"^sha-256=:([A-Za-z0-9+/]+=*):$")


class DiscoveryError(ValueError):
    """The document is not a discovery document this API can read."""


def relation(name):
    """The full extension relation URI for a short name, such as ``graph``."""
    return REL_BASE + name


class Link(object):
    """One target of one relation: its href and its RFC 9264 attributes."""

    __slots__ = ("relation", "href", "attributes")

    def __init__(self, relation_name, href, attributes):
        self.relation = relation_name
        self.href = href
        self.attributes = attributes

    @property
    def type(self):
        """The media type the document declares for the target, or None."""
        value = self.attributes.get("type")
        return value if isinstance(value, str) else None

    @property
    def digest(self):
        """The digest attribute as the single string it must be, or None."""
        value = self.attributes.get("digest")
        if isinstance(value, list) and len(value) == 1 and isinstance(value[0], str):
            return value[0]
        return None

    def attribute(self, name, default=None):
        """One attribute's value, unwrapped when it is a single-item array."""
        if name not in self.attributes:
            return default
        value = self.attributes[name]
        if isinstance(value, list) and len(value) == 1:
            return value[0]
        return value

    def verify(self, data):
        """True when the bytes you hold hash to this link's declared digest."""
        return verify_digest(self.digest, data)

    def fetch(self, fetcher):
        """Fetch this target with the callable you supply.  Nothing else fetches."""
        if fetcher is None:
            raise DiscoveryError("no fetcher was given; this API never opens a connection by itself")
        return fetcher(self.href)

    def __repr__(self):  # pragma: no cover - debugging aid only
        return "Link(%r, %r)" % (self.relation, self.href)


class DiscoveryDocument(object):
    """A parsed ``/.well-known/knowledge-linkset``."""

    def __init__(self, document):
        if not isinstance(document, dict) or not isinstance(document.get("linkset"), list) \
                or len(document["linkset"]) != 1 or not isinstance(document["linkset"][0], dict):
            raise DiscoveryError("not a link set with exactly one link context (AGSC-06-08)")
        self.document = document
        self.context = document["linkset"][0]
        anchor = self.context.get("anchor")
        if not isinstance(anchor, str):
            raise DiscoveryError("the link context carries no anchor (AGSC-05-03)")
        self.anchor = anchor

    @classmethod
    def from_bytes(cls, data):
        """Read a document from its served bytes, strictly (no duplicate members)."""
        if isinstance(data, bytes):
            data = data.decode("utf-8")
        return cls(parse_ijson(data))

    @classmethod
    def from_path(cls, path):
        """Read a document from a file on disk."""
        with open(path, "rb") as handle:
            return cls.from_bytes(handle.read())

    @property
    def wellknown_url(self):
        """Where this node's discovery document is served (AGSC-06-07)."""
        return resolve(self.anchor, ".well-known/" + WELLKNOWN_SUFFIX)

    def relations(self):
        """Every relation name the document uses, in document order."""
        return [name for name in self.context if name != "anchor"]

    def links(self, relation_name=None):
        """The links of one relation, or of every relation when none is named.

        A short extension name such as ``graph`` is accepted and expanded to its
        relation URI, so a caller need not spell the URI out.
        """
        if relation_name is None:
            names = self.relations()
        else:
            names = [relation_name]
            if relation_name not in self.context and relation(relation_name) in self.context:
                names = [relation(relation_name)]
        out = []
        for name in names:
            targets = self.context.get(name)
            if not isinstance(targets, list):
                continue
            for target in targets:
                if not isinstance(target, dict) or not isinstance(target.get("href"), str):
                    continue
                attributes = {key: target[key] for key in target if key != "href"}
                out.append(Link(name, target["href"], attributes))
        return out

    def peers(self):
        """The discovery documents this node names as peers (AGSC-10-12)."""
        return [one.href for one in self.links("peer")]

    def surfaces(self):
        """The declared surfaces, as name -> link (AGSC-11-16)."""
        out = {}
        for one in self.links("surface"):
            name = one.attribute("agsc-surface")
            if isinstance(name, str):
                out[name] = one
        return out


def verify_digest(declared, data):
    """True when ``data`` hashes to the declared ``sha-256=:<base64>:`` value."""
    if not isinstance(declared, str):
        return False
    match = _DIGEST.match(declared)
    if match is None:
        return False
    try:
        expected = base64.b64decode(match.group(1), validate=True)
    except (binascii.Error, ValueError):
        return False
    return hashlib.sha256(data).digest() == expected


def digest_of(data):
    """The ``sha-256=:<base64>:`` form of some bytes, as a document must carry it."""
    return "sha-256=:%s:" % base64.b64encode(hashlib.sha256(data).digest()).decode("ascii")


def read_chunks(data):
    """Read ``chunks.jsonl`` into a list of records (AGSC-06-26).

    When the file is the shard manifest of AGSC-06-31 — an object with
    ``shards`` and ``lines_total`` rather than one record per line — the manifest
    is returned as it stands, so the caller can fetch the shards it names and
    read each one with this same function.
    """
    if isinstance(data, bytes):
        data = data.decode("utf-8")
    stripped = data.strip()
    if stripped.startswith("{") and '"shards"' in stripped and "\n" not in stripped:
        manifest = json.loads(stripped)
        if isinstance(manifest, dict) and isinstance(manifest.get("shards"), list):
            return manifest
    out = []
    for number, line in enumerate(data.split("\n"), start=1):
        if line == "":
            continue
        try:
            out.append(json.loads(line))
        except ValueError as error:
            raise DiscoveryError("chunks.jsonl line %d is not JSON: %s" % (number, error))
    return out


def read_chunks_path(path):
    """Read a ``chunks.jsonl`` file from disk."""
    with open(path, "rb") as handle:
        return read_chunks(handle.read())


def read_graph(data):
    """Read ``graph.jsonld`` as plain JSON.  No RDF library, no triples."""
    if isinstance(data, bytes):
        data = data.decode("utf-8")
    return json.loads(data)


def read_graph_path(path):
    """Read a ``graph.jsonld`` file from disk."""
    with open(path, "rb") as handle:
        return read_graph(handle.read())


def local_path_for(document, href, site_root):
    """Where a same-origin target of the document lives inside a build output.

    Returns None when the target is not same-origin, because then nothing on
    this disk can answer for it.
    """
    from .urls import Url, decoded_path
    target = Url(href)
    base = Url(document.anchor)
    if target.origin != base.origin:
        return None
    path = decoded_path(target)
    if path.endswith("/"):
        path += "index.html"
    candidate = os.path.normpath(os.path.join(site_root, "." + path))
    root = os.path.abspath(site_root)
    if not candidate.startswith(root + os.sep):
        return None
    return candidate
