"""Slug → renderable CMS page, the mirror of fe-user ``useCmsStore._resolvePageOrTerm`` (§1–2).

Strict order: page → post → (``category/…``/``tag/…``) term archive → prefix
archive → the original 404. A preview never falls through, and any non-404
(``403`` for a wrong preview token) propagates. Layout and style lookups that
fail degrade to "no layout" / "no style", exactly like the SPA.
"""
import re
from dataclasses import dataclass
from typing import Any, Dict, Optional

from plugins.theme.theme.theme_api import NOT_FOUND, ThemeApiError

from .cms_api import CmsApi

TERMS_ARCHIVE_LAYOUT_SLUG = "terms-archive"
TERM_ARCHIVE_SLUG_PATTERN = re.compile(r"^(category|tag)/(.+)$")
POST_TYPE = "post"
SYNTHETIC_ROBOTS = "index,follow"
TERM_ARCHIVE_PAGE_TYPE = "term_archive"
DEFAULT_PAGE_TYPE = "page"


@dataclass(frozen=True)
class ResolvedCmsPage:
    """A page (real or synthetic) with its layout and resolved style CSS."""

    page: Dict[str, Any]
    layout: Optional[Dict[str, Any]]
    style_css: Optional[str]


def page_type_of(page: Dict[str, Any]) -> str:
    """The page-type template key: synthetic term archives have their own."""
    if page.get("term_archive"):
        return TERM_ARCHIVE_PAGE_TYPE
    return page.get("type") or DEFAULT_PAGE_TYPE


def _synthetic_page(
    page_id: str, slug: str, title: str, layout: Optional[Dict[str, Any]]
) -> Dict[str, Any]:
    """The fields every synthetic page carries (same defaults as the SPA)."""
    return {
        "id": page_id,
        "slug": slug,
        "type": DEFAULT_PAGE_TYPE,
        "title": title,
        "name": title,
        "content_html": "",
        "content_json": {},
        "resolved_layout_id": layout.get("id") if layout else None,
        "meta_title": title,
        "meta_description": None,
        "og_title": None,
        "og_description": None,
        "og_image_url": None,
        "canonical_url": None,
        "robots": SYNTHETIC_ROBOTS,
        "schema_json": None,
    }


class CmsPageResolver:
    """Resolves a public CMS path through the cms public API (one ``CmsApi`` per request)."""

    def __init__(self, cms_api: CmsApi) -> None:
        self._cms_api = cms_api

    def resolve(
        self, slug: str, preview_token: Optional[str] = None
    ) -> ResolvedCmsPage:
        try:
            post = self._fetch_post(slug, preview_token)
        except ThemeApiError as lookup_error:
            if lookup_error.status != NOT_FOUND or preview_token:
                raise
            archive = self._term_archive(slug) or self._prefix_archive(slug)
            if archive is None:
                raise
            return archive
        return ResolvedCmsPage(
            post, self._post_layout(post), self._post_style_css(post)
        )

    def _fetch_post(self, slug: str, preview_token: Optional[str]) -> Dict[str, Any]:
        try:
            return self._cms_api.post(slug, preview_token=preview_token)
        except ThemeApiError as lookup_error:
            if lookup_error.status != NOT_FOUND:
                raise
            return self._cms_api.post(
                slug, preview_token=preview_token, post_type=POST_TYPE
            )

    def _post_layout(self, post: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        layout_id = post.get("resolved_layout_id") or post.get("layout_id")
        if not layout_id:
            return None
        try:
            return self._cms_api.layout(layout_id)
        except ThemeApiError:
            return None

    def _post_style_css(self, post: Dict[str, Any]) -> Optional[str]:
        style_id = post.get("resolved_style_id") or post.get("style_id")
        if not style_id:
            return None
        try:
            return self._cms_api.style_css(style_id)
        except ThemeApiError:
            return None

    def _archive_assets(self) -> tuple:
        try:
            layout = self._cms_api.layout_by_slug(TERMS_ARCHIVE_LAYOUT_SLUG)
        except ThemeApiError:
            layout = None
        try:
            style_css = self._cms_api.default_style_css()
        except ThemeApiError:
            style_css = None
        return layout, style_css

    def _term_archive(self, slug: str) -> Optional[ResolvedCmsPage]:
        match = TERM_ARCHIVE_SLUG_PATTERN.match(slug)
        if match is None:
            return None
        try:
            term = self._cms_api.term(match.group(1), match.group(2))
        except ThemeApiError:
            return None
        layout, style_css = self._archive_assets()
        page = _synthetic_page(
            f"term-archive:{term['term_type']}:{term['slug']}",
            slug,
            term["name"],
            layout,
        )
        page["meta_description"] = term.get("description")
        page["term_archive"] = {
            "term_type": term["term_type"],
            "slug": term["slug"],
            "name": term["name"],
            "description": term.get("description"),
        }
        return ResolvedCmsPage(page, layout, style_css)

    def _prefix_archive(self, path: str) -> Optional[ResolvedCmsPage]:
        try:
            archive = self._cms_api.archive(path)
        except ThemeApiError:
            return None
        layout, style_css = self._archive_assets()
        page = _synthetic_page(f"prefix-archive:{path}", path, archive["title"], layout)
        page.update(
            type="archive",
            archive_prefix=path,
            items=archive.get("items") or [],
            archive_total=archive.get("total"),
            archive_page=archive.get("page"),
            archive_per_page=archive.get("per_page"),
            archive_pages=archive.get("pages"),
        )
        return ResolvedCmsPage(page, layout, style_css)
