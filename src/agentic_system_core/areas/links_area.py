"""Area ``links`` — spec/03: inverses, cycles, the cluster tree, anchors,
inline-link resolution and orphans.

Every member of ``expected`` is checked; an unknown member is a failure.
``warnings`` is the whole list of warnings the Link checks report, each
``{code, slug}`` in slug order: at 1.0 these are the orphans of AGSC-03-10.
"""

from .. import links
from ._assert import checks, shown


def _errors(items):
    """Every error finding of the Link checks over a set of items, in rule order."""
    _, findings = links.edges(items)
    cycle = links.requires_cycle(items)
    if cycle:
        findings.append(links.err("AGSC-E302", "requires cycle: %s" % " -> ".join(cycle),
                                  cycle=cycle))
    findings.extend(links.hierarchy_findings(items))
    findings.extend(links.body_link_report(items)["findings"])
    return findings


def orphans(items):
    """AGSC-03-10: the items with no inbound Link and no ``clusters[]`` entry.

    An inbound Link is any Link edge whose target is the item, authored or computed
    (AGSC-03-04, AGSC-03-05); a ``clusters[]`` entry is an inbound reference to the
    cluster it names; an inline link is an ``asc:mentions`` edge and not a Link
    (AGSC-03-11), so it does not count.  Returns the warnings in slug order.
    """
    edges, _ = links.edges(items)
    inbound = set(edge["target"] for edge in edges)
    for item in items:
        for name in item.get("clusters") or []:
            inbound.add(name)
    out = []
    for item in sorted(items, key=lambda one: one["slug"]):
        if item["slug"] in inbound or item.get("clusters"):
            continue
        out.append({"code": "AGSC-E305", "slug": item["slug"]})
    return out


def run(vector):
    given = vector["input"]
    expected = vector["expected"]
    items = []
    handled = set()

    def have(name):
        handled.add(name)
        return name in expected

    if isinstance(given.get("markdown"), str):
        found = links.anchors(given["markdown"])
        if have("anchors"):
            items.append(("anchors", found == expected["anchors"], shown(found)))
        if have("errors"):
            items.append(("errors", expected["errors"] == [], "anchors report no error"))
    else:
        given_items = given["items"]
        findings = _errors(given_items)
        codes = [one["code"] for one in findings]
        if have("edges"):
            edges, _ = links.edges(given_items)
            items.append(("edges", edges == expected["edges"], shown(edges)))
        if have("errors"):
            items.append(("errors", codes == expected["errors"], shown(codes)))
        if have("error"):
            items.append(("error", expected["error"] in codes, shown(codes)))
            first = [one for one in findings if one["code"] == expected["error"]]
            for member in ("cycle", "chain", "parents"):
                if have(member):
                    got = first[0].get(member) if first else None
                    items.append((member, got == expected[member], shown(got)))
        if have("warnings"):
            found = orphans(given_items)
            items.append(("warnings", found == expected["warnings"], shown(found)))
        if "resolved" in expected or "unresolved" in expected:
            report = links.body_link_report(given_items)
            for member, key in (("resolved", "resolved"), ("unresolved", "unresolved"),
                                ("skipped_external", "external")):
                if have(member):
                    items.append((member, report[key] == expected[member], shown(report[key])))

    unknown = sorted(set(expected) - handled)
    if unknown:
        items.append(("unhandled", False, "expected members not checked: %s" % shown(unknown)))
    return checks(items)
