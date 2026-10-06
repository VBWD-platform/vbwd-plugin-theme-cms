"""S152-06b — SuperHeader (SuperHeader.vue).

Logo (image or text) → nav = another widget fetched with
``GET /api/v1/cms/widgets/by-slug/<nav_widget_slug>`` and rendered through the
same widget templates (menu, html, …; a SuperHeader nav is refused, a failed
fetch renders an empty nav) → the PostSearch box → the account icon (login when
anonymous; dashboard for a viewer — the header area is a personalised region).
Defaults are the Vue ``DEFAULTS``; note the Vue template's ``data-test-id``.
"""
import pytest

from plugins.theme.theme.theme_api import ThemeApiError
from plugins.theme_cms.tests.unit.components.fakes import FakeCmsApi, FakeThemeRequest
from plugins.theme_cms.tests.unit.dom_contract import canonical, testids
from plugins.theme_cms.tests.unit.template_harness import render_component, theme_plugin
from plugins.theme_cms.theme_cms.components.super_header import (
    super_header_context_builder,
)
from plugins.theme_cms.theme_cms.registries import ComponentTemplateRegistry

TEMPLATE = "cms/components/super_header.html.j2"
ACCOUNT_ICON = (
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
    'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">'
    '<path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path>'
    '<circle cx="12" cy="7" r="4"></circle></svg>'
)
MENU_WIDGET = {
    "slug": "header-nav",
    "widget_type": "menu",
    "config": {},
    "menu_items": [{"id": "1", "label": "Docs", "page_slug": "docs"}],
}


@pytest.fixture(autouse=True)
def isolated_var_directory(tmp_path, monkeypatch):
    monkeypatch.setenv("VBWD_VAR_DIR", str(tmp_path / "var"))


def _context(config, cms_api, theme_request=None):
    build = super_header_context_builder(ComponentTemplateRegistry(), cms_api.factory)
    return build(config, {}, {}, theme_request or FakeThemeRequest(path="/about"))


def _render(context):
    return render_component(theme_plugin(), TEMPLATE, context)


def test_defaults_render_text_logo_nav_quicksearch_and_the_login_icon():
    cms_api = FakeCmsApi(widget_by_slug=MENU_WIDGET)

    html = _render(_context({"widget_slug": "site-header"}, cms_api))

    assert cms_api.calls == [("widget_by_slug", "header-nav")]
    assert canonical(html).startswith(
        canonical(
            '<header class="cms-super-header">'
            '<a class="cms-super-header__logo" href="/">'
            '<span class="cms-super-header__logo-text">VBWD</span></a>'
            '<div class="cms-super-header__nav">'
            '<nav class="cms-widget cms-widget--menu cms-widget--header-nav">'
        )
    )
    assert '<a href="/docs" target="_self" class="cms-menu__link">Docs</a>' in html
    assert '<div class="cms-super-header__search"><div class="post-search">' in html
    assert (
        'action="/search"' in html
        and 'hx-target="#post-search-listbox-site-header-search"' in html
    )
    assert canonical(html).endswith(
        canonical(
            '<div class="cms-super-header__auth">'
            '<a class="cms-super-header__auth-link cms-super-header__auth-link--icon" '
            'href="/login" aria-label="Login" title="Login" data-test-id="super-header-login-icon">'
            f"{ACCOUNT_ICON}</a></div></header>"
        )
    )


def test_a_viewer_gets_the_dashboard_icon():
    html = _render(
        _context(
            {"dashboard_label": "My account", "dashboard_path": "/dashboard/home"},
            FakeCmsApi(widget_by_slug=MENU_WIDGET),
            FakeThemeRequest(user_id="u-1"),
        )
    )

    assert (
        'href="/dashboard/home" aria-label="My account" title="My account" '
        'data-test-id="super-header-dashboard-icon"'
    ) in html


def test_logo_image_and_switched_off_sections():
    config = {
        "logo_image_url": "/logo.svg",
        "logo_text": "Acme <Co>",
        "logo_link": "/home",
        "show_search": False,
        "show_auth_links": False,
    }

    html = _render(_context(config, FakeCmsApi(widget_by_slug=MENU_WIDGET)))

    assert (
        '<a class="cms-super-header__logo" href="/home">'
        '<img class="cms-super-header__logo-img" src="/logo.svg" alt="Acme &lt;Co&gt;"></a>'
    ) in html
    assert "cms-super-header__search" not in html
    assert "cms-super-header__auth" not in html
    assert testids(html) == []


@pytest.mark.parametrize(
    "answer",
    [
        ThemeApiError(404, "missing"),
        {
            "slug": "x",
            "widget_type": "vue-component",
            "content_json": {"component": "SuperHeader"},
        },
        {
            "slug": "x",
            "widget_type": "vue-component",
            "config": {"component_name": "SuperHeader"},
        },
    ],
)
def test_a_missing_or_self_referencing_nav_renders_an_empty_nav(answer):
    html = _render(_context({}, FakeCmsApi(widget_by_slug=answer)))

    assert '<div class="cms-super-header__nav"></div>' in html


def test_an_html_nav_widget_renders_through_its_widget_template():
    nav = {
        "slug": "nav-html",
        "widget_type": "html",
        "content_json": {"content": "PGI+TmF2PC9iPg=="},
    }

    html = _render(
        _context({"nav_widget_slug": "nav-html"}, FakeCmsApi(widget_by_slug=nav))
    )

    assert (
        '<div class="cms-widget cms-widget--html"><div><b>Nav</b></div></div>' in html
    )


def test_search_options_come_from_the_header_config():
    html = _render(
        _context(
            {
                "widget_slug": "h",
                "search_placeholder": "Look up",
                "search_target_path": "/find",
                "search_scope": "pages",
                "quicksearch": False,
            },
            FakeCmsApi(widget_by_slug=MENU_WIDGET),
        )
    )

    assert 'placeholder="Look up"' in html and 'action="/find"' in html
    assert "hx-get" not in html
