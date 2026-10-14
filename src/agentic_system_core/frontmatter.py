"""Item frontmatter: the reader, the checks of spec/02 and the drop-in adoption.

The checks are derived from the rule text of spec/02 (and the error-code
precedence paragraph of spec/09 §9.4), not from a JSON Schema engine, so the
package stays standard-library only:

* AGSC-02-01 / 02-02 / 02-03 — the block, the closed YAML subset, failsafe
  scalars (:mod:`yamlsubset`).
* AGSC-02-05 / 02-05a — key-name pattern (``AGSC-E204``), unknown keys preserved
  and warned (``AGSC-E207``), the ``x-`` vendor namespace never warned.
* AGSC-02-06 — dates and instants.
* AGSC-02-07 / 02-09 / 08-01 — ``prov`` (``AGSC-E501`` when absent), origin
  enum, ``human:<id>`` operator, actor strings.
* AGSC-02-12…02-18, 02-96…02-99 — the type-specific keys.
* AGSC-02-24 — length bounds in code points and authored single-line strings.
* AGSC-02-90…02-93 — adoption of a bare Markdown file.

Codes follow §9.4's precedence: an enum violation is ``AGSC-E203``, a pattern
or length violation ``AGSC-E204``, a missing required key ``AGSC-E202``.
"""

import re
import unicodedata

from . import links as links_module
from . import yamlsubset
from .slug import SLUG_PATTERN

TYPES = ("concept", "episode", "procedure", "lesson", "cluster", "gate")
COMMON_KEYS = (
    "type", "title", "description", "status", "release", "tags", "aliases", "clusters", "lang",
    "date", "modified", "sources", "prov", "generated", "verified", "stale_after", "id", "iri",
    "spec_version", "attachments",
) + links_module.KEYS
TYPE_KEYS = {
    "concept": ("kind", "evidence", "maturity", "mapping", "signature", "signature_elements",
                "owasp_ids", "domains", "modality", "deployment", "implementations", "diagram",
                "produces", "consumes", "task_state", "verdict_digest"),
    "episode": ("started", "ended", "actor", "outcome", "refs", "usage"),
    "procedure": ("when", "inputs"),
    "lesson": ("severity",),
    "cluster": ("order", "family"),
    "gate": ("level", "checks", "enforce"),
}
REQUIRED_BY_TYPE = {
    "concept": ("kind",), "episode": ("started", "actor", "outcome"), "lesson": ("severity",),
    "gate": ("level",),
}
ENUMS = {
    "status": ("draft", "stable", "deprecated", "retired"),
    "kind": ("pattern", "taxonomy", "explainer", "principle", "decision", "spec", "task", "term",
             "architecture"),
    "evidence": ("explicit", "structural", "single-source"),
    "maturity": ("established", "emerging", "research"),
    "mapping": ("explicit", "author"),
    "outcome": ("success", "partial", "failure"),
    "severity": ("info", "warn", "block"),
    "level": ("L1", "L2"),
}
ORIGINS = ("human", "ai-assisted", "ai-generated", "imported")
GRADES = ("primary", "secondary", "tertiary")
TASK_STATES = ("TASK_STATE_UNSPECIFIED", "TASK_STATE_SUBMITTED", "TASK_STATE_WORKING",
               "TASK_STATE_INPUT_REQUIRED", "TASK_STATE_AUTH_REQUIRED", "TASK_STATE_COMPLETED",
               "TASK_STATE_FAILED", "TASK_STATE_CANCELED", "TASK_STATE_REJECTED")
GATE_CHECKS = {"L1": ("schema", "links"),
               "L2": ("schema", "links", "provenance", "determinism", "review")}
ENFORCE = ("status-check", "hook", "codeowner", "ruleset")

_KEY_NAME = re.compile(r"^[a-z][a-z0-9_-]*$")
_VENDOR = re.compile(r"^x-[a-z0-9]+(-[a-z0-9]+)+$")
_SLUG = re.compile(SLUG_PATTERN)
_LINK_TARGET = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*(?:#[a-z0-9]+(?:-[a-z0-9]+)*)?$")
_DATE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")
_INSTANT = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$")
#: AGSC-02-09: human:<id>, process:<id>, process:<id>/<version> (the ledger's trailing
#: build entry, AGSC-08-20a) or <producer>/<version>; the engine's item schema pattern.
_ACTOR = re.compile(r"^(?:human:[a-z0-9][a-z0-9._-]*|"
                    r"process:[a-z0-9][a-z0-9._-]*(?:/[A-Za-z0-9][A-Za-z0-9._+-]*)?|"
                    r"[A-Za-z0-9][A-Za-z0-9._-]*/[A-Za-z0-9][A-Za-z0-9._+-]*)$")
_HUMAN = re.compile(r"^human:[a-z0-9][a-z0-9._-]*$")
_TAG = re.compile(r"^[a-z0-9][a-z0-9-]*$")
_LANG = re.compile(r"^[A-Za-z]{2,8}(?:-[A-Za-z0-9]{1,8})*$")
_PORT = re.compile(r"^[a-z][a-z0-9-]{0,63}$")
_SEMVER = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+(?:-[0-9A-Za-z.-]+)?$")
_IRI = re.compile(r"^https://[^\x00-\x20]+/$")
_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_INTEGER = re.compile(r"^-?(?:0|[1-9][0-9]*)$")
#: AGSC-02-24: the code points an authored single-line string never carries.
_NOT_SINGLE_LINE = re.compile("[\x00-\x1f\x7f\x85  ]")


def finding(code, message, key=None, line=None, severity="error"):
    out = {"code": code, "message": message, "severity": severity}
    if key is not None:
        out["key"] = key
    if line is not None:
        out["line"] = line
    return out


def code_points(text):
    return len(text)


class _Checker(object):
    def __init__(self, data, lines):
        self.data = data
        self.lines = lines or {}
        self.findings = []

    def add(self, code, message, key, severity="error"):
        top = key.split("/")[0].split("[")[0]
        self.findings.append(finding(code, message, key=key, line=self.lines.get(top),
                                     severity=severity))

    def string(self, key, value):
        if not isinstance(value, str):
            self.add("AGSC-E201", "%s must be a string" % key, key)
            return False
        return True

    def single_line(self, key, value, low=None, high=None):
        if not self.string(key, value):
            return
        if _NOT_SINGLE_LINE.search(value):
            self.add("AGSC-E204", "%s is not an authored single-line string (AGSC-02-24)" % key,
                     key)
        size = code_points(value)
        if (low is not None and size < low) or (high is not None and size > high):
            self.add("AGSC-E204", "%s is %d code points, outside %s..%s (AGSC-02-24)"
                     % (key, size, low, high), key)

    def pattern(self, key, value, regex, what):
        if self.string(key, value) and regex.match(value) is None:
            self.add("AGSC-E204", "%s is not %s" % (key, what), key)

    def enum(self, key, value, allowed):
        if not isinstance(value, str) or value not in allowed:
            self.add("AGSC-E203", "%s %r is not one of %s" % (key, value, "|".join(allowed)), key)

    def array(self, key, value):
        if not isinstance(value, list):
            self.add("AGSC-E201", "%s must be a sequence" % key, key)
            return []
        return value

    def mapping(self, key, value):
        if not isinstance(value, dict):
            self.add("AGSC-E201", "%s must be a mapping" % key, key)
            return {}
        return value


def check(data, lines=None, slug=None):
    """Every finding for one frontmatter mapping (errors and warnings)."""
    c = _Checker(data, lines)
    kind_of = data.get("type")
    for key in data:
        if key == "slug" and slug is None:
            continue  # a pre-parsed vector item names its slug beside the keys under test
        if _KEY_NAME.match(key) is None:
            c.add("AGSC-E204", "key %r does not match ^[a-z][a-z0-9_-]*$ (AGSC-02-05)" % key, key)
        elif _VENDOR.match(key):
            continue
        elif key in COMMON_KEYS or key in TYPE_KEYS.get(kind_of, ()):
            continue
        elif key in links_module.AUTHORED_INVERSE_FORBIDDEN:
            c.add("AGSC-E306", "%s is a computed inverse and is never authored" % key, key)
        else:
            c.add("AGSC-E207", "unknown key %s is preserved" % key, key, severity="warn")

    if "type" not in data:
        c.add("AGSC-E202", "type is required", "type")
    else:
        c.enum("type", kind_of, TYPES)
    if "title" not in data:
        c.add("AGSC-E202", "title is required", "title")
    else:
        c.single_line("title", data["title"], 3, 120)
    if "prov" not in data:
        c.add("AGSC-E501", "prov is required on every item (AGSC-08-01)", "prov")
    else:
        prov = c.mapping("prov", data["prov"])
        if prov:
            if "origin" not in prov:
                c.add("AGSC-E202", "prov.origin is required", "prov/origin")
            else:
                c.enum("prov/origin", prov["origin"], ORIGINS)
            if "operator" not in prov:
                c.add("AGSC-E202", "prov.operator is required", "prov/operator")
            else:
                c.pattern("prov/operator", prov["operator"], _HUMAN, "a human:<id> actor")
            for name in ("agent", "model", "agreement"):
                if name in prov:
                    c.single_line("prov/" + name, prov[name])
    if "description" in data:
        c.single_line("description", data["description"], 40, 200)
    if "status" in data:
        c.enum("status", data["status"], ENUMS["status"])
    if "release" in data:
        c.pattern("release", data["release"], _SLUG, "a slug")
    if "id" in data:
        c.pattern("id", data["id"], _SLUG, "a slug")
        if slug is not None and data["id"] != slug:
            c.add("AGSC-E204", "id must equal the slug", "id")
    if "iri" in data:
        c.pattern("iri", data["iri"], _IRI, "an https IRI ending in /")
    if "spec_version" in data:
        c.pattern("spec_version", data["spec_version"], _SEMVER, "a semantic version")
    if "lang" in data:
        c.pattern("lang", data["lang"], _LANG, "a BCP 47 tag")
    for key in ("date", "modified"):
        if key in data:
            c.pattern(key, data[key], _DATE, "a YYYY-MM-DD date (AGSC-02-06)")
    for key in ("stale_after", "started", "ended"):
        if key in data and key in COMMON_KEYS + TYPE_KEYS.get(kind_of, ()):
            c.pattern(key, data[key], _INSTANT, "a YYYY-MM-DDTHH:MM:SSZ instant (AGSC-02-06)")
    for value in c.array("tags", data["tags"]) if "tags" in data else []:
        c.pattern("tags", value, _TAG, "a tag")
    for value in c.array("aliases", data["aliases"]) if "aliases" in data else []:
        c.single_line("aliases", value)
    for value in c.array("clusters", data["clusters"]) if "clusters" in data else []:
        c.pattern("clusters", value, _SLUG, "a slug")
    for key in links_module.KEYS:
        for value in c.array(key, data[key]) if key in data else []:
            c.pattern(key, value, _LINK_TARGET, "a slug or slug#anchor (AGSC-03-02)")
    for index, source in enumerate(c.array("sources", data["sources"])
                                   if "sources" in data else []):
        entry = c.mapping("sources", source)
        if entry and "resource" not in entry:
            c.add("AGSC-E202", "sources[%d].resource is required (AGSC-02-10)" % index, "sources")
        if "grade" in entry:
            c.enum("sources", entry["grade"], GRADES)
        for name in ("id", "title", "author"):
            if name in entry:
                c.single_line("sources", entry[name])
    if "generated" in data:
        generated = c.mapping("generated", data["generated"])
        if generated and "by" not in generated:
            c.add("AGSC-E202", "generated.by is required", "generated")
        if "by" in generated:
            c.pattern("generated", generated["by"], _ACTOR, "an actor string (AGSC-02-09)")
        if "at" in generated:
            c.pattern("generated", generated["at"], _INSTANT, "an instant (AGSC-02-06)")
    for entry in c.array("verified", data["verified"]) if "verified" in data else []:
        entry = c.mapping("verified", entry)
        for name, regex, what in (("by", _HUMAN, "a human:<id> actor"),
                                  ("at", _INSTANT, "an instant")):
            if name not in entry:
                c.add("AGSC-E202", "verified[].%s is required" % name, "verified")
            else:
                c.pattern("verified", entry[name], regex, what)
    for index, entry in enumerate(c.array("attachments", data["attachments"])
                                  if "attachments" in data else []):
        entry = c.mapping("attachments", entry)
        for name in ("file", "media_type", "alt"):
            if name not in entry:
                c.add("AGSC-E202", "attachments[%d].%s is required" % (index, name),
                      "attachments")
        if "alt" in entry:
            c.single_line("attachments", entry["alt"], 1, None)

    for key in REQUIRED_BY_TYPE.get(kind_of, ()):
        if key not in data:
            c.add("AGSC-E202", "%s is required on a %s" % (key, kind_of), key)
    if kind_of == "concept":
        _concept(c, data)
    elif kind_of == "episode":
        if "actor" in data:
            c.pattern("actor", data["actor"], _ACTOR, "an actor string (AGSC-02-09)")
        if "outcome" in data:
            c.enum("outcome", data["outcome"], ENUMS["outcome"])
        for value in c.array("refs", data["refs"]) if "refs" in data else []:
            c.pattern("refs", value, re.compile(r"^https?://"), "an http(s) URL")
    elif kind_of == "procedure":
        if "when" in data:
            c.single_line("when", data["when"], 1, 1024)
        for value in c.array("inputs", data["inputs"]) if "inputs" in data else []:
            c.single_line("inputs", value)
    elif kind_of == "lesson":
        if "severity" in data:
            c.enum("severity", data["severity"], ENUMS["severity"])
    elif kind_of == "cluster":
        if "order" in data and (not isinstance(data["order"], str)
                                or _INTEGER.match(data["order"]) is None):
            c.add("AGSC-E201", "order must be an integer", "order")
        if "family" in data:
            c.single_line("family", data["family"])
    elif kind_of == "gate":
        if "level" in data:
            c.enum("level", data["level"], ENUMS["level"])
        if "checks" in data and data.get("level") in GATE_CHECKS:
            checks = c.array("checks", data["checks"])
            if sorted(checks) != sorted(GATE_CHECKS[data["level"]]):
                c.add("AGSC-E203", "checks must equal the set level %s implies (AGSC-02-18)"
                      % data["level"], "checks")
        for value in c.array("enforce", data["enforce"]) if "enforce" in data else []:
            c.enum("enforce", value, ENFORCE)
    return c.findings


def _concept(c, data):
    kind = data.get("kind")
    if "kind" in data:
        c.enum("kind", kind, ENUMS["kind"])
    for key in ("evidence", "maturity", "mapping"):
        if key in data:
            c.enum(key, data[key], ENUMS[key])
    if "signature" in data and data["signature"] not in ("true", "false", True, False):
        c.add("AGSC-E201", "signature must be true or false (AGSC-02-04)", "signature")
    for key in ("produces", "consumes"):
        values = c.array(key, data[key]) if key in data else []
        for value in values:
            c.pattern(key, value, _PORT, "a port type name (AGSC-02-96)")
        if len(set(map(str, values))) != len(values):
            c.add("AGSC-E201", "%s names must be unique (AGSC-02-96)" % key, key)
    if "task_state" in data:
        if kind == "task":
            c.enum("task_state", data["task_state"], TASK_STATES)
        else:
            c.add("AGSC-E207", "task_state on a concept whose kind is not task is ignored "
                  "(AGSC-02-99)", "task_state", severity="warn")
    if "verdict_digest" in data:
        if kind == "architecture":
            c.pattern("verdict_digest", data["verdict_digest"], _DIGEST, "a SHA-256 hex digest")
        else:
            c.add("AGSC-E207", "verdict_digest on a concept whose kind is not architecture is "
                  "ignored (AGSC-02-97)", "verdict_digest", severity="warn")
    for key in ("signature_elements", "domains", "modality", "deployment"):
        for value in c.array(key, data[key]) if key in data else []:
            c.single_line(key, value)


def typed(data, kind_of=None):
    """Apply the item schema's non-string types to a failsafe mapping (AGSC-02-03)."""
    kind_of = kind_of or data.get("type")
    out = dict(data)
    if kind_of == "concept" and out.get("signature") in ("true", "false"):
        out["signature"] = out["signature"] == "true"
    if kind_of == "cluster" and isinstance(out.get("order"), str) and \
            _INTEGER.match(out["order"]):
        out["order"] = int(out["order"])
    return out


def plain(value):
    """A parsed mapping as plain dicts and lists (dropping the line records)."""
    if isinstance(value, dict):
        return dict((key, plain(item)) for key, item in value.items())
    if isinstance(value, list):
        return [plain(item) for item in value]
    return value


def read(markdown, slug=None):
    """(frontmatter or None, body, findings) for one item file."""
    text, body, error = yamlsubset.split_frontmatter(markdown)
    if error is not None:
        return None, markdown, [finding(error.code, error.message, line=error.line)]
    try:
        mapping = yamlsubset.load(text, first_line=2)
    except yamlsubset.YamlError as error:
        return None, body, [finding(error.code, error.message, line=error.line)]
    findings = check(mapping, lines=mapping.lines, slug=slug)
    return typed(plain(mapping)), body, findings


def task_state(item, own=True):
    """AGSC-02-99: (state, finding or None).  A foreign unknown value reads as UNSPECIFIED."""
    value = item.get("task_state", "TASK_STATE_UNSPECIFIED")
    if value in TASK_STATES:
        return value, None
    if own:
        return None, finding("AGSC-E203", "task_state %r is not an A2A 1.0 state" % value,
                             key="task_state")
    return "TASK_STATE_UNSPECIFIED", None


# --- adoption (AGSC-02-90 to AGSC-02-93) --------------------------------------

NOT_ADOPTED = ("README.md", "index.md", "_index.md")
_ATX_H1 = re.compile(r"^ {0,3}#(?:[ \t]+(.*?))?(?:[ \t]+#+)?[ \t]*$")


def slugify(stem):
    """AGSC-02-91: the slug of a filename stem."""
    text = unicodedata.normalize("NFC", stem)
    text = "".join(chr(ord(c) + 32) if "A" <= c <= "Z" else c for c in text)
    text = re.sub(r"[^a-z0-9]", "-", text)
    text = re.sub(r"-+", "-", text).strip("-")
    text = text[:64].rstrip("-")
    return text or "note"


def _operator(config, git_user_email, findings):
    bundle = (config or {}).get("bundle") or {}
    if bundle.get("operator"):
        return bundle["operator"]
    if git_user_email:
        local = unicodedata.normalize("NFC", git_user_email.split("@", 1)[0])
        local = "".join(chr(ord(c) + 32) if "A" <= c <= "Z" else c for c in local)
        local = re.sub(r"[^a-z0-9._-]", "-", local)
        local = re.sub(r"-+", "-", local).strip("-")
        local = re.sub(r"^[^a-z0-9]+", "", local)
        if local:
            findings.append(finding("AGSC-E506", "operator derived from git user.email",
                                    severity="warn"))
            return "human:" + local
    findings.append(finding("AGSC-E506", "operator defaulted to human:unknown", severity="warn"))
    return "human:unknown"


def _title(markdown, stem, slug, findings):
    title = None
    fence = None
    for line in markdown.split("\n"):
        stripped = line.lstrip(" ")
        if stripped.startswith("```") or stripped.startswith("~~~"):
            fence = None if fence and stripped.startswith(fence) else (fence or stripped[:3])
            continue
        if fence:
            continue
        match = _ATX_H1.match(line)
        if match and not line.lstrip().startswith("##"):
            title = match.group(1) or ""
            break
    title = unicodedata.normalize("NFC", title if title is not None else stem).strip()
    if len(title) > 120:
        findings.append(finding("AGSC-E506", "title clipped to 120 code points", severity="warn"))
        title = title[:120]
    if len(title) < 3:
        title = slug if len(slug) >= 3 else "note-" + slug
    return title


def adopt(path, markdown, config=None, git_user_email=None, taken=()):
    """(new path, output bytes as text, findings) for one file of a bare folder.

    A file already carrying a closed frontmatter block is returned unchanged
    (AGSC-02-91), and so is a README/index file, with its warning.
    """
    findings = []
    name = path.replace("\\", "/").split("/")[-1]
    if name in NOT_ADOPTED:
        return path, markdown, [finding("AGSC-E506", "%s is not adopted (AGSC-01-05)" % name,
                                        severity="warn")]
    if yamlsubset.has_closed_block(markdown):
        return path, markdown, []
    stem = name[:-3] if name.endswith(".md") else name
    slug = slugify(stem)
    base_slug, suffix = slug, 1
    while slug in taken:
        suffix += 1
        slug = "%s-%d" % (base_slug, suffix)
    if slug != stem:
        findings.append(finding("AGSC-E506", "slug %s differs from the stem %r" % (slug, stem),
                                severity="warn"))
    new_path = "content/concepts/%s.md" % slug
    in_place = path.startswith("content/") and path.count("/") == 2 and path == new_path
    front = [("type", "concept"), ("title", _title(markdown, stem, slug, findings))]
    if not in_place:
        front.append(("aliases", [path]))
    front.append(("prov", dict([("origin", "human"),
                                ("operator", _operator(config, git_user_email, findings))])))
    front.append(("kind", "explainer"))
    ordered = dict(front)
    output = "---\n" + yamlsubset.dump(ordered) + "---\n\n" + markdown
    return new_path, output, findings
