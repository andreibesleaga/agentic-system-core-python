"""The URL questions the checkers ask: absolute, same origin, what path."""

import pytest

from agentic_system_core import urls


def test_an_absolute_url_is_parsed():
    url = urls.Url("https://node.example/a/b?q=1#f")
    assert url.origin == "https://node.example"
    assert url.pathname == "/a/b"
    assert url.query == "q=1"
    assert url.fragment == "f"


def test_a_default_port_is_not_part_of_the_origin():
    assert urls.Url("https://node.example:443/").origin == "https://node.example"
    assert urls.Url("https://node.example:8443/").origin == "https://node.example:8443"
    assert urls.Url("http://node.example:80/").origin == "http://node.example"


def test_an_empty_path_reads_as_a_slash():
    assert urls.Url("https://node.example").pathname == "/"


def test_a_non_special_scheme_has_no_comparable_origin():
    assert urls.Url("urn:example:node").origin == "null"


@pytest.mark.parametrize("bad", ["/relative", "node.example/x", "https://", "https://a:99999/"])
def test_a_value_that_is_not_an_absolute_url_is_refused(bad):
    with pytest.raises(ValueError):
        urls.Url(bad)


def test_the_host_is_compared_lower_cased():
    assert urls.Url("https://NODE.example/").origin == "https://node.example"


def test_a_url_argument_is_told_from_a_file_argument():
    assert urls.is_url_argument("https://node.example/x")
    assert urls.is_url_argument("HTTP://node.example/x")
    assert not urls.is_url_argument("./www/.well-known/knowledge-linkset")
    assert not urls.is_url_argument("a:b")


def test_resolving_and_decoding():
    assert urls.resolve("https://node.example/a/", "b") == "https://node.example/a/b"
    assert urls.decoded_path(urls.Url("https://node.example/a%20b")) == "/a b"
