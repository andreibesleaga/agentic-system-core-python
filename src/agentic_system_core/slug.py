"""The slug grammar and the uniqueness rule (AGSC-01-10, AGSC-01-11).

The pattern is ``^[a-z0-9]+(?:-[a-z0-9]+)*$`` with a 1 to 64 code point bound
carried by a length check and never by a quantifier.  Written that way it
forbids a leading, a trailing and a doubled hyphen by construction, and it
compiles unchanged in every regular-expression engine, including the ones with
no lookahead.  Vector ``slug-0006`` exists to prove exactly that, so the
lookahead form must never come back.

Standard library only.
"""

import re

#: The portable pattern, spelled exactly as AGSC-01-10 spells it.
SLUG_PATTERN = "^[a-z0-9]+(?:-[a-z0-9]+)*$"
SLUG_RE = re.compile(SLUG_PATTERN)
MIN_LENGTH = 1
MAX_LENGTH = 64


def code_point_length(text):
    """The number of Unicode code points (AGSC-02-24), never bytes or units."""
    return len(text)


def is_valid(slug):
    """True when the string is a slug: the grammar and the 1 to 64 bound."""
    if not isinstance(slug, str):
        return False
    length = code_point_length(slug)
    if length < MIN_LENGTH or length > MAX_LENGTH:
        return False
    return SLUG_RE.match(slug) is not None


def check(slugs, files=None):
    """AGSC-E204 for every malformed slug, AGSC-E206 for every repeat, in order."""
    files = files or []
    findings = []
    seen = {}
    for index, slug in enumerate(slugs):
        name = files[index] if index < len(files) else ""
        if not is_valid(slug):
            findings.append({
                "code": "AGSC-E204", "col": 1, "file": name, "line": 1, "severity": "error",
                "slug": slug,
                "message": 'slug "%s" does not match %s within 1-64 code points'
                           % (slug, SLUG_PATTERN),
            })
            continue
        if slug in seen:
            findings.append({
                "code": "AGSC-E206", "col": 1, "file": name, "line": 1, "severity": "error",
                "slug": slug,
                "message": 'slug "%s" is already used by %s' % (slug, seen[slug] or "another item"),
            })
            continue
        seen[slug] = name
    return findings


def stem_of(path):
    """The file stem of a repository-relative path; ``/`` separates everywhere."""
    base = str(path).split("/")[-1]
    return re.sub(r"\.[^.]*$", "", base)
