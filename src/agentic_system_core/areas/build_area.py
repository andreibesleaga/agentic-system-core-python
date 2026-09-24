"""Area ``build`` — AGSC-06-16/06-23 (search), AGSC-06-33 (fragments), AGSC-06-17
(headers), AGSC-06-36 (security.txt) and AGSC-04-25/06-22 (content version).

Every member of ``expected`` is checked; an unknown member is a failure.  A
vector whose input is a whole Bundle (``bundle`` or inline ``files``) needs a
site build this package does not carry, and is reported as not run, by name.
"""

from .. import site
from ..jcs import canonicalize
from ._assert import checks, shown
from .jcs_area import member_order as _member_order


def _codes(findings):
    return [{"code": one["code"], "severity": one["severity"]} for one in findings]


def _cases(given, expected, handler):
    items = []
    wanted = dict((one["name"], one) for one in expected["cases"])
    for case in given["cases"]:
        want = wanted.get(case["name"])
        if want is None:
            items.append((case["name"], False, "no expectation for this case"))
            continue
        items.extend(handler(case, want))
    return items


def _security(case, want, base):
    text, findings = site.security_txt(case["authored"], case["instant"], base,
                                       case["legal"])
    out = [(case["name"] + ":text", text == want["text"], shown(text)),
           (case["name"] + ":findings", _codes(findings) == want["findings"],
            shown(_codes(findings)))]
    unknown = sorted(set(want) - {"findings", "name", "text"})
    if unknown:
        out.append((case["name"] + ":unhandled", False, shown(unknown)))
    return out


def _version(case, want):
    out = []
    if "git_log" in case:
        version, findings = site.content_version(case["git_log"], case["source_date_epoch"])
        out.append((case["name"] + ":version", version == want["bundle_version"], version))
        out.append((case["name"] + ":findings", _codes(findings) == want["findings"],
                    shown(_codes(findings))))
        if "ledger_kind_of_built_commit" in want:
            kind = site.ledger_kind(case["git_log"][-1])
            out.append((case["name"] + ":ledger-kind",
                        kind == want["ledger_kind_of_built_commit"], kind))
        unknown = set(want) - {"bundle_version", "findings", "ledger_kind_of_built_commit",
                               "name"}
    else:
        line = site.now_line(case["bundle_version"], case["generated_at"],
                             case["bundle_hash"], case["spec_version"])
        out.append((case["name"] + ":now-line", line in want["contains"], line))
        unknown = set(want) - {"contains", "name"}
    if unknown:
        out.append((case["name"] + ":unhandled", False, shown(sorted(unknown))))
    return out


#: Input shapes that need a full Bundle build (AGSC-04-02, AGSC-04-07).
NEEDS_BUILD = ("bundle", "files")


def run(vector):
    given = vector["input"]
    expected = vector["expected"]
    if any(shape in given for shape in NEEDS_BUILD):
        return {"status": "not-run",
                "detail": "needs a full Bundle build; not implemented by this package"}
    items = []
    handled = set()

    def have(name):
        handled.add(name)
        return name in expected

    if "build_instant" in given and have("stale"):
        got = site.stale_items(given["items"], given["build_instant"])
        items.append(("stale", got == expected["stale"], shown(got)))
    elif "items" in given:
        value = site.search_index(given["items"])
        if have("search"):
            items.append(("search", canonicalize(value) == canonicalize(expected["search"]),
                          canonicalize(value)))
        if have("output"):
            text = site.search_json(given["items"])
            items.append(("output", text == expected["output"], shown(text)))
        if have("wrong_if_code_point_sorted"):
            text = site.search_json(given["items"])
            names = list(value["terms"])
            code_point = sorted(names)
            utf16 = [one for one in _member_order(text) if one in value["terms"]]
            items.append(("not-code-point-order",
                          utf16 != code_point or len(names) < 2, shown(utf16)))
    elif "nquads" in given:
        files, index = site.fragments(given["nquads"], given["generated_at"])
        if have("index"):
            items.append(("index", canonicalize(index) == canonicalize(expected["index"]),
                          canonicalize(index)))
        if have("object_files"):
            objects = sorted(path for path in files if path.startswith("o/"))
            items.append(("object-files", objects == expected["object_files"], shown(objects)))
    elif "routes" in given:
        if have("headers"):
            headers = site.header_set(given["routes"])
            items.append(("headers", headers == expected["headers"], shown(headers)))
        if have("redirects"):
            items.append(("redirects", site.redirects() == expected["redirects"],
                          shown(site.redirects())))
        if have("header_fallback_admitted"):
            items.append(("fallback", site.PROFILE_LINK_HEADER
                          == expected["header_fallback_admitted"], site.PROFILE_LINK_HEADER))
        if have("file_bytes_asserted"):
            items.append(("file-bytes", expected["file_bytes_asserted"] is False,
                          "a byte assertion needs a rule that pins the file grammar"))
    elif "cases" in given and have("cases"):
        if any("authored" in case for case in given["cases"]):
            items.extend(_cases(given, expected,
                                lambda case, want: _security(case, want, given["base"])))
        else:
            items.extend(_cases(given, expected, _version))

    unknown = sorted(set(expected) - handled)
    if unknown:
        items.append(("unhandled", False, "expected members not checked: %s" % shown(unknown)))
    if not items:
        items.append(("shape", False, "no input shape this handler knows"))
    return checks(items)
