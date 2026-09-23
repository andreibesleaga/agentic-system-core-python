"""Links: the fourteen keys, their inverses, the integrity checks, heading anchors
and inline-link resolution — spec/03, derived from the rule text.

* AGSC-03-01 / 03-04 — the closed key list and the computed inverses; an
  authored inverse is ``AGSC-E306``.
* AGSC-03-05 / 03-06 — symmetric keys materialise both directions; an edge
  asserted from both sides is one edge, not two.
* AGSC-03-07 — ``requires`` is acyclic; a cycle is ``AGSC-E302`` naming every
  slug on it in discovery order.
* AGSC-03-08 — ``broader``/``narrower`` acyclic (``AGSC-E303``); a cluster has
  at most one ``broader`` (``AGSC-E308``, parents in code-point order) and the
  tree is at most three levels deep (``AGSC-E307``, the chain root-first).
* AGSC-03-02 / 03-09 — targets resolve by exact slug; ``derived-from`` and
  ``supersedes`` (and the Mode-2 keys, AGSC-03-20) must exist (``AGSC-E301``).
* AGSC-03-11 — a relative inline link or image resolves, relative to the file
  that carries it, to an item, an asset or an anchor of one; otherwise
  ``AGSC-E310``, and ``AGSC-E902`` when it escapes the Bundle root.
* AGSC-03-13 — the heading-anchor algorithm.
"""

import unicodedata

from . import markdown

CORE_KEYS = ("related", "broader", "narrower", "uses", "requires", "excludes",
             "derived-from", "contradicts", "supersedes")
MODE2_KEYS = ("implements", "verifies", "covers", "blocked-by", "decided-by")
KEYS = CORE_KEYS + MODE2_KEYS

#: authored key -> computed inverse key (AGSC-03-01 table).
INVERSE = {
    "related": "related", "broader": "narrower", "narrower": "broader", "uses": "used-by",
    "requires": "required-by", "excludes": "excludes", "derived-from": "derivation-of",
    "contradicts": "contradicts", "supersedes": "superseded-by",
    "implements": "implemented-by", "verifies": "verified-by", "covers": "covered-by",
    "blocked-by": "blocks", "decided-by": "decides",
}
SYMMETRIC = ("related", "excludes", "contradicts")
#: AGSC-03-04: the inverse names that may never be authored.
AUTHORED_INVERSE_FORBIDDEN = ("used-by", "required-by", "derivation-of", "superseded-by",
                              "implemented-by", "verified-by", "covered-by", "blocks",
                              "decides")

TYPE_PLURAL = {
    "concept": "concepts", "lesson": "lessons", "episode": "episodes",
    "procedure": "procedures", "cluster": "clusters", "gate": "gates",
}


def err(code, message, **extra):
    out = {"code": code, "message": message, "severity": "error"}
    out.update(extra)
    return out


def target_slug(value):
    """``<slug>`` or ``<slug>#<anchor>`` -> (slug, anchor or None)."""
    if "#" in value:
        slug, anchor = value.split("#", 1)
        return slug, anchor
    return value, None


def authored_links(item):
    """The item's Link keys in the closed-list order, each value list as authored."""
    return [(key, list(item[key])) for key in KEYS if isinstance(item.get(key), list)]


def edges(items):
    """Every authored edge plus every computed inverse, deduplicated.

    Returns (edges, findings).  An edge is {computed, key, source, target}; the
    list is sorted by (source, key, target) — items by slug and links by
    (key, target), AGSC-04-13.
    """
    slugs = set(item["slug"] for item in items)
    seen = {}
    findings = []
    for item in sorted(items, key=lambda one: one["slug"]):
        for key in sorted(item):
            if key in AUTHORED_INVERSE_FORBIDDEN:
                findings.append(err("AGSC-E306", "%s authors the computed inverse %s"
                                    % (item["slug"], key), file=item["slug"]))
        for key, values in authored_links(item):
            for value in values:
                target, _ = target_slug(value)
                if target not in slugs:
                    findings.append(err("AGSC-E301", "%s %s -> %s does not resolve"
                                        % (item["slug"], key, target), file=item["slug"]))
                    continue
                forward = (item["slug"], key, target)
                seen[forward] = False
                inverse = (target, INVERSE[key], item["slug"])
                if inverse not in seen:
                    seen[inverse] = True
    out = [{"computed": computed, "key": key, "source": source, "target": target}
           for (source, key, target), computed in seen.items()]
    out.sort(key=lambda one: (one["source"], one["key"], one["target"]))
    return out, findings


def requires_cycle(items):
    """The first ``requires`` cycle found by a depth-first walk in slug order, or None."""
    graph = {}
    for item in items:
        graph[item["slug"]] = [target_slug(value)[0] for value in item.get("requires") or []]
    state = {}
    stack = []

    def visit(node):
        state[node] = 1
        stack.append(node)
        for target in graph.get(node, []):
            if target not in graph:
                continue
            if state.get(target) == 1:
                return stack[stack.index(target):]
            if state.get(target) is None:
                found = visit(target)
                if found:
                    return found
        stack.pop()
        state[node] = 2
        return None

    for node in sorted(graph):
        if state.get(node) is None:
            found = visit(node)
            if found:
                return list(found)
    return None


def hierarchy_findings(items):
    """AGSC-03-08: acyclicity, then mono-parent, then depth — each checked separately."""
    findings = []
    by_slug = dict((item["slug"], item) for item in items)
    parents = {}
    for item in items:
        for value in item.get("broader") or []:
            parents.setdefault(item["slug"], []).append(target_slug(value)[0])
    for item in items:
        for value in item.get("narrower") or []:
            child = target_slug(value)[0]
            if item["slug"] not in parents.setdefault(child, []):
                parents[child].append(item["slug"])
    # acyclicity over the broader relation
    state = {}
    cycle = []

    def visit(node, path):
        state[node] = 1
        path.append(node)
        for parent in parents.get(node, []):
            if state.get(parent) == 1:
                cycle.extend(path[path.index(parent):])
                return True
            if state.get(parent) is None and visit(parent, path):
                return True
        path.pop()
        state[node] = 2
        return False

    for node in sorted(parents):
        if state.get(node) is None and visit(node, []):
            findings.append(err("AGSC-E303", "broader/narrower cycle: %s" % " -> ".join(cycle),
                                cycle=cycle))
            return findings
    for slug in sorted(parents):
        item = by_slug.get(slug)
        if item is None or item.get("type") != "cluster":
            continue
        if len(parents[slug]) > 1:
            findings.append(err("AGSC-E308", "cluster %s has more than one broader" % slug,
                                parents=sorted(parents[slug]), file=slug))
    for slug in sorted(parents):
        item = by_slug.get(slug)
        if item is None or item.get("type") != "cluster":
            continue
        chain = [slug]
        node = slug
        while parents.get(node):
            node = sorted(parents[node])[0]
            chain.insert(0, node)
        if len(chain) > 3:
            findings.append(err("AGSC-E307", "cluster tree deeper than 3 levels: %s"
                                % " > ".join(chain), chain=chain, file=slug))
    return findings


# --- anchors (AGSC-03-13) ----------------------------------------------------

def anchor_base(text):
    """NFC -> ASCII lowercase -> drop outside [a-z0-9 -] -> spaces to '-' -> collapse -> trim."""
    text = unicodedata.normalize("NFC", text)
    text = "".join(chr(ord(c) + 32) if "A" <= c <= "Z" else c for c in text)
    text = "".join(c for c in text if c in "abcdefghijklmnopqrstuvwxyz0123456789 -")
    text = text.replace(" ", "-")
    while "--" in text:
        text = text.replace("--", "-")
    return text.strip("-")


def anchors(body):
    """Every heading anchor of a body, in document order."""
    out = []
    taken = set()
    empty = 0
    for heading in markdown.headings(body):
        base = anchor_base(markdown.plain_heading_text(heading.text))
        if base == "":
            empty += 1
            base = "section-%d" % empty
        candidate = base
        suffix = 1
        while candidate in taken:
            suffix += 1
            candidate = "%s-%d" % (base, suffix)
        taken.add(candidate)
        out.append(candidate)
    return out


# --- inline-link resolution (AGSC-03-11) ------------------------------------

def is_external(destination):
    """A destination with a scheme (or protocol-relative) names another origin."""
    if destination.startswith("//"):
        return True
    head = destination.split("/", 1)[0].split("#", 1)[0].split("?", 1)[0]
    if ":" not in head:
        return False
    scheme = head.split(":", 1)[0]
    return scheme[:1].isalpha() and all(c.isalnum() or c in "+.-" for c in scheme)


def item_path(item):
    """The Bundle-relative path of an item's file under content/ (AGSC-01-02)."""
    return "%s/%s.md" % (TYPE_PLURAL.get(item.get("type"), "concepts"), item["slug"])


def resolve_path(from_path, destination):
    """Resolve a relative path against the file that carries it.

    Returns (segments or None when it escapes the root, fragment or None).
    """
    fragment = None
    if "#" in destination:
        destination, fragment = destination.split("#", 1)
    destination = destination.split("?", 1)[0]
    if destination == "":
        return from_path.split("/"), fragment
    if destination.startswith("/"):
        parts = []
        pieces = destination[1:].split("/")
    else:
        parts = from_path.split("/")[:-1]
        pieces = destination.split("/")
    for piece in pieces:
        if piece in ("", "."):
            continue
        if piece == "..":
            if not parts:
                return None, fragment
            parts.pop()
            continue
        parts.append(piece)
    if destination.endswith("/") and parts:
        parts[-1] = parts[-1] + "/"
    return parts, fragment


def locate(items, from_item, destination, assets=()):
    """Resolve one relative destination to ('item', slug, anchor) / ('asset', path, None)
    / ('escape', None, None) / ('missing', path, anchor)."""
    parts, fragment = resolve_path(item_path(from_item), destination)
    if parts is None:
        return ("escape", None, None)
    path = "/".join(parts)
    if path.startswith("assets/") and path[len("assets/"):] in assets:
        return ("asset", path, None)
    clean = path.rstrip("/")
    if clean.endswith(".md"):
        clean = clean[:-3]
    for item in items:
        if item_path(item)[:-3] == clean:
            return ("item", item["slug"], fragment)
    return ("missing", path, fragment)


def body_link_report(items, assets=()):
    """AGSC-03-11 over every item body: resolved, unresolved and skipped external targets."""
    resolved, unresolved, external, findings = [], [], [], []
    anchor_sets = dict((item["slug"], set(anchors(item.get("body") or ""))) for item in items)
    for item in sorted(items, key=lambda one: one["slug"]):
        for link in markdown.links(item.get("body") or ""):
            destination = link.destination
            if is_external(destination):
                external.append(destination)
                continue
            kind, where, fragment = locate(items, item, destination, assets)
            if kind == "escape":
                unresolved.append(destination)
                findings.append(err("AGSC-E902", "%s escapes the Bundle root" % destination,
                                    file=item_path(item), line=link.line))
            elif kind == "asset" or (kind == "item" and (
                    fragment is None or fragment in anchor_sets[where])):
                resolved.append(destination)
            else:
                unresolved.append(destination)
                findings.append(err("AGSC-E310", "%s does not resolve" % destination,
                                    file=item_path(item), line=link.line))
    return {"external": external, "findings": findings, "resolved": resolved,
            "unresolved": unresolved}


def mentions(items):
    """AGSC-05-27: one (referrer, referenced) pair per pair of distinct items linked inline."""
    pairs = set()
    for item in items:
        for link in markdown.links(item.get("body") or ""):
            if is_external(link.destination):
                continue
            kind, where, _ = locate(items, item, link.destination)
            if kind == "item" and where != item["slug"]:
                pairs.add((item["slug"], where))
    return sorted(pairs)
