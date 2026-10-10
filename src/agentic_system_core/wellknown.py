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

Given a URL, the response headers of the rules on cross-origin reading
(AGSC-11-03) and caching (AGSC-11-05) are also checked, on the document and on
every same-origin public artefact the run fetches: errors at Level 2 and above,
warnings below (AGSC-09-93, amended 2026-10-06 for 1.0.0).

Error codes.  Section 9.4 of the specification names no dedicated code for
these shape checks, so this checker uses the same code for the same fault as the
Node tool does, under the precedence paragraph: AGSC-E201 for document shape,
media type and order; AGSC-E202 for a missing REQUIRED attribute; AGSC-E204 for
a malformed digest; AGSC-E209 for a relation outside AGSC-06-10/06-35;
AGSC-E506 (a warning) for a relation or a target attribute of a newer MINOR,
which is ignored (AGSC-00-21, AGSC-09-93);
AGSC-E210 for a surface declaration that disagrees with the node; AGSC-E601 for
non-canonical bytes at Level 2 and above; AGSC-E901/E902/E904/E905/E907 for
input and transport faults.  A missing response header or header value is
AGSC-E202 and one the rules forbid is AGSC-E201.

Standard library only.
"""

import base64
import hashlib
import json
import os
import re

from . import MEDIA_TYPE, PROFILE_URI, REL_BASE, SPEC_VERSION, WELLKNOWN_SUFFIX
from .diagnostics import envelope, finding
from .jcs import canonicalize_raw, compare_utf16, parse_ijson, utf16_key
from .net import MAX_BYTES, TARGET_MAX_BYTES, TransportError
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
    "access", "boards", "context", "contribute", "graph", "ledger", "now",
    "ontology", "peer", "signature", "skills", "surface",
])
#: AGSC-06-08 and AGSC-11-16 (with AGSC-06-35's `profile` and RFC 9264 section
#: 4.2.4.1's `hreflang`): every target attribute this version defines.  A document of
#: a newer MINOR may carry others; they are ignored with a warning (AGSC-00-21,
#: AGSC-09-93).
KNOWN_ATTRIBUTES = frozenset([
    "agsc-access", "agsc-bundle-hash", "agsc-bundle-version", "agsc-contribute-mode",
    "agsc-counts", "agsc-generated-at", "agsc-ledger-head", "agsc-spec-version",
    "agsc-surface", "agsc-surface-version", "agsc-tombstone", "agsc-visibility", "digest",
    "hreflang", "media", "profile", "title", "title*", "type",
])
#: RFC 9264 section 4.2.4.1: the target attributes whose value is a plain string.
STRING_ATTRIBUTES = frozenset(["type", "title", "media"])
#: AGSC-06-08: the attributes the graph link carries at
#: Level 2 and above, `agsc-bundle-version` among them.
LEVEL2_ATTRIBUTES = ("agsc-bundle-hash", "agsc-bundle-version", "agsc-counts",
                     "agsc-generated-at", "agsc-spec-version")
#: AGSC-11-20: what a restricted node must omit.
RESTRICTED_FORBIDDEN = ("agsc-bundle-hash", "agsc-bundle-version", "agsc-counts",
                        "agsc-ledger-head")
#: AGSC-11-20: the targets a restricted node serves unauthenticated, and so the only
#: ones whose `digest` it may publish (its Level-0 view).
OPEN_WHEN_RESTRICTED = ("/graph.jsonld", "/llms.txt")
#: AGSC-04-25: the grammar of a content version.
VERSION_GRAMMAR = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+-]{0,63}$")
#: AGSC-11-16: the surface names a node may declare.
SURFACES = frozenset(["llms-txt", "chunks", "mcp", "webmcp", "a2a-card", "solid", "responder"])
SURFACE_NEEDS_VERSION = frozenset(["mcp", "webmcp", "a2a-card", "solid", "responder"])
#: AGSC-11-16: the access classes.
ACCESS = frozenset(["none", "consent", "credential"])

#: AGSC-11-03: the public artefacts, as origin-rooted paths (a node occupies a whole
#: origin at 1.0, AGSC-01-19).
PUBLIC_ARTEFACT = re.compile(
    r"^/(?:\.well-known/knowledge-linkset|graph\.(?:jsonld|ttl|nq)|ns/.*|llms(?:-full)?\.txt"
    r"|chunks(?:-[^/]+)?\.jsonl|ledger\.jsonl|search(?:-[^/]+)?\.json|pages/[^/]+\.(?:md|jsonld)"
    r"|skills/.*|now\.md|boards/.*|attachments/.*|graph/fragments/.*)$", re.DOTALL)
#: AGSC-11-05: the three routes served with ``Cache-Control: no-cache``.
NO_CACHE = ("/.well-known/knowledge-linkset", "/now.md", "/ledger.jsonl")
#: AGSC-11-03: the response headers a public artefact exposes to another origin.
EXPOSED = ("Link", "ETag", "Content-Type")

_PRIVATE_SURFACE = re.compile(r"^x-[a-z0-9]+(-[a-z0-9]+)+$")
_DIGEST = re.compile(r"^sha-256=:[A-Za-z0-9+/]{43}=:$")
_PARAMETER = re.compile(r';\s*([A-Za-z0-9!#$&^_.+\-]+)\s*=\s*("(?:[^"\\]|\\.)*"|[^;]*)')
_LINK_HEADER = re.compile(r"^\s*<([^>]*)>(.*)$")
_LINK_REL = re.compile(r';\s*rel\s*=\s*(?:"([^"]*)"|([^;\s]+))', re.IGNORECASE)


def _compact(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


class Source(object):
    """One document to check, with the way its targets are resolved."""

    def __init__(self, kind, name, data, headers=None, site_root=None, fetcher=None, dev=False,
                 retrieved_from=None):
        self.kind = kind
        self.name = name
        #: the URL the document was finally read from, after redirects (AGSC-06-08)
        self.retrieved_from = retrieved_from
        self.data = data
        self.headers = headers
        self.site_root = site_root
        self.fetcher = fetcher
        self.dev = dev
        self.reads = 1
        #: (final URL, response headers) of every target this run fetched
        self.fetched = []

    def resolve_target(self, href, anchor):
        """The bytes of one target, or None when it cannot be checked offline."""
        if self.kind == "memory":
            # An in-memory document has no site beside it: every digest target is
            # "not checkable offline", never an I/O error.
            return None
        if self.kind == "url":
            self.reads += 1
            final, headers, body = self.fetcher(href, self.dev, cap=TARGET_MAX_BYTES)
            self.fetched.append((final, headers))
            return body
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
        final, headers, body = fetcher(target, dev, cap=MAX_BYTES)
        return Source("url", target, body, headers=headers, fetcher=fetcher, dev=dev,
                      retrieved_from=final)
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
    """Whether the served media type and profile satisfy AGSC-06-07.

    The media type is ``application/linkset+json`` in every case, and the profile URI
    rides on its ``profile`` parameter or on a ``Link: ...; rel="profile"`` header: the
    header replaces only the parameter, never the media type (AGSC-09-93).
    """
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
    return {"checked": True, "essence": essence, "profile": by_parameter or by_link,
            "ok": essence == MEDIA_TYPE and (by_parameter or by_link)}


def _media_type_shortfall(media):
    """The one message for a media type that fails AGSC-06-07, or None when it holds."""
    if not media["checked"] or media["ok"]:
        return None
    if media["essence"] != MEDIA_TYPE and media["profile"]:
        return ('media type "%s" is not %s; the profile Link header replaces only the profile '
                'parameter, never the media type (AGSC-06-07)' % (media["essence"], MEDIA_TYPE))
    if media["essence"] != MEDIA_TYPE:
        return ('media type "%s" is not %s and no profile is carried: need %s with '
                'profile="%s", or %s with a Link header rel="profile" (AGSC-06-07)'
                % (media["essence"], MEDIA_TYPE, MEDIA_TYPE, PROFILE_URI, MEDIA_TYPE))
    return ('media type %s carries no profile: need profile="%s", or a Link header with '
            'rel="profile" (AGSC-06-07)' % (MEDIA_TYPE, PROFILE_URI))


def _header_values(headers, name):
    value = headers.get(name)
    if value is None:
        return None
    return ", ".join(value) if isinstance(value, (list, tuple)) else str(value)


def _tokens(value):
    return [one.strip().lower() for one in (value or "").split(",") if one.strip()]


def header_shortfalls(headers, cors, no_cache):
    """One response's shortfalls against AGSC-11-03 (when ``cors``) and AGSC-11-05."""
    out = []
    if cors:
        origin = _header_values(headers, "access-control-allow-origin")
        if origin is None:
            out.append(("AGSC-E202", 'no Access-Control-Allow-Origin: a public artefact is served '
                                     'with "*" (AGSC-11-03)'))
        elif origin.strip() != "*":
            out.append(("AGSC-E201", 'Access-Control-Allow-Origin is %s, not "*" (AGSC-11-03)'
                        % _compact(origin)))
        exposed = _header_values(headers, "access-control-expose-headers")
        missing = [name for name in EXPOSED if name.lower() not in _tokens(exposed)]
        if exposed is None:
            out.append(("AGSC-E202", "no Access-Control-Expose-Headers: a public artefact exposes "
                                     "Link, ETag, Content-Type (AGSC-11-03)"))
        elif missing:
            out.append(("AGSC-E202", "Access-Control-Expose-Headers %s does not name %s (AGSC-11-03)"
                        % (_compact(exposed), ", ".join(missing))))
        if _header_values(headers, "access-control-allow-credentials") is not None:
            out.append(("AGSC-E201", "Access-Control-Allow-Credentials is sent; no public artefact "
                                     "carries it (AGSC-11-03)"))
    if _header_values(headers, "etag") is None:
        out.append(("AGSC-E202", "no ETag: every public artefact is sent with one (AGSC-11-05)"))
    cache = _header_values(headers, "cache-control")
    if no_cache and "no-cache" not in _tokens(cache):
        out.append(("AGSC-E202", "Cache-Control is %s, not no-cache (AGSC-11-05)"
                    % _compact(cache or "")))
    if "immutable" in _tokens(cache):
        out.append(("AGSC-E201", "Cache-Control carries immutable, which no 1.0 route may "
                                 "(AGSC-11-05)"))
    return out


def _check_headers(source, anchor, restricted, level, report):
    """AGSC-09-93: the headers of the document and of every same-origin public artefact read."""
    if source.kind != "url" or source.headers is None:
        return
    severity = "error" if level >= 2 else "warn"
    seen = set()
    responses = [(source.retrieved_from or source.name, source.headers, True)]
    responses += [(final, headers, False) for final, headers in source.fetched]
    for final, headers, is_document in responses:
        if headers is None or final in seen:
            continue
        url = Url(final)
        if url.origin != anchor.origin:
            continue
        if not is_document and PUBLIC_ARTEFACT.match(url.pathname) is None:
            continue
        seen.add(final)
        lowered = {str(name).lower(): value for name, value in headers.items()}
        for code, message in header_shortfalls(
                lowered, cors=is_document or not restricted,
                no_cache=is_document or url.pathname in NO_CACHE):
            report(code, "%s: %s" % (final, message), severity=severity)


def check(source, level, findings, dev=False):
    """Check one document, appending findings.  Returns the anchor and the peers."""

    def report(code, message, severity="error"):
        findings.append(finding(code, source.name, message, severity=severity))

    shortfall = _media_type_shortfall(_media_type_state(source.headers))
    if shortfall is not None:
        report("AGSC-E201", shortfall)

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

    # AGSC-06-08: a document whose anchor is not on the origin it was retrieved from is
    # not that node's discovery document (RFC 9264 section 9, RFC 8615 section 4.3).
    if source.kind == "url" and source.retrieved_from is not None:
        origin = Url(source.retrieved_from).origin
        if origin != anchor.origin:
            report(
                "AGSC-E907",
                "anchor %s is not on the origin the document was retrieved from (%s); it is not "
                "that node's discovery document (AGSC-06-08)" % (raw_anchor, origin),
            )

    keys = list(context.keys())
    if keys != sorted(keys, key=utf16_key):
        report(
            "AGSC-E201",
            "link context members are not ordered as JSON member names (AGSC-06-08, AGSC-04-05)",
        )

    graph_link = _graph_link(context)
    restricted = isinstance(graph_link.get("agsc-visibility"), list) and "restricted" in [
        str(one) for one in graph_link["agsc-visibility"]]
    ledger = context.get(REL_BASE + "ledger")
    if restricted:
        # AGSC-11-20: a restricted node omits its content facts and its ledger link.
        for name in RESTRICTED_FORBIDDEN:
            if name in graph_link:
                report("AGSC-E210",
                       'a restricted node must omit "%s": per-type population, the fingerprint, '
                       "the content version and the ledger head are content facts (AGSC-11-20)"
                       % name)
        if isinstance(ledger, list) and ledger:
            report("AGSC-E210", "a restricted node publishes no rel#ledger link (AGSC-11-20)")
    elif level >= 2 and not (isinstance(ledger, list) and ledger):
        # AGSC-10-04 / AGSC-09-93: the derived ledger is part of Level 2, so a public
        # node claiming it publishes /ledger.jsonl and links it.
        report("AGSC-E202", "no rel#ledger link: a Level >= 2 node publishes /ledger.jsonl "
                            "and links it (AGSC-10-04, AGSC-09-93)")
    declared, newer = _declared_version(context)
    bundle_version = graph_link.get("agsc-bundle-version")
    if isinstance(bundle_version, list):
        if len(bundle_version) != 1:
            report("AGSC-E210", "agsc-bundle-version carries exactly one value (AGSC-06-08, "
                                "AGSC-04-25)")
        elif VERSION_GRAMMAR.match(str(bundle_version[0])) is None:
            report("AGSC-E204", "agsc-bundle-version %s is outside the grammar of AGSC-04-25"
                   % _compact(str(bundle_version[0])))
        # AGSC-00-23: the attribute is defined from specification MAJOR 1 (AGSC-04-25).
        major = re.match(r"^(\d+)\.", declared) if declared is not None else None
        if major is not None and int(major.group(1)) < 1:
            report("AGSC-E210", "the node publishes agsc-bundle-version while declaring "
                                "agsc-spec-version %s, which does not define it (AGSC-00-23, "
                                "AGSC-04-25)" % _compact(declared))
    bundle_hash = graph_link.get("agsc-bundle-hash")
    peers = []
    for relation in [name for name in keys if name != "anchor"]:
        extension = relation[len(REL_BASE):] if relation.startswith(REL_BASE) else None
        if relation not in REGISTERED and not (extension is not None and extension in EXTENSIONS):
            if newer:
                report("AGSC-E506",
                       "relation %s is not defined by this version; the document declares the "
                       "newer %s, so it is ignored (AGSC-00-21, AGSC-09-93)"
                       % (_compact(relation), declared), severity="warn")
                continue
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
                if newer and name not in KNOWN_ATTRIBUTES:
                    report("AGSC-E506",
                           "relation %s: target attribute %s is not defined by this version; the "
                           "document declares the newer %s, so it is ignored (AGSC-00-21, "
                           "AGSC-09-93)" % (relation, name, declared), severity="warn")
                    continue
                value = target[name]
                if name in STRING_ATTRIBUTES:
                    if not isinstance(value, str):
                        report("AGSC-E201",
                               "relation %s: target attribute %s must be a string "
                               "(RFC 9264 section 4.2.4.1)" % (relation, name))
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
                and extension not in ("surface", "peer", "signature")
            )
            opened = same_origin and parsed.pathname.endswith(OPEN_WHEN_RESTRICTED)
            digest = target.get("digest")
            if restricted and "digest" in target and not opened:
                report("AGSC-E210",
                       "relation %s: a restricted node must omit the digest of %s, a target it "
                       "does not serve unauthenticated (AGSC-11-20)" % (relation, href))
            # AGSC-06-08 / AGSC-04-15: the bundle hash is the SHA-256 of graph.nq, so where
            # both are published it equals the digest of the rel#graph link to it.
            if (extension == "graph" and parsed.pathname.endswith("/graph.nq")
                    and isinstance(digest, list) and isinstance(bundle_hash, list)
                    and bundle_hash and digest
                    and str(bundle_hash[0]) != str(digest[0])):
                report("AGSC-E210",
                       "agsc-bundle-hash %s is not the digest of %s, the bundle hash of "
                       "AGSC-04-15 (AGSC-06-08)" % (_compact(str(bundle_hash[0])), href))
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
            elif level >= 2 and artefact and not (restricted and not opened):
                report("AGSC-E202",
                       "relation %s: artefact link %s carries no digest (required at Level >= 2, "
                       "AGSC-06-08a)" % (relation, href))
            is_graph = relation == "describedby" and parsed.pathname.endswith("/graph.jsonld")
            if level >= 2 and is_graph:
                for name in LEVEL2_ATTRIBUTES:
                    if name not in target and not (restricted and name in RESTRICTED_FORBIDDEN):
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

    _check_headers(source, anchor, restricted, level, report)
    return {"anchor": raw_anchor, "peers": peers}


_MAJOR_MINOR = re.compile(r"^(\d+)\.(\d+)(?:\.|$)")


def _major_minor(version):
    match = _MAJOR_MINOR.match(str(version))
    return (int(match.group(1)), int(match.group(2))) if match else None


def _graph_link(context):
    """The describedby target naming the graph: the node's own declaration is read there."""
    targets = context.get("describedby")
    if isinstance(targets, list):
        for one in targets:
            if isinstance(one, dict) and isinstance(one.get("href"), str) \
                    and one["href"].endswith("/graph.jsonld"):
                return one
    return {}


def _declared_version(context):
    """AGSC-00-21 / AGSC-09-93: the ``agsc-spec-version`` the document declares on the
    describedby link to its graph, and whether it is this checker's MAJOR with a newer
    MINOR.  Only then are unknown relations and attributes ignored; a document of
    another MAJOR has no such tolerance."""
    value = _graph_link(context).get("agsc-spec-version")
    if not isinstance(value, list) or not value:
        return None, False
    declared = str(value[0])
    theirs, mine = _major_minor(declared), _major_minor(SPEC_VERSION)
    newer = theirs is not None and mine is not None and theirs[0] == mine[0] \
        and theirs[1] > mine[1]
    return declared, newer




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
