"""Area ``graph`` — spec/05 and AGSC-04-15, AGSC-06-32.

From 1.1 also the readings of the Link graph (AGSC-05-33, graph-0029), the ten
questions (AGSC-05-34, graph-0030 to graph-0039), the SKOS view (AGSC-05-36,
graph-0040) and the context address that does not follow the ontology version
(AGSC-05-09, graph-0043). Every member of ``expected`` is checked; a member this handler does not
know is a failure, so a vector can never pass on an assertion nobody made.
"""

from .. import context as context_module
from .. import derive, links, questions, skos
from .. import graph as graph_module
from ..jcs import canonicalize
from ..rdf import Literal, nquads_term, prefix_block, turtle_has_blank_node, turtle_term
from ._assert import checks, shown


def _base(given):
    if isinstance(given.get("site"), dict):
        return given["site"]["base"]
    return given["base"]


def _export_blocks(markdown_text):
    """The bodies of fenced code blocks whose info string is ``turtle export``."""
    blocks, current, fence = [], None, None
    for line in markdown_text.split("\n"):
        stripped = line.lstrip(" ")
        if fence is None:
            if stripped.startswith("```") or stripped.startswith("~~~"):
                marker = stripped[:3]
                run = len(stripped) - len(stripped.lstrip(marker[0]))
                fence = marker[0] * run
                info = stripped[run:].split()
                current = [] if info[:2] == ["turtle", "export"] else None
            continue
        if stripped.startswith(fence) and stripped.strip(fence[0]).strip() == "":
            if current is not None:
                blocks.append("\n".join(current))
            fence, current = None, None
            continue
        if current is not None:
            current.append(line)
    return blocks


def _jsonld_files(given, expected, base):
    """graph-0028 (AGSC-05-09, AGSC-06-02): graph.jsonld and each per-item file, whole,
    compared after JCS; the per-item files are exactly one per item."""
    bundle, data, url = given.get("bundle"), given.get("attachment_bytes"), given.get("context_url")
    whole = graph_module.to_jsonld(given["items"], base, bundle, data, context_url=url)
    out = [("graph.jsonld", canonicalize(whole) == canonicalize(expected.get("graph_jsonld")),
            canonicalize(whole))]
    wanted = expected.get("per_item", {})
    slugs = sorted(item["slug"] for item in given["items"])
    out.append(("per-item files", slugs == sorted(wanted), shown(slugs)))
    for item in given["items"]:
        single = graph_module.to_jsonld([item], base, bundle, data, context_url=url)
        one = canonicalize(graph_module.restrict_to(whole, single))
        out.append(("pages/%s.jsonld" % item["slug"],
                    item["slug"] in wanted and one == canonicalize(wanted[item["slug"]]), one))
    return out


#: graph-0029 states its readings over items with no base; the dataset it compares with
#: is written at this one (the engine's handler does the same).
_READINGS_BASE = "https://a.example/"


def _property_of_key(key):
    """The RDF property a reading's key is written with, or None (``derivation-of``)."""
    if key in graph_module.LINK_PROPERTIES:
        return graph_module.LINK_PROPERTIES[key][0]
    owner = [name for name, inverse in links.INVERSE.items() if inverse == key]
    return graph_module.LINK_PROPERTIES[owner[0]][1] if owner else None


def _stored(readings, items):
    """The transitive and closure readings that are a triple of the dataset (none may be)."""
    triples = graph_module.dataset(items, _READINGS_BASE)
    by_slug = dict((item["slug"], item) for item in items)

    def iri(slug):
        return graph_module.IRI(graph_module.item_iri(_READINGS_BASE, by_slug[slug]))
    return [one for one in readings
            if one["because"][0]["rule"] in ("transitive", "closure")
            and _property_of_key(one["key"]) is not None
            and (iri(one["source"]), graph_module.IRI(_property_of_key(one["key"])),
                 iri(one["target"])) in triples]


def _readings(given, have, expected):
    """graph-0029 (AGSC-05-33): the readings, in order; none is stored in the graph."""
    edges, _ = links.edges(given["items"])
    got = derive.readings(edges)
    out = []
    if have("readings"):
        out.append(("readings", canonicalize(got) == canonicalize(expected["readings"]),
                    canonicalize(got)))
    if have("graph_files_unchanged"):
        stored = _stored(got, given["items"])
        out.append(("graph-files-unchanged",
                    (stored == []) == expected["graph_files_unchanged"], shown(stored)))
    return out


def _question(given, have, expected):
    """graph-0030 to graph-0039 (AGSC-05-34): one question over the shared fixture."""
    got = questions.answer(given["question"], given["items"], subject=given.get("subject"),
                           selection=given.get("selection") or [], at=given.get("at"))
    have("answer")  # a case with no answer stated fails on the comparison below
    return [("question %s" % given["question"],
             canonicalize(got) == canonicalize(expected.get("answer")), canonicalize(got))]


def _context_address(given, have, expected):
    """graph-0043 (AGSC-05-09): the Bundle written once per ontology version the case
    names, each time with the persistent context address of a Level-0 node: every
    document names the one ``CONTEXT_URL`` and all are byte-identical.  This writer
    reads no ontology version at all, which is the rule's point."""
    base = _base(given)
    written = [graph_module.to_jsonld(given["items"], base, context_url=context_module.CONTEXT_URL)
               for _ in given["ontology_versions"]]
    urls = [one.get("@context") for one in written]
    documents = [canonicalize(one) for one in written]
    out = []
    if have("context_url"):
        out.append(("context_url", bool(urls) and all(url == expected["context_url"]
                                                       for url in urls), shown(urls)))
    if have("graph_jsonld_identical_across_ontology_versions"):
        same = all(one == documents[0] for one in documents)
        out.append(("identical", same == expected["graph_jsonld_identical_across_ontology_versions"],
                    "the documents differ across ontology versions"))
    return out


def run(vector):
    given = vector["input"]
    expected = vector["expected"]
    if "bundle" in given and isinstance(given.get("item"), dict):
        # graph-0027 and its kind: the real lint and build over a whole Bundle.
        return {"status": "not-run",
                "detail": "needs the real lint and build over a whole Bundle; not implemented by this package"}
    items = []
    handled = set()

    def have(name):
        handled.add(name)
        return name in expected

    if isinstance(given.get("question"), int):
        items.extend(_question(given, have, expected))

    elif isinstance(given.get("ontology_versions"), list):
        items.extend(_context_address(given, have, expected))

    elif "readings" in expected:
        items.extend(_readings(given, have, expected))

    elif isinstance(given.get("items"), list):
        base = _base(given)
        bundle = given.get("bundle")
        data = given.get("attachment_bytes")
        quads = graph_module.to_nquads(given["items"], base, bundle, data)
        ttl = graph_module.to_turtle(given["items"], base, bundle, data)
        lines = quads.split("\n")[:-1]
        if have("nquads"):
            items.append(("nquads", quads == expected["nquads"], shown(quads)))
        if have("turtle"):
            items.append(("turtle", ttl == expected["turtle"], shown(ttl)))
        if have("prefix_block_is_constant"):
            items.append(("prefix-block", ttl.startswith(prefix_block() + "\n")
                          == expected["prefix_block_is_constant"], shown(ttl[:400])))
        if any([have("graph_jsonld"), have("per_item")]):
            items.extend(_jsonld_files(given, expected, base))
        if have("turtle_never_contains"):
            items.append(("turtle-never-contains", expected["turtle_never_contains"] not in ttl,
                          expected["turtle_never_contains"]))
        if have("verdict_digest_exported"):
            digests = [one["verdict_digest"] for one in given["items"] if "verdict_digest" in one]
            exported = any(digest in quads for digest in digests) or "verdictDigest" in quads
            items.append(("verdict-digest", exported == expected["verdict_digest_exported"],
                          shown(exported)))
        if have("blank_nodes"):
            count = sum(1 for line in lines if "_:" in line)
            items.append(("blank-nodes", count == expected["blank_nodes"], shown(count)))
        if have("forbidden"):
            present = [one for one in expected["forbidden"] if one in ttl or one in quads]
            items.append(("forbidden", present == [], shown(present)))
        if have("contains"):
            missing = [one for one in expected["contains"] if one not in lines]
            items.append(("contains", missing == [], shown(missing)))
        if have("excludes"):
            found = [one for one in expected["excludes"]
                     if any(line.startswith(one) for line in lines)]
            items.append(("excludes", found == [], shown(found)))
        if have("mentions_lines"):
            got = [line + "\n" for line in lines if "/ns#mentions>" in line]
            items.append(("mentions", got == expected["mentions_lines"], shown(got)))
        if have("inverse_materialised"):
            pairs = set((line.split(" ")[0], line.split(" ")[2])
                        for line in lines if "/ns#mentions>" in line)
            inverse = any((b, a) in pairs for a, b in pairs)
            items.append(("inverse", inverse == expected["inverse_materialised"],
                          shown(inverse)))
        if have("skos"):
            # graph-0040 (AGSC-05-36): the SKOS view, the whole file.
            view = skos.skos_view(graph_module.dataset(given["items"], base, bundle, data),
                                  skos.scheme_record(given))
            items.append(("skos", view == expected["skos"], shown(view)))
        if have("whole_file_asserted"):
            items.append(("whole-file", expected["whole_file_asserted"] is False,
                          "a whole-file assertion needs `nquads`"))

    elif isinstance(given.get("markdown"), str):
        blank = any(turtle_has_blank_node(one) for one in _export_blocks(given["markdown"]))
        code = "AGSC-E605" if blank else None
        if have("error"):
            items.append(("error", code == expected["error"], shown(code)))

    elif "bundle_id" in given:
        outcomes = []
        for value in given["value"]:
            try:
                outcomes.append(("ok", graph_module.resolve_memory(value, given["bundle_id"])))
            except graph_module.GraphError as error:
                outcomes.append(("error", error.code))
        if have("resolved"):
            items.append(("resolved", outcomes[0] == ("ok", expected["resolved"]),
                          shown(outcomes)))
        if have("foreign_bundle"):
            items.append(("foreign", outcomes[1] == ("error", expected["foreign_bundle"]["error"]),
                          shown(outcomes)))
        if have("emitted_as_rdf_subject"):
            emitted = True
            try:
                graph_module.nquads({(graph_module.IRI(given["value"][0]),
                                      graph_module.IRI(graph_module.RDF_TYPE),
                                      graph_module.IRI(graph_module.ASC + "Concept"))})
            except ValueError:
                emitted = False
            items.append(("never-a-subject", emitted == expected["emitted_as_rdf_subject"],
                          shown(emitted)))

    elif "ontology_terms" in given:
        external = given.get("external_properties", given.get("external_properties_used", []))
        built = context_module.build(given["ontology_terms"], external)
        if have("context"):
            items.append(("context", canonicalize(built) == canonicalize(expected["context"]),
                          canonicalize(built)))
        if have("term_names"):
            names = context_module.term_names(
                given["ontology_terms"],
                [one if isinstance(one, str) else one["property"] for one in external])
            items.append(("term-names", names == expected["term_names"], shown(names)))
        if have("roundtrip_byte_identical"):
            first, again = context_module.roundtrip_bytes(
                context_module.sample_triples(built), built)
            items.append(("roundtrip", (first == again) == expected["roundtrip_byte_identical"],
                          "re-compacted bytes differ"))

    elif "literal" in given:
        plain = nquads_term(Literal(given["literal"]))
        if have("nquads_literal"):
            items.append(("literal", plain == expected["nquads_literal"], shown(plain)))
        if have("nquads_lang"):
            lang = nquads_term(Literal(given["lang_literal"]["value"],
                                       lang=given["lang_literal"]["lang"]))
            items.append(("lang", lang == expected["nquads_lang"], shown(lang)))
        if have("nquads_typed"):
            typed = nquads_term(Literal(
                given["typed_literal"]["value"],
                datatype=context_module.expand_curie(given["typed_literal"]["datatype"])))
            items.append(("typed", typed == expected["nquads_typed"], shown(typed)))
        if have("forbidden_forms"):
            found = [one for one in expected["forbidden_forms"] if one in plain]
            items.append(("forbidden-forms", found == [], shown(found)))
        if have("turtle_literal_has_explicit_xsd_string"):
            explicit = "^^" in turtle_term(Literal(given["literal"]))
            items.append(("turtle-plain", explicit
                          == expected["turtle_literal_has_explicit_xsd_string"], shown(explicit)))

    unknown = sorted(set(expected) - handled)
    if unknown:
        items.append(("unhandled", False, "expected members not checked: %s" % shown(unknown)))
    if not items:
        items.append(("shape", False, "no input shape this handler knows"))
    return checks(items)

