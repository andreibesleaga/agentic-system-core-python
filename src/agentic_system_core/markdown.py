"""A small CommonMark 0.31.2 scanner: headings and inline links, nothing else.

AGSC-02-20 fixes the body syntax as CommonMark 0.31.2, and two rules read a
body: AGSC-03-13 (heading anchors) and AGSC-03-11 (inline links resolve).  This
module finds exactly those two things and renders nothing.  The subset it
recognises is written down here so a reader can see where it stops:

Blocks
  * fenced code blocks (````` ``` ````` or ``~~~``, at most three spaces of
    indent, closed by a fence of the same character at least as long, with no
    info string) — their content is never a heading and never a link;
  * indented code blocks (four or more spaces, not continuing a paragraph);
  * ATX headings (``#`` to ``######``, at most three spaces of indent, followed
    by a space, a tab or the end of the line; an optional closing sequence of
    ``#`` preceded by a space is removed);
  * setext headings (a paragraph followed by a line of ``=`` or ``-``);
  * blank lines end a paragraph; every other line is paragraph text.

Inlines, within paragraph and heading text
  * backslash escapes of ASCII punctuation;
  * code spans (a backtick run closed by a run of the same length) — no link
    inside one;
  * inline links and images ``[text](destination "title")`` with the
    destination either ``<...>`` or a run without spaces whose parentheses
    balance, and escapes inside it removed.

Not recognised, by design: reference-style links, autolinks, raw HTML, block
quotes and list containers as containers (their lines are read as paragraph
text, which finds the same links and loses only headings nested inside a
container).  A link inside a container is still found.
"""

import re

_ATX = re.compile(r"^ {0,3}(#{1,6})(?:[ \t]+(.*?))?[ \t]*$")
_ATX_CLOSE = re.compile(r"(?:^|[ \t]+)#+[ \t]*$")
_FENCE = re.compile(r"^( {0,3})(`{3,}|~{3,})(.*)$")
_SETEXT = re.compile(r"^ {0,3}(=+|-+)[ \t]*$")
_THEMATIC = re.compile(r"^ {0,3}((?:\*[ \t]*){3,}|(?:-[ \t]*){3,}|(?:_[ \t]*){3,})$")
_PUNCT = set("!\"#$%&'()*+,-./:;<=>?@[\\]^_`{|}~")


class Heading(object):
    __slots__ = ("level", "text", "line")

    def __init__(self, level, text, line):
        self.level = level
        self.text = text
        self.line = line


class Link(object):
    __slots__ = ("text", "destination", "image", "line")

    def __init__(self, text, destination, image, line):
        self.text = text
        self.destination = destination
        self.image = image
        self.line = line


def _blocks(text):
    """Yield ('heading', Heading) and ('para', (first_line, text)) in document order."""
    lines = text.split("\n")
    fence = None
    paragraph = []
    start = 0
    out = []

    def flush():
        if paragraph:
            out.append(("para", (start, "\n".join(paragraph))))
            del paragraph[:]

    for number, line in enumerate(lines, 1):
        if fence is not None:
            match = _FENCE.match(line)
            if match and match.group(2)[0] == fence[0] and len(match.group(2)) >= len(fence) \
                    and match.group(3).strip() == "":
                fence = None
            continue
        match = _FENCE.match(line)
        if match and not (match.group(2)[0] == "`" and "`" in match.group(3)):
            flush()
            fence = match.group(2)
            continue
        if line.strip() == "":
            flush()
            continue
        if not paragraph and len(line) - len(line.lstrip(" ")) >= 4:
            continue  # indented code block
        if paragraph:
            setext = _SETEXT.match(line)
            if setext:
                level = 1 if setext.group(1)[0] == "=" else 2
                content = "\n".join(one.strip() for one in paragraph)
                out.append(("heading", Heading(level, content, start)))
                del paragraph[:]
                continue
        atx = _ATX.match(line)
        if atx:
            flush()
            content = atx.group(2) or ""
            content = _ATX_CLOSE.sub("", content)
            out.append(("heading", Heading(len(atx.group(1)), content.strip(), number)))
            continue
        if _THEMATIC.match(line):
            flush()
            continue
        if not paragraph:
            start = number
        paragraph.append(line)
    flush()
    return out


def headings(text):
    """Every heading of a body, in document order."""
    return [value for kind, value in _blocks(text) if kind == "heading"]


def _link_close(text, index):
    """Given text[index] == '[', return the index of the matching ']' or -1."""
    depth = 0
    position = index
    while position < len(text):
        char = text[position]
        if char == "\\" and position + 1 < len(text):
            position += 2
            continue
        if char == "`":
            end = _code_span_end(text, position)
            if end > 0:
                position = end
                continue
        if char == "[":
            depth += 1
        elif char == "]":
            depth -= 1
            if depth == 0:
                return position
        position += 1
    return -1


def _code_span_end(text, index):
    """If a code span opens at index, the index just past it, else 0."""
    run = 0
    while index + run < len(text) and text[index + run] == "`":
        run += 1
    position = index + run
    while position < len(text):
        if text[position] == "`":
            other = 0
            while position + other < len(text) and text[position + other] == "`":
                other += 1
            if other == run:
                return position + other
            position += other
        else:
            position += 1
    return 0


def _unescape(text):
    out = []
    index = 0
    while index < len(text):
        if text[index] == "\\" and index + 1 < len(text) and text[index + 1] in _PUNCT:
            out.append(text[index + 1])
            index += 2
        else:
            out.append(text[index])
            index += 1
    return "".join(out)


def _destination(text, index):
    """Parse '(' destination [title] ')' at text[index] == '('.  Returns (dest, end) or None."""
    position = index + 1
    while position < len(text) and text[position] in " \t\n":
        position += 1
    if position < len(text) and text[position] == "<":
        end = position + 1
        while end < len(text) and text[end] not in ">\n":
            end += 2 if text[end] == "\\" else 1
        if end >= len(text) or text[end] != ">":
            return None
        raw = text[position + 1:end]
        position = end + 1
    else:
        depth = 0
        end = position
        while end < len(text):
            char = text[end]
            if char == "\\" and end + 1 < len(text):
                end += 2
                continue
            if char in " \t\n" or ord(char) < 0x20:
                break
            if char == "(":
                depth += 1
            elif char == ")":
                if depth == 0:
                    break
                depth -= 1
            end += 1
        raw = text[position:end]
        position = end
    while position < len(text) and text[position] in " \t\n":
        position += 1
    if position < len(text) and text[position] in "\"'(":
        closer = ")" if text[position] == "(" else text[position]
        end = position + 1
        while end < len(text) and text[end] != closer:
            end += 2 if text[end] == "\\" else 1
        if end >= len(text):
            return None
        position = end + 1
        while position < len(text) and text[position] in " \t\n":
            position += 1
    if position >= len(text) or text[position] != ")":
        return None
    return _unescape(raw), position + 1


def inline_links(text, first_line=1):
    """Every inline link and image of one run of inline text, in order."""
    out = []
    index = 0
    while index < len(text):
        char = text[index]
        if char == "\\":
            index += 2
            continue
        if char == "`":
            end = _code_span_end(text, index)
            if end:
                index = end
                continue
            while index < len(text) and text[index] == "`":
                index += 1
            continue
        if char == "[":
            image = index > 0 and text[index - 1] == "!" and \
                (index < 2 or text[index - 2] != "\\")
            close = _link_close(text, index)
            if close > 0 and close + 1 < len(text) and text[close + 1] == "(":
                parsed = _destination(text, close + 1)
                if parsed is not None:
                    destination, end = parsed
                    label = text[index + 1:close]
                    line = first_line + text.count("\n", 0, index)
                    out.append(Link(label, destination, image, line))
                    # a link inside the label of an image is still a link
                    if image:
                        out.extend(inline_links(label, line))
                    index = end
                    continue
        index += 1
    return out


def links(text):
    """Every inline link and image of a body, outside code, in document order."""
    out = []
    for kind, value in _blocks(text):
        if kind == "heading":
            out.extend(inline_links(value.text, value.line))
        else:
            out.extend(inline_links(value[1], value[0]))
    return out


def plain_heading_text(text):
    """Heading content with inline links reduced to their text and escapes removed."""
    pieces = []
    index = 0
    for link in inline_links(text):
        marker = ("![" if link.image else "[") + link.text + "]("
        found = text.find(marker, index)
        if found < 0:  # pragma: no cover - the link was found in this same text
            continue
        close = _destination(text, found + len(marker) - 1)
        pieces.append(text[index:found])
        pieces.append(link.text)
        index = close[1] if close else found + len(marker)
    pieces.append(text[index:])
    return _unescape("".join(pieces))
