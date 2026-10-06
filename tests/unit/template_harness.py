"""Render theme_cms templates through the REAL theme renderer (basic theme + the
templates and translations theme_cms contributes), with a context built by the
real :class:`CmsPageContextBuilder`.
"""
from pathlib import Path

from flask import Flask

from plugins.theme import ThemePlugin
from plugins.theme_cms.theme_cms.page_context import (
    CmsPageContextBuilder,
    CmsSiteSettings,
)
from plugins.theme_cms.theme_cms.page_resolver import ResolvedCmsPage
from plugins.theme_cms.theme_cms.plugin_paths import (
    TEMPLATES_DIRECTORY,
    TRANSLATIONS_DIRECTORY,
)
from plugins.theme_cms.theme_cms.registries import (
    ComponentTemplateRegistry,
    default_page_type_registry,
)

DISPATCH_TEMPLATE = "cms/dispatch.html.j2"
TEST_COMPONENT_TEMPLATES = Path(__file__).parent / "component_templates"
SITE = CmsSiteSettings(
    public_base_url="https://site.example",
    home_slug="index",
    global_head_html='<meta name="site-verification" content="abc">',
)


def theme_plugin() -> ThemePlugin:
    plugin = ThemePlugin()
    plugin.on_enable()
    plugin.theme_registry.add_contributed_template_path(TEMPLATES_DIRECTORY)
    plugin.theme_registry.add_contributed_translation_path(TRANSLATIONS_DIRECTORY)
    plugin.theme_registry.add_contributed_template_path(TEST_COMPONENT_TEMPLATES)
    return plugin


def page_context(page, layout=None, style_css=None, component_registry=None):
    builder = CmsPageContextBuilder(
        default_page_type_registry(),
        component_registry or ComponentTemplateRegistry(),
        SITE,
        route_params={"slug": page.get("slug")},
        theme_request=None,
    )
    context = builder.build(ResolvedCmsPage(page, layout, style_css))
    context["language"] = context.pop("page_language", "en")
    context["default_language"] = "en"
    return context


def render(plugin, context, template=DISPATCH_TEMPLATE, viewer=None):
    app = Flask(__name__)
    app.testing = True
    with app.app_context():
        if viewer is None:
            return plugin.renderer.render(template, context)
        return plugin.renderer.render(template, context, viewer=viewer)


def render_with_regions(plugin, context):
    app = Flask(__name__)
    app.testing = True
    with app.app_context():
        return plugin.renderer.render_with_regions(DISPATCH_TEMPLATE, context)


def render_component(plugin, template, component_context, language="en"):
    """One component template, as the vue-component widget includes it."""
    return render(
        plugin,
        {
            "component_context": component_context,
            "language": language,
            "default_language": "en",
        },
        template=template,
    )
