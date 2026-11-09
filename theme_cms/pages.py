"""The themed pages of the fe-user cms plugin (S152-06a §1, §9; owner fe-user "cms").

``/`` (home slug from ``GET /api/v1/cms/config``), ``/pages``, the two embed
routes and the catch-all ``/<path:slug>`` registered with the LOWEST priority.
Werkzeug matches by rule specificity, not registration order, so any static or
more specific adapter page (``/shop``) wins over the catch-all anyway.
"""
from typing import Any, Dict, List, Mapping, Optional

from flask import abort

from plugins.theme.theme.page_registry import PUBLIC_PAGE, SPA_ONLY_PREFIXES, ThemePage
from plugins.theme.theme.theme_api import (
    FORBIDDEN,
    NOT_FOUND,
    ThemeApiError,
    call_api,
)
from plugins.theme.theme.theme_request import ThemeRequest

from .cms_api import CmsApi
from .components.archives import pagination
from .components.post_card import archive_display, post_list_view
from .language_policy import read_cms_config
from .page_context import CmsPageContextBuilder, CmsSiteSettings, SeoOverrides
from .page_resolver import CmsPageResolver
from .registries import ComponentTemplateRegistry, PageTypeTemplateRegistry

CMS_FE_USER_PLUGIN = "cms"
DISPATCH_TEMPLATE = "cms/dispatch.html.j2"
ACCESS_DENIED_TEMPLATE = "cms/access_denied.html.j2"
HOME_PRIORITY = 100
SPECIFIC_PRIORITY = 50
CATCH_ALL_PRIORITY = -1000
DEFAULT_HOME_SLUG = "index"
FIRST_PAGE = 1
CATEGORY_TERM_TYPE = "category"
PAGE_POST_TYPE = "page"
EMBED_ARCHIVE_META_FIELDS = ("published_at",)
CORE_PUBLIC_CONFIG_PATH = "/api/v1/config"

# Public fe-user SPA routes that no theme adapter renders, so they reach the
# catch-all ``/<path:slug>``. The catch-all hands them back with a PLAIN 404 (no
# not-found label) and nginx serves the SPA shell. Segment-wise prefixes, like
# SPA_ONLY_PREFIXES. A route missing here still works for users (nginx serves
# the SPA shell) but answers HTTP 404 — keep this in sync with the fe-user routes.
# A more specific themed rule (``/pay/stripe``) still wins over the catch-all.
SPA_APP_ROUTE_PREFIXES = (
    "/index.html",  # core router: redirect to home
    "/pay",  # payment plugins: /pay/<provider>[/success|/cancel|/voucher]
    "/ghrm",  # ghrm: /ghrm/auth/github/callback
    "/software",  # ghrm catalogue base (default ``catalogue_page_slug``)
    "/s",  # office: /s/:token public share
    "/landing1",  # landing1
    "/embed/landing1",  # landing1 embed
    "/pharmacy",  # shop-pharma
    "/marketplace",  # marketplace vendor area
)


def _page_number(query_args: Mapping[str, Any]) -> int:
    try:
        return max(int(query_args.get("page") or FIRST_PAGE), FIRST_PAGE)
    except ValueError:
        return FIRST_PAGE


def embed_archive_view(listing: Mapping[str, Any], post_type: str) -> Dict[str, Any]:
    """CmsEmbedArchive: excerpt-mode PostCards linking back into embed mode."""
    display = archive_display({}, "excerpt", EMBED_ARCHIVE_META_FIELDS)
    return {
        "is_empty": not listing.get("total"),
        "post_list": post_list_view(
            listing.get("items") or [], display, f"/cms/embed/{post_type}/post/"
        ),
        "pagination": pagination(
            listing.get("page") or FIRST_PAGE, listing.get("pages") or FIRST_PAGE
        ),
    }


def _core_site_name(theme_request: ThemeRequest) -> str:
    """Core's white-label ``site_name`` (public config); empty when unset or unreadable."""
    try:
        public_config = call_api(theme_request, "GET", CORE_PUBLIC_CONFIG_PATH)
    except ThemeApiError:
        return ""
    return str(public_config.get("site_name") or "")


def _is_spa_path(path: str) -> bool:
    return any(
        path == prefix or path.startswith(prefix + "/")
        for prefix in SPA_ONLY_PREFIXES + SPA_APP_ROUTE_PREFIXES
    )


class CmsPages:
    """Builds the cms ``ThemePage`` list and the context of each page."""

    def __init__(
        self,
        page_type_registry: PageTypeTemplateRegistry,
        component_registry: ComponentTemplateRegistry,
    ) -> None:
        self._page_type_registry = page_type_registry
        self._component_registry = component_registry

    def theme_pages(self) -> List[ThemePage]:
        def page(
            rule: str, endpoint: str, priority: int, template: str, build_context
        ) -> ThemePage:
            return ThemePage(
                rule=rule,
                endpoint=endpoint,
                owner_fe_user_plugin=CMS_FE_USER_PLUGIN,
                priority=priority,
                auth=PUBLIC_PAGE,
                template=template,
                build_context=build_context,
            )

        return [
            page("/", "cms_home", HOME_PRIORITY, DISPATCH_TEMPLATE, self.home_context),
            page(
                "/pages",
                "cms_pages_index",
                SPECIFIC_PRIORITY,
                "cms/pages_index.html.j2",
                self.pages_index_context,
            ),
            page(
                "/cms/embed/<post_type>/post/<path:slug>",
                "cms_embed_post",
                SPECIFIC_PRIORITY,
                DISPATCH_TEMPLATE,
                self.slug_page_context,
            ),
            page(
                "/cms/embed/<post_type>/<category>",
                "cms_embed_archive",
                SPECIFIC_PRIORITY,
                "cms/embed_archive.html.j2",
                self.embed_archive_context,
            ),
            page(
                "/<path:slug>",
                "cms_page",
                CATCH_ALL_PRIORITY,
                DISPATCH_TEMPLATE,
                self.slug_page_context,
            ),
        ]

    def home_context(self, theme_request: ThemeRequest) -> Dict[str, Any]:
        cms_api = CmsApi(theme_request)
        home_slug = cms_api.site_config().get("home_slug") or DEFAULT_HOME_SLUG
        return self._cms_page_context(theme_request, cms_api, home_slug)

    def slug_page_context(self, theme_request: ThemeRequest) -> Dict[str, Any]:
        slug = theme_request.view_args["slug"]
        if _is_spa_path(f"/{slug}"):
            # A plain, unlabelled 404 (not ThemeApiError → labelled themed 404):
            # nginx falls back to the SPA, which owns this path.
            abort(NOT_FOUND)
        return self._cms_page_context(theme_request, CmsApi(theme_request), slug)

    def cms_slug_page_context(
        self,
        theme_request: ThemeRequest,
        cms_slug: str,
        seo_overrides: Optional[SeoOverrides] = None,
    ) -> Dict[str, Any]:
        """An adapter route rendered inside the CMS page ``cms_slug`` (fe-user
        ``CmsPage`` with a fixed ``slug`` prop): the page is chosen by
        ``cms_slug``, its widgets read the route's own params (S152-06 §7).
        ``seo_overrides`` give the route its own SEO head instead of the template's.
        """
        return self._cms_page_context(
            theme_request, CmsApi(theme_request), cms_slug, seo_overrides
        )

    def _cms_page_context(
        self,
        theme_request: ThemeRequest,
        cms_api: CmsApi,
        slug: str,
        seo_overrides: Optional[SeoOverrides] = None,
    ) -> Dict[str, Any]:
        try:
            resolved = CmsPageResolver(cms_api).resolve(
                slug, preview_token=theme_request.query_args.get("preview_token")
            )
        except ThemeApiError as lookup_error:
            if lookup_error.status != FORBIDDEN:
                raise
            return {"page_type_template": ACCESS_DENIED_TEMPLATE, "page_title": ""}
        cms_config = read_cms_config()
        site_settings = CmsSiteSettings(
            public_base_url=str(cms_config.get("public_base_url") or ""),
            home_slug=str(cms_api.site_config().get("home_slug") or DEFAULT_HOME_SLUG),
            global_head_html=str(cms_config.get("global_head_html") or ""),
            site_name=_core_site_name(theme_request)
            if seo_overrides and seo_overrides.title
            else "",
        )
        builder = CmsPageContextBuilder(
            self._page_type_registry,
            self._component_registry,
            site_settings,
            theme_request.view_args,
            theme_request,
            seo_overrides,
        )
        return builder.build(resolved)

    def embed_archive_context(self, theme_request: ThemeRequest) -> Dict[str, Any]:
        post_type = theme_request.view_args["post_type"]
        listing = CmsApi(theme_request).posts(
            {
                "type": post_type,
                "term_type": CATEGORY_TERM_TYPE,
                "term_slug": theme_request.view_args["category"],
                "page": _page_number(theme_request.query_args),
            }
        )
        return {"page_title": "", **embed_archive_view(listing, post_type)}

    def pages_index_context(self, theme_request: ThemeRequest) -> Dict[str, Any]:
        cms_api = CmsApi(theme_request)
        active_category = theme_request.query_args.get("category")
        listing = cms_api.posts(
            {
                "type": PAGE_POST_TYPE,
                "term_type": CATEGORY_TERM_TYPE,
                "term_slug": active_category,
                "page": _page_number(theme_request.query_args),
                "per_page": theme_request.query_args.get("per_page"),
            }
        )
        return {
            "page_title": "",
            "listing": listing,
            "categories": cms_api.categories(),
            "active_category": active_category,
        }
