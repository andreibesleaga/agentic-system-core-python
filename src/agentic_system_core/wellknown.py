"""The discovery-file checker: the Python twin of the engine's validate-wellknown.

It reads one document served at ``/.well-known/knowledge-linkset`` and checks it
against AGSC-06-07 to AGSC-06-10, AGSC-06-08a, AGSC-06-35 and AGSC-11-16, and,
when a second document is given, the mutual check of AGSC-10-12.  The output is
the AGSC-09-11 envelope; the exit code is 0 for a pass, 1 for a fail and 2 for a
usage fault.

Levels mean what AGSC-10-02 to AGSC-10-05 say they mean.  At Level 0 and 1 the
shape, the relation names, the ordering and the digest form are checked; at
Level 2 and above the document must additionally be canonical bytes, every
artefact link must carry a digest, and the extra attributes of AGSC-06-08 must
be present.  When the document is read from a file, the digests are verified
against the bytes on disk, because a build output can be checked with no
network at all.

Error codes.  Section 9.4 of the specification names no dedicated code for
these shape checks, so this checker uses the same code for the same fault as the
Node tool does, under the precedence paragraph: AGSC-E201 for document shape,
media type and order; AGSC-E202 for a missing REQUIRED attribute; AGSC-E204 for
a malformed digest; AGSC-E209 for a relation outside AGSC-06-10/06-35;
AGSC-E210 for a surface declaration that disagrees with the node; AGSC-E601 for
non-canonical bytes at Level 2 and above; AGSC-E901/E902/E904/E905/E907 for
input and transport faults.

Standard library only.
"""

import base64
import hashlib
import json
import os
import re

from . import MEDIA_TYPE, PROFILE_URI, REL_BASE, WELLKNOWN_SUFFIX
from .diagnostics import envelope, finding
from .jcs import canonicalize_raw, compare_utf16, parse_ijson, utf16_key
from .net import MAX_BYTES, TransportError
from .urls import Url, decoded_path, is_url_argument, resolve

VERB = "validate-wellknown"

#: AGSC-06-10 plus AGSC-06-35: the registered relation names a document may use.
REGISTERED = frozenset([
    "alternate", "author", "cite-as", "collection", "describedby", "item", "license",
    "related", "service-desc", "service-doc", "service-meta",
])
#: AGSC-06-35: the related-system relations that MUST carry a media type.
RELATED_ONLY = frozenset(["cite-as", "related", "service-desc", "service-meta", "collection",
                          "item"])
#: AGSC-06-10: the extension relation names, used as REL_BASE + name.
EXTENSIONS = frozenset([
    "graph", "ontology", "context", "now", "skills", "ledger", "peer",
    "surface", "contribute", "access",
])
#: RFC 9264 section 4.2.4.2: the target attributes whose value is a plain string.
STRING_ATTRIBUTES = frozenset(["type", "title", "media"])
#: AGSC-06-08 as amended at rc.6 (D113): the attributes the graph link carries at
#: Level 2 and above, `agsc-bundle-version` among them.
LEVEL2_ATTRIBUTES = ("agsc-bundle-hash", "agsc-bundle-version", "agsc-counts",
                     "agsc-generated-at", "agsc-spec-version")
#: AGSC-11-20: what a restricted node must omit, and what it must still carry.
RESTRICTED_FORBIDDEN = ("agsc-bundle-hash", "agsc-bundle-version", "agsc-counts",
                        "agsc-ledger-head")
RESTRICTED_REQUIRED = ("agsc-generated-at", "agsc-spec-version")
#: AGSC-11-16: the surface names a node may declare.
SURFACES = frozenset(["llms-txt", "chunks", "mcp", "webmcp", "a2a-card", "solid", "responder"])
SURFACE_NEEDS_VERSION = frozenset(["mcp", "webmcp", "a2a-card", "solid", "responder"])
#: AGSC-11-16: the access classes.
ACCESS = frozenset(["none", "consent", "credential"])

_PRIVATE_SURFACE = re.compile(r"^x-[a-z0-9]+(-[a-z0-9]+)+$")
_DIGEST = re.compile(r"^sha-256=:[A-Za-z0-9+/]{43}=:$")
_PARAMETER = re.compile(r';\s*([A-Za-z0-9!#$&^_.+\-]+)\s*=\s*("(?:[^"\\]|\\.)*"|[^;]*)')
_LINK_HEADER = re.compile(r"^\s*<([^>]*)>(.*)$")
_LINK_REL = re.compile(r';\s*rel\s*=\s*(?:"([^"]*)"|([^;\s]+))', re.IGNORECASE)


def _compact(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


class Source(object):
    """One document to check, with the way its targets are resolved."""

    def __init__(self, kind, name, data, headers=None, site_root=None, fetcher=None, dev=False):
        self.kind = kind
        self.name = name
        self.data = data
        self.headers = headers
        self.site_root = site_root
        self.fetcher = fetcher
        self.dev = dev
        self.reads = 1

    def resolve_target(self, href, anchor):
        """The bytes of one target, or None when it cannot be checked offline."""
        if self.kind == "memory":
            # An in-memory document has no site beside it: every digest target is
            # "not checkable offline", never an I/O error.
            return None
        if self.kind == "url":
            self.reads += 1
            return self.fetcher(href, self.dev)[2]
        if self.site_root is None:
            raise TransportError(
                "AGSC-E901",
                "file is not inside a .well-known/ directory; targets cannot be resolved",
            )
        target = Url(href)
        base = Url(anchor)
        if target.origin != base.origin:
            return None
        path = decoded_path(target)
        if path.endswith("/"):
            path += "index.html"
        candidate = os.path.normpath(os.path.join(self.site_root, "." + path))
        if not candidate.startswith(self.site_root + os.sep):
            raise TransportError("AGSC-E902", "path escapes the site root: %s" % href)
        if not os.path.exists(candidate):
            raise TransportError("AGSC-E901", "target not found on disk: %s" % path)
        self.reads += 1
        with open(candidate, "rb") as handle:
            return handle.read()


def from_value(document, name="(memory)"):
    """An in-memory source; a value is written in its canonical form plus one LF."""
    if isinstance(document, (bytes, bytearray)):
        data = bytes(document)
    else:
        data = (canonicalize_raw(document) + "\n").encode("utf-8")
    return Source("memory", name, data)


def load(target, allow_network=False, fetcher=None, dev=False):
    """Open a document, from a file always and from a URL only when allowed."""
    if is_url_argument(target):
        if not allow_network:
            raise TransportError(
                "AGSC-E905",
                "reading a URL needs --allow-network; this package never opens a connection "
                "unless the command line says so",
            )
        if fetcher is None:  # pragma: no cover - the CLI always supplies one
            from .net import fetch as fetcher  # noqa: F811
        final, headers, body = fetcher(target, dev)
        return Source("url", target, body, headers=headers, fetcher=fetcher, dev=dev)
    path = os.path.abspath(target)
    if not os.path.isfile(path):
        raise TransportError("AGSC-E901", "file not found: %s" % target)
    if os.path.getsize(path) > MAX_BYTES:
        raise TransportError("AGSC-E904", "file exceeds 1 MiB")
    directory = os.path.dirname(path)
    site_root = os.path.dirname(directory) if os.path.basename(directory) == ".well-known" else None
    with open(path, "rb") as handle:
        data = handle.read()
    return Source("file", target, data, site_root=site_root)


def _media_type_state(headers):
    """Whether the served media type and profile satisfy AGSC-06-07."""
    if headers is None:
        return {"checked": False}
    content_type = str(headers.get("content-type", ""))
    essence = content_type.split(";")[0].strip().lower()
    parameters = {}
    for match in _PARAMETER.finditer(content_type):
        value = match.group(2).strip()
        if value.startswith('"'):
            value = re.sub(r"\\(.)", r"\1", value[1:-1])
        parameters[match.group(1).lower()] = value
    by_parameter = essence == MEDIA_TYPE and PROFILE_URI in parameters.get("profile", "").split()
    link_header = headers.get("link", "")
    if isinstance(link_header, (list, tuple)):
        link_header = ",".join(link_header)
    by_link = False
    for part in re.split(r",(?=\s*<)", link_header):
        match = _LINK_HEADER.match(part)
        if match is None:
            continue
        relation = _LINK_REL.search(match.group(2))
        if match.group(1) == PROFILE_URI and relation is not None:
            names = (relation.group(1) or relation.group(2)).split()
            if "profile" in names:
                by_link = True
    return {"checked": True, "essence": essence, "ok": by_parameter or by_link}


def check(source, level, findings, dev=False):
    """Check one document, appending findings.  Returns the anchor and the peers."""

    def report(code, message, severity="error"):
        findings.append(finding(code, source.name, message, severity=severity))

    media = _media_type_state(source.headers)
    if media["checked"] and not media["ok"]:
        report(
            "AGSC-E201",
            'media type is "%s" and no profile is carried: need %s with profile="%s", or a Link '
            'header with rel="profile" (AGSC-06-07)' % (media["essence"], MEDIA_TYPE, PROFILE_URI),
        )
    if media["checked"] and media["ok"] and media["essence"] != MEDIA_TYPE:
        report("AGSC-E201", 'media type "%s" is not %s (AGSC-06-07)' % (media["essence"], MEDIA_TYPE))

    try:
        text = source.data.decode("utf-8")
    except UnicodeDecodeError:
        report("AGSC-E201", "document is not valid UTF-8")
        return None
    try:
        document = parse_ijson(text)
    except ValueError as error:
        report("AGSC-E201", "not I-JSON: %s" % error)
        return None
    if level >= 2 and text != canonicalize_raw(document) + "\n":
        report(
            "AGSC-E601",
            "document is not JCS-canonical with exactly one trailing LF (AGSC-04-04, AGSC-06-08)",
        )
    if not isinstance(document, dict):
        report("AGSC-E201", "document is not a JSON object")
        return None
    top = list(document.keys())
    if len(top) != 1 or top[0] != "linkset":
        report(
            "AGSC-E201",
            '"linkset" must be the sole top-level member; found %s (AGSC-06-08, RFC 9264 '
            "section 4.2.1)" % _compact(top),
        )
        if not isinstance(document.get("linkset"), list):
            return None
    linkset = document.get("linkset")
    if not isinstance(linkset, list) or len(linkset) != 1:
        report("AGSC-E201", "linkset must be an array holding exactly one link context object "
                            "(AGSC-06-08)")
        if not isinstance(linkset, list) or not linkset:
            return None
    context = linkset[0]
    if not isinstance(context, dict):
        report("AGSC-E201", "link context is not an object")
        return None
    raw_anchor = context.get("anchor")
    anchor = None
    if isinstance(raw_anchor, str):
        try:
            anchor = Url(raw_anchor)
        except ValueError:
            anchor = None
        if anchor is not None:
            allowed = anchor.scheme == "https" or (dev and anchor.scheme == "http")
            if not allowed or not raw_anchor.endswith("/"):
                anchor = None
    if anchor is None:
        report(
            "AGSC-E201",
            'anchor must be the absolute https Bundle IRI ending in "/" (AGSC-05-03); got %s'
            % _compact(raw_anchor),
        )
        return None

    keys = list(context.keys())
    if keys != sorted(keys, key=utf16_key):
        report(
            "AGSC-E201",
            "link context members are not ordered as JSON member names (AGSC-06-08, AGSC-04-05)",
        )

    restricted = _is_restricted(context)
    peers = []
    for relation in [name for name in keys if name != "anchor"]:
        extension = relation[len(REL_BASE):] if relation.startswith(REL_BASE) else None
        if relation not in REGISTERED and not (extension is not None and extension in EXTENSIONS):
            report(
                "AGSC-E209",
                "relation %s is neither a registered name of AGSC-06-10/06-35 nor a "
                ".../rel#<name> extension URI" % _compact(relation),
            )
        targets = context[relation]
        if not isinstance(targets, list) or not targets:
            report(
                "AGSC-E201",
                "relation %s: value must be a non-empty array of target objects "
                "(RFC 9264 section 4.2.2)" % relation,
            )
            continue
        previous = None
        for target in targets:
            if not isinstance(target, dict) or not isinstance(target.get("href"), str):
                report("AGSC-E201",
                       "relation %s: every target is an object with a string href" % relation)
                continue
            href = target["href"]
            try:
                parsed = Url(href)
            except ValueError:
                report("AGSC-E201", "relation %s: href %s is not absolute (AGSC-06-10)"
                       % (relation, _compact(href)))
                continue
            if previous is not None and compare_utf16(previous, href) >= 0:
                report("AGSC-E201",
                       "relation %s: targets are not ordered by href code point (AGSC-06-10)"
                       % relation)
            previous = href
            for name in target:
                if name == "href":
                    continue
                value = target[name]
                if name in STRING_ATTRIBUTES:
                    if not isinstance(value, str):
                        report("AGSC-E201",
                               "relation %s: target attribute %s must be a string "
                               "(RFC 9264 section 4.2.4.2)" % (relation, name))
                elif name == "title*":
                    if not isinstance(value, list):
                        report("AGSC-E201",
                               "relation %s: title* must be an array "
                               "(RFC 9264 section 4.2.4.2)" % relation)
                elif (not isinstance(value, list) or not value
                      or not all(isinstance(one, str) for one in value)):
                    report("AGSC-E201",
                           "relation %s: target attribute %s must be a non-empty array of "
                           "strings (AGSC-06-10)" % (relation, name))
            same_origin = parsed.origin == anchor.origin
            artefact = (
                same_origin
                and not parsed.pathname.endswith("/")
                and relation not in ("license", "service-doc")
                and extension not in ("surface", "peer")
            )
            digest = target.get("digest")
            if "digest" in target:
                if (not isinstance(digest, list) or len(digest) != 1
                        or not isinstance(digest[0], str) or _DIGEST.match(digest[0]) is None):
                    report("AGSC-E204",
                           'relation %s: digest must be one "sha-256=:<base64>:" string '
                           "(AGSC-06-08, RFC 9530, RFC 9651)" % relation)
                elif level >= 2 or source.kind == "file":
                    try:
                        data = source.resolve_target(href, raw_anchor)
                        if data is not None:
                            actual = "sha-256=:%s:" % base64.b64encode(
                                hashlib.sha256(data).digest()).decode("ascii")
                            if actual != digest[0]:
                                report("AGSC-E201",
                                       "relation %s: digest does not match the bytes of %s"
                                       % (relation, href))
                    except TransportError as error:
                        report(error.code, "relation %s: %s" % (relation, error.message))
            elif level >= 2 and artefact and not restricted:
                report("AGSC-E202",
                       "relation %s: artefact link %s carries no digest (required at Level >= 2, "
                       "AGSC-06-08a)" % (relation, href))
            if restricted:
                for name in RESTRICTED_FORBIDDEN:
                    if name in target:
                        report("AGSC-E210",
                               "relation %s: %s is forbidden on a restricted node "
                               "(AGSC-11-20, AGSC-09-93)" % (relation, name))
            is_graph = relation == "describedby" and parsed.pathname.endswith("/graph.jsonld")
            if level >= 2 and is_graph:
                for name in (RESTRICTED_REQUIRED if restricted else LEVEL2_ATTRIBUTES):
                    if name not in target:
                        report("AGSC-E202",
                               "describedby %s: %s is required at Level >= 2 (AGSC-06-08)"
                               % (href, name))
            if level >= 2 and extension == "ledger" and not restricted \
                    and "agsc-ledger-head" not in target:
                report("AGSC-E202",
                       "rel#ledger: agsc-ledger-head is required at Level >= 2 (AGSC-06-08)")
            if relation in RELATED_ONLY and not isinstance(target.get("type"), str):
                report("AGSC-E209",
                       "related-system link %s %s must carry type (AGSC-06-35)" % (relation, href))
            if extension == "peer":
                peers.append(href)
            if extension == "surface":
                _check_surface(target, href, parsed, raw_anchor, source, report)

    return {"anchor": raw_anchor, "peers": peers}


def _is_restricted(context):
    """AGSC-11-20: ``agsc-visibility: ["restricted"]`` on the anchor's describedby link."""
    targets = context.get("describedby")
    if not isinstance(targets, list):
        return False
    return any(isinstance(one, dict) and one.get("agsc-visibility") == ["restricted"]
               for one in targets)


def _check_surface(target, href, parsed, anchor, source, report):
    """The AGSC-11-16 declaration checks for one rel#surface target."""
    declared = target.get("agsc-surface")
    access = target.get("agsc-access")
    version = target.get("agsc-surface-version")
    name = declared[0] if isinstance(declared, list) and len(declared) == 1 else None
    if name is None:
        report("AGSC-E210",
               "rel#surface %s: agsc-surface must carry exactly one value (AGSC-11-16)" % href)
    elif name not in SURFACES and _PRIVATE_SURFACE.match(name) is None:
        report("AGSC-E210",
               "rel#surface %s: unknown surface %s (AGSC-11-16; a reader treats it as not served, "
               "AGSC-11-02)" % (href, _compact(name)), severity="warn")
    if not (isinstance(access, list) and len(access) == 1):
        report("AGSC-E210",
               "rel#surface %s: agsc-access must carry exactly one value (AGSC-11-16)" % href)
    elif access[0] not in ACCESS:
        report("AGSC-E210",
               "rel#surface %s: unknown access class %s (read as credential, AGSC-11-02)"
               % (href, _compact(access[0])), severity="warn")
    if name in SURFACE_NEEDS_VERSION and not (isinstance(version, list) and len(version) == 1):
        report("AGSC-E210",
               "rel#surface %s: agsc-surface-version is required for %s (AGSC-11-16)" % (href, name))
    if name in ("llms-txt", "chunks") and version is not None:
        report("AGSC-E210",
               "rel#surface %s: agsc-surface-version must be absent for %s (AGSC-11-16)"
               % (href, name))
    if name == "llms-txt" and parsed.pathname != "/llms.txt" \
            and not parsed.pathname.endswith("/llms.txt"):
        report("AGSC-E210", "rel#surface llms-txt must target /llms.txt (AGSC-11-16)")
    if name in ("llms-txt", "chunks"):
        try:
            source.resolve_target(href, anchor)
        except TransportError as error:
            report("AGSC-E210",
                   "rel#surface %s: target does not resolve: %s" % (name, error.message))


def canonical_wellknown(result):
    """The canonical well-known URL of a checked document's node."""
    return resolve(result["anchor"], ".well-known/" + WELLKNOWN_SUFFIX)


def mutual_findings(first_name, first, second_name, second):
    """AGSC-10-12: each of two checked documents names the other under rel#peer."""
    out = []
    if canonical_wellknown(second) not in first["peers"]:
        out.append(finding(
            "AGSC-E907", first_name,
            "resolved, not mutual: no rel#peer names %s (AGSC-10-12)"
            % canonical_wellknown(second)))
    if canonical_wellknown(first) not in second["peers"]:
        out.append(finding(
            "AGSC-E907", second_name,
            "resolved, not mutual: no rel#peer names %s (AGSC-10-12)"
            % canonical_wellknown(first)))
    return out


def validate(target, level=0, peer=None, dev=False, allow_network=False, fetcher=None):
    """Check one document, and a peer when given.  Returns (envelope, files read)."""
    findings = []
    reads = [0]

    def run(name):
        try:
            source = load(name, allow_network=allow_network, fetcher=fetcher, dev=dev)
        except TransportError as error:
            reads[0] += 1
            findings.append(finding(error.code, name, error.message))
            return None, None
        result = check(source, level, findings, dev=dev)
        reads[0] += source.reads
        return source, result

    _, first = run(target)
    if peer is not None:
        _, second = run(peer)

        if first is not None and second is not None:
            findings.extend(mutual_findings(target, first, peer, second))
        elif not findings:  # pragma: no cover - a document that yields no result
            # always reports why, so this guard can only fire if that ever stops
            # being true; it is kept so the run can never end silently.
            findings.append(finding(
                "AGSC-E907", peer, "peer check could not run: a document is invalid"))
    return envelope(findings, VERB), reads[0]
