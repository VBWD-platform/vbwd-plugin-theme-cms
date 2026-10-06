"""S152-06b — theme_cms registers a server twin for every cms Vue component.

The names are the ``registerCmsVueComponent`` names of fe-user
``plugins/cms/index.ts`` (drift-checked against the checkout when it is next to
vbwd-backend; skipped in an isolated plugin CI clone). Each twin's template
exists; the two htmx fragments (quick search GET, contact form POST) are
declared for the theme's fragment registry; the cms document ships the
cookie-consent and quick-search runtimes.
"""
import re
from pathlib import Path

import pytest

from plugins.theme_cms.theme_cms.components import (
    CMS_COMPONENT_NAMES,
    cms_fragments,
    register_cms_components,
)
from plugins.theme_cms.theme_cms.plugin_paths import TEMPLATES_DIRECTORY
from plugins.theme_cms.theme_cms.registries import ComponentTemplateRegistry

BACKEND_ROOT = Path(__file__).resolve().parents[4]
FE_USER_CMS_INDEX = (
    BACKEND_ROOT.parent / "vbwd-fe-user" / "plugins" / "cms" / "index.ts"
)
VUE_REGISTRATION = re.compile(r"registerCmsVueComponent\('([A-Za-z]+)'")

EXPECTED_NAMES = {
    "CmsBreadcrumb",
    "NativePricingPlans",
    "ContactForm",
    "Category",
    "PostTermList",
    "Search",
    "SearchResults",
    "TagArchive",
    "TermArchive",
    "PostArchive",
    "AddonCatalog",
    "CustomCode",
    "CookieConsent",
    "SuperHeader",
}


def _registry():
    registry = ComponentTemplateRegistry()
    register_cms_components(registry)
    return registry


def test_the_fourteen_cms_component_names_are_registered():
    registry = _registry()

    assert set(CMS_COMPONENT_NAMES) == EXPECTED_NAMES
    assert all(registry.resolve(name) is not None for name in EXPECTED_NAMES)


def test_every_component_template_exists():
    registry = _registry()

    for name in EXPECTED_NAMES:
        template = registry.resolve(name).template
        assert (TEMPLATES_DIRECTORY / template).is_file(), (name, template)


def test_category_and_post_term_list_are_the_same_widget():
    registry = _registry()

    assert (
        registry.resolve("Category").template
        == registry.resolve("PostTermList").template
    )


def test_names_match_the_fe_user_cms_registrations():
    if not FE_USER_CMS_INDEX.is_file():
        pytest.skip("fe-user checkout not mounted next to vbwd-backend")

    vue_names = set(
        VUE_REGISTRATION.findall(FE_USER_CMS_INDEX.read_text(encoding="utf-8"))
    )

    assert vue_names == EXPECTED_NAMES


def test_the_fragments_are_quick_search_get_and_contact_post():
    fragments = {fragment.rule: fragment for fragment in cms_fragments()}

    assert fragments["/_render/_fragment/cms/search"].methods == ("GET",)
    assert fragments["/_render/_fragment/cms/contact"].methods == ("POST",)
    assert {fragment.owner_fe_user_plugin for fragment in fragments.values()} == {"cms"}
    assert {fragment.template for fragment in fragments.values()} == {
        "cms/fragments/quicksearch.html.j2",
        "cms/components/contact_form.html.j2",
    }


def test_the_cms_document_ships_the_component_runtimes():
    document = (TEMPLATES_DIRECTORY / "cms" / "document.html.j2").read_text(
        encoding="utf-8"
    )

    assert '{% include "cms/partials/cms_cookie_consent_runtime.js" %}' in document
    assert '{% include "cms/partials/cms_search_runtime.js" %}' in document
