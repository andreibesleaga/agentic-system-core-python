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

    def fake(href, dev=False, cap=net.MAX_BYTES):
        seen.append(href)
        return 302, {"location": "https://example.org/%d" % len(seen)}, b""

    monkeypatch.setattr(net, "fetch_once", fake)
    with pytest.raises(net.TransportError) as error:
        net.fetch("https://example.org/")
    assert error.value.code == "AGSC-E905"
    assert len(seen) == net.REDIRECT_LIMIT + 1


def test_fetch_reports_a_status_that_is_not_two_hundred(monkeypatch):
    monkeypatch.setattr(net, "fetch_once", lambda href, dev=False, cap=net.MAX_BYTES: (404, {}, b""))
    with pytest.raises(net.TransportError) as error:
        net.fetch("https://example.org/")
    assert error.value.code == "AGSC-E907"


def test_fetch_returns_the_final_url_headers_and_bytes(monkeypatch):
    calls = []

    def fake(href, dev=False, cap=net.MAX_BYTES):
        calls.append(href)
        if len(calls) == 1:
            return 301, {"location": "/final"}, b""
        return 200, {"content-type": "application/linkset+json"}, b"{}"

    monkeypatch.setattr(net, "fetch_once", fake)
    final, headers, body = net.fetch("https://example.org/start")
    assert final == "https://example.org/final"
    assert body == b"{}"
    assert headers["content-type"] == "application/linkset+json"


class _Socket(object):
    """Records every timeout set on it."""

    def __init__(self):
        self.timeouts = []

    def settimeout(self, value):
        self.timeouts.append(value)


class _FakeResponse(object):
    """A response read from memory, a piece at a time, as a socket gives it."""

    def __init__(self, status, headers, body, clock=None, step=0):
        #: the file object a real response reads through, down to its socket
        self.fp = type("File", (), {"raw": type("SocketIO", (), {"_sock": _Socket()})()})()
        self.status = status
        self._headers = headers
        self._body = body
        self._at = 0
        #: a one-element list the test's clock reads; each read advances it by ``step``
        self._clock = clock
        self._step = step

    def read1(self, limit):
        if self._clock is not None:
            self._clock[0] += self._step
        piece = self._body[self._at:self._at + limit]
        self._at += len(piece)
        return piece

    read = read1

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


def test_a_response_over_the_cap_is_e907(fake_connection):
    # AGSC-11-10(f): a fetch aborted at its cap is AGSC-E907, not AGSC-E904, the code
    # of a local input file over 1 MiB (AGSC-01-16).
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
    assert error.value.code == "AGSC-E907"
    assert "AGSC-11-10(f)" in error.value.message
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


def test_a_target_is_capped_at_the_federation_default_not_at_one_mebibyte(fake_connection):
    # Targets other than the discovery document are held to
    # federation.max_bytes' default (AGSC-11-01), so a graph over 1 MiB can be checked.
    assert net.TARGET_MAX_BYTES == 33554432

    class Large(_FakeConnection):
        def __init__(self, *arguments, **keywords):
            _FakeConnection.__init__(self, *arguments, **keywords)
            self.response = _FakeResponse(200, {}, b" " * (2 * net.MAX_BYTES))

    net._PinnedHTTPSConnection = Large
    status, _, body = net.fetch_once("https://node.example/graph.jsonld", cap=net.TARGET_MAX_BYTES)
    assert status == 200 and len(body) == 2 * net.MAX_BYTES
    with pytest.raises(net.TransportError) as error:
        net.fetch_once("https://node.example/graph.jsonld")
    assert error.value.code == "AGSC-E907"


def test_one_deadline_holds_the_whole_response_not_an_idle_timer(fake_connection, monkeypatch):
    # AGSC-11-10(e, f): a server that sends one piece every two seconds would keep an
    # idle timer from ever firing.  The fetch has ONE deadline, from the request to the
    # last byte, and every socket wait is bounded by what is left.
    clock = [1000.0]
    monkeypatch.setattr(net.time, "monotonic", lambda: clock[0])
    sockets = []

    class Slow(_FakeConnection):
        def __init__(self, *arguments, **keywords):
            _FakeConnection.__init__(self, *arguments, **keywords)
            self.response = _FakeResponse(200, {}, b"x" * (8 * 65536), clock=clock, step=2.0)
            sockets.append(self.response.fp.raw._sock)

    net._PinnedHTTPSConnection = Slow
    with pytest.raises(net.TransportError) as error:
        net.fetch_once("https://node.example/")
    assert error.value.code == "AGSC-E907"
    assert "timeout" in error.value.message
    waits = sockets[0].timeouts
    assert waits and all(0 < one <= net.TIMEOUT_SECONDS for one in waits)
    assert waits == sorted(waits, reverse=True), "each wait is bounded by the time left"


def test_a_response_inside_the_deadline_is_read_whole(fake_connection, monkeypatch):
    clock = [0.0]
    monkeypatch.setattr(net.time, "monotonic", lambda: clock[0])

    class Steady(_FakeConnection):
        def __init__(self, *arguments, **keywords):
            _FakeConnection.__init__(self, *arguments, **keywords)
            self.response = _FakeResponse(200, {}, b"y" * (3 * 65536), clock=clock, step=1.0)

    net._PinnedHTTPSConnection = Steady
    _, _, body = net.fetch_once("https://node.example/")
    assert body == b"y" * (3 * 65536)
