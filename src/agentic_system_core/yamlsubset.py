"""The closed YAML subset of AGSC-02-02, read with the failsafe schema of AGSC-02-03.

Admitted: block mappings, block sequences, flow sequences of scalars, plain,
single-quoted and double-quoted scalars, ``|`` and ``>`` block scalars, and
comments.  Every scalar is a string (failsafe): ``no``, ``on``, ``~``, ``1e3``
and ``0x1F`` stay text.  Rejected, each under its own code (AGSC-02-02):

* an anchor or an alias — ``AGSC-E103``;
* a tag or a merge key — ``AGSC-E104``;
* a flow mapping or a complex key — ``AGSC-E105``;
* a duplicate key — ``AGSC-E106``;
* a document marker inside the block (``---`` / ``...``) — ``AGSC-E107``.

Every error carries the 1-based line of the file it was found on.  Each mapping
records the line of each of its keys in ``lines`` so a later check can point at
the key it faults.  Standard library only; no general YAML library is involved,
so nothing outside the subset can be accepted by accident.
"""

import re


class YamlError(ValueError):
    def __init__(self, code, message, line):
        ValueError.__init__(self, "%s (line %d)" % (message, line))
        self.code = code
        self.message = message
        self.line = line


class Mapping(dict):
    """A dict that also remembers the line of every key."""

    def __init__(self):
        dict.__init__(self)
        self.lines = {}


_KEY = re.compile(r"^([^\s'\"#][^:#]*?|'[^']*'|\"(?:[^\"\\]|\\.)*\")[ \t]*:(?:[ \t]+|$)(.*)$")
_ESCAPES = {"0": "\0", "a": "\a", "b": "\b", "t": "\t", "\t": "\t", "n": "\n", "v": "\v",
            "f": "\f", "r": "\r", "e": "\x1b", " ": " ", '"': '"', "/": "/", "\\": "\\",
            "N": "\x85", "_": "\xa0", "L": " ", "P": " "}


def _indent(text):
    return len(text) - len(text.lstrip(" "))


def _strip_comment(text):
    """Remove a trailing `` #`` comment outside quotes."""
    quote = None
    index = 0
    while index < len(text):
        char = text[index]
        if quote:
            if quote == '"' and char == "\\":
                index += 2
                continue
            if char == quote:
                if quote == "'" and text[index + 1:index + 2] == "'":
                    index += 2
                    continue
                quote = None
        elif char in "'\"" and (index == 0 or text[index - 1] in " \t[,"):
            quote = char
        elif char == "#" and (index == 0 or text[index - 1] in " \t"):
            return text[:index].rstrip()
        index += 1
    return text.rstrip()


def _double(text, line):
    out = []
    index = 0
    while index < len(text):
        char = text[index]
        if char == "\\":
            code = text[index + 1:index + 2]
            if code in _ESCAPES:
                out.append(_ESCAPES[code])
                index += 2
                continue
            width = {"x": 2, "u": 4, "U": 8}.get(code)
            digits = text[index + 2:index + 2 + width] if width else ""
            if width and len(digits) == width and all(c in "0123456789abcdefABCDEF"
                                                      for c in digits):
                out.append(chr(int(digits, 16)))
                index += 2 + width
                continue
            raise YamlError("AGSC-E201", "invalid escape in a double-quoted scalar", line)
        out.append(char)
        index += 1
    return "".join(out)


def _check_scalar_start(text, line):
    if text.startswith("&") or text.startswith("*"):
        raise YamlError("AGSC-E103", "YAML anchor or alias", line)
    if text.startswith("!"):
        raise YamlError("AGSC-E104", "YAML tag", line)
    if text.startswith("{"):
        raise YamlError("AGSC-E105", "flow mapping", line)


def scalar(text, line):
    """One inline scalar in failsafe form."""
    text = text.strip()
    _check_scalar_start(text, line)
    if text.startswith('"'):
        if len(text) < 2 or not text.endswith('"') or _unescaped_quote_inside(text):
            raise YamlError("AGSC-E201", "unterminated double-quoted scalar", line)
        return _double(text[1:-1], line)
    if text.startswith("'"):
        if len(text) < 2 or not text.endswith("'"):
            raise YamlError("AGSC-E201", "unterminated single-quoted scalar", line)
        return text[1:-1].replace("''", "'")
    return text


def _unescaped_quote_inside(text):
    index = 1
    while index < len(text) - 1:
        if text[index] == "\\":
            index += 2
            continue
        if text[index] == '"':
            return True
        index += 1
    return False


def flow_sequence(text, line):
    """``[a, "b", 'c']`` — a flow sequence of scalars only."""
    inner = text.strip()[1:-1]
    items, current, quote, index = [], [], None, 0
    while index < len(inner):
        char = inner[index]
        if quote:
            current.append(char)
            if quote == '"' and char == "\\":
                current.append(inner[index + 1:index + 2])
                index += 2
                continue
            if char == quote:
                quote = None
        elif char in "'\"":
            quote = char
            current.append(char)
        elif char in "[{":
            raise YamlError("AGSC-E105", "nested flow collection", line)
        elif char == ",":
            items.append("".join(current))
            current = []
        else:
            current.append(char)
        index += 1
    if quote:
        raise YamlError("AGSC-E201", "unterminated quoted scalar in a flow sequence", line)
    tail = "".join(current)
    if tail.strip() or items:
        items.append(tail)
    out = []
    for item in items:
        if item.strip() == "":
            if item is items[-1] and len(items) > 1:
                continue
            raise YamlError("AGSC-E201", "empty entry in a flow sequence", line)
        if ":" in item and item.strip()[:1] not in "'\"" and re.search(r":(\s|$)", item):
            raise YamlError("AGSC-E105", "flow mapping entry in a flow sequence", line)
        out.append(scalar(item, line))
    return out


class _Reader(object):
    def __init__(self, lines, first_line):
        # (file line number, text) for every line that is not blank or a comment,
        # but keep blank lines for block scalars.
        self.lines = lines
        self.first = first_line
        self.index = 0

    def number(self, index):
        return self.first + index

    def skip_blank(self):
        while self.index < len(self.lines):
            text = self.lines[self.index]
            if text.strip() == "" or text.lstrip().startswith("#"):
                self.index += 1
                continue
            break

    def peek(self):
        self.skip_blank()
        if self.index >= len(self.lines):
            return None
        return self.lines[self.index]

    def node(self, indent):
        """The block node starting at the current line, at ``indent`` or deeper."""
        text = self.peek()
        if text is None or _indent(text) < indent:
            return ""
        line = self.number(self.index)
        body = text.strip()
        if body.startswith("- ") or body == "-":
            return self.sequence(_indent(text))
        if body.startswith("? ") or body == "?":
            raise YamlError("AGSC-E105", "complex key", line)
        return self.mapping(_indent(text))

    def mapping(self, indent):
        out = Mapping()
        while True:
            text = self.peek()
            if text is None or _indent(text) < indent:
                return out
            line = self.number(self.index)
            if _indent(text) > indent:
                raise YamlError("AGSC-E201", "unexpected indentation", line)
            body = text.strip()
            if body.startswith("? ") or body == "?":
                raise YamlError("AGSC-E105", "complex key", line)
            if body.startswith("- "):
                return out
            if body.startswith("{"):
                raise YamlError("AGSC-E105", "flow mapping", line)
            if body.startswith("&") or body.startswith("*"):
                raise YamlError("AGSC-E103", "YAML anchor or alias", line)
            if body.startswith("!"):
                raise YamlError("AGSC-E104", "YAML tag", line)
            match = _KEY.match(body)
            if match is None:
                raise YamlError("AGSC-E201", "not a mapping entry", line)
            key = scalar(match.group(1), line) if match.group(1)[:1] in "'\"" \
                else match.group(1).strip()
            if key == "<<":
                raise YamlError("AGSC-E104", "merge key", line)
            if key in out:
                raise YamlError("AGSC-E106", "duplicate key %s" % key, line)
            rest = _strip_comment(match.group(2))
            self.index += 1
            out.lines[key] = line
            out[key] = self.value(rest, indent, line, in_sequence=False)

    def sequence(self, indent):
        out = []
        while True:
            text = self.peek()
            if text is None or _indent(text) != indent:
                if text is not None and _indent(text) > indent:
                    raise YamlError("AGSC-E201", "unexpected indentation",
                                    self.number(self.index))
                return out
            body = text.strip()
            if not (body.startswith("- ") or body == "-"):
                return out
            line = self.number(self.index)
            rest = body[1:].lstrip(" ")
            child_indent = indent + (len(body) - len(rest))
            if _KEY.match(rest) and rest[:1] not in "'\"[":
                # a mapping that starts on the dash line
                self.lines[self.index] = " " * child_indent + rest
                out.append(self.mapping(child_indent))
                continue
            self.index += 1
            out.append(self.value(_strip_comment(rest), indent, line, in_sequence=True))

    def value(self, rest, indent, line, in_sequence):
        if rest == "":
            nxt = self.peek()
            if nxt is not None and (_indent(nxt) > indent or (
                    not in_sequence and _indent(nxt) == indent and nxt.strip().startswith("- "))):
                return self.node(_indent(nxt))
            return ""
        _check_scalar_start(rest, line)
        if rest[0] in "|>":
            return self.block_scalar(rest, indent, line)
        if rest.startswith("["):
            if not rest.endswith("]"):
                raise YamlError("AGSC-E201", "unterminated flow sequence", line)
            return flow_sequence(rest, line)
        if rest[0] in "'\"":
            return scalar(rest, line)
        # a plain scalar may continue on more-indented lines (folded with one space)
        parts = [rest]
        while self.index < len(self.lines):
            text = self.lines[self.index]
            if text.strip() == "" or _indent(text) <= indent or text.lstrip().startswith("#"):
                break
            piece = _strip_comment(text.strip())
            if re.search(r":(\s|$)", piece):
                raise YamlError("AGSC-E201", "a mapping value inside a plain scalar",
                                self.number(self.index))
            parts.append(piece)
            self.index += 1
        return " ".join(parts)

    def block_scalar(self, header, indent, line):
        style = header[0]
        chomp = "clip"
        explicit = None
        for char in header[1:].strip():
            if char == "-":
                chomp = "strip"
            elif char == "+":
                chomp = "keep"
            elif char.isdigit():
                explicit = int(char)
            else:
                raise YamlError("AGSC-E201", "bad block-scalar header", line)
        collected = []
        block_indent = indent + explicit if explicit else None
        while self.index < len(self.lines):
            text = self.lines[self.index]
            if text.strip() == "":
                collected.append("")
                self.index += 1
                continue
            if block_indent is None:
                if _indent(text) <= indent:
                    break
                block_indent = _indent(text)
            if _indent(text) < block_indent:
                break
            collected.append(text[block_indent:])
            self.index += 1
        trailing = 0
        while collected and collected[-1] == "":
            collected.pop()
            trailing += 1
        if style == "|":
            content = "\n".join(collected)
        else:
            content = _fold(collected)
        if not collected:
            return "" if chomp != "keep" else "\n" * trailing
        if chomp == "strip":
            return content
        if chomp == "keep":
            return content + "\n" * (trailing + 1)
        return content + "\n"


def _fold(lines):
    """YAML 1.2 line folding for a ``>`` block: a single break between two
    normal lines becomes a space, each empty line is one LF, and a break next to
    a more-indented line is kept."""
    content = ""
    previous = None
    pending = 0
    for part in lines:
        if part == "":
            pending += 1
            continue
        if previous is None:
            content = "\n" * pending + part
        elif previous.startswith(" ") or part.startswith(" "):
            content += "\n" + "\n" * pending + part
        elif pending:
            content += "\n" * pending + part
        else:
            content += " " + part
        previous = part
        pending = 0
    return content


def load(text, first_line=2):
    """Parse the text between the two ``---`` lines.  ``first_line`` is its file line."""
    lines = text.split("\n")
    for index, raw in enumerate(lines):
        if raw.rstrip() in ("---", "...") or raw.startswith("--- ") or raw.startswith("%"):
            raise YamlError("AGSC-E107", "a document marker or directive inside the block",
                            first_line + index)
        if raw.startswith("\t"):
            raise YamlError("AGSC-E201", "tab indentation", first_line + index)
    reader = _Reader(lines, first_line)
    if reader.peek() is None:
        return Mapping()
    first = reader.peek()
    if first.strip().startswith("- "):
        raise YamlError("AGSC-E201", "frontmatter is a mapping, not a sequence",
                        reader.number(reader.index))
    result = reader.mapping(_indent(first))
    rest = reader.peek()
    if rest is not None:
        raise YamlError("AGSC-E201", "unexpected content", reader.number(reader.index))
    return result


def split_frontmatter(markdown):
    """(yaml text, body, error) — AGSC-02-01's block, or an error code and line."""
    lines = markdown.split("\n")
    if not lines or lines[0].rstrip("\r") != "---":
        return None, markdown, YamlError("AGSC-E101", "frontmatter missing", 1)
    for index in range(1, len(lines)):
        if lines[index].rstrip("\r") == "---":
            return ("\n".join(lines[1:index]), "\n".join(lines[index + 1:]), None)
    return None, markdown, YamlError("AGSC-E102", "frontmatter not terminated", 1)


def has_closed_block(markdown):
    return split_frontmatter(markdown)[2] is None


# --- the emitted profile (AGSC-04-19) -------------------------------------------

_RESOLVES = re.compile(
    r"^(?:~|null|Null|NULL|true|True|TRUE|false|False|FALSE|yes|Yes|YES|no|No|NO|on|On|ON|"
    r"off|Off|OFF|y|Y|n|N|[-+]?(?:\d[\d_]*)?\.?\d+(?:[eE][-+]?\d+)?|0x[0-9A-Fa-f_]+|0o?[0-7_]+|"
    r"[-+]?\.(?:inf|Inf|INF)|\.(?:nan|NaN|NAN)|\d{4}-\d\d?-\d\d?(?:[Tt ].*)?)$")
_INDICATORS = "-?:,[]{}#&*!|>'\"%@`"


def needs_quotes(value):
    return (value == "" or _RESOLVES.match(value) is not None or value[0] in _INDICATORS
            or value != value.strip() or ": " in value or " #" in value or value.endswith(":")
            or any(ord(c) < 0x20 for c in value))


def emit_scalar(value):
    if needs_quotes(value):
        return '"%s"' % value.replace("\\", "\\\\").replace('"', '\\"')
    return value


def dump(mapping, indent=0):
    """Block style, two-space indent, sequence items two spaces under their key."""
    out = []
    pad = " " * indent
    for key, value in mapping.items():
        if isinstance(value, dict):
            out.append("%s%s:" % (pad, key))
            out.append(dump(value, indent + 2).rstrip("\n"))
        elif isinstance(value, list):
            out.append("%s%s:" % (pad, key))
            for item in value:
                if isinstance(item, dict):
                    inner = dump(item, indent + 4).rstrip("\n").split("\n")
                    first = inner[0][indent + 4:]
                    out.append("%s  - %s" % (pad, first))
                    out.extend(inner[1:])
                else:
                    out.append("%s  - %s" % (pad, emit_scalar(str(item))))
        else:
            out.append("%s%s: %s" % (pad, key, emit_scalar(str(value))))
    return "\n".join(out) + "\n"
