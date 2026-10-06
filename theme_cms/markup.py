"""Raw text for ``<style>`` / ``<script type="application/ld+json">`` elements.

The SPA sets CSS and JSON-LD as DOM text, which can never end its element. In
server HTML the same text is raw element content, so a ``</style`` or ``</script``
inside it would close the element early; these helpers neutralise exactly that
and return ``Markup`` so autoescape leaves CSS such as ``a > b`` intact.
"""
import json
import re
from typing import Any

from markupsafe import Markup

_STYLE_END_TAG = re.compile(r"</(style)", re.IGNORECASE)


def style_text(css: Any) -> Markup:
    """CSS safe to place inside ``<style>…</style>``."""
    return Markup(_STYLE_END_TAG.sub(r"<\\/\1", str(css or "")))


def json_script_text(value: Any) -> Markup:
    """JSON safe inside ``<script type="application/ld+json">`` (``<`` → ``\\u003c``)."""
    return Markup(json.dumps(value, ensure_ascii=False).replace("<", "\\u003c"))
