"""Area ``frontmatter`` — spec/02: the YAML subset, failsafe scalars, the item
checks, length in code points, task state and adoption.

Every member of ``expected`` is checked; an unknown member is a failure.
"""

from .. import frontmatter
from ..jcs import canonicalize
from ._assert import checks, shown


def _errors(findings):
    return [one for one in findings if one["severity"] == "error"]


def run(vector):
    given = vector["input"]
    expected = vector["expected"]
    items = []
    handled = set()

    def have(name):
        handled.add(name)
        return name in expected

    if isinstance(given.get("markdown"), str):
        data, _, findings = frontmatter.read(given["markdown"])
        errors = _errors(findings)
        if have("frontmatter"):
            items.append(("frontmatter", data is not None and
                          canonicalize(data) == canonicalize(expected["frontmatter"]),
                          shown(data)))
        if have("errors"):
            codes = [one["code"] for one in errors]
            items.append(("errors", codes == expected["errors"], shown(codes)))
        if have("error"):
            codes = [one["code"] for one in errors]
            items.append(("error", codes == [expected["error"]], shown(errors)))
            if have("line"):
                lines = [one.get("line") for one in errors]
                items.append(("line", lines == [expected["line"]], shown(lines)))
        if have("warnings"):
            warnings = sorted(({"code": one["code"], "key": one.get("key")}
                               for one in findings if one["severity"] == "warn"),
                              key=lambda one: (one["key"] or "", one["code"]))
            items.append(("warnings", warnings == expected["warnings"], shown(warnings)))

    elif isinstance(given.get("frontmatter"), dict):
        data = given["frontmatter"]
        # A pre-parsed case states only the keys under test (tests/vectors/README.md,
        # Input shapes): a finding about a key the case does not state — a required
        # key it leaves out — is outside the case and is not compared.
        stated = set(data)
        findings = [one for one in frontmatter.check(data) if one.get("key") in stated]
        if have("findings"):
            got = [{"code": one["code"], "key": one.get("key"), "severity": one["severity"]}
                   for one in findings]
            items.append(("findings", got == expected["findings"], shown(got)))
        if have("valid"):
            valid = _errors(findings) == []
            items.append(("valid", valid == expected["valid"], shown(findings)))
        if have("preserved"):
            kept = dict((key, data[key]) for key in expected["preserved"] if key in data)
            items.append(("preserved", kept == expected["preserved"], shown(kept)))

    elif isinstance(given.get("files"), list):
        config = given.get("config")
        outcomes = [frontmatter.adopt(one["path"], one["markdown"], config)
                    for one in given["files"]]
        path, output, findings = outcomes[0]
        if have("path"):
            items.append(("path", path == expected["path"], path))
        if have("output"):
            items.append(("output", output == expected["output"], shown(output)))
        if have("findings"):
            got = [{"code": one["code"], "severity": one["severity"]} for one in findings]
            items.append(("findings", got == expected["findings"], shown(got)))
        if have("idempotent"):
            again_path, again, again_findings = frontmatter.adopt(path, output, config)
            same = again == output and again_path == path and again_findings == []
            data, _, read_findings = frontmatter.read(output)
            items.append(("idempotent", same == expected["idempotent"], shown(again_findings)))
            items.append(("adopted-file-has-no-error", _errors(read_findings) == [],
                          shown(read_findings)))

    elif isinstance(given.get("own_items"), list):
        results = []
        for item in sorted(given["own_items"], key=lambda one: one["slug"]):
            state, problem = frontmatter.task_state(item, own=True)
            if problem is not None:
                results.append({"code": problem["code"], "slug": item["slug"]})
            else:
                results.append({"slug": item["slug"], "state": state})
        if have("results"):
            items.append(("results", results == expected["results"], shown(results)))
        if have("foreign_read_as"):
            state, _ = frontmatter.task_state({"task_state": given["foreign_board_state"]},
                                              own=False)
            items.append(("foreign", state == expected["foreign_read_as"], state))

    elif isinstance(given.get("items"), list):
        results = []
        for item in given["items"]:
            findings = frontmatter.check({"title": item["title"]}, slug=None)
            title_findings = [one for one in findings if one.get("key") == "title"]
            entry = {"code_points": frontmatter.code_points(item["title"]),
                     "slug": item["slug"], "valid": not title_findings}
            if title_findings:
                entry["code"] = title_findings[0]["code"]
            results.append(entry)
        if have("results"):
            items.append(("results", results == expected["results"], shown(results)))

    unknown = sorted(set(expected) - handled)
    if unknown:
        items.append(("unhandled", False, "expected members not checked: %s" % shown(unknown)))
    if not items:
        items.append(("shape", False, "no input shape this handler knows"))
    return checks(items)
