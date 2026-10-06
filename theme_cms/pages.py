"""The themed pages of the fe-user cms plugin (S152-06a §1, §9; owner fe-user "cms").

``/`` (home slug from ``GET /api/v1/cms/config``), ``/pages``, the two embed
routes and the catch-all ``/<path:slug>`` registered with the LOWEST priority.
Werkzeug matches by rule specificity, not registration order, so any static or
more specific adapter page (``/shop``) wins over the catch-all anyway.
"""
from typing import Any, Dict, List, Mapping

from plugins.theme.theme.page_registry import PUBLIC_PAGE, SPA_ONLY_PREFIXES, ThemePage
from plugins.theme.theme.theme_api import FORBIDDEN, NOT_FOUND, ThemeApiError
from plugins.theme.theme.theme_request import ThemeRequest

from .cms_api import CmsApi
from .components.archives import pagination
from .components.post_card import archive_display, post_list_view
from .language_policy import read_cms_config
from .page_context import CmsPageContextBuilder, CmsSiteSettings
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


def _is_spa_only_path(path: str) -> bool:
    return any(
        path == prefix or path.startswith(prefix + "/") for prefix in SPA_ONLY_PREFIXES
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
        if _is_spa_only_path(f"/{slug}"):
            raise ThemeApiError(NOT_FOUND, "an SPA-only path is never themed")
        return self._cms_page_context(theme_request, CmsApi(theme_request), slug)

    def cms_slug_page_context(
        self, theme_request: ThemeRequest, cms_slug: str
    ) -> Dict[str, Any]:
        """An adapter route rendered inside the CMS page ``cms_slug`` (fe-user
        ``CmsPage`` with a fixed ``slug`` prop): the page is chosen by
        ``cms_slug``, its widgets read the route's own params (S152-06 §7).
        """
        return self._cms_page_context(theme_request, CmsApi(theme_request), cms_slug)

    def _cms_page_context(
        self, theme_request: ThemeRequest, cms_api: CmsApi, slug: str
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
        )
        builder = CmsPageContextBuilder(
            self._page_type_registry,
            self._component_registry,
            site_settings,
            theme_request.view_args,
            theme_request,
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
