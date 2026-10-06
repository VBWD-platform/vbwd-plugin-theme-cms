"""Search (PostSearch.vue), SearchResults (PostSearchResults.vue) and the quick-search
fragment (S152-06b).

The box is a GET form writing ``?q=`` to ``target_path`` (or the current page) —
the URL the SPA's ``router.push`` produces — so the classic flow needs no JS.
``quicksearch`` turns the input into an htmx island over
``GET /_render/_fragment/cms/search``, which calls ``GET /api/v1/cms/search``
exactly as ``usePosts.bySearch`` does. SearchResults renders from ``?q=``.
"""
import json
import math
import re
from typing import Any, Callable, Dict, List, Mapping, Optional

from plugins.theme.theme.theme_api import ThemeApiError

from ..cms_api import CmsApi
from .post_card import archive_display, post_list_view

CmsApiFactory = Callable[[Any], Any]

SEARCH_FRAGMENT_PATH = "/_render/_fragment/cms/search"
DEFAULT_PLACEHOLDER = "Search…"
QUICKSEARCH_DEFAULT_LIMIT = 6
QUICKSEARCH_MAX_LIMIT = 20
QUICKSEARCH_MIN_LIMIT = 1
DEFAULT_PER_PAGE = 20
FIRST_PAGE = 1
LISTBOX_ID_PREFIX = "post-search-listbox-"
SCOPES = ("pages", "posts", "both")
SCOPE_TYPES = {"pages": "page", "posts": "post"}
LEGACY_TYPE_SCOPES = {"page": "pages", "post": "posts"}
_UNSAFE_ID_CHARACTERS = re.compile(r"[^A-Za-z0-9_-]")


def resolve_scope(scope: Any, legacy_type: Any = None) -> str:
    """``utils/searchScope.ts`` ``resolveScope``: explicit scope, legacy type, else both."""
    if scope in SCOPES:
        return str(scope)
    return LEGACY_TYPE_SCOPES.get(legacy_type, "both")


def scope_to_type(scope: Any, legacy_type: Any = None) -> Optional[str]:
    """The ``/cms/search`` ``type`` of a scope; ``both`` filters nothing."""
    return SCOPE_TYPES.get(resolve_scope(scope, legacy_type))


def resolve_search_types(widget_config: Mapping[str, Any]) -> List[str]:
    types = widget_config.get("types")
    if not isinstance(types, list):
        return []
    return [str(post_type).strip() for post_type in types if str(post_type).strip()]


def _clamped_limit(raw_limit: Any) -> int:
    is_number = isinstance(raw_limit, (int, float)) and not isinstance(raw_limit, bool)
    if not is_number or not math.isfinite(raw_limit):
        return QUICKSEARCH_DEFAULT_LIMIT
    return min(max(QUICKSEARCH_MIN_LIMIT, math.floor(raw_limit)), QUICKSEARCH_MAX_LIMIT)


def safe_element_id(value: Any) -> str:
    return _UNSAFE_ID_CHARACTERS.sub("", str(value or ""))


def build_search_box_context(
    widget_config: Mapping[str, Any],
    page: Mapping[str, Any],
    route_params: Mapping[str, Any],
    theme_request: Any,
) -> Dict[str, Any]:
    """The ``Search`` box (also embedded by SuperHeader)."""
    listbox_id = LISTBOX_ID_PREFIX + safe_element_id(widget_config.get("widget_slug"))
    quicksearch = None
    if widget_config.get("quicksearch") is True:
        values = {
            "type": scope_to_type(widget_config.get("scope")),
            "limit": _clamped_limit(
                widget_config.get("quicksearch_limit", QUICKSEARCH_DEFAULT_LIMIT)
            ),
            "listbox": listbox_id,
        }
        quicksearch = {
            "url": SEARCH_FRAGMENT_PATH,
            "values": json.dumps(
                {key: value for key, value in values.items() if value is not None}
            ),
        }
    return {
        "action": widget_config.get("target_path") or theme_request.path,
        "placeholder": widget_config.get("placeholder") or DEFAULT_PLACEHOLDER,
        "query": theme_request.query_args.get("q") or "",
        "listbox_id": listbox_id,
        "quicksearch": quicksearch,
    }


def _fragment_limit(raw_limit: Any) -> int:
    try:
        return _clamped_limit(int(raw_limit))
    except (TypeError, ValueError):
        return QUICKSEARCH_DEFAULT_LIMIT


def _search_items(cms_api: Any, query: Mapping[str, Any]) -> Dict[str, Any]:
    """``usePosts.bySearch``: the matches, or none when the request fails."""
    try:
        result = (
            cms_api.search({key: value for key, value in query.items() if value}) or {}
        )
    except ThemeApiError:
        result = {}
    items = result.get("items") or []
    return {"items": items, "total": result.get("total", len(items))}


def build_quicksearch_fragment_context(
    theme_request: Any, cms_api_factory: CmsApiFactory = CmsApi
) -> Dict[str, Any]:
    """The dropdown for ``?q=&type=&limit=&listbox=`` (closed when nothing matches)."""
    query_text = str(theme_request.query_args.get("q") or "").strip()
    limit = _fragment_limit(theme_request.query_args.get("limit"))
    results: List[Mapping[str, Any]] = []
    if query_text:
        query = {
            "q": query_text,
            "page": FIRST_PAGE,
            "per_page": limit,
            "type": theme_request.query_args.get("type"),
        }
        results = _search_items(cms_api_factory(theme_request), query)["items"][:limit]
    return {
        "listbox_id": safe_element_id(theme_request.query_args.get("listbox")),
        "options": [
            {"title": result.get("title") or "", "href": f"/{result.get('slug') or ''}"}
            for result in results
        ],
    }


def _result_count_label(total: int, query_text: str) -> str:
    noun = "result" if total == 1 else "results"
    return f'Showing {total} {noun} for "{query_text}"'


def build_search_results_context(
    widget_config: Mapping[str, Any],
    page: Mapping[str, Any],
    route_params: Mapping[str, Any],
    theme_request: Any,
    cms_api_factory: CmsApiFactory = CmsApi,
) -> Dict[str, Any]:
    """SearchResults: the matches of ``?q=`` (written by a Search box anywhere)."""
    query_text = str(theme_request.query_args.get("q") or "").strip()
    if not query_text:
        return {"query": ""}
    types = resolve_search_types(widget_config)
    query = {
        "q": query_text,
        "page": FIRST_PAGE,
        "per_page": widget_config.get("per_page") or DEFAULT_PER_PAGE,
        "types": ",".join(types) if types else None,
        "type": None
        if types
        else scope_to_type(widget_config.get("scope"), widget_config.get("type")),
        "term_type": widget_config.get("scope_term_type"),
        "term_slug": widget_config.get("scope_term_slug"),
    }
    result = _search_items(cms_api_factory(theme_request), query)
    return {
        "query": query_text,
        "count_label": _result_count_label(result["total"], query_text),
        "post_list": post_list_view(
            result["items"], archive_display(widget_config, "titles")
        ),
        "is_empty": not result["items"],
    }
