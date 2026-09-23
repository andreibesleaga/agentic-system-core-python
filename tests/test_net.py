"""The address rules that guard a network read.  No socket is opened here."""

import pytest

from agentic_system_core import net


@pytest.mark.parametrize("address", [
    "10.0.0.1", "192.168.1.1", "169.254.169.254", "172.16.0.1", "100.64.0.1",
    "192.0.2.1", "203.0.113.5", "224.0.0.1", "255.255.255.255",
    "fc00::1", "fe80::1", "2001:db8::1", "::", "ff00::1",
])
def test_a_private_or_reserved_address_is_refused(address):
    assert net.is_refused(address)


@pytest.mark.parametrize("address", ["93.184.216.34", "8.8.8.8", "2606:2800:220:1:248:1893:25c8:1946"])
def test_a_public_address_is_allowed(address):
    assert not net.is_refused(address)


def test_loopback_is_refused_unless_dev_is_asked_for():
    assert net.is_refused("127.0.0.1")
    assert not net.is_refused("127.0.0.1", dev=True)
    assert net.is_refused("::1")
    assert not net.is_refused("::1", dev=True)
    assert net.is_loopback("127.0.0.5")
    assert net.is_loopback("::1")
    assert not net.is_loopback("::2")


def test_a_scheme_other_than_http_or_https_is_refused():
    with pytest.raises(net.TransportError) as error:
        net.fetch_once("ftp://example.org/x")
    assert error.value.code == "AGSC-E905"


def test_plain_http_is_refused_without_dev():
    with pytest.raises(net.TransportError) as error:
        net.fetch_once("http://example.org/x")
    assert error.value.code == "AGSC-E905"


def test_a_literal_private_address_is_refused_before_any_socket():
    with pytest.raises(net.TransportError) as error:
        net.fetch_once("https://10.0.0.1/x")
    assert error.value.code == "AGSC-E905"
    with pytest.raises(net.TransportError):
        net.fetch_once("https://[fc00::1]/x")


def test_plain_http_to_a_public_literal_is_refused_even_under_dev():
    with pytest.raises(net.TransportError) as error:
        net.fetch_once("http://93.184.216.34/x", dev=True)
    assert error.value.code == "AGSC-E905"


def test_a_relative_argument_is_not_a_url():
    with pytest.raises(ValueError):
        net.fetch_once("not-a-url")


def test_fetch_follows_at_most_three_redirects(monkeypatch):
    seen = []

    def fake(href, dev=False):
        seen.append(href)
        return 302, {"location": "https://example.org/%d" % len(seen)}, b""

    monkeypatch.setattr(net, "fetch_once", fake)
    with pytest.raises(net.TransportError) as error:
        net.fetch("https://example.org/")
    assert error.value.code == "AGSC-E905"
    assert len(seen) == net.REDIRECT_LIMIT + 1


def test_fetch_reports_a_status_that_is_not_two_hundred(monkeypatch):
    monkeypatch.setattr(net, "fetch_once", lambda href, dev=False: (404, {}, b""))
    with pytest.raises(net.TransportError) as error:
        net.fetch("https://example.org/")
    assert error.value.code == "AGSC-E907"


def test_fetch_returns_the_final_url_headers_and_bytes(monkeypatch):
    calls = []

    def fake(href, dev=False):
        calls.append(href)
        if len(calls) == 1:
            return 301, {"location": "/final"}, b""
        return 200, {"content-type": "application/linkset+json"}, b"{}"

    monkeypatch.setattr(net, "fetch_once", fake)
    final, headers, body = net.fetch("https://example.org/start")
    assert final == "https://example.org/final"
    assert body == b"{}"
    assert headers["content-type"] == "application/linkset+json"


class _FakeResponse(object):
    def __init__(self, status, headers, body):
        self.status = status
        self._headers = headers
        self._body = body

    def read(self, limit):
        return self._body[:limit]

    def getheaders(self):
        return list(self._headers.items())


class _FakeConnection(object):
    """A connection that answers from memory.  No socket, no resolver, no server."""

    last = None

    def __init__(self, *arguments, **keywords):
        _FakeConnection.last = self
        self.arguments = arguments
        self.requested = None
        self.closed = False
        self.response = _FakeResponse(200, {"Content-Type": "application/linkset+json"}, b"{}")
        self.error = None

    def request(self, method, target, headers=None):
        self.requested = (method, target, headers)
        if self.error is not None:
            raise self.error

    def getresponse(self):
        return self.response

    def close(self):
        self.closed = True


@pytest.fixture
def fake_connection(monkeypatch):
    monkeypatch.setattr(net, "_PinnedHTTPSConnection", _FakeConnection)
    monkeypatch.setattr(net, "_PinnedHTTPConnection", _FakeConnection)
    monkeypatch.setattr(net.socket, "getaddrinfo",
                        lambda *a, **k: [(net.socket.AF_INET, 0, 0, "", ("93.184.216.34", 443))])
    return _FakeConnection


def test_a_request_carries_the_path_the_query_and_the_accept_header(fake_connection):
    status, headers, body = net.fetch_once("https://node.example/a?b=1")
    assert status == 200
    assert body == b"{}"
    assert headers["content-type"] == "application/linkset+json"
    method, target, sent = fake_connection.last.requested
    assert (method, target) == ("GET", "/a?b=1")
    assert "linkset+json" in sent["Accept"]
    assert fake_connection.last.closed


def test_a_response_over_the_cap_is_e904(fake_connection):
    net._PinnedHTTPSConnection = fake_connection
    connection_holder = {}

    class Big(_FakeConnection):
        def __init__(self, *arguments, **keywords):
            _FakeConnection.__init__(self, *arguments, **keywords)
            self.response = _FakeResponse(200, {}, b"x" * (net.MAX_BYTES + 1))
            connection_holder["one"] = self

    net._PinnedHTTPSConnection = Big
    with pytest.raises(net.TransportError) as error:
        net.fetch_once("https://node.example/")
    assert error.value.code == "AGSC-E904"
    assert connection_holder["one"].closed


def test_a_socket_error_becomes_e907(fake_connection):
    class Broken(_FakeConnection):
        def __init__(self, *arguments, **keywords):
            _FakeConnection.__init__(self, *arguments, **keywords)
            self.error = OSError("connection reset")

    net._PinnedHTTPSConnection = Broken
    with pytest.raises(net.TransportError) as error:
        net.fetch_once("https://node.example/")
    assert error.value.code == "AGSC-E907"


def test_a_resolved_private_address_is_refused_before_any_socket(monkeypatch):
    monkeypatch.setattr(net.socket, "getaddrinfo",
                        lambda *a, **k: [(net.socket.AF_INET, 0, 0, "", ("10.1.2.3", 443))])
    with pytest.raises(net.TransportError) as error:
        net.fetch_once("https://internal.example/")
    assert error.value.code == "AGSC-E905"


def test_a_name_that_resolves_to_a_public_address_is_classified(monkeypatch):
    monkeypatch.setattr(net.socket, "getaddrinfo", lambda *a, **k: [
        (net.socket.AF_INET6, 0, 0, "", ("2606:2800:220:1:248:1893:25c8:1946", 443, 0, 0)),
    ])
    assert net._classify("node.example", False) == \
        [(6, "2606:2800:220:1:248:1893:25c8:1946")]


def test_plain_http_to_a_name_that_is_not_loopback_is_refused(monkeypatch):
    monkeypatch.setattr(net.socket, "getaddrinfo",
                        lambda *a, **k: [(net.socket.AF_INET, 0, 0, "", ("93.184.216.34", 80))])
    with pytest.raises(net.TransportError) as error:
        net.fetch_once("http://node.example/", dev=True)
    assert error.value.code == "AGSC-E905"


def test_plain_http_to_loopback_under_dev_is_allowed(monkeypatch, fake_connection):
    monkeypatch.setattr(net.socket, "getaddrinfo",
                        lambda *a, **k: [(net.socket.AF_INET, 0, 0, "", ("127.0.0.1", 8080))])
    net._PinnedHTTPConnection = _FakeConnection
    status, _, _ = net.fetch_once("http://localhost:8080/x", dev=True)
    assert status == 200


def test_the_pinned_connections_are_built_without_opening_anything():
    import ssl
    https = net._PinnedHTTPSConnection("node.example", "93.184.216.34", 443, 10,
                                       ssl.create_default_context())
    assert https.host == "node.example" and https._pinned == "93.184.216.34"
    plain = net._PinnedHTTPConnection("localhost", "127.0.0.1", 8080, 10)
    assert plain.port == 8080 and plain._pinned == "127.0.0.1"
