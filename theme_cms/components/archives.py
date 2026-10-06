"""The post-listing widgets: PostArchive, TermArchive, TagArchive, Category (S152-06b).

Server twins of fe-user ``PostArchiveWidget.vue``, ``TermArchiveWidget.vue``,
``TagArchive.vue`` and ``PostTermListWidget.vue``. Each fetches through the one
``GET /api/v1/cms/posts`` path (``usePosts``) and renders the shared PostList.
The SPA's pagination buttons become ``?page=N`` links; a failed fetch is an
empty list, as ``usePosts`` swallows errors.
"""
import re
from typing import Any, Callable, Dict, List, Mapping, Optional
from urllib.parse import urlencode

from plugins.theme.theme.theme_api import ThemeApiError

from ..cms_api import CmsApi
from .post_card import archive_display, post_list_view

CmsApiFactory = Callable[[Any], Any]

DEFAULT_POST_TYPE = "post"
DEFAULT_PER_PAGE = 20
FIRST_PAGE = 1
CATEGORY_TERM_TYPE = "category"
TAG_TERM_TYPE = "tag"
ARCHIVE_META_FIELDS = ("published_at",)
TERM_ARCHIVE_SLUG_PATTERN = re.compile(r"^(category|tag)/(.+)$")
RSS_FEED_ROUTE = "/api/v1/cms/rss.xml"
PAGE_QUERY_PARAMETER = "page"


def requested_page(theme_request: Any) -> int:
    """``?page=`` as a page number; anything else is the first page."""
    try:
        page = int(theme_request.query_args.get(PAGE_QUERY_PARAMETER) or FIRST_PAGE)
    except (TypeError, ValueError):
        return FIRST_PAGE
    return max(page, FIRST_PAGE)


def fetch_listing(cms_api: Any, query: Mapping[str, Any]) -> Dict[str, Any]:
    """``usePosts``: the listing, or an empty first page when the fetch fails."""
    try:
        listing = cms_api.posts(query) or {}
    except ThemeApiError:
        listing = {}
    return {
        "items": listing.get("items") or [],
        "page": listing.get("page") or query.get("page") or FIRST_PAGE,
        "pages": listing.get("pages") or FIRST_PAGE,
    }


def pagination(page: int, pages: int) -> Optional[Dict[str, Any]]:
    """The prev / next links of a paginated listing; ``None`` for a single page."""
    if pages <= FIRST_PAGE:
        return None
    return {
        "page": page,
        "pages": pages,
        "previous_href": f"?page={page - 1}" if page > FIRST_PAGE else None,
        "next_href": f"?page={page + 1}" if page < pages else None,
    }


def title_case_slug(slug: str) -> str:
    """``getting-started`` → ``Getting Started`` (first letter of each word)."""
    return " ".join(word[0].upper() + word[1:] for word in slug.split("-") if word)


def build_post_archive_context(
    widget_config: Mapping[str, Any],
    page: Mapping[str, Any],
    route_params: Mapping[str, Any],
    theme_request: Any,
    cms_api_factory: CmsApiFactory = CmsApi,
) -> Dict[str, Any]:
    """PostArchive: every published post of ``type``, newest first, paginated."""
    query = {
        "type": widget_config.get("type") or DEFAULT_POST_TYPE,
        "page": requested_page(theme_request),
        "per_page": widget_config.get("posts_per_page") or DEFAULT_PER_PAGE,
    }
    listing = fetch_listing(cms_api_factory(theme_request), query)
    display = archive_display(widget_config, "category", ARCHIVE_META_FIELDS)
    paginate = widget_config.get("paginate") is not False
    return {
        "post_list": post_list_view(listing["items"], display),
        "pagination": pagination(listing["page"], listing["pages"])
        if paginate
        else None,
    }


def _route_term(route_params: Mapping[str, Any]) -> Optional[re.Match]:
    return TERM_ARCHIVE_SLUG_PATTERN.match(str(route_params.get("slug") or ""))


def _prefix_archive_context(
    page: Mapping[str, Any], display: Mapping[str, Any]
) -> Dict[str, Any]:
    items = page.get("items") or []
    return {
        "mode": "archive",
        "heading": page.get("title") or "",
        "description": "",
        "post_list": post_list_view(items, display),
        "is_empty": not items,
        "pagination": None,
    }


def _resolved_term(
    page: Mapping[str, Any], term_type: str, term_slug: str
) -> Mapping[str, Any]:
    term = page.get("term_archive") or {}
    if term.get("slug") == term_slug and term.get("term_type") == term_type:
        return term
    return {}


def build_term_archive_context(
    widget_config: Mapping[str, Any],
    page: Mapping[str, Any],
    route_params: Mapping[str, Any],
    theme_request: Any,
    cms_api_factory: CmsApiFactory = CmsApi,
) -> Dict[str, Any]:
    """TermArchive: the ``/category/<slug>`` / ``/tag/<slug>`` term, or a prefix archive."""
    display = archive_display(widget_config, "category", ARCHIVE_META_FIELDS)
    match = _route_term(route_params)
    if match is None:
        if page.get("type") == "archive" and page.get("archive_prefix"):
            return _prefix_archive_context(page, display)
        return {"mode": "prompt"}
    term_type = TAG_TERM_TYPE if match.group(1) == TAG_TERM_TYPE else CATEGORY_TERM_TYPE
    term_slug = match.group(2)
    query = {
        "type": widget_config.get("type") or DEFAULT_POST_TYPE,
        "term_type": term_type,
        "term_slug": term_slug,
        "page": requested_page(theme_request),
        "per_page": widget_config.get("posts_per_page") or DEFAULT_PER_PAGE,
    }
    listing = fetch_listing(cms_api_factory(theme_request), query)
    term = _resolved_term(page, term_type, term_slug)
    paginate = widget_config.get("paginate") is not False
    return {
        "mode": term_type,
        "heading": term.get("name") or title_case_slug(term_slug.split("/")[-1]),
        "description": term.get("description") or "",
        "post_list": post_list_view(listing["items"], display),
        "is_empty": not listing["items"],
        "pagination": pagination(listing["page"], listing["pages"])
        if paginate
        else None,
    }


def build_tag_archive_context(
    widget_config: Mapping[str, Any],
    page: Mapping[str, Any],
    route_params: Mapping[str, Any],
    theme_request: Any,
    cms_api_factory: CmsApiFactory = CmsApi,
) -> Dict[str, Any]:
    """TagArchive: the posts of the ``?tag=`` slug (written by tag chips elsewhere)."""
    tag_slug = str(theme_request.query_args.get("tag") or "").strip()
    if not tag_slug:
        return {"tag_slug": ""}
    query = {
        "type": widget_config.get("type") or DEFAULT_POST_TYPE,
        "term_type": widget_config.get("term_type") or TAG_TERM_TYPE,
        "term_slug": tag_slug,
        "page": FIRST_PAGE,
        "per_page": widget_config.get("limit") or DEFAULT_PER_PAGE,
    }
    listing = fetch_listing(cms_api_factory(theme_request), query)
    return {
        "tag_slug": tag_slug,
        "tag_label": title_case_slug(tag_slug),
        "post_list": post_list_view(
            listing["items"], archive_display(widget_config, "excerpt")
        ),
        "is_empty": not listing["items"],
    }


def rss_feed_href(post_type: str, term_type: str, term_slug: str) -> str:
    """``rssFeedHref``: the backend feed of one term (``URLSearchParams`` encoding)."""
    query = {
        "type": post_type or DEFAULT_POST_TYPE,
        "term_type": term_type,
        "term_slug": term_slug,
    }
    return f"{RSS_FEED_ROUTE}?{urlencode(query)}"


def build_term_list_context(
    widget_config: Mapping[str, Any],
    page: Mapping[str, Any],
    route_params: Mapping[str, Any],
    theme_request: Any,
    cms_api_factory: CmsApiFactory = CmsApi,
) -> Dict[str, Any]:
    """Category / PostTermList: the posts of the term pinned in the widget config."""
    post_type = widget_config.get("type")
    term_type = widget_config.get("term_type")
    term_slug = widget_config.get("term_slug")
    items: List[Mapping[str, Any]] = []
    rss_href = None
    if post_type and term_type and term_slug:
        query = {
            "type": post_type,
            "term_type": term_type,
            "term_slug": term_slug,
            "page": FIRST_PAGE,
            "per_page": widget_config.get("limit") or DEFAULT_PER_PAGE,
        }
        items = fetch_listing(cms_api_factory(theme_request), query)["items"]
        rss_href = rss_feed_href(post_type, term_type, term_slug)
    return {
        "rss_href": rss_href,
        "post_list": post_list_view(items, archive_display(widget_config, "titles")),
    }
