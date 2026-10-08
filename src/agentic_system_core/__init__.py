"""Agentic System Core — the Python side of the reference implementation.

What this package IS: two checkers a consumer can run with nothing but Python,
plus a small reading API for a published node, plus one ``agsc`` command that
runs those natively and hands every other verb to the Node engine when it is
installed.

What this package is NOT: a second implementation of the engine.  Building a
Bundle, emitting a site, composing, governing and the rest stay with the Node
package ``agentic-system-core``; see the README.

Every rule identifier below is a rule of the AgenticSystemCore specification.
"""

# PEP 440 spelling of the SemVer pre-release 1.0.0-rc.7 (see README, "Version").
__version__ = "1.0.0rc7"

#: The SemVer spelling the specification and the Node package use.
SEMVER_VERSION = "1.0.0-rc.7"

#: The specification version this package implements (spec/00-overview.md).
SPEC_VERSION = "1.0.0-rc.7"

#: The well-known URI suffix of AGSC-06-07: /.well-known/knowledge-linkset.
WELLKNOWN_SUFFIX = "knowledge-linkset"

#: The path the suffix is served at.
WELLKNOWN_PATH = "/.well-known/" + WELLKNOWN_SUFFIX

#: The link relation and profile name (unchanged by the suffix rename).
LINK_RELATION = "agentic-knowledge"

#: The profile URI a conforming discovery document carries (AGSC-06-07).
PROFILE_URI = "https://w3id.org/agentic-system-core/profile/agentic-knowledge"

#: The base of the extension relation URIs of AGSC-06-10.
REL_BASE = "https://w3id.org/agentic-system-core/rel#"

#: The media type of the discovery document (RFC 9264).
MEDIA_TYPE = "application/linkset+json"

# Deprecated: the published 0.0.1 stub carried the old well-known path here.
# Retained as an alias so a 0.0.1 consumer does not break.
AGENTIC_KNOWLEDGE_URI = WELLKNOWN_SUFFIX

__all__ = [
    "AGENTIC_KNOWLEDGE_URI",
    "LINK_RELATION",
    "MEDIA_TYPE",
    "PROFILE_URI",
    "REL_BASE",
    "SEMVER_VERSION",
    "SPEC_VERSION",
    "WELLKNOWN_PATH",
    "WELLKNOWN_SUFFIX",
    "__version__",
]
