"""The Agent2Agent agent card ``/.well-known/agent-card.json`` (AGSC-06-34).

The twin of the engine's ``src-ts/distribution/a2a-card.ts``: the A2A 1.0 Agent Card,
written only for a node that declares the ``a2a-card`` surface and a ``responder``
surface (AGSC-06-07), every responder an A2A one (version ``a2a:<version>``,
AGSC-11-21) and the ``a2a-card`` version a bare A2A version such as ``1.0``.  A card
declared with no responder is a card without an endpoint, the error AGSC-E210; one
that would not be a true A2A card is not written, with the warning AGSC-E210, and the
discovery document does not declare it (``served_declarations``).  A responder's
``security_schemes`` and ``security_requirements`` become the card's ``securitySchemes``
and ``securityRequirements``.  Vectors disc-0030, disc-0031, disc-0035 and disc-0038.

The engine writes the card through the official A2A JavaScript SDK's JSON form of the
message (``AgentCard.toJSON``, the protobuf JSON mapping: an empty string, an empty list
and an empty map are left out, a sub-message stays), then sets ``skills`` to ``[]``
when the node has no skill pack, then JCS and one LF.  This module writes the same
members by the same rule.  The Python A2A SDK (``a2a-sdk``) is not used: it is a
runtime dependency with seven of its own, and this package has none
(``dependencies = []``); the engine's bytes, through the shared vectors, are the
oracle.  Pure: data in, text out.  Standard library only.
"""

import re

from .diagnostics import finding
from .jcs import canonicalize

#: AGSC-06-34 with AGSC-01-18: the ``protocolBinding`` of a responder that names none.
DEFAULT_BINDING = "JSONRPC"
#: AGSC-06-34: the ``tags`` of every skill (A2A 1.0 section 4.4.5 requires them).
SKILL_TAGS = ("knowledge", "skill-pack")
#: AGSC-11-21: the version prefix of a responder that is an Agent2Agent server.
A2A_PREFIX = "a2a:"
#: AGSC-11-16: the protocol version of ``a2a-card``, the bare form the schema admits.
A2A_VERSION = re.compile(r"^[0-9]+\.[0-9]+(?:\.[0-9]+)?$")


def declared(surfaces, name):
    """The ``surfaces[]`` entries that declare the surface ``name``, in order."""
    return [one for one in surfaces if isinstance(one, dict) and one.get("surface") == name]


def _text(value):
    """JavaScript's ``String()`` of a configured value: ``undefined`` when absent."""
    if value is None:
        return "undefined"
    return str(value)


def _unpublishable(surfaces):
    """Why a node that declares ``a2a-card`` and a responder gets no card, or None."""
    if any(not _text(one.get("version")).startswith(A2A_PREFIX)
           for one in declared(surfaces, "responder")):
        return ("a responder whose version is not a2a:<version> is not an A2A endpoint, and the "
                "card would list it as one")
    version = declared(surfaces, "a2a-card")[0].get("version")
    if A2A_VERSION.match(_text(version)) is None:
        shown = "undefined" if version is None else canonicalize(version)
        return ("the a2a-card version %s is not an A2A protocol version such as 1.0, and the "
                "card would carry it as the protocolVersion of every interface" % shown)
    return None


def eligible(surfaces):
    """AGSC-06-34: both surfaces declared, every responder an A2A one, a bare A2A version."""
    return bool(declared(surfaces, "a2a-card")) and bool(declared(surfaces, "responder")) \
        and _unpublishable(surfaces) is None


def card_findings(surfaces):
    """AGSC-06-07, AGSC-06-34: the findings of a declared card that is not written."""
    if not declared(surfaces, "a2a-card"):
        return []
    if not declared(surfaces, "responder"):
        return [finding("AGSC-E210", "agsc.config.json",
                        "surfaces[] declares a2a-card but no responder surface: a card without "
                        "an endpoint is not published (AGSC-06-07, AGSC-06-34; a local MCP tool "
                        "server is not an A2A endpoint)")]
    why = _unpublishable(surfaces)
    if why is None:
        return _open_credential_findings(surfaces)
    target = _text(declared(surfaces, "a2a-card")[0].get("target"))
    return [finding("AGSC-E210", "agsc.config.json",
                    "no /.well-known/agent-card.json is written: %s; the discovery document does "
                    "not declare a2a-card at %s either (AGSC-06-34, AGSC-11-16, AGSC-11-21)"
                    % (why, target), severity="warn")]


def _open_credential_findings(surfaces):
    """AGSC-06-34 as amended 2026-11-10: a ``credential`` responder that names no
    ``security_schemes`` leaves a card an A2A client reads as open."""
    return [finding("AGSC-E210", "agsc.config.json",
                    "the responder %s is declared with access credential and its entry names no "
                    "security_schemes, so the card carries no securitySchemes and an A2A client "
                    "reads it as open (AGSC-06-34, AGSC-11-16)" % _text(one.get("target")),
                    severity="warn")
            for one in declared(surfaces, "responder")
            if one.get("access") == "credential" and not one.get("security_schemes")]


def served_declarations(surfaces):
    """AGSC-11-16 as amended 2026-11-10: the declaration-only surfaces less an ``a2a-card``
    that gets no card, so the discovery document declares no card the node does not serve
    (the engine's ``well-known.js#servedDeclarations``)."""
    if not declared(surfaces, "a2a-card") or eligible(surfaces):
        return list(surfaces)
    return [one for one in surfaces
            if not (isinstance(one, dict) and one.get("surface") == "a2a-card")]


def _pruned(value):
    """The protobuf JSON mapping the SDK writes a message in: an empty string or list is
    left out, a sub-message stays.  Members A2A does not define are not dropped here, as
    the engine's codec drops them (README, "Differences from the engine")."""
    if isinstance(value, dict):
        return dict((name, _pruned(one)) for name, one in value.items() if one not in ("", []))
    if isinstance(value, list):
        return [_pruned(one) for one in value]
    return value


def _security(surfaces):
    """AGSC-06-34 as amended 2026-11-10: the card's ``securitySchemes`` (the first entry
    to give a name wins) and ``securityRequirements``, from the responder entries in order."""
    schemes, requirements = {}, []
    for one in declared(surfaces, "responder"):
        for name, scheme in (one.get("security_schemes") or {}).items():
            schemes.setdefault(name, _pruned(scheme))
        requirements.extend(_pruned(entry) for entry in one.get("security_requirements") or [])
    return schemes, requirements


def _first_text(*values):
    for value in values:
        if isinstance(value, str) and value != "":
            return value
    return ""


def _present(fields):
    """The protobuf JSON mapping of the SDK's writer: an empty string or list is left out."""
    return dict((name, value) for name, value in fields.items() if value not in ("", []))


def card(surfaces, packs, title, bundle_version, spec_version, visibility=None,
         description=None, tagline=None):
    """AGSC-06-34: the card's members as the SDK's JSON writer writes them.  ``version``
    is the content version, and on a restricted node the specification version
    (AGSC-11-20 stamps no content version where an unauthenticated reader can read it)."""
    protocol = _first_text(declared(surfaces, "a2a-card")[0].get("version"))
    interfaces = [_present({"protocolBinding": _first_text(one.get("binding"), DEFAULT_BINDING),
                            "protocolVersion": protocol, "tenant": "",
                            "url": _text(one.get("target"))})
                  for one in declared(surfaces, "responder")]
    skills = [_present({"description": _first_text(pack.get("description")), "examples": [],
                        "id": pack.get("name"), "inputModes": [], "name": pack.get("name"),
                        "outputModes": [], "securityRequirements": [], "tags": list(SKILL_TAGS)})
              for pack in packs]
    version = spec_version if visibility == "restricted" else bundle_version
    schemes, requirements = _security(surfaces)
    out = _present({
        "defaultInputModes": ["text/plain"], "defaultOutputModes": ["application/json"],
        "description": _first_text(description, tagline, title), "name": title,
        "securityRequirements": requirements, "signatures": [], "skills": skills,
        "supportedInterfaces": interfaces, "version": version,
    })
    if schemes:
        out["securitySchemes"] = schemes
    # A sub-message stays, its own empty `extensions` left out; an empty map (the
    # security schemes) is left out.  A2A 1.0 section 4.4.1: `skills` is required, so a
    # node with no pack has `skills` [].
    out["capabilities"] = {}
    out.setdefault("skills", [])
    return out


def card_bytes(surfaces, packs, title, bundle_version, spec_version, visibility=None,
               description=None, tagline=None):
    """AGSC-06-34: the bytes of ``/.well-known/agent-card.json`` (JCS, one trailing LF),
    or None when the node is not eligible (AGSC-06-07)."""
    if not eligible(surfaces):
        return None
    return canonicalize(card(surfaces, packs, title, str(bundle_version), str(spec_version),
                             visibility, description, tagline)) + "\n"
