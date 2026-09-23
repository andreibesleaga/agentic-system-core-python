"""Just enough URL handling to read a discovery document the way a browser does.

The discovery-file rules talk about absolute URLs, about same-origin targets and
about path names, so this module answers exactly those three questions and
nothing else.  It follows the WHATWG URL rules for the schemes that matter here
(``http`` and ``https``): a default port is not part of the origin, the host is
compared lower-cased, and a URL with no scheme is not absolute.

Standard library only.
"""

import re
from urllib.parse import unquote, urlsplit, urljoin

_SCHEME = re.compile(r"^[A-Za-z][A-Za-z0-9+.\-]*:")

#: The schemes whose authority is mandatory and whose default port is dropped.
SPECIAL_PORTS = {"http": 80, "https": 443, "ws": 80, "wss": 443, "ftp": 21}


class Url(object):
    """An absolute URL, with the three members the checkers read."""

    __slots__ = ("href", "scheme", "host", "port", "origin", "pathname", "query", "fragment")

    def __init__(self, href):
        if _SCHEME.match(href) is None:
            raise ValueError("not an absolute URL: %s" % href)
        parts = urlsplit(href)
        self.href = href
        self.scheme = parts.scheme.lower()
        self.host = (parts.hostname or "").lower()
        try:
            self.port = parts.port
        except ValueError:
            raise ValueError("not an absolute URL: %s" % href)
        self.query = parts.query
        self.fragment = parts.fragment
        if self.scheme in SPECIAL_PORTS:
            if not self.host:
                raise ValueError("not an absolute URL: %s" % href)
            port = self.port
            authority = self.host
            if port is not None and port != SPECIAL_PORTS[self.scheme]:
                authority = "%s:%d" % (self.host, port)
            self.origin = "%s://%s" % (self.scheme, authority)
            self.pathname = parts.path or "/"
        else:
            self.origin = "null"
            self.pathname = parts.path

    def __repr__(self):  # pragma: no cover - debugging aid only
        return "Url(%r)" % self.href


def is_url_argument(text):
    """True when a command-line argument names a URL rather than a file.

    The Node tool tells the two apart with the same test — a scheme followed by
    ``//`` — so that a relative path such as ``a:b`` is never mistaken for one.
    """
    return re.match(r"^[a-z][a-z0-9+.\-]*://", text, re.IGNORECASE) is not None


def resolve(base, reference):
    """Resolve a reference against a base URL, as a browser would."""
    return urljoin(base, reference)


def decoded_path(url):
    """The percent-decoded path of a URL, for mapping onto a file on disk."""
    return unquote(url.pathname)
