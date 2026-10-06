"""CmsBreadcrumb — the trail of fe-user ``buildCmsBreadcrumbTrail`` (S152-06b).

The blog / post / prefix-archive space gets the cumulative-prefix trail (each
segment links to its prefix, labelled by a matching category term name, else
the title-cased segment) with the post title as the current crumb; any other
titled CMS page gets Home → title. Rendered with the markup of core
``VbwdBreadcrumb`` (the widget maps ``separator`` / ``css`` / ``max_label_length``).
The SPA's client-side label override (``setBreadcrumbLabel``) has no server twin.
"""
import re
from typing import Any, Dict, List, Mapping, Optional

from ..markup import style_text

ROOT_NAME = "Home"
ROOT_PATH = "/"
DEFAULT_SEPARATOR = "/"
DEFAULT_MAX_LABEL_LENGTH = 60
ELLIPSIS = "…"
CATEGORY_TERM_TYPE = "category"
BLOG_SPACE_TYPES = ("post", "archive")
POST_TYPE = "post"
_WORD_START = re.compile(r"\b\w", re.ASCII)


def slug_to_label(slug: str) -> str:
    """``my-cat`` → ``My Cat``, ``2026`` → ``2026``."""
    return _WORD_START.sub(lambda match: match.group(0).upper(), slug.replace("-", " "))


def _is_blog_space(page: Mapping[str, Any]) -> bool:
    return page.get("type") in BLOG_SPACE_TYPES or bool(page.get("archive_prefix"))


def _label_for_segment(segment: str, page: Mapping[str, Any]) -> str:
    for term in page.get("terms") or []:
        is_category = term.get("term_type") in (CATEGORY_TERM_TYPE, None, "")
        slug = str(term.get("slug") or "")
        if is_category and (slug == segment or slug.split("/")[-1] == segment):
            return str(term.get("name"))
    return slug_to_label(segment)


def _blog_space_trail(path: str, page: Mapping[str, Any]) -> List[Dict[str, Any]]:
    segments = [segment for segment in path.lstrip("/").split("/") if segment]
    trail: List[Dict[str, Any]] = [{"label": ROOT_NAME, "to": ROOT_PATH}]
    for index, segment in enumerate(segments):
        if index < len(segments) - 1:
            trail.append(
                {
                    "label": _label_for_segment(segment, page),
                    "to": "/" + "/".join(segments[: index + 1]),
                }
            )
        elif page.get("type") == POST_TYPE:
            label = page.get("title") or page.get("name") or slug_to_label(segment)
            trail.append({"label": label, "current": True})
        else:
            trail.append({"label": _label_for_segment(segment, page), "current": True})
    return trail


def build_cms_breadcrumb_trail(
    path: str, page: Optional[Mapping[str, Any]]
) -> Optional[List[Dict[str, Any]]]:
    """The crumbs for ``path``, or ``None`` when the cms owns no page there."""
    if not page:
        return None
    if _is_blog_space(page):
        return _blog_space_trail(path, page)
    title = page.get("title") or page.get("name")
    if not title:
        return None
    return [{"label": ROOT_NAME, "to": ROOT_PATH}, {"label": title, "current": True}]


def _truncate(label: str, max_length: int) -> str:
    return label[:max_length] + ELLIPSIS if len(label) > max_length else label


def build_breadcrumb_context(
    widget_config: Mapping[str, Any],
    page: Mapping[str, Any],
    route_params: Mapping[str, Any],
    theme_request: Any,
) -> Dict[str, Any]:
    max_length = widget_config.get("max_label_length") or DEFAULT_MAX_LABEL_LENGTH
    trail = build_cms_breadcrumb_trail(theme_request.path, page) or []
    return {
        "separator": widget_config.get("separator") or DEFAULT_SEPARATOR,
        "css": style_text(widget_config.get("css")),
        "crumbs": [
            {
                "label": _truncate(str(crumb["label"]), int(max_length)),
                "href": None if crumb.get("current") else crumb.get("to"),
            }
            for crumb in trail
        ],
    }
