"""CustomCode (CustomCodeWidget.vue) — the cms widget trust model's one raw output (S152-06b).

Like fe-user ``buildCustomCodeScripts``, only the ``<script>`` elements of the
admin-pasted ``config.code`` are kept: every attribute, plus the body of an
inline script. Other markup is dropped (visible markup belongs in an HTML
widget). In server HTML the scripts run natively.
"""
from html.parser import HTMLParser
from typing import Any, Dict, List, Mapping, Optional, Tuple

from markupsafe import escape

SCRIPT_TAG = "script"


class _ScriptCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.scripts: List[Tuple[List[Tuple[str, Optional[str]]], str]] = []
        self._open_attributes: Optional[List[Tuple[str, Optional[str]]]] = None
        self._body: List[str] = []

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        if tag == SCRIPT_TAG:
            self._open_attributes = attrs
            self._body = []

    def handle_data(self, data: str) -> None:
        if self._open_attributes is not None:
            self._body.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == SCRIPT_TAG and self._open_attributes is not None:
            self.scripts.append((self._open_attributes, "".join(self._body)))
            self._open_attributes = None


def _attribute(name: str, value: Optional[str]) -> str:
    return f" {name}" if value is None else f' {name}="{escape(value)}"'


def custom_code_scripts(code: Any) -> str:
    """The rebuilt ``<script>`` elements of ``code`` (raw HTML, admin-trusted)."""
    if not code or not str(code).strip():
        return ""
    collector = _ScriptCollector()
    collector.feed(str(code))
    collector.close()
    rebuilt = []
    for attributes, body in collector.scripts:
        is_external = any(name == "src" and value for name, value in attributes)
        rendered_attributes = "".join(
            _attribute(name, value) for name, value in attributes
        )
        rebuilt.append(
            f"<script{rendered_attributes}>{'' if is_external else body}</script>"
        )
    return "".join(rebuilt)


def build_custom_code_context(
    widget_config: Mapping[str, Any],
    page: Mapping[str, Any],
    route_params: Mapping[str, Any],
    theme_request: Any,
) -> Dict[str, Any]:
    return {"scripts": custom_code_scripts(widget_config.get("code"))}
