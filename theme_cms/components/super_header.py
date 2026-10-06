"""SuperHeader (SuperHeader.vue) — logo, a nav widget by slug, search, account icon (S152-06b).

The nav is another cms widget fetched with ``GET /api/v1/cms/widgets/by-slug/<slug>``
and rendered through the same widget templates (so a menu keeps its burger).
A nav that is itself a SuperHeader is refused (no recursion); a failed fetch
renders an empty nav. The account icon links to login for the anonymous page
render and to the dashboard when ``/regions`` re-renders the header for a viewer.
The SPA's opt-in sticky behaviour (``stickable``) has no server twin yet.
"""
from typing import Any, Callable, Dict, Mapping, Optional

from plugins.theme.theme.theme_api import ThemeApiError

from ..cms_api import CmsApi
from ..registries import ComponentContextBuilder, ComponentTemplateRegistry
from ..widget_views import WidgetViewBuilder
from .search import build_search_box_context

CmsApiFactory = Callable[[Any], Any]

SELF_COMPONENT_NAME = "SuperHeader"
VUE_COMPONENT_WIDGET_TYPE = "vue-component"
SEARCH_SLUG_SUFFIX = "-search"
DEFAULTS: Dict[str, Any] = {
    "logo_image_url": "",
    "logo_text": "VBWD",
    "logo_link": "/",
    "nav_widget_slug": "header-nav",
    "search_placeholder": "Search…",
    "search_target_path": "/search",
    "search_scope": "both",
    "quicksearch": True,
    "quicksearch_limit": 6,
    "login_label": "Login",
    "login_path": "/login",
    "dashboard_label": "Dashboard",
    "dashboard_path": "/dashboard",
}


def _setting(widget_config: Mapping[str, Any], key: str) -> Any:
    """``config[key] ?? DEFAULTS[key]``."""
    value = widget_config.get(key)
    return DEFAULTS[key] if value is None else value


def _is_super_header(widget: Mapping[str, Any]) -> bool:
    if widget.get("widget_type") != VUE_COMPONENT_WIDGET_TYPE:
        return False
    component_name = (widget.get("content_json") or {}).get("component") or (
        widget.get("config") or {}
    ).get("component_name")
    return component_name == SELF_COMPONENT_NAME


def _auth_link(widget_config: Mapping[str, Any], theme_request: Any) -> Dict[str, str]:
    if theme_request.viewer.user_id is not None:
        return {
            "href": _setting(widget_config, "dashboard_path"),
            "label": _setting(widget_config, "dashboard_label"),
            "test_id": "super-header-dashboard-icon",
        }
    return {
        "href": _setting(widget_config, "login_path"),
        "label": _setting(widget_config, "login_label"),
        "test_id": "super-header-login-icon",
    }


def _search_config(widget_config: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        "placeholder": _setting(widget_config, "search_placeholder"),
        "target_path": _setting(widget_config, "search_target_path"),
        "scope": _setting(widget_config, "search_scope"),
        "quicksearch": _setting(widget_config, "quicksearch"),
        "quicksearch_limit": _setting(widget_config, "quicksearch_limit"),
        "widget_slug": f"{widget_config.get('widget_slug') or ''}{SEARCH_SLUG_SUFFIX}",
    }


def super_header_context_builder(
    component_registry: ComponentTemplateRegistry,
    cms_api_factory: CmsApiFactory = CmsApi,
) -> ComponentContextBuilder:
    """The SuperHeader context builder (it renders a nested widget, so it needs the registry)."""

    def nav_widget(
        widget_config: Mapping[str, Any],
        page: Mapping[str, Any],
        route_params: Mapping[str, Any],
        theme_request: Any,
    ) -> Optional[Dict[str, Any]]:
        slug = _setting(widget_config, "nav_widget_slug")
        if not slug:
            return None
        try:
            widget = cms_api_factory(theme_request).widget_by_slug(slug)
        except ThemeApiError:
            return None
        if not widget or _is_super_header(widget):
            return None
        builder = WidgetViewBuilder(
            component_registry, page, route_params, theme_request
        )
        return builder.build(widget)

    def build(
        widget_config: Mapping[str, Any],
        page: Mapping[str, Any],
        route_params: Mapping[str, Any],
        theme_request: Any,
    ) -> Dict[str, Any]:
        show_search = widget_config.get("show_search") is not False
        return {
            "logo_image_url": _setting(widget_config, "logo_image_url"),
            "logo_text": _setting(widget_config, "logo_text"),
            "logo_link": _setting(widget_config, "logo_link"),
            "nav_widget": nav_widget(widget_config, page, route_params, theme_request),
            "search": (
                build_search_box_context(
                    _search_config(widget_config), page, route_params, theme_request
                )
                if show_search
                else None
            ),
            "auth_link": (
                _auth_link(widget_config, theme_request)
                if widget_config.get("show_auth_links") is not False
                else None
            ),
        }

    return build
