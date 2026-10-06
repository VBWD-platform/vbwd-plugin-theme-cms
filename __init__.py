"""Theme adapter mirroring the fe-user cms plugin (pages, posts, CMS widgets) (S152).

Renders only when ``VBWD_FRONTEND_MODE=theme``; in the default ``vue`` mode the
theme mounts no page route and the Vue SPA serves every page. On enable it
plugs the CMS language policy into the theme (D13), contributes its templates,
translations and the ported SPA component stylesheets, and registers the cms pages (``/``, ``/pages``, embeds and
the lowest-priority catch-all), the server twins of the cms Vue components and
their htmx fragments. It talks to cms over its public API only (D3).
"""
from typing import Optional

from vbwd.plugins.base import BasePlugin, PluginMetadata

from plugins.theme.theme.page_registry import resolve_theme_plugin
from plugins.theme_cms.theme_cms.components import (
    cms_fragments,
    register_cms_components,
)
from plugins.theme_cms.theme_cms.language_policy import CmsLanguagePolicy
from plugins.theme_cms.theme_cms.pages import CmsPages
from plugins.theme_cms.theme_cms.plugin_paths import (
    STYLESHEETS_DIRECTORY,
    TEMPLATES_DIRECTORY,
    TRANSLATIONS_DIRECTORY,
)
from plugins.theme_cms.theme_cms.registries import (
    ComponentTemplateRegistry,
    default_page_type_registry,
)


class ThemeCmsPlugin(BasePlugin):
    """Theme adapter mirroring the fe-user cms plugin (pages, posts, CMS widgets)."""

    def __init__(self) -> None:
        super().__init__()
        self.page_type_registry = default_page_type_registry()
        self.component_registry = ComponentTemplateRegistry()
        register_cms_components(self.component_registry)

    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="theme_cms",
            version="1.0.0",
            author="VBWD Team",
            description="Theme adapter mirroring the fe-user cms plugin (pages, posts, CMS widgets).",
            dependencies=["theme>=1.0", "cms"],
        )

    def on_enable(self) -> None:
        theme_plugin = resolve_theme_plugin()
        theme_plugin.set_language_policy(CmsLanguagePolicy())
        theme_plugin.theme_registry.add_contributed_template_path(TEMPLATES_DIRECTORY)
        theme_plugin.theme_registry.add_contributed_translation_path(
            TRANSLATIONS_DIRECTORY
        )
        theme_plugin.theme_registry.add_contributed_stylesheet_path(
            STYLESHEETS_DIRECTORY
        )
        cms_pages = CmsPages(self.page_type_registry, self.component_registry)
        for page in cms_pages.theme_pages():
            theme_plugin.page_registry.register(page)
        for fragment in cms_fragments():
            theme_plugin.fragment_registry.register(fragment)

    def get_url_prefix(self) -> Optional[str]:
        # No blueprint of its own: the theme mounts the registered pages.
        return ""
