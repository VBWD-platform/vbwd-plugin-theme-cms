"""TipTap JSON → HTML, a port of fe-user ``CmsPageTypeBase.renderNode`` (S152-06a §4).

The SPA renders a post body from ``content_json`` when ``content_html`` is
empty; this is the same algorithm, node for node and mark for mark, so both
renderers emit the same bytes (parity fixture ``tests/fixtures/tiptap_parity.json``).
The output is trusted HTML: every text and attribute value is escaped here,
exactly as the SPA escapes it.
"""
from typing import Any, Callable, Dict, Mapping

DEFAULT_HEADING_LEVEL = 2
EMPTY_PARAGRAPH_CONTENT = "&nbsp;"


def _escape_html(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _escape_attribute(value: str) -> str:
    return value.replace('"', "&quot;").replace("<", "&lt;")


def _attribute_text(attributes: Mapping[str, Any], name: str) -> str:
    value = attributes.get(name)
    return "" if value is None else str(value)


def _link(text: str, attributes: Mapping[str, Any]) -> str:
    href = _escape_attribute(_attribute_text(attributes, "href"))
    target = attributes.get("target")
    target_attribute = f' target="{_escape_attribute(str(target))}"' if target else ""
    return f'<a href="{href}"{target_attribute}>{text}</a>'


_SIMPLE_MARK_TAGS = {
    "bold": "strong",
    "italic": "em",
    "underline": "u",
    "strike": "s",
    "code": "code",
}


def _render_text(node: Mapping[str, Any]) -> str:
    text = _escape_html(str(node.get("text") or ""))
    for mark in node.get("marks") or []:
        mark_type = mark.get("type")
        if mark_type in _SIMPLE_MARK_TAGS:
            tag = _SIMPLE_MARK_TAGS[mark_type]
            text = f"<{tag}>{text}</{tag}>"
        elif mark_type == "link":
            text = _link(text, mark.get("attrs") or {})
    return text


def _heading(node: Mapping[str, Any], children: str) -> str:
    level = int((node.get("attrs") or {}).get("level") or DEFAULT_HEADING_LEVEL)
    return f"<h{level}>{children}</h{level}>"


def _image(node: Mapping[str, Any], _children: str) -> str:
    attributes = node.get("attrs") or {}
    source = _escape_attribute(_attribute_text(attributes, "src"))
    alternative_text = _escape_attribute(_attribute_text(attributes, "alt"))
    return f'<img src="{source}" alt="{alternative_text}" style="max-width:100%">'


def _wrap(tag: str) -> Callable[[Mapping[str, Any], str], str]:
    return lambda _node, children: f"<{tag}>{children}</{tag}>"


_BLOCK_RENDERERS: Dict[str, Callable[[Mapping[str, Any], str], str]] = {
    "doc": lambda _node, children: children,
    "paragraph": lambda _node, children: f"<p>{children or EMPTY_PARAGRAPH_CONTENT}</p>",
    "heading": _heading,
    "bulletList": _wrap("ul"),
    "orderedList": _wrap("ol"),
    "listItem": _wrap("li"),
    "blockquote": _wrap("blockquote"),
    "codeBlock": lambda _node, children: f"<pre><code>{children}</code></pre>",
    "hardBreak": lambda _node, _children: "<br>",
    "horizontalRule": lambda _node, _children: "<hr>",
    "image": _image,
}


def _render_node(node: Mapping[str, Any]) -> str:
    if node.get("type") == "text":
        return _render_text(node)
    children = "".join(_render_node(child) for child in node.get("content") or [])
    renderer = _BLOCK_RENDERERS.get(str(node.get("type")))
    # Unknown node types render their children (the SPA's ``default`` branch).
    return renderer(node, children) if renderer else children


def render_tiptap_document(document: Any) -> str:
    """The HTML of a TipTap document; anything that is not a JSON object renders nothing."""
    if not isinstance(document, Mapping):
        return ""
    return _render_node(document)
