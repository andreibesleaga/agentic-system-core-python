"""The ``discovery`` cases of the web connection and of the 1.1 chunk facts.

Each handler is the twin of the engine's handler of the same vector in
``tests/conformance/areas/_discovery-web.js``, and calls the module that gives the data
the case pins:

* disc-0026 (AGSC-06-40) — the Signposting links of ``/`` as a set of {href, rel, type}
  (``signposting.home_links``), and the checker's warning AGSC-E202 for a home page
  whose ``Link`` header lacks the ``describedby`` link
  (``wellknown_facts.home_link_findings``);
* disc-0027 (AGSC-06-41) — the Dataset block of the home page, as a JSON value
  (``signposting.dataset_block``);
* disc-0028, disc-0029 (AGSC-06-42) — ``/.well-known/ai-catalog.json`` and
  ``/.well-known/ard.json``, as bytes, with their findings (``catalogue``);
* disc-0030, disc-0031 (AGSC-06-34, AGSC-06-07) — the agent card as bytes, or none and
  why (``agentcard``);
* disc-0033 (AGSC-06-44, AGSC-09-93 (b)) — this package's checker at the case's Level
  over the document and the files it names, held as a build output: valid, and the
  codes reported (``wellknown.from_build``).

Every member of ``expected`` a handler does not read is a failure, so a case never
passes on an assertion nobody made.
"""

from .. import agentcard, catalogue, signposting, wellknown, wellknown_facts
from ._assert import checks, shown

#: The routes every disc-0026 node writes (the engine's handler lists the same).
_HOME_ROUTES = ("/index.html", "/.well-known/knowledge-linkset", "/graph.jsonld", "/graph.nq",
                "/graph.ttl")


def _by_name(cases):
    return dict((one["name"], one) for one in cases or [])


def _codes(found):
    return [{"code": one["code"], "severity": one["severity"]} for one in found]


def _unknown(name, want, known):
    unknown = sorted(set(want) - set(known) - {"name"})
    return [(name + ":unhandled", False, shown(unknown))] if unknown else []


def _findings_match(expected, found):
    """Every expected finding is met by one found (code and severity), and no more."""
    got = _codes(found)
    missing = [one for one in expected if not any(
        all(other.get(key) == value for key, value in one.items()) for other in got)]
    return not missing and len(got) == len(expected), shown(got)


def _link_key(link):
    return shown(link)


def _signposting(vector):
    items = []
    wanted = _by_name(vector["expected"].get("cases"))
    for given in vector["input"]["cases"]:
        config = {"bundle": {} if "license_url" not in given else
                  {"license_url": given["license_url"]},
                  "related": given.get("related"), "site": {"base": given["base"]},
                  "visibility": given.get("visibility")}
        routes = list(_HOME_ROUTES) + (["/chunks.jsonl"] if given.get("chunks_served") else []) \
            + (["/legal/index.html"] if given.get("legal_emitted") else [])
        got = sorted(signposting.home_links(config, routes), key=_link_key)
        want = wanted.get(given["name"], {})
        expected = sorted(want.get("links_as_set") or [], key=_link_key)
        items.append((given["name"] + ":links", got == expected and "links_as_set" in want,
                      shown(got)))
        items.extend(_unknown(given["name"], want, ["links_as_set"]))
    validators = _by_name(vector["expected"].get("validator_cases"))
    for given in vector["input"].get("validator_cases") or []:
        want = validators.get(given["name"], {})
        found = wellknown_facts.home_link_findings(given["home_link_header"],
                                                   anchor="https://a.example/")
        ok, detail = _findings_match(want.get("findings") or [], found)
        items.append((given["name"] + ":findings", ok and "findings" in want, detail))
        items.extend(_unknown(given["name"], want, ["findings"]))
    return items


def _dataset(vector):
    items = []
    wanted = _by_name(vector["expected"]["cases"])
    for given in vector["input"]["cases"]:
        config = {"bundle": given.get("bundle"), "site": given.get("site"),
                  "visibility": given.get("visibility")}
        block = signposting.dataset_block(config, given["instant"], set(given["files_served"]),
                                          description=given.get("description"),
                                          name=(given.get("site") or {}).get("title"))
        want = wanted.get(given["name"], {})
        items.append((given["name"], "block" in want and block == want["block"], shown(block)))
        items.extend(_unknown(given["name"], want, ["block"]))
    return items


def _catalogue(route):
    def handler(vector):
        items = []
        wanted = _by_name(vector["expected"]["cases"])
        for given in vector["input"]["cases"]:
            config = {"bundle": {"id": given.get("bundle_id")},
                      "discovery": {"ai_catalog": given.get("ai_catalog")},
                      "site": given.get("site")}
            files, found = catalogue.catalogue_files(
                config, given["discovery_document_bytes"], card_bytes=given.get("card_bytes"),
                description=given.get("description"))
            want = wanted.get(given["name"], {})
            text = files.get(route)
            items.append((given["name"] + ":file", "file" in want and text == want["file"],
                          shown(text)))
            ok, detail = _findings_match(want.get("findings", []), found)
            items.append((given["name"] + ":findings", ok, detail))
            items.extend(_unknown(given["name"], want, ["file", "findings"]))
        return items
    return handler


def _card(vector):
    items = []
    wanted = _by_name(vector["expected"]["cases"])
    for given in vector["input"]["cases"]:
        surfaces = given.get("surfaces") or []
        text = agentcard.card_bytes(surfaces, given.get("packs") or [],
                                    (given.get("site") or {}).get("title"),
                                    given.get("bundle_version"), given.get("spec_version"),
                                    visibility=given.get("visibility"),
                                    description=given.get("description"))
        want = wanted.get(given["name"], {})
        items.append((given["name"] + ":file", "file" in want and text == want["file"],
                      shown(text)))
        if "findings" in want:
            ok, detail = _findings_match(want["findings"], agentcard.card_findings(surfaces))
            items.append((given["name"] + ":findings", ok, detail))
        items.extend(_unknown(given["name"], want, ["file", "findings"]))
    return items


def _chunk_surface(vector):
    items = []
    wanted = _by_name(vector["expected"]["cases"])
    for given in vector["input"]["cases"]:
        findings = []
        wellknown.check(wellknown.from_build(given["document"], given["files"]), given["level"],
                        findings)
        errors = [one for one in findings if one["severity"] == "error"]
        codes = sorted(set(one["code"] for one in findings))
        want = wanted.get(given["name"], {})
        items.append((given["name"] + ":valid", (errors == []) == want.get("valid"),
                      shown(findings)))
        items.append((given["name"] + ":codes", codes == want.get("codes_reported"), shown(codes)))
        items.extend(_unknown(given["name"], want, ["valid", "codes_reported"]))
    return items


#: vector id -> handler, as the engine's ``HANDLERS`` of ``_discovery-web.js``.
HANDLERS = {
    "disc-0026": _signposting,
    "disc-0027": _dataset,
    "disc-0028": _catalogue(catalogue.AI_CATALOG_PATH),
    "disc-0029": _catalogue(catalogue.ARD_PATH),
    "disc-0030": _card,
    "disc-0031": _card,
    "disc-0033": _chunk_surface,
}


def run(vector):
    """The verdict of one web-connection case, or None when the id is not one of them."""
    handler = HANDLERS.get(vector.get("id"))
    if handler is None:
        return None
    items = handler(vector)
    unknown = sorted(set(vector["expected"]) - {"cases", "validator_cases"})
    if unknown:
        items.append(("unhandled", False, "expected members not checked: %s" % shown(unknown)))
    if not items:
        items.append(("shape", False, "the case states no case this handler reads"))
    return checks(items)
