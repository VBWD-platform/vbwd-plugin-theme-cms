"""Canonical DOM form for the component DOM-contract tests (S152-06b).

The expected fixtures are written from the Vue templates; the themed output
must have the same elements, attributes, classes and text. Whitespace between
tags, attribute order and class order carry no meaning in the DOM, so they are
normalised; everything else must match exactly.
"""
from html.parser import HTMLParser
from typing import List, Optional, Tuple

_WHITESPACE_PRESERVING = {"script", "style", "textarea", "pre"}


class _CanonicalHtml(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.lines: List[str] = []
        self._raw_depth = 0

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        self.lines.append(f"<{tag}{_attributes(attrs)}>")
        if tag in _WHITESPACE_PRESERVING:
            self._raw_depth += 1

    def handle_startendtag(self, tag, attrs) -> None:
        self.lines.append(f"<{tag}{_attributes(attrs)}>")

    def handle_endtag(self, tag: str) -> None:
        if tag in _WHITESPACE_PRESERVING:
            self._raw_depth -= 1
        self.lines.append(f"</{tag}>")

    def handle_data(self, data: str) -> None:
        text = data if self._raw_depth else " ".join(data.split())
        if text.strip():
            self.lines.append(text)


def _attributes(attrs: List[Tuple[str, Optional[str]]]) -> str:
    rendered = []
    for name, value in sorted(attrs):
        if name == "class" and value is not None:
            value = " ".join(sorted(value.split()))
        rendered.append(name if value is None else f'{name}="{value}"')
    return "".join(f" {attribute}" for attribute in rendered)


def canonical(html: str) -> str:
    """One element / text node per line, attributes and classes sorted."""
    parser = _CanonicalHtml()
    parser.feed(str(html))
    parser.close()
    return "\n".join(parser.lines)


def testids(html: str) -> List[str]:
    """Every ``data-testid`` value in document order."""
    found: List[str] = []

    class _Collector(HTMLParser):
        def handle_starttag(self, tag, attrs):
            found.extend(value for name, value in attrs if name == "data-testid")

    _Collector().feed(str(html))
    return found
