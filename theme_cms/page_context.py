"""The template context of one resolved CMS page (S152-06a §3–5, §8, D13).

The mirror of what ``CmsPageTypeBase`` / ``CmsPageTypePost`` / ``CmsLayoutRenderer``
compute in the SPA: the body (``content_html`` or TipTap), the page-type template,
the layout's area views, the one page style, the SEO head fields
(``injectSeoMeta``), the post hero and the language alternates (W3).
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


@dataclass(frozen=True)
class CmsSiteSettings:
    """Site-wide cms values a page needs: canonical base, home slug, global head HTML."""

    public_base_url: str
    home_slug: str
    global_head_html: str


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
    return f"{(public_base_url or '').rstrip('/')}{path}"


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
        "schema_json": json_script_text(schema_json) if schema_json else None,
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
    ) -> None:
        self._page_type_registry = page_type_registry
        self._component_registry = component_registry
        self._site_settings = site_settings
        self._route_params = route_params
        self._theme_request = theme_request

    def build(self, resolved: ResolvedCmsPage) -> Dict[str, Any]:
        page = resolved.page
        title = _page_title(page)
        canonical_url = derive_canonical_url(
            page.get("canonical_url"),
            page.get("slug"),
            self._site_settings.public_base_url,
            self._site_settings.home_slug,
        )
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
            "cms_seo": _seo_fields(page, title, canonical_url),
            "cms_post_hero": _post_hero(page),
            "cms_tags_custom_fields": tags_and_custom_fields(page),
            "language_alternates": list(page.get("translations") or []),
            "current_url": canonical_url,
        }
        if page.get("language"):
            context[PAGE_LANGUAGE_CONTEXT_KEY] = page["language"]
        return context

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
