"""RDF terms and the two byte-pinned serialisations: canonical N-Quads and stable Turtle.

Derived from the rule text alone:

* AGSC-05-31 — the three literal forms: language-tagged (no datatype), typed,
  and plain (``xsd:string``: bare in Turtle, explicit in N-Quads).
* AGSC-05-32 — N-Quads escaping: ``\\\\ \\" \\n \\r \\t`` and ``\\u00XX``
  (lowercase hex) for every other character below U+0020; everything else is
  written as itself in UTF-8.
* AGSC-04-13 / AGSC-04-15 — lines sorted by their serialised bytes, each ending
  with `` .`` and one LF.  For UTF-8 text, byte order is code-point order, which
  is Python's own string order.
* AGSC-05-10 — the stable-Turtle profile, every byte of which is fixed: the
  constant prefix block, the blank-line layout, subject/predicate/object order,
  the four-space clause indent, ``a`` for ``rdf:type`` and prefixed names only
  for legal ``PN_LOCAL`` local parts.

A dataset here is blank-node-free by construction (AGSC-05-08): every subject
and every IRI object is an IRI, so canonicalisation is a sort (AGSC-04-16).
Standard library only.
"""

import re

ASC = "https://w3id.org/agentic-system-core/ns#"
DCTERMS = "http://purl.org/dc/terms/"
PROV = "http://www.w3.org/ns/prov#"
RDFS = "http://www.w3.org/2000/01/rdf-schema#"
SCHEMA = "https://schema.org/"
SKOS = "http://www.w3.org/2004/02/skos/core#"
XSD = "http://www.w3.org/2001/XMLSchema#"
RDF_TYPE = "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"
XSD_STRING = XSD + "string"
XSD_DATETIME = XSD + "dateTime"

#: AGSC-05-10(a): the constant prefix block, in code-point order of the prefix name.
PREFIXES = (
    ("asc", ASC),
    ("dcterms", DCTERMS),
    ("prov", PROV),
    ("rdfs", RDFS),
    ("schema", SCHEMA),
    ("skos", SKOS),
    ("xsd", XSD),
)


class IRI(object):
    """An IRI term."""

    __slots__ = ("value",)

    def __init__(self, value):
        self.value = value

    def __eq__(self, other):
        return isinstance(other, IRI) and other.value == self.value

    def __ne__(self, other):
        return not self == other

    def __hash__(self):
        return hash(("iri", self.value))

    def __repr__(self):
        return "IRI(%r)" % self.value


class Literal(object):
    """A literal in exactly one of the three forms of AGSC-05-31.

    ``lang`` set: form (a).  ``datatype`` set to anything but ``xsd:string``:
    form (b).  Neither: form (c), the plain ``xsd:string``.
    """

    __slots__ = ("value", "datatype", "lang")

    def __init__(self, value, datatype=None, lang=None):
        if lang is not None and datatype is not None:
            raise ValueError("a language-tagged literal carries no datatype (AGSC-05-31)")
        if lang == "":
            raise ValueError("an empty language tag is never emitted (AGSC-05-31)")
        if datatype == XSD_STRING:
            datatype = None
        self.value = value
        self.datatype = datatype
        self.lang = lang.lower() if lang is not None else None

    def _key(self):
        return ("lit", self.value, self.datatype, self.lang)

    def __eq__(self, other):
        return isinstance(other, Literal) and other._key() == self._key()

    def __ne__(self, other):
        return not self == other

    def __hash__(self):
        return hash(self._key())

    def __repr__(self):
        return "Literal(%r, %r, %r)" % (self.value, self.datatype, self.lang)


def escape(text):
    """AGSC-05-32: the six escapes and nothing else."""
    out = []
    for char in text:
        code = ord(char)
        if char == "\\":
            out.append("\\\\")
        elif char == '"':
            out.append('\\"')
        elif char == "\n":
            out.append("\\n")
        elif char == "\r":
            out.append("\\r")
        elif char == "\t":
            out.append("\\t")
        elif code < 0x20:
            out.append("\\u%04x" % code)
        else:
            out.append(char)
    return "".join(out)


def _iri_text(value):
    """IRIs take the same control-character escaping and no percent re-encoding."""
    return "<%s>" % escape(value)


def nquads_term(term):
    """One term in N-Quads form."""
    if isinstance(term, IRI):
        return _iri_text(term.value)
    text = '"%s"' % escape(term.value)
    if term.lang is not None:
        return "%s@%s" % (text, term.lang)
    return "%s^^%s" % (text, _iri_text(term.datatype or XSD_STRING))


def nquads(triples, graph=None):
    """The canonical N-Quads document: one line per statement, byte-sorted, deduplicated.

    ``graph`` is the graph name written as every line's fourth term, or None for
    the default graph.
    """
    suffix = " %s ." % _iri_text(graph) if graph is not None else " ."
    lines = set()
    for subject, predicate, obj in triples:
        _check_subject(subject)
        lines.add("%s %s %s%s\n" % (
            _iri_text(subject.value), _iri_text(predicate.value), nquads_term(obj), suffix))
    return "".join(sorted(lines))


def _check_subject(subject):
    if not isinstance(subject, IRI):
        raise ValueError("every subject is an IRI (AGSC-05-08)")
    if subject.value.startswith("memory://"):
        raise ValueError("memory:// is never an RDF subject (AGSC-05-04)")


# --- Turtle -----------------------------------------------------------------

# PN_CHARS_BASE of the Turtle grammar (RDF 1.1 Turtle, production [163s]).
_BASE_RANGES = (
    (0x41, 0x5A), (0x61, 0x7A), (0xC0, 0xD6), (0xD8, 0xF6), (0xF8, 0x2FF),
    (0x370, 0x37D), (0x37F, 0x1FFF), (0x200C, 0x200D), (0x2070, 0x218F),
    (0x2C00, 0x2FEF), (0x3001, 0xD7FF), (0xF900, 0xFDCF), (0xFDF0, 0xFFFD),
    (0x10000, 0xEFFFF),
)


def _pn_chars_base(char):
    code = ord(char)
    return any(low <= code <= high for low, high in _BASE_RANGES)


def _pn_chars_u(char):
    return char == "_" or _pn_chars_base(char)


def _pn_chars(char):
    code = ord(char)
    return (_pn_chars_u(char) or char == "-" or "0" <= char <= "9" or code == 0xB7
            or 0x300 <= code <= 0x36F or 0x203F <= code <= 0x2040)


def is_pn_local(text):
    """A legal PN_LOCAL written without any PLX escape.

    [168s] PN_LOCAL ::= (PN_CHARS_U | ':' | [0-9] | PLX)
                        ((PN_CHARS | '.' | ':' | PLX)* (PN_CHARS | ':' | PLX))?
    An empty local part is not a PN_LOCAL, and a local part that would need a
    ``\\`` or ``%`` escape is written as a full IRI instead.
    """
    if text == "":
        return False
    first = text[0]
    if not (_pn_chars_u(first) or first == ":" or "0" <= first <= "9"):
        return False
    for char in text[1:]:
        if not (_pn_chars(char) or char in ".:"):
            return False
    return text[-1] != "."


def turtle_iri(value):
    """A prefixed name where AGSC-05-10(d) allows one, else ``<IRI>``."""
    for prefix, namespace in PREFIXES:
        if value.startswith(namespace) and is_pn_local(value[len(namespace):]):
            return "%s:%s" % (prefix, value[len(namespace):])
    return _iri_text(value)


def turtle_term(term):
    if isinstance(term, IRI):
        return turtle_iri(term.value)
    text = '"%s"' % escape(term.value)
    if term.lang is not None:
        return "%s@%s" % (text, term.lang)
    if term.datatype is None:
        return text
    return "%s^^%s" % (text, turtle_iri(term.datatype))


def prefix_block():
    return "".join("@prefix %s: <%s> .\n" % pair for pair in PREFIXES)


def turtle(triples):
    """The whole of ``graph.ttl`` under the AGSC-05-10 profile."""
    by_subject = {}
    for subject, predicate, obj in triples:
        _check_subject(subject)
        by_subject.setdefault(subject.value, {}).setdefault(predicate.value, set()).add(
            turtle_term(obj))
    blocks = []
    for subject in sorted(by_subject):
        clauses = []
        predicates = by_subject[subject]
        for predicate in sorted(predicates):
            verb = "a" if predicate == RDF_TYPE else turtle_iri(predicate)
            clauses.append("%s %s" % (verb, " , ".join(sorted(predicates[predicate]))))
        blocks.append("%s %s .\n" % (turtle_iri(subject), " ;\n    ".join(clauses)))
    return prefix_block() + "".join("\n" + block for block in blocks)


_BLANK_TOKEN = re.compile(r"_:|\[|\(")


def turtle_has_blank_node(text):
    """True when a Turtle fragment introduces a blank node (AGSC-05-08).

    Blank nodes arise from a ``_:`` label, a ``[ ... ]`` property list or an
    ``( ... )`` collection.  IRIs, strings and comments are skipped so that a
    bracket inside them is not mistaken for one.
    """
    index = 0
    length = len(text)
    while index < length:
        char = text[index]
        if char == "<":
            end = text.find(">", index + 1)
            index = length if end < 0 else end + 1
            continue
        if char in "\"'":
            quote = text[index:index + 3] if text[index:index + 3] in ('"""', "'''") else char
            index += len(quote)
            while index < length and not text.startswith(quote, index):
                index += 2 if text[index] == "\\" else 1
            index += len(quote)
            continue
        if char == "#":
            end = text.find("\n", index)
            index = length if end < 0 else end + 1
            continue
        if _BLANK_TOKEN.match(text, index):
            return True
        index += 1
    return False
