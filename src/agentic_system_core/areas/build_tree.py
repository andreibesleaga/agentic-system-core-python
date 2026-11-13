"""The ``build`` cases whose expectations are facts about a whole build (build-0020 to
build-0028): AGSC-00-05 (what a retired and a draft item leave on each surface),
AGSC-01-19 (``build.out`` naming ``content/`` or ``dist/`` is refused), AGSC-01-20 (the
release switchboard), AGSC-05-07 (the page copy drops a Link to a draft), AGSC-06-01
(the route set), AGSC-07-19 and AGSC-07-20 (``/skills/index.json`` and its locks) and
AGSC-06-18 (the TDM reservation file and its robots groups).

This package writes no site, so it cannot produce the files these cases speak about;
``run-vectors`` reports them as not run.  What it can do is read a tree another writer
built and check every expectation against it, so the cases are checked by a second
implementation.  :func:`check` takes the vector and ``build``, a callable that runs a
build for a sub-case (or ``None``) and returns ``{"exit", "findings", "files",
"written"}``: the exit code, the findings of the ``--json`` envelope, the bytes of each
file under ``build.out`` by route (``/index.html``), and every path the run added
anywhere in the Bundle.  The test suite passes one that runs the engine's build.  The
checks follow the engine's handler, ``tests/conformance/areas/_build-surfaces.js``,
member for member; a member nothing reads is a failure.
"""

import hashlib
import json
import posixpath
import re

from ..jcs import canonicalize
from ._assert import checks, shown

#: The members one build's surface checks read (build-0020, 0022, 0023, 0028).
SURFACE_MEMBERS = frozenset(("carried_by", "files_contain", "in_no_file", "no_error_finding",
                             "not_carried_by", "route_bytes", "routes_absent", "routes_present"))


def file_of(route):
    """The file a route is served from: a route ending in ``/`` is its ``index.html``."""
    return route + "index.html" if route.endswith("/") else route


def _text(files, route):
    data = files.get(file_of(route))
    return None if data is None else data.decode("utf-8")


def _same(one, other):
    """Equal JSON values: arrays in order, objects in any member order, ``true`` never ``1``."""
    return canonicalize(one) == canonicalize(other)


def _parse(text, fallback):
    try:
        return json.loads(text)
    except (TypeError, ValueError):
        return fallback


def is_jcs_with_one_lf(text):
    """AGSC-04-04: one JSON value in JCS form followed by exactly one LF."""
    if text is None or not text.endswith("\n") or text.endswith("\n\n"):
        return False
    value = _parse(text, None)
    return value is not None and canonicalize(value) + "\n" == text


# --- one build, the surfaces -------------------------------------------------------

def _clean_build(expected, run):
    errors = [one["code"] for one in run["findings"] if one.get("severity") == "error"]
    ok = (not errors) == expected["no_error_finding"] and run["exit"] == 0
    return [("no error finding", ok, "exit %s %s" % (run["exit"], shown(errors)))]


def _strings(expected, member, files, wanted):
    """``carried_by``, ``not_carried_by``, ``files_contain``: route -> strings."""
    out = []
    for route, strings in sorted(expected.get(member, {}).items()):
        body = _text(files, route)
        for one in strings:
            ok = body is not None and (one in body) == wanted
            out.append(("%s %s %s" % (route, member, one), ok,
                        "absent" if body is None else shown(body[:400])))
    return out


def surface_checks(expected, run):
    """Every surface member a vector states over one build."""
    files = run["files"]
    out = _clean_build(expected, run) if "no_error_finding" in expected else []
    out.extend(("emits " + route, file_of(route) in files, route)
               for route in expected.get("routes_present", []))
    out.extend(("no " + route, file_of(route) not in files, route)
               for route in expected.get("routes_absent", []))
    out.extend(_strings(expected, "carried_by", files, True))
    out.extend(_strings(expected, "not_carried_by", files, False))
    out.extend(_strings(expected, "files_contain", files, True))
    for one in expected.get("in_no_file", []):
        hits = [route for route, data in sorted(files.items())
                if one in route or one in data.decode("latin-1")]
        out.append(("no file names " + one, not hits, shown(hits)))
    for route, data in sorted(expected.get("route_bytes", {}).items()):
        body = _text(files, route)
        out.append((route + " bytes", body == data, shown(body)))
    return out


def _surfaces(vector, build):
    return surface_checks(vector["expected"], build(None)), SURFACE_MEMBERS


# --- the route set (build-0024) ------------------------------------------------------

_SCRIPT_SRC = re.compile(r'<script\b[^>]*\bsrc="([^"]+)"')
_STYLESHEET = re.compile(r'<link\b[^>]*\brel="stylesheet"[^>]*\bhref="([^"]+)"')
_OTHER_ORIGIN = re.compile(r"^[a-z][a-z0-9+.-]*:|^//", re.I)


def page_assets(files):
    """The same-origin files the emitted HTML pages load (script src, stylesheet href)."""
    loaded = set()
    for route, data in files.items():
        if not route.endswith(".html"):
            continue
        folder = route[:route.rindex("/") + 1]
        html = data.decode("utf-8")
        for ref in _SCRIPT_SRC.findall(html) + _STYLESHEET.findall(html):
            if not _OTHER_ORIGIN.search(ref):
                loaded.add(ref if ref.startswith("/") else posixpath.normpath(folder + ref))
    return loaded


def _route_set(vector, build):
    expected = vector["expected"]
    run = build(None)
    loaded = page_assets(run["files"])
    assets = [one for one in run["files"] if one.endswith((".js", ".css")) and one in loaded]
    routes = sorted(one[:-len("index.html")] if one.endswith("/index.html") else one
                    for one in run["files"] if one not in assets)
    want = sorted(expected["routes"])
    out = surface_checks(expected, run)
    out.append(("the route set", routes == want, "extra %s missing %s" % (
        shown([one for one in routes if one not in want]),
        shown([one for one in want if one not in routes]))))
    out.extend(("emits " + one, one in assets, shown(assets))
               for one in expected["page_assets_required"])
    out.append(("other files are page assets", expected["other_files_are_page_assets"] is True,
                shown(assets)))
    out.append(("deployment profile", vector["input"].get("deployment_profile") == "cloudflare-pages",
                "this check reads the Cloudflare Pages profile (AGSC-06-17)"))
    return out, SURFACE_MEMBERS | {"other_files_are_page_assets", "page_assets_required", "routes"}


# --- sub-cases -------------------------------------------------------------------------

def _sub_cases(vector, build, members, handler):
    """Run ``handler(name, want, run)`` for each sub-case; ``members`` are the ones it reads."""
    out = []
    wanted = dict((one["name"], one) for one in vector["expected"]["cases"])
    for sub in vector["input"]["cases"]:
        want = wanted.get(sub["name"])
        if want is None:
            out.append((sub["name"], False, "the vector states no expected case of this name"))
            continue
        out.extend(handler(sub["name"], want, build(sub)))
        unknown = sorted(set(want) - members - {"name"})
        if unknown:
            out.append((sub["name"] + " unhandled", False, shown(unknown)))
    return out, {"cases"}


def _subset_of(expected, actual):
    """Every member the vector states is present and equal in the finding."""
    return all(key in actual and _same(value, actual[key]) for key, value in expected.items())


def _build_out_case(name, want, run):
    out = []
    if "exit" in want:
        out.append((name + " exit", run["exit"] == want["exit"], "exit %s" % run["exit"]))
    if "exit_one_of" in want:
        out.append((name + " exit", run["exit"] in want["exit_one_of"], "exit %s" % run["exit"]))
    if "findings" in want:
        missing = [one for one in want["findings"]
                   if not any(_subset_of(one, have) for have in run["findings"])]
        out.append((name + " findings", not missing, "unmatched %s in %s" % (
            shown(missing), shown([one.get("code") for one in run["findings"]]))))
    for code in want.get("codes_absent", []):
        out.append(("%s no %s" % (name, code),
                    all(one.get("code") != code for one in run["findings"]), shown(run["findings"])))
    if "nothing_written" in want:
        out.append((name + " nothing written", (not run["written"]) == want["nothing_written"],
                    shown(run["written"])))
    if "written_only_under" in want:
        outside = [one for one in run["written"] if not one.startswith(want["written_only_under"])]
        out.append(("%s writes only under %s" % (name, want["written_only_under"]),
                    bool(run["written"]) and not outside, shown(outside)))
    return out


def _build_out(vector, build):
    members = {"codes_absent", "exit", "exit_one_of", "findings", "nothing_written",
               "written_only_under"}
    return _sub_cases(vector, build, members, _build_out_case)


def _skills_index_case(name, want, run):
    text = _text(run["files"], "/skills/index.json")
    index = _parse(text, None)
    index = index if isinstance(index, dict) else {}
    out = [(name + " JCS and one LF", is_jcs_with_one_lf(text) == want["jcs_with_one_lf"], shown(text)),
           (name + " members", sorted(index) == sorted(want["members"]), shown(sorted(index)))]
    for key in ("bundle_version", "license", "spec_version", "terms"):
        out.append(("%s %s" % (name, key), index.get(key) == want[key], shown(index.get(key))))
    packs = index.get("packs") if isinstance(index.get("packs"), list) else []
    out.append((name + " packs", len(packs) == len(want["packs"]), shown(packs)))
    for number, pack in enumerate(want["packs"]):
        got = packs[number] if number < len(packs) else {}
        label = "%s pack %d" % (name, number)
        rest = dict((key, value) for key, value in got.items() if key != "lock")
        out.append((label + " members", sorted(got) == sorted(want["pack_members"]), shown(sorted(got))))
        out.append((label, _same(rest, pack), shown(rest)))
        out.append((label + " has a lock", "lock" in got, shown(got)))
    return out


def _skills_index(vector, build):
    members = {"bundle_version", "jcs_with_one_lf", "license", "members", "pack_members", "packs",
               "spec_version", "terms"}
    return _sub_cases(vector, build, members, _skills_index_case)


# --- the skill locks (build-0026) ----------------------------------------------------

_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_LOCK_ROUTE = re.compile(r"\.lock$|lock(file)?\.json$", re.I)


def _skills_lock(vector, build):
    expected = vector["expected"]
    run = build(None)
    index = _parse(_text(run["files"], "/skills/index.json"), None)
    packs = index.get("packs") if isinstance(index, dict) and isinstance(index.get("packs"), list) else []
    out = [("packs_count", len(packs) == expected["packs_count"], str(len(packs)))]
    for pack in packs:
        lock = pack.get("lock") or {}
        out.append(("%s lock members" % pack.get("name"),
                    sorted(lock) == sorted(expected["lock_members"]), shown(lock)))
        served = run["files"].get(str(pack.get("path")))
        digest = None if served is None else hashlib.sha256(served).hexdigest()
        ok = bool(_HEX64.match(str(lock.get("SKILL.md")))) and lock.get("SKILL.md") == digest
        out.append(("%s lock is the hash of %s" % (pack.get("name"), pack.get("path")),
                    ok == expected["lock_is_sha256_of_skill_md"],
                    "lock %s served %s" % (lock.get("SKILL.md"), digest)))
    routes = [one for one in sorted(run["files"]) if _LOCK_ROUTE.search(one)]
    out.append(("no lock route", (not routes) == expected["no_lock_route"], shown(routes)))
    return out, {"lock_is_sha256_of_skill_md", "lock_members", "no_lock_route", "packs_count"}


# --- the TDM reservation (build-0027) ------------------------------------------------

def tdm_matches(pattern, target):
    """A TDMRep location against a path: a prefix match in which ``*`` stands for any
    characters and a final ``$`` ends the pattern (TDM Reservation Protocol, 6.1)."""
    anchored = pattern.endswith("$")
    body = pattern[:-1] if anchored else pattern
    source = ".*".join(re.escape(part) for part in body.split("*"))
    return re.match(source + ("$" if anchored else ""), target) is not None


_FIELD = re.compile(r"^([A-Za-z-]+)\s*:\s*(.*)$")


def disallow_all_groups(robots):
    """The user agents of the robots.txt groups that carry ``Disallow: /``, in file order."""
    out, agents, in_rules = [], [], False
    for raw in (robots or "").split("\n"):
        match = _FIELD.match(re.sub(r"#.*$", "", raw).strip())
        if match is None:
            continue
        field, value = match.group(1).lower(), match.group(2)
        if field == "user-agent":
            if in_rules:
                agents, in_rules = [], False
            agents.append(value)
        elif field in ("allow", "disallow"):
            in_rules = True
            if field == "disallow" and value == "/":
                out.extend(one for one in agents if one not in out)
    return out


def _reservation(rules, target):
    for rule in rules if isinstance(rules, list) else []:
        if isinstance(rule, dict) and isinstance(rule.get("location"), str) \
                and tdm_matches(rule["location"], target):
            return rule.get("tdm-reservation")
    return None


def _tdmrep_case(name, want, run):
    text = _text(run["files"], "/.well-known/tdmrep.json")
    rules = _parse(text, [])
    out = [(name + " JCS and one LF", is_jcs_with_one_lf(text) == want["jcs_with_one_lf"], shown(text))]
    for target, reservation in sorted(want["reservation_for_paths"].items()):
        got = _reservation(rules, target)
        out.append(("%s %s" % (name, target), got == reservation, "got %s" % shown(got)))
    out.extend(("%s no %s" % (name, route), route not in run["files"], route)
               for route in want["routes_absent"])
    groups = disallow_all_groups(_text(run["files"], "/robots.txt"))
    out.append((name + " robots groups", groups == want["robots_disallow_all_groups"], shown(groups)))
    return out


def _tdmrep(vector, build):
    members = {"jcs_with_one_lf", "reservation_for_paths", "robots_disallow_all_groups",
               "routes_absent"}
    return _sub_cases(vector, build, members, _tdmrep_case)


#: case id -> handler(vector, build) -> (checks, the expected members it reads).
HANDLERS = {
    "build-0020": _surfaces,
    "build-0021": _build_out,
    "build-0022": _surfaces,
    "build-0023": _surfaces,
    "build-0024": _route_set,
    "build-0025": _skills_index,
    "build-0026": _skills_lock,
    "build-0027": _tdmrep,
    "build-0028": _surfaces,
}


def check(vector, build):
    """The verdict on one case over the tree ``build`` returns: pass, fail with the
    reasons, skip for a withdrawn case, or not run for a case this module does not hold."""
    if vector.get("level") == "withdrawn":
        return {"status": "skip", "withdrawn": True, "detail": "withdrawn (AGSC-00-16)"}
    handler = HANDLERS.get(vector["id"])
    if handler is None:
        return {"status": "not-run", "detail": "%s is not a case over a whole build" % vector["id"]}
    items, members = handler(vector, build)
    unknown = sorted(set(vector["expected"]) - members)
    if unknown:
        items.append(("unhandled", False, "expected members not checked: %s" % shown(unknown)))
    return checks(items)


__all__ = ["HANDLERS", "SURFACE_MEMBERS", "check", "disallow_all_groups", "file_of",
           "is_jcs_with_one_lf", "page_assets", "surface_checks", "tdm_matches"]
