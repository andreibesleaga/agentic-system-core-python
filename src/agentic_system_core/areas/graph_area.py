"""Area ``graph`` — spec/05 and AGSC-04-15, AGSC-06-32.

Every member of ``expected`` is checked; a member this handler does not know is
a failure, so a vector can never pass on an assertion nobody made.
"""

from .. import context as context_module
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

    if isinstance(given.get("items"), list):
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

