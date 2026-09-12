"""Agentic System Core — name reservation for a specification under development.

No runtime is published in the 0.0.x line. These constants mirror the reference
implementation so that early consumers do not hard-code a superseded value.
"""

# The well-known URI suffix (decision D60, 2026-09-04).
WELLKNOWN_SUFFIX = "knowledge-linkset"

# The link relation and Profile URI keep the name `agentic-knowledge` (unchanged by D60).
LINK_RELATION = "agentic-knowledge"
PROFILE_URI = "https://w3id.org/agentic-system-core/profile/agentic-knowledge"

# Deprecated: the published 0.0.1 stub carried the old well-known path here.
# Retained as an alias so a 0.0.1 consumer does not break; removed at 0.1.0.
AGENTIC_KNOWLEDGE_URI = WELLKNOWN_SUFFIX

__version__ = "0.0.2"
__all__ = [
    "WELLKNOWN_SUFFIX",
    "LINK_RELATION",
    "PROFILE_URI",
    "AGENTIC_KNOWLEDGE_URI",
    "__version__",
]
