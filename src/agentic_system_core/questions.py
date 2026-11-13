"""The ten questions of the graph (AGSC-05-34, the competency questions of AGSC-05-13).

What: each question is a function of the items of the published projection
(AGSC-06-30), the subject, and for questions 4 and 9 a selection and an instant. The
answer has the shape of the table in the rule; every list is sorted by code point, has
no repeats and never holds the subject.

Why: ``graph-0030`` to ``graph-0039`` pin one answer each, and a port that answers the
same questions must give the same lists. The engine's ``src/knowledge/questions.js`` is
the reference. The SPARQL text of the questions is informative and is not run here,
as the engine does not run it. Edges come from ``links.edges``, the key names from the
relation table, and instants are read without a clock.

Standard library only.
"""

import re

from . import links
from .relations import INVERSE

_INSTANT = re.compile(r"^(\d{4})-(\d{2})-(\d{2})(?:[T ](\d{2}):(\d{2})(?::(\d{2})(?:\.(\d+))?)?"
                      r"(Z|[+-]\d{2}:?\d{2})?)?$")


def _sorted(values):
    return sorted(set(values))


def _list(item, key):
    value = item.get(key)
    return value if isinstance(value, list) else []


def days_from_civil(year, month, day):
    """Days since 1970-01-01 of a proleptic Gregorian date."""
    year = year - 1 if month <= 2 else year
    era = year // 400
    yoe = year - era * 400
    doy = (153 * (month + (-3 if month > 2 else 9)) + 2) // 5 + day - 1
    return era * 146097 + yoe * 365 + yoe // 4 - yoe // 100 + doy - 719468


def instant_of(value):
    """Milliseconds since the epoch of an ISO date or date-time (a date is its midnight,
    UTC), or None when it does not parse."""
    match = _INSTANT.match(str(value))
    if match is None:
        return None
    year, month, day, hour, minute, second = (int(part or 0) for part in match.groups()[:6])
    zone = match.group(8)
    offset = 0
    if zone and zone != "Z":
        offset = (-1 if zone[0] == "-" else 1) * (int(zone[1:3]) * 60 + int(zone[-2:]))
    fraction = float("0." + match.group(7)) * 1000 if match.group(7) else 0
    minutes = (days_from_civil(year, month, day) * 24 + hour) * 60 + minute - offset
    return minutes * 60000 + second * 1000 + fraction


def is_stale(stale_after, at):
    """AGSC-02-11: stale means ``stale_after`` is earlier than the instant, both read as
    instants; text order where either does not parse."""
    if stale_after is None:
        return False
    first, second = instant_of(stale_after), instant_of(at)
    if first is None or second is None:
        return str(stale_after) < str(at)
    return first < second


def _neighbours(items, key):
    edges, _ = links.edges(items)
    adjacency = {}
    for edge in edges:
        if edge["key"] == key:
            adjacency.setdefault(edge["source"], []).append(edge["target"])
    return adjacency


def _reach(adjacency, start):
    """The items reached from ``start`` by one or more steps, never ``start`` itself."""
    seen = {start}
    queue = [start]
    while queue:
        for following in adjacency.get(queue.pop(0), []):
            if following not in seen:
                seen.add(following)
                queue.append(following)
    seen.discard(start)
    return sorted(seen)


def _reached_by(items, subject, key):
    return _reach(_neighbours(items, key), subject)


def _never_with(items, subject):
    return _sorted(one for one in _neighbours(items, "excludes").get(subject, [])
                   if one != subject)


def _missing_ports(items, subject, selection):
    provided = set()
    for item in items:
        if item["slug"] == subject or item["slug"] in selection:
            provided.update(_list(item, "produces"))
    own = [one for one in items if one["slug"] == subject]
    return _sorted(name for name in (_list(own[0], "consumes") if own else [])
                   if name not in provided)


def _verification(items, subject):
    def adjacent(key):
        return _sorted(_neighbours(items, key).get(subject, []))
    return {"verified_by": adjacent(INVERSE["verifies"]), "verifies": adjacent("verifies")}


def _lineage(items, subject):
    origin = _reached_by(items, subject, "derived-from")
    episodes = set(item["slug"] for item in items if item.get("type") == "episode")
    return {"episodes": [slug for slug in origin if slug in episodes], "lineage": origin}


def _under_cluster(items, subject):
    """Nesting is ``broader`` of a cluster (AGSC-05-19)."""
    clusters = set(item["slug"] for item in items if item.get("type") == "cluster")
    children = {}
    edges, _ = links.edges(items)
    for edge in edges:
        if edge["key"] == "broader" and edge["source"] in clusters:
            children.setdefault(edge["target"], []).append(edge["source"])
    below = _reach(children, subject)
    inside = set([subject] + below)
    members = [item["slug"] for item in items if item["slug"] not in clusters
               and any(name in inside for name in _list(item, "clusters"))]
    return {"clusters": below, "items": _sorted(members)}


def _unhealthy(items, selection, at):
    by_slug = dict((item["slug"], item) for item in items)
    out = []
    for slug in _sorted(selection):
        if slug not in by_slug:
            continue
        item = by_slug[slug]
        reasons = [status for status in ("deprecated", "draft", "retired")
                   if item.get("status") == status]
        if is_stale(item.get("stale_after"), at):
            reasons.append("stale")
        if reasons:
            out.append({"reasons": reasons, "slug": slug})
    return out


def _sources_and_sharers(items, subject):
    def resources(item):
        return [one.get("resource") for one in _list(item, "sources")
                if isinstance(one, dict) and isinstance(one.get("resource"), str)]
    own = [one for one in items if one["slug"] == subject]
    sources = _sorted(resources(own[0]) if own else [])
    others = [item for item in items if item["slug"] != subject]
    shared = []
    for resource in sources:
        sharers = _sorted(item["slug"] for item in others if resource in resources(item))
        if sharers:
            shared.append({"items": sharers, "resource": resource})
    return {"shared": shared, "sources": sources}


def answer(number, items, subject=None, selection=(), at=None):
    """Question ``number`` (1 to 10) of AGSC-05-34, by its number in the table."""
    selection = list(selection)
    table = {
        1: lambda: _reached_by(items, subject, "requires"),
        2: lambda: _never_with(items, subject),
        3: lambda: _reached_by(items, subject, INVERSE["supersedes"]),
        4: lambda: _missing_ports(items, subject, selection),
        5: lambda: _verification(items, subject),
        6: lambda: _reached_by(items, subject, "blocked-by"),
        7: lambda: _lineage(items, subject),
        8: lambda: _under_cluster(items, subject),
        9: lambda: _unhealthy(items, selection, at),
        10: lambda: _sources_and_sharers(items, subject),
    }
    if number not in table:
        raise ValueError("AGSC-05-34: there are ten questions, numbered 1 to 10, not %r"
                         % (number,))
    return table[number]()
