"""The guarded HTTP reader used only when the caller explicitly allows network.

Nothing in this package reaches the network unless the command line says
``--allow-network``; the reading API never fetches at all and takes an injected
callable instead.  When network reading is allowed, the same protections the
Node tool applies (AGSC-11-07/08/09) apply here:

* https only, with plain http allowed to loopback under ``--dev``;
* every address the host resolves to is classified before a socket is opened,
  and the connection is made to that classified address, so the name cannot
  resolve to one address for the check and another for the request;
* at most three redirects, a ten-second timeout and a one-megabyte cap.

The address classification is a pure function and is tested directly; the few
lines that open a socket are the only ones this package cannot exercise without
a network, and they are marked as such.
"""

import http.client
import ipaddress
import socket
import ssl

from .urls import Url, resolve

#: The fetch cap of the Node tool: one mebibyte.
MAX_BYTES = 1048576
#: The federation defaults of AGSC-11-06.
REDIRECT_LIMIT = 3
TIMEOUT_SECONDS = 10

_BLOCKED_V4 = [
    "0.0.0.0/8", "10.0.0.0/8", "100.64.0.0/10", "169.254.0.0/16", "172.16.0.0/12",
    "192.0.0.0/24", "192.0.2.0/24", "192.88.99.0/24", "192.168.0.0/16", "198.18.0.0/15",
    "198.51.100.0/24", "203.0.113.0/24", "224.0.0.0/4", "240.0.0.0/4", "255.255.255.255/32",
]
_BLOCKED_V6 = [
    "::/128", "::/96", "::ffff:0:0/96", "64:ff9b::/96", "64:ff9b:1::/48", "100::/64",
    "100:0:0:1::/64", "2001::/32", "2001:2::/48", "2001:10::/28", "2001:db8::/32",
    "2002::/16", "3fff::/20", "5f00::/16", "fc00::/7", "fe80::/10", "fec0::/10", "ff00::/8",
]

_NETWORKS_V4 = [ipaddress.ip_network(one) for one in _BLOCKED_V4]
_NETWORKS_V6 = [ipaddress.ip_network(one) for one in _BLOCKED_V6]
_LOOPBACK_V4 = ipaddress.ip_network("127.0.0.0/8")


class TransportError(Exception):
    """A transport fault, carrying the registered code that names it."""

    def __init__(self, code, message):
        super().__init__(message)
        self.code = code
        self.message = message


def is_loopback(address):
    """True for 127.0.0.0/8 and ::1."""
    parsed = ipaddress.ip_address(address)
    if parsed.version == 4:
        return parsed in _LOOPBACK_V4
    return parsed == ipaddress.ip_address("::1")


def is_refused(address, dev=False):
    """True when this package must not open a connection to the address.

    Loopback is refused unless ``dev`` is set, which is how the Node tool lets a
    developer check a document served from their own machine.
    """
    parsed = ipaddress.ip_address(address)
    if is_loopback(address):
        return not dev
    networks = _NETWORKS_V4 if parsed.version == 4 else _NETWORKS_V6
    return any(parsed in network for network in networks)


def _classify(host, dev):
    """Resolve a host and return the addresses, refusing the ones AGSC-11-08 bans."""
    try:
        parsed = ipaddress.ip_address(host.strip("[]"))
        candidates = [(parsed.version, str(parsed))]
    except ValueError:
        try:
            infos = socket.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)
        except socket.gaierror as error:  # pragma: no cover - needs a resolver
            raise TransportError("AGSC-E907", "cannot resolve %s: %s" % (host, error))
        candidates = []
        for family, _, _, _, sockaddr in infos:
            version = 6 if family == socket.AF_INET6 else 4
            candidates.append((version, sockaddr[0]))
    if not candidates:  # pragma: no cover - getaddrinfo raises instead
        raise TransportError("AGSC-E907", "no address for %s" % host)
    for _, address in candidates:
        if is_refused(address, dev):
            raise TransportError("AGSC-E905", "address refused: %s" % address)
    return candidates


class _PinnedHTTPSConnection(http.client.HTTPSConnection):
    """An HTTPS connection to one already-classified address, with the real SNI."""

    def __init__(self, host, address, port, timeout, context):
        http.client.HTTPSConnection.__init__(self, host, port=port, timeout=timeout, context=context)
        self._pinned = address

    def connect(self):  # pragma: no cover - opens a real socket
        self.sock = socket.create_connection((self._pinned, self.port), self.timeout)
        self.sock = self._context.wrap_socket(self.sock, server_hostname=self.host)


class _PinnedHTTPConnection(http.client.HTTPConnection):
    """A plain-HTTP connection to one already-classified loopback address."""

    def __init__(self, host, address, port, timeout):
        http.client.HTTPConnection.__init__(self, host, port=port, timeout=timeout)
        self._pinned = address

    def connect(self):  # pragma: no cover - opens a real socket
        self.sock = socket.create_connection((self._pinned, self.port), self.timeout)


def fetch_once(href, dev=False):
    """One request, with no redirect following.  Returns status, headers and bytes."""
    url = Url(href)
    if url.scheme not in ("https", "http"):
        raise TransportError("AGSC-E905", "scheme not allowed: %s:" % url.scheme)
    plain = url.scheme == "http"
    if plain and not dev:
        raise TransportError("AGSC-E905", "http is allowed only to loopback under --dev")
    candidates = _classify(url.host, dev)
    if plain and not all(is_loopback(address) for _, address in candidates):
        raise TransportError("AGSC-E905", "http is allowed only to loopback under --dev")
    address = candidates[0][1]
    port = url.port or (80 if plain else 443)
    if plain:
        connection = _PinnedHTTPConnection(url.host, address, port, TIMEOUT_SECONDS)
    else:
        connection = _PinnedHTTPSConnection(
            url.host, address, port, TIMEOUT_SECONDS, ssl.create_default_context()
        )
    target = url.pathname + (("?" + url.query) if url.query else "")
    try:
        connection.request(
            "GET", target, headers={"Accept": "application/linkset+json, application/json;q=0.5"}
        )
        response = connection.getresponse()
        body = response.read(MAX_BYTES + 1)
        if len(body) > MAX_BYTES:
            raise TransportError("AGSC-E904", "response exceeds 1 MiB")
        headers = {name.lower(): value for name, value in response.getheaders()}
        return response.status, headers, body
    except TransportError:
        raise
    except (OSError, http.client.HTTPException) as error:
        raise TransportError("AGSC-E907", str(error))
    finally:
        connection.close()


def fetch(href, dev=False):
    """Follow up to three redirects and return the final URL, headers and bytes."""
    current = href
    hop = 0
    while True:
        status, headers, body = fetch_once(current, dev)
        if status in (301, 302, 303, 307, 308) and headers.get("location"):
            if hop >= REDIRECT_LIMIT:
                raise TransportError("AGSC-E905", "more than %d redirects" % REDIRECT_LIMIT)
            current = resolve(current, headers["location"])
            hop += 1
            continue
        if status != 200:
            raise TransportError("AGSC-E907", "HTTP %d for %s" % (status, current))
        return current, headers, body
