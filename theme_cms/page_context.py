"""The template context of one resolved CMS page (S152-06a §3–5, §8, D13).

The mirror of what ``CmsPageTypeBase`` / ``CmsPageTypePost`` / ``CmsLayoutRenderer``
compute in the SPA: the body (``content_html`` or TipTap), the page-type template,
the layout's area views, the one page style, the SEO head fields
(``injectSeoMeta``), the post hero and the language alternates (W3). An adapter
route rendered inside a template page may replace that page's SEO head with its
own :class:`SeoOverrides` (applied here, in one place).
"""
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional
from urllib.parse import quote

from markupsafe import Markup

from .layout_areas import widgets_for_area
from .markup import json_script_text, style_text
from .page_resolver import ResolvedCmsPage, page_type_of
from .registries import ComponentTemplateRegistry, PageTypeTemplateRegistry
from .tags_custom_fields import tags_and_custom_fields
from .tiptap import render_tiptap_document
from .widget_views import WidgetViewBuilder

CONTENT_AREA_TYPE = "content"
TAG_TERM_TYPE = "tag"
# ``encodeURIComponent`` leaves exactly these unescaped.
URI_COMPONENT_SAFE_CHARACTERS = "-_.!~*'()"
# ``CmsPageTypePost.escAttr`` strips these before a URL goes into ``url("…")``.
CSS_URL_BREAKOUT_CHARACTERS = "\"'()\\"
PAGE_LANGUAGE_CONTEXT_KEY = "page_language"
TITLE_SEPARATOR = " — "
SITE_ROOT_PATH_PREFIX = "/"
PROTOCOL_RELATIVE_PREFIX = "//"


@dataclass(frozen=True)
class CmsSiteSettings:
    """Site-wide cms values a page needs: canonical base, home slug, global head HTML.

    ``site_name`` (core's white-label name) suffixes an overridden title only.
    """

    public_base_url: str
    home_slug: str
    global_head_html: str
    site_name: str = ""


@dataclass(frozen=True)
class SeoOverrides:
    """An adapter route's own SEO head over the template CMS page it renders in.

    fe-user mounts e.g. ``/shop/product/:slug`` as ``CmsPage`` with a fixed slug, so
    without overrides every such URL carries the template page's head. ``None``
    keeps the template's value. ``title`` is the subject (suffixed with the site
    name) and also becomes og:title; ``description`` also becomes og:description;
    site-relative ``canonical_path`` / ``image_url`` are made absolute. A canonical
    override also sets og:url and drops the template's language alternates (they
    are the template's translations, not this URL's).
    """

    title: Optional[str] = None
    description: Optional[str] = None
    robots: Optional[str] = None
    canonical_path: Optional[str] = None
    image_url: Optional[str] = None
    og_type: Optional[str] = None


def site_url(public_base_url: Optional[str], path_or_url: str) -> str:
    """A site-relative path (``/x``) on ``public_base_url``; anything else unchanged."""
    if not path_or_url.startswith(SITE_ROOT_PATH_PREFIX) or path_or_url.startswith(
        PROTOCOL_RELATIVE_PREFIX
    ):
        return path_or_url
    return f"{(public_base_url or '').rstrip('/')}{path_or_url}"


def derive_canonical_url(
    stored_canonical_url: Optional[str],
    slug: Optional[str],
    public_base_url: Optional[str],
    home_slug: Optional[str],
) -> str:
    """The cms canonical rule (``plugins/cms/src/services/seo_canonical.py``), restated
    because adapters may not import cms (D3): the stored override wins, else
    ``public_base_url`` + ``/<slug>``, with ``/`` for the home slug or an empty slug.
    """
    if stored_canonical_url:
        return stored_canonical_url
    normalized_slug = (slug or "").lstrip("/")
    is_root = not normalized_slug or bool(home_slug and normalized_slug == home_slug)
    path = "/" if is_root else f"/{normalized_slug}"
    return site_url(public_base_url, path)


def _page_title(page: Mapping[str, Any]) -> str:
    return page.get("meta_title") or page.get("name") or page.get("title") or ""


def _seo_fields(
    page: Mapping[str, Any], title: str, canonical_url: str
) -> Dict[str, Any]:
    schema_json = page.get("schema_json")
    return {
        "description": page.get("meta_description"),
        "robots": page.get("robots"),
        "canonical_url": canonical_url,
        "og_title": page.get("og_title") or title,
        "og_description": page.get("og_description"),
        "og_image": page.get("og_image_url"),
        "og_type": None,
        "og_url": None,
        "schema_json": json_script_text(schema_json) if schema_json else None,
    }


def _overridden_seo_fields(
    seo: Dict[str, Any],
    overrides: SeoOverrides,
    title: str,
    public_base_url: str,
) -> Dict[str, Any]:
    """``seo`` with every value the overrides supply (``title`` is the final title)."""
    replacements = {
        "description": overrides.description,
        "og_description": overrides.description,
        "robots": overrides.robots,
        "og_title": title if overrides.title else None,
        "og_image": site_url(public_base_url, overrides.image_url)
        if overrides.image_url
        else None,
        "og_type": overrides.og_type,
        "og_url": seo["canonical_url"] if overrides.canonical_path else None,
    }
    return {
        **seo,
        **{key: value for key, value in replacements.items() if value is not None},
    }


def _post_hero(page: Mapping[str, Any]) -> Dict[str, Any]:
    image_url = str(page.get("featured_image_url") or "")
    for character in CSS_URL_BREAKOUT_CHARACTERS:
        image_url = image_url.replace(character, "")
    return {
        "enabled": (page.get("type_data") or {}).get("show_featured_hero") is not False,
        "title": page.get("title") or page.get("name") or "",
        "excerpt": page.get("excerpt") or "",
        "image_url": image_url,
        "tags": [
            {
                "name": term.get("name") or "",
                "href": f"/tag/{quote(str(term.get('slug') or ''), safe=URI_COMPONENT_SAFE_CHARACTERS)}",
            }
            for term in page.get("terms") or []
            if term.get("term_type") == TAG_TERM_TYPE
        ],
    }


def _page_style_css(page: Mapping[str, Any], style_css: Optional[str]) -> Markup:
    parts = [part for part in (style_css, page.get("source_css")) if part]
    return style_text("\n".join(parts))


class CmsPageContextBuilder:
    """Builds the context for one page render (the widget views need the request)."""

    def __init__(
        self,
        page_type_registry: PageTypeTemplateRegistry,
        component_registry: ComponentTemplateRegistry,
        site_settings: CmsSiteSettings,
        route_params: Mapping[str, Any],
        theme_request: Any,
        seo_overrides: Optional[SeoOverrides] = None,
    ) -> None:
        self._page_type_registry = page_type_registry
        self._component_registry = component_registry
        self._site_settings = site_settings
        self._route_params = route_params
        self._theme_request = theme_request
        self._seo_overrides = seo_overrides or SeoOverrides()

    def build(self, resolved: ResolvedCmsPage) -> Dict[str, Any]:
        page = resolved.page
        title = self._title(page)
        canonical_url = self._canonical_url(page)
        layout = resolved.layout
        context: Dict[str, Any] = {
            "cms_page": page,
            "page_type_template": self._page_type_registry.resolve(page_type_of(page)),
            "page_title": title,
            "cms_page_heading": page.get("title") or page.get("name") or "",
            "cms_body_html": Markup(
                page.get("content_html")
                or render_tiptap_document(page.get("content_json"))
            ),
            "cms_layout": self._layout_view(page, layout) if layout else None,
            "cms_layout_head_html": Markup((layout or {}).get("head_html") or ""),
            "cms_global_head_html": Markup(self._site_settings.global_head_html or ""),
            "cms_page_style_css": _page_style_css(page, resolved.style_css),
            "cms_seo": _overridden_seo_fields(
                _seo_fields(page, title, canonical_url),
                self._seo_overrides,
                title,
                self._site_settings.public_base_url,
            ),
            "cms_post_hero": _post_hero(page),
            "cms_tags_custom_fields": tags_and_custom_fields(page),
            "language_alternates": self._language_alternates(page),
            "current_url": canonical_url,
        }
        if page.get("language"):
            context[PAGE_LANGUAGE_CONTEXT_KEY] = page["language"]
        return context

    def _title(self, page: Mapping[str, Any]) -> str:
        subject = self._seo_overrides.title
        if not subject:
            return _page_title(page)
        site_name = self._site_settings.site_name
        return f"{subject}{TITLE_SEPARATOR}{site_name}" if site_name else subject

    def _canonical_url(self, page: Mapping[str, Any]) -> str:
        canonical_path = self._seo_overrides.canonical_path
        if canonical_path:
            return site_url(self._site_settings.public_base_url, canonical_path)
        return derive_canonical_url(
            page.get("canonical_url"),
            page.get("slug"),
            self._site_settings.public_base_url,
            self._site_settings.home_slug,
        )

    def _language_alternates(self, page: Mapping[str, Any]) -> List[Dict[str, Any]]:
        if self._seo_overrides.canonical_path:
            return []
        return list(page.get("translations") or [])

    def _layout_view(
        self, page: Mapping[str, Any], layout: Mapping[str, Any]
    ) -> Dict[str, Any]:
        widget_view_builder = WidgetViewBuilder(
            self._component_registry, page, self._route_params, self._theme_request
        )
        content_blocks = page.get("content_blocks") or {}
        areas: List[Dict[str, Any]] = []
        for area in layout.get("areas") or []:
            is_content = area.get("type") == CONTENT_AREA_TYPE
            block_html = (content_blocks.get(area.get("name")) or {}).get(
                "content_html"
            )
            widgets = (
                []
                if is_content
                else widgets_for_area(
                    area.get("name"),
                    layout.get("assignments"),
                    page.get("page_assignments"),
                )
            )
            areas.append(
                {
                    "name": area.get("name") or "",
                    "type": area.get("type") or "",
                    "is_content": is_content,
                    "block_html": Markup(block_html) if block_html else None,
                    "widgets": [
                        widget_view_builder.build(widget) for widget in widgets
                    ],
                }
            )
        return {"slug": layout.get("slug") or "", "areas": areas}
