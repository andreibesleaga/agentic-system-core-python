"""What a discovery document states about the files it links, checked against them.

The 1.1 checks of the discovery-file checker (``wellknown.py``) that read a linked file
rather than the document alone, each the twin of a function of the engine's
``tools/validate-wellknown``:

* ``chunk_facts_missing`` and ``chunk_facts_findings`` — at Level 2 and above, the
  chunks surface link of a document of 1.1.0 or later states ``digest``,
  ``agsc-chunk-count`` and ``agsc-chunk-set``, and the count and the set commitment are
  recomputed over the chunk lines read (AGSC-06-44, AGSC-09-93 (b));
  ``requireChunkFacts`` and ``recomputeChunkFacts`` in the engine;
* ``ledger_length_findings`` — an ``agsc-ledger-length`` is the number of entries of
  the ledger read (AGSC-06-44, AGSC-09-93 (c)); ``checkLedgerLength``;
* ``card_target_findings`` — an ``a2a-card`` declared on the node's own origin names a
  card the node serves, else the warning AGSC-E210 (AGSC-11-16); ``checkCardTarget``;
* ``home_link_findings`` — given a URL, the ``Link`` header of the node's home page
  carries the ``describedby`` link to the discovery document, else the warning
  AGSC-E202, because AGSC-06-25 makes that header a SHOULD (AGSC-06-40);
  ``homeLinkFindings`` and ``checkHomeLink``.

Each takes the ``report`` callable of one run and the ``Source`` the targets are read
through, so the codes, severities and the reads counted are the engine's.  Standard
library only; the ``Link`` values are split as RFC 8288 section 3 writes them, with no
parser library, as the engine's standalone tool does (AGSC-09-90).
"""

import base64
import hashlib
import json
import re

from . import WELLKNOWN_SUFFIX
from .diagnostics import finding
from .net import TARGET_MAX_BYTES, TransportError, counted
from .urls import Url, resolve

#: AGSC-06-44: what the chunks surface link of a public node states from 1.1 on.
CHUNK_ATTRIBUTES = ("digest", "agsc-chunk-count", "agsc-chunk-set")

_MAJOR_MINOR = re.compile(r"^(\d+)\.(\d+)(?:\.|$)")
_FIELD_VALUES = re.compile(r",(?=\s*<)")
_LINK_VALUE = re.compile(r"^\s*<([^>]*)>(.*)$", re.DOTALL)
_REL = re.compile(r';\s*rel\s*=\s*(?:"([^"]*)"|([^;,\s]+))', re.IGNORECASE)


def from_one_one(declared):
    """True when ``declared`` (an ``agsc-spec-version``) is 1.1.0 or later."""
    match = _MAJOR_MINOR.match(str(declared))
    return match is not None and (int(match.group(1)), int(match.group(2))) >= (1, 1)


def _stated(target, name):
    value = target.get(name)
    return value[0] if isinstance(value, list) and len(value) == 1 else None


def chunk_facts_missing(target, href, declared, level, report):
    """AGSC-09-93 (b), AGSC-06-44: at Level 2 and above a document of 1.1.0 or later
    states the three facts on its public chunks link; each one absent is AGSC-E202."""
    if level < 2 or not from_one_one(declared):
        return
    for name in CHUNK_ATTRIBUTES:
        if name not in target:
            report("AGSC-E202", "rel#surface %s: the chunks surface link of a %s document carries "
                                "no %s (required at Level >= 2, AGSC-06-44)" % (href, declared, name))


def _js_string(value):
    """The text JavaScript's ``String()`` gives a value a JSON line can hold, as the
    engine joins each chunk ``id`` into the set commitment."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return "null"
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    if isinstance(value, list):
        return ",".join("" if one is None else _js_string(one) for one in value)
    if isinstance(value, dict):
        return "[object Object]"
    return str(value)


def _refuse_constant(name):
    raise ValueError("%s is not JSON" % name)


def _lines(data):
    """The JSON lines of a file, read as the engine reads them (``JSON.parse`` of each
    non-empty line of the UTF-8 text, so ``NaN`` is refused)."""
    text = data.decode("utf-8", "replace")
    return [json.loads(line, parse_constant=_refuse_constant)
            for line in text.split("\n") if line != ""]


def _chunk_lines(data, href, anchor, source):
    """The chunk lines a chunks file holds: its own lines or, when it is the manifest of
    AGSC-06-31 (one object with ``shards`` and no ``id``), the lines of every shard in
    manifest order.  A shard on another origin is not read from disk."""
    lines = _lines(data)
    manifest = lines[0] if len(lines) == 1 else None
    if not (isinstance(manifest, dict) and isinstance(manifest.get("shards"), list)
            and "id" not in manifest):
        return lines
    out = []
    for shard in manifest["shards"]:
        part = source.resolve_target(resolve(href, _js_string(shard)), anchor, checked=False)
        if part is not None:
            out.extend(_lines(part))
    return out


def _chunk_id(line):
    if not isinstance(line, dict):
        if line is None:
            raise ValueError("a chunk line is null")
        return "undefined"
    return _js_string(line["id"]) if "id" in line else "undefined"


def chunk_facts_findings(target, href, data, anchor, source, level, report):
    """AGSC-09-93 (b), AGSC-06-44: the count and the set commitment, recomputed over the
    lines read: the commitment is the SHA-256 over each ``id`` and one LF, in file
    order.  (The ``digest`` is recomputed with every other digest.)"""
    if level < 2 or ("agsc-chunk-count" not in target and "agsc-chunk-set" not in target):
        return
    try:
        lines = _chunk_lines(data, href, anchor, source)
        joined = "".join(_chunk_id(line) + "\n" for line in lines)
    except (ValueError, TransportError) as error:
        report("AGSC-E201", "rel#surface %s: the chunk lines cannot be read to recompute "
                            "agsc-chunk-count and agsc-chunk-set: %s" % (href, error))
        return
    commitment = "sha-256=:%s:" % base64.b64encode(
        hashlib.sha256(joined.encode("utf-8")).digest()).decode("ascii")
    if "agsc-chunk-count" in target and _stated(target, "agsc-chunk-count") != str(len(lines)):
        report("AGSC-E201", "rel#surface %s: agsc-chunk-count %s is not the %d lines of the "
                            "fetched file (AGSC-06-44)"
               % (href, json.dumps(target["agsc-chunk-count"]), len(lines)))
    if "agsc-chunk-set" in target and _stated(target, "agsc-chunk-set") != commitment:
        report("AGSC-E201", "rel#surface %s: agsc-chunk-set does not match the ids of the "
                            "fetched lines (AGSC-06-44)" % href)


def ledger_length_findings(target, href, anchor, source, level, report):
    """AGSC-09-93 (c), AGSC-06-44: an ``agsc-ledger-length``, when present, is the number
    of entries of the ledger read: from a file at every Level, from a URL at Level 2
    and above."""
    if "agsc-ledger-length" not in target or (level < 2 and source.kind != "file"):
        return
    try:
        data = source.resolve_target(href, anchor, checked=False)
    except TransportError as error:
        report(error.code, "rel#ledger: %s" % error.message)
        return
    if data is None:
        return
    entries = len([line for line in data.decode("utf-8", "replace").split("\n") if line != ""])
    value = target["agsc-ledger-length"]
    if not (isinstance(value, list) and len(value) == 1 and value[0] == str(entries)):
        report("AGSC-E201", "rel#ledger %s: agsc-ledger-length %s is not the %d entries of the "
                            "fetched ledger (AGSC-06-44)" % (href, json.dumps(value), entries))


def card_target_findings(href, parsed, anchor, source, report):
    """AGSC-11-16: an ``a2a-card`` declared on the node's own origin names a card the node
    serves.  A warning, not an error: a 1.0 node declared the surface and served no card
    (decision D-15).  A card on another origin is not read, the surface being
    declaration-only (AGSC-11-17)."""
    if parsed.origin != Url(anchor).origin:
        return
    try:
        source.resolve_target(href, anchor, checked=False)
    except TransportError as error:
        if error.code == "AGSC-E906":
            report("AGSC-E906", "rel#surface a2a-card: %s" % error.message)
            return
        report("AGSC-E210", "rel#surface a2a-card: the declared card %s is not served by this "
                            "node: %s (AGSC-11-16)" % (href, error.message), severity="warn")


def home_link_findings(values, anchor="https://invalid.example/", file="/"):
    """AGSC-06-40 with AGSC-06-25: the values of the ``Link`` header of ``/`` carry a
    ``describedby`` link whose target, resolved against the anchor, is the discovery
    document.  Its absence is the warning AGSC-E202: the header is a SHOULD."""
    wellknown = resolve(anchor, ".well-known/" + WELLKNOWN_SUFFIX)
    listed = values if isinstance(values, (list, tuple)) else ([] if values is None else [values])
    for one in _FIELD_VALUES.split(",".join(str(value) for value in listed)):
        match = _LINK_VALUE.match(one)
        relation = _REL.search(match.group(2)) if match is not None else None
        if relation is None or resolve(anchor, match.group(1)) != wellknown:
            continue
        if "describedby" in (relation.group(1) or relation.group(2)).lower().split():
            return []
    return [finding("AGSC-E202", file, "the Link header of / carries no describedby link to %s "
                                       "(AGSC-06-25, AGSC-06-40: a SHOULD)" % wellknown,
                    severity="warn")]


def check_home_link(source, anchor, findings):
    """AGSC-06-40: given a URL, the ``Link`` header of the node's home page, the anchor.
    The request counts against the run's budget but is not one of the files read."""
    if source.kind != "url":
        return
    try:
        _, headers, _ = counted(source.fetcher, anchor, source.dev, TARGET_MAX_BYTES,
                                source.budget)
    except TransportError as error:
        findings.append(finding("AGSC-E202", anchor, "the Link header of / could not be read: %s "
                                                     "(AGSC-06-25, AGSC-06-40)" % error.message,
                                severity="warn"))
        return
    findings.extend(home_link_findings(headers.get("link"), anchor=anchor, file=anchor))
