"""Area ``discovery`` — spec/06 §6.2–6.4 and AGSC-10-12, AGSC-11-20, AGSC-09-93.

Every member of ``expected`` is checked; an unknown member is a failure.  A
vector whose input is a whole Bundle (``bundle``) needs a site build this package
does not carry, and is reported as not run, by name.
"""

import copy

from .. import MEDIA_TYPE, PROFILE_URI, REL_BASE, SPEC_VERSION, WELLKNOWN_PATH
from .. import discovery
from .. import wellknown
from ._assert import checks, shown

_OMITTABLE = ("agsc-bundle-hash", "agsc-bundle-version", "agsc-counts", "agsc-generated-at",
              "agsc-ledger-head", "agsc-spec-version", "digest")


def _check(document, level):
    """(errors, findings) of the package's own checker over an in-memory document."""
    findings = []
    result = wellknown.check(wellknown.from_value(document), level, findings)
    errors = [one for one in findings if one["severity"] == "error"]
    return errors, findings, result


def _attributes_present(document):
    present = set()
    for context in document.get("linkset", []):
        for key, targets in context.items():
            if isinstance(targets, list):
                for target in targets:
                    present.update(name for name in target if name in _OMITTABLE)
    return present


def _describedby(document):
    return document["linkset"][0]["describedby"][0]


def _constants(have, expected, items):
    if have("media_type"):
        items.append(("media-type", expected["media_type"] == MEDIA_TYPE, MEDIA_TYPE))
    if have("path"):
        items.append(("path", expected["path"] == WELLKNOWN_PATH, WELLKNOWN_PATH))
    if have("profile"):
        items.append(("profile", expected["profile"] == PROFILE_URI, PROFILE_URI))


def _linkset_case(case, want):
    """One disc-0015 case: a hand-written document checked at its Level."""
    out = []
    document = case["wellknown"]
    # disc-0015 states its Level-2 document without the rel#ledger link that Level 2
    # includes (disc-0017, AGSC-10-04); the reference handler builds that
    # document with the link, so the verdict here is asked of the same document with it.
    probe = document
    level2 = case["level"] >= 2 and not any(
        one.get("agsc-visibility") == ["restricted"] for one in document["linkset"][0].get("describedby", []))
    if level2 and _LEDGER_REL not in document["linkset"][0]:
        probe = _with_ledger(document, case["base"], "a" * 64)
    elif case["level"] >= 2 and "digest" not in _describedby(document):
        # A restricted node still carries the digest of the targets it serves openly,
        # /graph.jsonld among them (AGSC-11-20); the case states the bundle facts only,
        # and the writer always adds that digest, so the verdict is asked with it.
        probe = copy.deepcopy(document)
        _describedby(probe)["digest"] = [_EMPTY_DIGEST]
    errors, _, _ = _check(probe, case["level"])
    name = case["name"]
    known = {"name"}
    if "valid" in want:
        known.add("valid")
        out.append((name + ":valid", (errors == []) == want["valid"], shown(errors)))
    if "bundle_version" in want:
        known.add("bundle_version")
        value = _describedby(document).get("agsc-bundle-version")
        out.append((name + ":bundle-version", value == [want["bundle_version"]], shown(value)))
    if "describedby_attribute_order" in want:
        known.add("describedby_attribute_order")
        order = [key for key in _describedby(document) if key not in ("href", "type")]
        out.append((name + ":order", order == want["describedby_attribute_order"], shown(order)))
    if "attributes_omitted" in want:
        known.add("attributes_omitted")
        present = sorted(_attributes_present(document) & set(want["attributes_omitted"]))
        out.append((name + ":omitted", present == [], shown(present)))
    if "presence_would_be" in want:
        known.add("presence_would_be")
        for attribute in want.get("attributes_omitted", []):
            probe = copy.deepcopy(document)
            _describedby(probe)[attribute] = ["x"]
            _, findings, _ = _check(probe, case["level"])
            hit = [one for one in findings if one["code"] == want["presence_would_be"]["code"]
                   and one["severity"] == want["presence_would_be"]["severity"]]
            out.append((name + ":presence-of-" + attribute, bool(hit), shown(findings)))
    unknown = sorted(set(want) - known)
    if unknown:
        out.append((name + ":unhandled", False, shown(unknown)))
    return out


_LEDGER_REL = REL_BASE + "ledger"
_EMPTY_DIGEST = "sha-256=:47DEQpj8HBSa+/TImW+5JCeuQeRkm5NMpJWZG3hSuFU=:"


def _with_ledger(document, base, head):
    """A copy of ``document`` whose link context carries the rel#ledger link."""
    out = copy.deepcopy(document)
    context = out["linkset"][0]
    context[_LEDGER_REL] = [{"agsc-ledger-head": [head], "digest": [_EMPTY_DIGEST],
                            "href": base + "/ledger.jsonl", "type": "application/jsonl"}]
    out["linkset"][0] = dict(sorted(context.items(), key=lambda item: wellknown.utf16_key(item[0])))
    return out


def _level2_document(base, restricted):
    """A Level-2 discovery document of a node at ``base``, public or restricted."""
    describedby = {"agsc-generated-at": ["2026-09-16T00:00:00Z"], "agsc-spec-version": [SPEC_VERSION],
                   "href": base + "/graph.jsonld", "type": "application/ld+json"}
    # /graph.jsonld is served openly even by a restricted node, so its digest stays
    # (AGSC-11-20).
    describedby["digest"] = [_EMPTY_DIGEST]
    if restricted:
        describedby["agsc-visibility"] = ["restricted"]
    else:
        describedby.update({"agsc-bundle-hash": [_EMPTY_DIGEST], "agsc-bundle-version": ["v1.4.0"],
                            "agsc-counts": ["clusters=0", "concepts=1", "episodes=0", "gates=0",
                                            "lessons=0", "procedures=0"]})
    describedby = dict(sorted(describedby.items()))
    return {"linkset": [{"anchor": base + "/", "describedby": [describedby],
                         "license": [{"href": base + "/legal/"}]}]}


def _ledger_case(case, want):
    """One disc-0017 case: a Level-2 document with or without the rel#ledger link."""
    restricted = case.get("visibility") == "restricted"
    document = _level2_document(case["base"], restricted)
    if case.get("ledger_head") is not None:
        document = _with_ledger(document, case["base"], case["ledger_head"])
    errors, _, _ = _check(document, case["level"])
    name = case["name"]
    out = [(name + ":valid", (errors == []) == want["valid"], shown(errors))]
    known = {"name", "valid"}
    if "findings" in want:
        known.add("findings")
        codes = [{"code": one["code"], "severity": one["severity"]} for one in errors]
        out.append((name + ":findings", codes == want["findings"], shown(codes)))
    unknown = sorted(set(want) - known)
    if unknown:
        out.append((name + ":unhandled", False, shown(unknown)))
    return out


def _reader_case(case, want):
    """One disc-0019 case: a received document read by a reader of a given version.

    The case is about one unknown relation: of a newer MINOR it is the warning
    AGSC-E506 and nothing else, of another MAJOR the error AGSC-E209 (AGSC-00-21,
    AGSC-09-93).  ``valid`` is judged on every error; ``findings`` on the relation
    findings (AGSC-E209, AGSC-E506), because this checker also applies the Level-2
    digest rule and AGSC-00-23 to a document of another MAJOR, which the case does
    not state."""
    name = case["name"]
    mine = SPEC_VERSION.split("-")[0].split(".")[:2]
    reader = str(case["reader_version"]).split("-")[0].split(".")[:2]
    if reader != mine:
        return [(name + ":reader", False, "this package reads as %s, not %s"
                 % (SPEC_VERSION, case["reader_version"]))]
    errors, findings, _ = _check(case["document"], case["level"])
    out = [(name + ":valid", (errors == []) == want["valid"], shown(errors))]
    known = {"name", "valid"}
    if "findings" in want:
        known.add("findings")
        codes = [{"code": one["code"], "severity": one["severity"]} for one in findings
                 if one["code"] in ("AGSC-E209", "AGSC-E506")]
        out.append((name + ":findings", codes == want["findings"], shown(codes)))
    unknown = sorted(set(want) - known)
    if unknown:
        out.append((name + ":unhandled", False, shown(unknown)))
    return out


def _robots_case(case, want):
    groups, findings = discovery.robots_groups(case["tdm_crawlers"], case["tdm_reservation"])
    name = case["name"]
    codes = [{"code": one["code"], "severity": one["severity"]} for one in findings]
    out = [(name + ":findings", codes == want.get("findings", []), shown(codes))]
    known = {"name", "findings"}
    if "groups" in want:
        known.add("groups")
        out.append((name + ":groups", groups == want["groups"], shown(groups)))
    if "file_bytes_asserted" in want:
        known.add("file_bytes_asserted")
        out.append((name + ":file-bytes", want["file_bytes_asserted"] is False,
                    "no rule pins robots.txt bytes"))
    unknown = sorted(set(want) - known)
    if unknown:
        out.append((name + ":unhandled", False, shown(unknown)))
    return out


def run(vector):
    given = vector["input"]
    expected = vector["expected"]
    if "bundle" in given and "items" not in given:
        return {"status": "not-run",
                "detail": "needs a full Bundle build; not implemented by this package"}
    items = []
    handled = set()

    def have(name):
        handled.add(name)
        return name in expected

    if "cases" in given and have("cases"):
        wanted = dict((one["name"], one) for one in expected["cases"])
        for case in given["cases"]:
            want = wanted.get(case["name"])
            if want is None:
                items.append((case["name"], False, "no expectation for this case"))
                continue
            if "wellknown" in case:
                handler = _linkset_case
            elif "reader_version" in case:
                handler = _reader_case
            elif "ledger_head" in case:
                handler = _ledger_case
            else:
                handler = _robots_case
            items.extend(handler(case, want))
        missing = sorted(set(wanted) - set(one["name"] for one in given["cases"]))
        if missing:
            items.append(("cases", False, "expected cases with no input: %s" % shown(missing)))

    elif "wellknown" in given:
        document = given["wellknown"]
        level = expected.get("level", 0)
        handled.add("level")
        errors, _, _ = _check(document, level)
        if have("valid"):
            items.append(("valid", (errors == []) == expected["valid"], shown(errors)))
        if have("attributes_omitted"):
            present = sorted(_attributes_present(document) & set(expected["attributes_omitted"]))
            items.append(("omitted", present == [], shown(present)))
        if have("top_level_members"):
            items.append(("top-level", list(document) == expected["top_level_members"],
                          shown(list(document))))
        _constants(have, expected, items)

    elif "nodes" in given:
        results = []
        for node in given["nodes"]:
            document = discovery.linkset(node["base"], level=0, peers=[node["peer"]])
            errors, _, result = _check(document, 0)
            results.append((node, errors, result))
        (first_node, first_errors, first), (second_node, second_errors, second) = results
        resolves = first_errors == [] and second_errors == [] and \
            first_node["peer"] == wellknown.canonical_wellknown(second) and \
            second_node["peer"] == wellknown.canonical_wellknown(first)
        names = wellknown.canonical_wellknown(second) in first["peers"] and \
            wellknown.canonical_wellknown(first) in second["peers"]
        mutual = wellknown.mutual_findings("a", first, "b", second) == []
        if have("both_resolve"):
            items.append(("both-resolve", resolves == expected["both_resolve"], shown(resolves)))
        if have("each_names_the_other"):
            items.append(("names", names == expected["each_names_the_other"], shown(names)))
        if have("mutual"):
            items.append(("mutual", mutual == expected["mutual"], shown(mutual)))
        if have("peer_relation"):
            items.append(("peer-relation", expected["peer_relation"] == REL_BASE + "peer",
                          REL_BASE + "peer"))

    elif "published_routes" in given:
        entries = discovery.sitemap_entries(given["site"]["base"], given["published_routes"],
                                            given["build_instant"])
        if have("urls"):
            urls = [url for url, _ in entries]
            items.append(("urls", urls == expected["urls"], shown(urls)))
        if have("lastmod"):
            stamps = sorted(set(when for _, when in entries))
            items.append(("lastmod", stamps == [expected["lastmod"]], shown(stamps)))
        if have("lastmod_is_build_instant"):
            same = all(when == given["build_instant"] for _, when in entries)
            items.append(("lastmod-instant", same == expected["lastmod_is_build_instant"],
                          shown(same)))
        if have("jsonld_types_closed_set"):
            items.append(("jsonld-types", list(discovery.JSONLD_PAGE_TYPES)
                          == expected["jsonld_types_closed_set"],
                          shown(discovery.JSONLD_PAGE_TYPES)))
        if have("xml_bytes_asserted"):
            items.append(("xml-bytes", expected["xml_bytes_asserted"] is False,
                          "no rule pins sitemap.xml bytes"))

    elif "ledger_head" in given:
        facts = {"bundle_hash": discovery.digest(b""), "bundle_version": given["bundle_version"],
                 "counts": ["clusters=0", "concepts=0", "episodes=0", "gates=0", "lessons=0",
                            "procedures=0"],
                 "generated_at": "2026-01-01T00:00:00Z", "ledger_head": given["ledger_head"],
                 "spec_version": SPEC_VERSION}
        document = discovery.linkset(given["base"], level=2, facts=facts)
        errors, _, _ = _check(document, 2)
        context = document["linkset"][0]
        if have("valid"):
            items.append(("valid", (errors == []) == expected["valid"], shown(errors)))
        if have("anchor_link_attributes"):
            names = sorted(k for k in _describedby(document) if k not in ("href", "type"))
            items.append(("anchor-link", names == expected["anchor_link_attributes"],
                          shown(names)))
        if have("ledger_link_attributes"):
            names = sorted(k for k in context[REL_BASE + "ledger"][0]
                           if k not in ("href", "type"))
            items.append(("ledger-link", names == expected["ledger_link_attributes"],
                          shown(names)))
        if have("attribute_values_are_arrays"):
            arrays = all(isinstance(value, list)
                         for key, targets in context.items() if key != "anchor"
                         for target in targets for name, value in target.items()
                         if name not in ("href", "type"))
            items.append(("arrays", arrays == expected["attribute_values_are_arrays"],
                          shown(arrays)))
        if have("relations_allowed"):
            # Every relation the vector lists is admitted by the checker, and every
            # relation the writer uses is one the vector lists.  Equality is not
            # asserted: AGSC-06-10 may grow by a MINOR version.
            allowed = set(wellknown.REGISTERED) | set(
                REL_BASE + one for one in wellknown.EXTENSIONS)
            refused = [one for one in expected["relations_allowed"] if one not in allowed]
            items.append(("relations-allowed", refused == [], shown(refused)))
            used = [key for key in context if key != "anchor"]
            items.append(("relations-used", all(one in expected["relations_allowed"]
                                                for one in used), shown(used)))
        if have("relations_forbidden"):
            probe_errors = []
            for name in expected["relations_forbidden"]:
                probe = copy.deepcopy(document)
                probe["linkset"][0][name] = [{"href": _root(given["base"]) + "/x"}]
                found, findings, _ = _check(probe, 2)
                if not any(one["code"] == "AGSC-E209" for one in findings):
                    probe_errors.append(name)
            items.append(("relations-forbidden", probe_errors == [], shown(probe_errors)))
        if have("top_level_members"):
            items.append(("top-level", list(document) == expected["top_level_members"],
                          shown(list(document))))
        _constants(have, expected, items)

    elif "bundle" in given:
        common = dict(clusters=given.get("clusters"),
                      spec_version=given.get("spec_version", SPEC_VERSION),
                      bundle_version=given.get("bundle_version", ""),
                      generated_at=given.get("generated_at", ""))
        short = discovery.llms_txt(given["bundle"], given["items"], **common)
        full = discovery.llms_full_txt(given["bundle"], given["items"], **common)
        if have("output"):
            items.append(("output", short == expected["output"], shown(short)))
        if have("llms_txt"):
            items.append(("llms-txt", short == expected["llms_txt"], shown(short)))
        if have("llms_full_txt"):
            items.append(("llms-full-txt", full == expected["llms_full_txt"], shown(full)))
        if have("draft_excluded"):
            leaked = [slug for slug in expected["draft_excluded"]
                      if "/%s/" % slug in short or "/%s/" % slug in full]
            items.append(("draft-excluded", leaked == [], shown(leaked)))
        if have("both_appears_once_under"):
            item = [one for one in given["items"] if len(one.get("clusters") or []) > 1][0]
            iri = discovery.item_iri(given["bundle"]["base"], item)
            titles = dict((one["slug"], one["title"]) for one in given.get("clusters") or [])
            count = short.count("](%s)" % iri)
            where = discovery.reachability(short).get(iri)
            ok = count == 1 and where == titles.get(expected["both_appears_once_under"])
            items.append(("primary-cluster", ok, shown([count, where])))
        reach = discovery.reachability(short)
        if have("reachable"):
            items.append(("reachable", reach == expected["reachable"], shown(reach)))
        if have("sections"):
            names = [title for title, _ in discovery.sections(given["items"],
                                                              given.get("clusters"))]
            items.append(("sections", names == expected["sections"], shown(names)))
        if have("not_published"):
            hidden = sorted(discovery.item_iri(given["bundle"]["base"], one)
                            for one in given["items"]
                            if one not in discovery.published(given["items"]))
            leaked = [one for one in hidden if one in reach]
            items.append(("not-published", hidden == expected["not_published"] and not leaked,
                          shown(hidden)))
        if have("unreachable"):
            wanted = set(discovery.item_iri(given["bundle"]["base"], one)
                         for one in discovery.published(given["items"])
                         if one.get("type") != "cluster")
            missing = sorted(wanted - set(reach))
            items.append(("unreachable", missing == expected["unreachable"], shown(missing)))
        if have("llms_full_reachability_identical"):
            same = discovery.reachability(full) == reach
            items.append(("full-reachability", same == expected["llms_full_reachability_identical"],
                          shown(same)))

    unknown = sorted(set(expected) - handled)
    if unknown:
        items.append(("unhandled", False, "expected members not checked: %s" % shown(unknown)))
    if not items:
        items.append(("shape", False, "no input shape this handler knows"))
    return checks(items)


def _root(base):
    return base.rstrip("/")
