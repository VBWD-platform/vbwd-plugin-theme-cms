"""The server twins of the fe-user cms ``registerCmsVueComponent`` widgets (S152-06b).

``register_cms_components`` fills the ComponentTemplateRegistry with the 14
names fe-user ``plugins/cms/index.ts`` registers (Category and PostTermList are
one widget); ``cms_fragments`` are the htmx islands two of them post to.
"""
from typing import List, Tuple

from plugins.theme.theme.fragment_registry import ThemeFragment

from ..registries import (
    ComponentContextBuilder,
    ComponentTemplate,
    ComponentTemplateRegistry,
)
from .archives import (
    build_post_archive_context,
    build_tag_archive_context,
    build_term_archive_context,
    build_term_list_context,
)
from .breadcrumb import build_breadcrumb_context
from .contact_form import (
    CONTACT_FRAGMENT_PATH,
    build_contact_form_context,
    build_contact_fragment_context,
)
from .cookie_consent import build_cookie_consent_context
from .custom_code import build_custom_code_context
from .pricing import build_addon_catalog_context, build_native_pricing_plans_context
from .search import (
    SEARCH_FRAGMENT_PATH,
    build_quicksearch_fragment_context,
    build_search_box_context,
    build_search_results_context,
)
from .super_header import super_header_context_builder

CMS_FE_USER_PLUGIN = "cms"
COMPONENT_TEMPLATE = "cms/components/{name}.html.j2"
CONTACT_FORM_TEMPLATE = COMPONENT_TEMPLATE.format(name="contact_form")


def _component_specs(
    registry: ComponentTemplateRegistry,
) -> List[Tuple[str, str, ComponentContextBuilder]]:
    return [
        ("CmsBreadcrumb", "breadcrumb", build_breadcrumb_context),
        (
            "NativePricingPlans",
            "native_pricing_plans",
            build_native_pricing_plans_context,
        ),
        ("ContactForm", "contact_form", build_contact_form_context),
        ("Category", "term_list", build_term_list_context),
        ("PostTermList", "term_list", build_term_list_context),
        ("Search", "search", build_search_box_context),
        ("SearchResults", "search_results", build_search_results_context),
        ("TagArchive", "tag_archive", build_tag_archive_context),
        ("TermArchive", "term_archive", build_term_archive_context),
        ("PostArchive", "post_archive", build_post_archive_context),
        ("AddonCatalog", "addon_catalog", build_addon_catalog_context),
        ("CustomCode", "custom_code", build_custom_code_context),
        ("CookieConsent", "cookie_consent", build_cookie_consent_context),
        ("SuperHeader", "super_header", super_header_context_builder(registry)),
    ]


CMS_COMPONENT_NAMES = tuple(
    name for name, _template, _builder in _component_specs(ComponentTemplateRegistry())
)


def register_cms_components(registry: ComponentTemplateRegistry) -> None:
    for name, template_name, build_context in _component_specs(registry):
        registry.register(
            ComponentTemplate(
                name=name,
                template=COMPONENT_TEMPLATE.format(name=template_name),
                build_context=build_context,
            )
        )


def cms_fragments() -> List[ThemeFragment]:
    return [
        ThemeFragment(
            rule=SEARCH_FRAGMENT_PATH,
            endpoint="cms_quicksearch_fragment",
            owner_fe_user_plugin=CMS_FE_USER_PLUGIN,
            template="cms/fragments/quicksearch.html.j2",
            build_context=build_quicksearch_fragment_context,
        ),
        ThemeFragment(
            rule=CONTACT_FRAGMENT_PATH,
            endpoint="cms_contact_form_fragment",
            owner_fe_user_plugin=CMS_FE_USER_PLUGIN,
            template=CONTACT_FORM_TEMPLATE,
            build_context=build_contact_fragment_context,
            methods=("POST",),
        ),
    ]
