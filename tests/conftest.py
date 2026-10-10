"""Shared paths for the suite.  No network, no clock, no randomness."""

import os
import pathlib

import pytest

HERE = pathlib.Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures"
WELLKNOWN = FIXTURES / "wellknown"
VECTORS = FIXTURES / "vectors"

#: The sibling checkouts, when they sit beside this one.  The equivalence test
#: needs the engine; the two site tests need the built sites.  Every other test
#: runs without any of them, and each one says so when it is skipped.
NEIGHBOURS = HERE.parent.parent
ENGINE = NEIGHBOURS / "agentic-system-core"

#: The built discovery files of the two nodes, when their checkouts are here.
SITE_DOCUMENTS = [
    NEIGHBOURS / "AgenticSystemCore.com" / "www" / ".well-known" / "knowledge-linkset",
    NEIGHBOURS / "AgenticSystemCore-Patterns" / "www" / ".well-known" / "knowledge-linkset",
]


@pytest.fixture
def wellknown_dir():
    return WELLKNOWN


@pytest.fixture
def vectors_dir():
    return VECTORS


def case(name):
    """The discovery document of one fixture case."""
    path = WELLKNOWN / name / ".well-known" / "knowledge-linkset"
    if not path.exists():
        path = WELLKNOWN / name / "plain" / "knowledge-linkset"
    return str(path)


def engine_available():
    return (ENGINE / "tools" / "validate-wellknown").is_file() and _node_on_path()


def _node_on_path():
    for entry in os.environ.get("PATH", "").split(os.pathsep):
        if entry and os.path.isfile(os.path.join(entry, "node")):
            return True
    return False
