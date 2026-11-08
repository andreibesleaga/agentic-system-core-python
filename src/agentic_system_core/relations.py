"""The relation table of AGSC-03-01: the fourteen Link keys and what is known about each.

What: one row per key — its computed inverse, whether it is symmetric, its RDF property
and inverse property, its combiner, whether it reads transitively, what a self-link to
it is (AGSC-03-23), its Expected target kinds cell (AGSC-03-25) and its plain meaning.

Why a data file: the table is a fact of the frozen specification, and the engine keeps
it once, in ``src/knowledge/relations.js``. ``data/relations.json`` is that table as the
command in docs/MAINTAINING.md derives it, never typed, and the suite fails when it
drifts. ``links.py``, ``graph.py``, ``derive.py`` and ``questions.py`` take their key
lists, inverses and properties from here, so the package holds one copy, not two.

Standard library only.
"""

import json
import os

from .rdf import PREFIXES

_DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "relations.json")
_NAMESPACES = dict(PREFIXES)


def data_bytes():
    """The bytes of ``data/relations.json`` as shipped."""
    with open(_DATA, "rb") as handle:
        return handle.read()


def expand(curie):
    """``skos:related`` -> its full IRI over the constant prefix block (AGSC-05-10)."""
    prefix, _, local = curie.partition(":")
    if prefix not in _NAMESPACES or local == "":
        raise ValueError("%s is not a compact IRI over the constant prefixes" % curie)
    return _NAMESPACES[prefix] + local


#: AGSC-03-01, the section 3.1 table: the nine core keys, then the five Mode-2 keys.
RELATIONS = tuple(json.loads(data_bytes().decode("utf-8"))["relations"])
#: key -> its row.
ROW = dict((row["key"], row) for row in RELATIONS)
#: AGSC-03-01: the nine core keys and the five Mode-2 keys (AGSC-03-18), in table order.
CORE_KEYS = tuple(row["key"] for row in RELATIONS[:9])
MODE2_KEYS = tuple(row["key"] for row in RELATIONS[9:])
KEYS = CORE_KEYS + MODE2_KEYS
#: AGSC-03-02: authored key -> computed inverse name.
INVERSE = dict((row["key"], row["inverse"]) for row in RELATIONS)
#: AGSC-03-05: the keys materialised in both directions.
SYMMETRIC = tuple(row["key"] for row in RELATIONS if row["symmetric"])
#: AGSC-03-04: the computed names that are never authored (``narrower`` is a key).
COMPUTED_KEYS = tuple(row["inverse"] for row in RELATIONS
                      if not row["symmetric"] and row["inverse"] not in KEYS)
#: AGSC-05-16 / AGSC-05-23: key -> (property IRI, inverse property IRI or None). A
#: symmetric key's inverse is its own property; ``derived-from`` has no inverse property.
LINK_PROPERTIES = dict(
    (row["key"], (expand(row["property"]),
                  expand(row["property"]) if row["symmetric"]
                  else (expand(row["inverseProperty"]) if "inverseProperty" in row else None)))
    for row in RELATIONS)
