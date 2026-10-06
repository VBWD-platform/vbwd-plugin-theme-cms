"""What each widget template receives — the mirror of fe-user ``CmsWidgetRenderer`` (§6).

``WidgetViewBuilder.build(widget)`` turns one cms widget payload into a plain
dict the ``cms/widgets/<widget_type>.html.j2`` template renders. HTML content is
decoded like the SPA does (base64 → UTF-8); menus get the SPA's href rule and
one child level; a ``vue-component`` is resolved in the
:class:`ComponentTemplateRegistry` (a pending S153 component hands the page to the SPA).
"""
import base64
import binascii
import re
from typing import Any, Dict, List, Mapping, Optional

from markupsafe import Markup

from plugins.theme.theme.theme_api import NOT_FOUND, ThemeApiError

from .markup import style_text
from .registries import ComponentTemplateRegistry

CART_BADGE_COMPONENT = "CartBadge"
DEFAULT_LINK_TARGET = "_self"
NO_LINK_HREF = "#"
WIDGET_SLUG_CONFIG_KEY = "widget_slug"
# Components of fe-user plugins that are ALWAYS the SPA (D7): a themed page
# links to the SPA page instead of rendering them.
SPA_ONLY_COMPONENT_LINKS = {"TukTukIntakeWidget": "/tuktuk/chat"}
# Components the SPA renders whose themed twin is still pending (S153 adapters).
# A page that needs one is handed to the SPA (404 → nginx @spa) instead of being
# served without it (D5). A registered twin always wins, so S153 drains this set
# simply by registering its components.
SPA_HANDOFF_COMPONENTS = frozenset(
    {"GhrmCatalogueContent", "GhrmPackageDetail", "MeinchatChatWidget"}
)
_UNSAFE_COMPONENT_NAME_CHARACTERS = re.compile(r"[^A-Za-z0-9_]")


def decode_widget_html(encoded: Any) -> str:
    """``decodeURIComponent(escape(atob(encoded)))``; the raw value when it does not decode."""
    if not encoded:
        return ""
    try:
        return base64.b64decode(str(encoded), validate=True).decode("utf-8")
    except (binascii.Error, UnicodeDecodeError):
        return str(encoded)


def _menu_link_href(item: Mapping[str, Any]) -> str:
    if item.get("url"):
        return str(item["url"])
    if item.get("page_slug"):
        return f"/{item['page_slug']}"
    return NO_LINK_HREF


def _menu_link(item: Mapping[str, Any], href: str) -> Dict[str, Any]:
    return {
        "label": item.get("label") or "",
        "href": href,
        "target": item.get("target") or DEFAULT_LINK_TARGET,
        "icon": item.get("icon"),
    }


def _menu_tree(menu_items: List[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    """Root items, each with its direct children (one level, as the SPA renders)."""
    root_items = []
    for item in menu_items:
        if item.get("parent_id"):
            continue
        children = [
            _menu_link(child, _menu_link_href(child))
            for child in menu_items
            if child.get("parent_id") == item.get("id")
        ]
        # A parent's own link only toggles its sub-menu.
        href = NO_LINK_HREF if children else _menu_link_href(item)
        root_items.append(
            {
                **_menu_link(item, href),
                "children": children,
                "has_children": bool(children),
            }
        )
    return root_items


class WidgetViewBuilder:
    """Builds widget views for one page render (components need the page + request)."""

    def __init__(
        self,
        component_registry: ComponentTemplateRegistry,
        page: Mapping[str, Any],
        route_params: Mapping[str, Any],
        theme_request: Any,
    ) -> None:
        self._component_registry = component_registry
        self._page = page
        self._route_params = route_params
        self._theme_request = theme_request

    def build(self, widget: Mapping[str, Any]) -> Dict[str, Any]:
        widget_type = widget.get("widget_type")
        view: Dict[str, Any] = {
            "widget_type": widget_type,
            "slug": widget.get("slug") or "",
            "css": style_text(widget.get("source_css")),
        }
        content_json = widget.get("content_json") or {}
        if widget_type == "html":
            view["html"] = Markup(decode_widget_html(content_json.get("content")))
        elif widget_type == "menu":
            view.update(self._menu_view(widget))
        elif widget_type == "slideshow":
            view["slides"] = [
                {
                    "url": image.get("url") or "",
                    "alt": image.get("alt") or "",
                    "caption": image.get("caption") or "",
                }
                for image in content_json.get("images") or []
            ]
        elif widget_type == "vue-component":
            view.update(self._vue_component_view(widget, content_json))
        return view

    def _menu_view(self, widget: Mapping[str, Any]) -> Dict[str, Any]:
        show_cart = (widget.get("config") or {}).get("show_cart") is True
        return {
            "menu_items": _menu_tree(list(widget.get("menu_items") or [])),
            "show_cart": show_cart,
            "cart_badge": (
                self._component_view(CART_BADGE_COMPONENT, {}) if show_cart else None
            ),
        }

    def _vue_component_view(
        self, widget: Mapping[str, Any], content_json: Mapping[str, Any]
    ) -> Dict[str, Any]:
        config = dict(widget.get("config") or {})
        component_name = str(
            content_json.get("component") or config.get("component_name") or ""
        )
        config[WIDGET_SLUG_CONFIG_KEY] = widget.get("slug")
        component_view = self._component_view(component_name, config)
        if component_view is None and component_name in SPA_HANDOFF_COMPONENTS:
            raise ThemeApiError(
                NOT_FOUND, f"component '{component_name}' is rendered by the SPA"
            )
        return {
            "component": component_view,
            "component_name": _UNSAFE_COMPONENT_NAME_CHARACTERS.sub("", component_name),
            "spa_link_href": SPA_ONLY_COMPONENT_LINKS.get(component_name),
        }

    def _component_view(
        self, component_name: str, widget_config: Mapping[str, Any]
    ) -> Optional[Dict[str, Any]]:
        component = self._component_registry.resolve(component_name)
        if component is None:
            return None
        return {
            "template": component.template,
            "context": component.build_context(
                widget_config, self._page, self._route_params, self._theme_request
            ),
        }
