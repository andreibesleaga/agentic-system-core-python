"""Site artefacts whose bytes or facts a rule pins: the search index, static
query fragments, the served header set, ``security.txt`` and the content version.

Derived from the rule text:

* AGSC-06-16 / 06-23 / 06-21 — ``search.json``, its normative tokenizer and its shards.
* AGSC-06-33 — ``/graph/fragments/index.json``.
* AGSC-06-17 — the header set and the redirect (the facts, never a file grammar).
* AGSC-06-36 — ``/.well-known/security.txt``.
* AGSC-04-25 / 06-22 — the content version and the NOW line.
* AGSC-08-20a — the ledger ``kind`` of one git-log element.

Standard library only.  The General_Category table is the runtime's
``unicodedata`` (AGSC-04-22 admits Unicode 15.0 to 18.0 for the vector set).
"""

import datetime
import hashlib
import re
import unicodedata

from . import PROFILE_URI, WELLKNOWN_PATH
from .jcs import canonicalize

# --- the tokenizer (AGSC-06-23) ----------------------------------------------

_FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})")


def strip_fenced_code(body):
    """The body with every fenced code block (fences included) removed."""
    out = []
    fence = None
    for line in body.split("\n"):
        match = _FENCE.match(line)
        if fence is None:
            if match:
                fence = match.group(1)
                continue
            out.append(line)
        elif match and match.group(1)[0] == fence[0] and len(match.group(1)) >= len(fence) \
                and line.strip().strip(fence[0]) == "":
            fence = None
    return "\n".join(out)


def is_token_char(char):
    if "a" <= char <= "z" or "0" <= char <= "9":
        return True
    category = unicodedata.category(char)
    return category[0] in "LM" or category == "Nd"


def tokens(text):
    """NFC, ASCII lower-case, split on non-token characters, drop tokens under 2 code points."""
    text = unicodedata.normalize("NFC", text)
    text = "".join(chr(ord(c) + 32) if "A" <= c <= "Z" else c for c in text)
    out, current = [], []
    for char in text + " ":
        if is_token_char(char):
            current.append(char)
            continue
        if len(current) >= 2:
            out.append("".join(current))
        current = []
    return out


def item_tokens(item):
    parts = [item.get("title") or "", item.get("description") or ""]
    parts.extend(item.get("tags") or [])
    parts.append(strip_fenced_code(item.get("body") or ""))
    found = []
    for part in parts:
        found.extend(tokens(part))
    return found


def search_index(items):
    """``search.json`` (AGSC-06-16) for the published items given, as a value."""
    ordered = sorted(items, key=lambda one: one["slug"])
    docs, terms = [], {}
    for index, item in enumerate(ordered):
        doc = {"slug": item["slug"], "title": item.get("title", "")}
        if item.get("description"):
            doc["description"] = item["description"]
        if item.get("clusters"):
            doc["cluster"] = item["clusters"][0]
        docs.append(doc)
        for token in item_tokens(item):
            postings = terms.setdefault(token, [])
            if not postings or postings[-1] != index:
                postings.append(index)
    return {"docs": docs, "terms": terms}


def search_json(items):
    """The emitted bytes: JCS (UTF-16 member order) plus one LF (AGSC-04-04)."""
    return canonicalize(search_index(items)) + "\n"


#: AGSC-06-21: above this many items the index is sharded.
ITEMS_PER_SHARD = 500


def search_files(items, per_shard=ITEMS_PER_SHARD):
    """[(path, value)] of the search index (AGSC-06-21).

    At or below the bound ``/search.json`` is the whole index.  Above it the items,
    in slug order, are cut into shards ``/search-<nn>.json`` (zero-padded from 01) of
    at most ``per_shard`` items, each a complete AGSC-06-16 index over its own slice
    whose postings count from zero in its own ``docs[]``, and ``/search.json`` is the
    manifest ``{docs_total, shards}``.
    """
    ordered = sorted(items, key=lambda one: one["slug"])
    if len(ordered) <= per_shard:
        return [("/search.json", search_index(ordered))]
    shards = [("/search-%02d.json" % (number + 1), search_index(ordered[start:start + per_shard]))
              for number, start in enumerate(range(0, len(ordered), per_shard))]
    manifest = {"docs_total": len(ordered), "shards": [path for path, _ in shards]}
    return [("/search.json", manifest)] + shards


# --- static query fragments (AGSC-06-33) --------------------------------------

def _terms_of(line):
    subject, rest = line.split(" ", 1)
    predicate = rest.split(" ", 1)[0]
    return subject[1:-1], predicate[1:-1]


def fragment_name(iri):
    return hashlib.sha256(iri.encode("utf-8")).hexdigest()[:16]


def fragments(nquads_text, generated_at):
    """(files {path: bytes-as-text}, index value) for one ``graph.nq``."""
    by_subject, by_predicate = {}, {}
    for line in nquads_text.split("\n"):
        if not line:
            continue
        subject, predicate = _terms_of(line)
        by_subject.setdefault(subject, []).append(line)
        by_predicate.setdefault(predicate, []).append(line)
    files = {}
    for folder, table in (("s", by_subject), ("p", by_predicate)):
        for iri, lines in table.items():
            files["%s/%s.nq" % (folder, fragment_name(iri))] = \
                "".join(one + "\n" for one in sorted(lines))
    index = {
        "generated_at": generated_at,
        "predicates": sorted(path for path in files if path.startswith("p/")),
        "subjects": sorted(path for path in files if path.startswith("s/")),
    }
    return files, index


# --- the header set and the redirect (AGSC-06-17) -----------------------------

#: AGSC-06-17 (amended 2026-10-02): the least policy a node serves; a writer MAY add
#: directives that only restrict further, so a case asserts containment.
CSP = "default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self'; connect-src 'self'"
LINKSET_CONTENT_TYPE = 'application/linkset+json; profile="%s"' % PROFILE_URI
MARKDOWN_CONTENT_TYPE = "text/markdown; charset=utf-8; variant=GFM"
PROFILE_LINK_HEADER = 'Link: <%s>; rel="profile"' % PROFILE_URI
LEGACY_WELLKNOWN = "/.well-known/agentic-knowledge"


def header_set(routes):
    """The normative header facts for a route set: {pattern: {header: value}}."""
    headers = {"/*": {"Content-Security-Policy": CSP}}
    if any(route.startswith("/pages/") and route.endswith(".md") for route in routes):
        headers["/pages/*.md"] = {"Content-Type": MARKDOWN_CONTENT_TYPE}
    if WELLKNOWN_PATH in routes:
        headers[WELLKNOWN_PATH] = {"Content-Type": LINKSET_CONTENT_TYPE}
    return headers


def redirects():
    return [{"from": LEGACY_WELLKNOWN, "status": 301, "to": WELLKNOWN_PATH}]


# --- security.txt (AGSC-06-36) -------------------------------------------------

#: RFC 9116 §2.5 field names in the registry's case.
SECURITY_FIELDS = ("Acknowledgments", "Canonical", "Contact", "Encryption", "Expires",
                   "Hiring", "Policy", "Preferred-Languages")
_FIELD_CASE = dict((name.lower(), name) for name in SECURITY_FIELDS)
_INSTANT = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
_FIELD = re.compile(r"^([A-Za-z0-9-]+):[ \t]*(.*)$")


def parse_instant(text):
    return datetime.datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ")


def render_instant(moment):
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


def _finding(code, message, severity="error"):
    return {"code": code, "message": message, "severity": severity}


def security_txt(authored, instant, base, legal):
    """(text or None, findings).  ``authored`` is the Bundle root's file or None."""
    route = base.rstrip("/") + "/.well-known/security.txt"
    if authored is None:
        return None, [_finding("AGSC-E901", "the Bundle root carries no .well-known/security.txt")]
    findings, fields = [], []
    for raw in authored.split("\n"):
        line = raw.rstrip("\r")
        if line.strip() == "" or line.lstrip().startswith("#"):
            continue
        match = _FIELD.match(line)
        if match is None:
            findings.append(_finding("AGSC-E204", "not a field line: %s" % line))
            continue
        name = _FIELD_CASE.get(match.group(1).lower(), match.group(1))
        value = " ".join(match.group(2).split())
        fields.append((name, value))
    names = [name for name, _ in fields]
    if "Contact" not in names:
        findings.append(_finding("AGSC-E202", "no Contact: field (RFC 9116 §2.5.3)"))
    build = parse_instant(instant)
    expires = [value for name, value in fields if name == "Expires"]
    if len(expires) > 1:
        findings.append(_finding("AGSC-E204", "Expires appears more than once"))
    for value in expires[:1]:
        if not _INSTANT.match(value):
            findings.append(_finding("AGSC-E204", "Expires is not an AGSC-04-10 instant"))
            continue
        moment = parse_instant(value)
        if moment <= build:
            findings.append(_finding("AGSC-E204", "Expires is not after the build instant"))
        elif moment - build > datetime.timedelta(days=365):
            findings.append(_finding("AGSC-E204", "Expires is more than a year ahead", "warn"))
    if not expires:
        if build == datetime.datetime(1970, 1, 1):
            findings.append(_finding(
                "AGSC-E204", "the build instant is the default 0: commit the Bundle once or "
                "set SOURCE_DATE_EPOCH before an Expires can be derived"))
        else:
            fields.append(("Expires", render_instant(build + datetime.timedelta(days=364))))
    if "Canonical" not in names:
        fields.append(("Canonical", route))
    if "Policy" not in names and legal:
        fields.append(("Policy", base.rstrip("/") + "/legal/"))
    if any(one["severity"] == "error" for one in findings):
        return None, findings
    return "".join("%s: %s\n" % pair for pair in fields), findings


# --- the content version (AGSC-04-25) ----------------------------------------

VERSION_GRAMMAR = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+-]{0,63}$")


def _usable_tag(element):
    tag = element.get("tag")
    return tag if isinstance(tag, str) and VERSION_GRAMMAR.match(tag) else None


def content_version(git_log, source_date_epoch):
    """(bundle_version, findings) — the first branch of AGSC-04-25 that applies."""
    findings = []
    if not git_log:
        moment = datetime.datetime(1970, 1, 1) + datetime.timedelta(seconds=source_date_epoch)
        if source_date_epoch == 0:
            findings.append(_finding("AGSC-E606", "no git history: the build instant is 0",
                                     "warn"))
        return "0.0.0+" + moment.strftime("%Y%m%dT%H%M%SZ"), findings
    built = git_log[-1]
    if built.get("tag") is not None and _usable_tag(built) is None:
        findings.append(_finding("AGSC-E506", "tag %s is outside the content-version grammar"
                                 % built["tag"], "warn"))
    if _usable_tag(built):
        return built["tag"], findings
    short = built["sha"][:12].lower()
    for index in range(len(git_log) - 2, -1, -1):
        tag = _usable_tag(git_log[index])
        if tag:
            return "%s+%d.g%s" % (tag, len(git_log) - 1 - index, short), findings
    return "0.0.0+%d.g%s" % (len(git_log), short), findings


def ledger_kind(element):
    """AGSC-08-20a: release when a v* tag points at the commit, else merge or commit."""
    tag = element.get("tag")
    if isinstance(tag, str) and tag.startswith("v"):
        return "release"
    if len(element.get("parents") or []) >= 2 or "Proposal" in (element.get("trailers") or {}):
        return "merge"
    return "commit"


def stale_items(items, instant):
    """AGSC-02-11: an item is stale when its ``stale_after`` is EARLIER than the
    build instant, by comparison only.  Both are AGSC-02-06 instants, so their
    code-point order is their time order; an equal value is not stale, and an
    item with no ``stale_after`` never is.  Sorted by slug (AGSC-04-13)."""
    stale = [one["slug"] for one in items
             if one.get("stale_after") is not None
             and str(one["stale_after"]) < str(instant)]
    return sorted(stale)


def now_line(bundle_version, generated_at, bundle_hash, spec_version):
    """AGSC-06-22: the four values, in order, with the fixed separators."""
    return "content version %s, built at %s, fingerprint %s, specification %s" % (
        bundle_version, generated_at, bundle_hash, spec_version)
