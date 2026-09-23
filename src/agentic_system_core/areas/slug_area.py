"""Area ``slug`` — AGSC-01-10 (the grammar and the 1 to 64 bound) and AGSC-01-11
(uniqueness across the whole Bundle).

Every expectation follows from the vector's own input: a list of candidate
strings and the verdicts, or a list of file paths and the collision code.
"""

from .. import slug as slug_module
from ._assert import checks, shown


def run(vector):
    given = vector["input"]
    expected = vector["expected"]
    items = []

    # The pattern itself is the subject of the case.
    if isinstance(given.get("candidates"), list):
        valid = [one for one in given["candidates"] if slug_module.is_valid(one)]
        invalid = [one for one in given["candidates"] if not slug_module.is_valid(one)]
        items.append(("valid", valid == expected.get("valid"), shown(valid)))
        items.append(("invalid", invalid == expected.get("invalid"), shown(invalid)))
        if expected.get("pattern") is not None:
            items.append(("pattern", slug_module.SLUG_PATTERN == expected["pattern"],
                          slug_module.SLUG_PATTERN))
        if expected.get("lookahead") is False:
            items.append(("no-lookahead",
                          "(?=" not in slug_module.SLUG_PATTERN
                          and "(?!" not in slug_module.SLUG_PATTERN,
                          slug_module.SLUG_PATTERN))
        return checks(items)

    # Uniqueness over a list of paths.
    if isinstance(given.get("paths"), list):
        stems = [slug_module.stem_of(one) for one in given["paths"]]
        findings = slug_module.check(stems, files=given["paths"])
        codes = [one["code"] for one in findings]
        items.append(("error", bool(findings) and codes[0] == expected.get("error"), shown(codes)))
        return checks(items)

    candidates = given["slugs"] if isinstance(given.get("slugs"), list) else [given.get("slug")]
    findings = slug_module.check(candidates)
    codes = [one["code"] for one in findings]
    if isinstance(expected.get("valid"), list):
        verdicts = [slug_module.is_valid(one) for one in candidates]
        items.append(("valid", verdicts == expected["valid"], shown(verdicts)))
    if isinstance(expected.get("error"), str):
        items.append(("error", bool(findings) and codes[0] == expected["error"], shown(codes)))
    return checks(items)
