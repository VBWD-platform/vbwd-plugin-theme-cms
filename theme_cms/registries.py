"""Template registries — the server twins of fe-user ``registerCmsPageType`` and
``registerCmsVueComponent`` (S152-06a §3 + §6).

``PageTypeTemplateRegistry`` maps a cms post ``type`` to its page template;
unknown types render as ``page`` (``resolveCmsPageType`` → page). The
``ComponentTemplateRegistry`` maps a ``vue-component`` widget's component name
to a template + the context builder that fetches its data through C2. Adapters
(theme_shop, theme_booking, …) register their components from ``on_enable``.
"""
from dataclasses import dataclass
from typing import Any, Callable, Dict, Mapping, Optional

from flask import current_app

PAGE_TYPE = "page"
PAGE_TYPE_TEMPLATE = "cms/page_types/{page_type}.html.j2"
BUILT_IN_PAGE_TYPES = ("page", "post", "term_archive", "archive")

# (widget_config, page, route_params, theme_request) -> template context
ComponentContextBuilder = Callable[
    [Mapping[str, Any], Mapping[str, Any], Mapping[str, Any], Any], Dict[str, Any]
]


class ComponentTemplateRegistrationError(ValueError):
    """A component template the registry refuses (a name registered twice)."""


@dataclass(frozen=True)
class ComponentTemplate:
    """A themed CMS component: the same ``name`` the Vue registry uses."""

    name: str
    template: str
    build_context: ComponentContextBuilder


class PageTypeTemplateRegistry:
    """cms post ``type`` → page template; a later registration of a type wins.

    ``page`` is always registered: it is the fallback of every unknown type.
    """

    def __init__(self) -> None:
        self._templates_by_type: Dict[str, str] = {
            PAGE_TYPE: PAGE_TYPE_TEMPLATE.format(page_type=PAGE_TYPE)
        }

    def register(self, page_type: str, template: str) -> None:
        self._templates_by_type[page_type] = template

    def resolve(self, page_type: Optional[str]) -> str:
        if page_type in self._templates_by_type:
            return self._templates_by_type[page_type]
        return self._templates_by_type[PAGE_TYPE]


def default_page_type_registry() -> PageTypeTemplateRegistry:
    """The registry with the page types theme_cms ships."""
    registry = PageTypeTemplateRegistry()
    for page_type in BUILT_IN_PAGE_TYPES:
        registry.register(page_type, PAGE_TYPE_TEMPLATE.format(page_type=page_type))
    return registry


class ComponentTemplateRegistry:
    """Component name → :class:`ComponentTemplate`."""

    def __init__(self) -> None:
        self._components_by_name: Dict[str, ComponentTemplate] = {}

    def register(self, component: ComponentTemplate) -> None:
        if component.name in self._components_by_name:
            raise ComponentTemplateRegistrationError(
                f"cms component template '{component.name}' is already registered"
            )
        self._components_by_name[component.name] = component

    def resolve(self, name: Optional[str]) -> Optional[ComponentTemplate]:
        return self._components_by_name.get(name or "")


THEME_CMS_PLUGIN_NAME = "theme_cms"


def resolve_component_template_registry() -> ComponentTemplateRegistry:
    """The running app's component registry; adapters register their components here."""
    plugin_manager = getattr(current_app, "plugin_manager")
    theme_cms_plugin = plugin_manager.get_plugin(THEME_CMS_PLUGIN_NAME)
    if theme_cms_plugin is None:
        raise LookupError("theme_cms plugin is not installed")
    registry: ComponentTemplateRegistry = theme_cms_plugin.component_registry
    return registry
