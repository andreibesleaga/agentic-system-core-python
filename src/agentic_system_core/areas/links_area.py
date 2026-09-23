"""Area ``links`` — spec/03: inverses, cycles, the cluster tree, anchors and
inline-link resolution.

Every member of ``expected`` is checked; an unknown member is a failure.
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
