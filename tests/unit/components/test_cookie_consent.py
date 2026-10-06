"""S152-06b — CookieConsent (CookieConsent.vue) server markup.

The server cannot read localStorage, so the dialog ships ``hidden``; the cms
runtime (``cms_cookie_consent_runtime.js``, tested with node:test) reads the
SAME ``vbwd_cookie_consent`` record and opens it when a decision is needed.
Both layers are rendered; the customize layer is hidden until asked for. Config:
consent_version (1), privacy_policy_url (/privacy), position / legacy mode=banner,
additional_text, backdrop_opacity (0.55, clamped), show_settings_button, categories.
"""
import pytest

from plugins.theme_cms.tests.unit.components.fakes import FakeThemeRequest
from plugins.theme_cms.tests.unit.dom_contract import canonical, testids
from plugins.theme_cms.tests.unit.template_harness import render_component, theme_plugin
from plugins.theme_cms.theme_cms.components.cookie_consent import (
    build_cookie_consent_context,
)

TEMPLATE = "cms/components/cookie_consent.html.j2"


@pytest.fixture(autouse=True)
def isolated_var_directory(tmp_path, monkeypatch):
    monkeypatch.setenv("VBWD_VAR_DIR", str(tmp_path / "var"))


def _render(config):
    context = build_cookie_consent_context(config, {}, {}, FakeThemeRequest())
    return render_component(theme_plugin(), TEMPLATE, context)


def _category(name, label, purpose, checked=False, disabled=False):
    state = (" checked" if checked else "") + (" disabled" if disabled else "")
    return (
        '<li class="cookie-consent__category"><label class="cookie-consent__category-label">'
        f'<input type="checkbox" class="cookie-consent__toggle" data-cookie-category="{name}" '
        f'data-testid="cookie-toggle-{name}"{state}>'
        f'<span class="cookie-consent__category-name">{label}</span></label>'
        f'<p class="cookie-consent__category-purpose">{purpose}</p></li>'
    )


def test_the_dialog_markup_matches_the_vue_template_and_ships_hidden():
    html = _render(
        {"categories": ["necessary", "statistics"], "additional_text": "Note"}
    )

    assert canonical(html) == canonical(
        '<div class="cookie-consent__backdrop" style="background: rgba(0, 0, 0, 0.55)" '
        'data-testid="cookie-consent-backdrop" data-consent-version="1" hidden>'
        '<div class="cookie-consent" role="dialog" aria-modal="true" '
        'aria-labelledby="cookie-consent-title" data-testid="cookie-consent">'
        '<h2 id="cookie-consent-title" class="cookie-consent__title" '
        'data-cookie-consent-layer="summary">We value your privacy</h2>'
        '<p class="cookie-consent__summary" data-cookie-consent-layer="summary">'
        "We use cookies to run the site and, with your consent, to measure and improve it. "
        "You can accept all, reject all, or choose per purpose."
        '<a href="/privacy" class="cookie-consent__policy-link" '
        'data-testid="cookie-policy-link">Privacy policy</a></p>'
        '<p class="cookie-consent__additional" data-testid="cookie-additional-text" '
        'data-cookie-consent-layer="summary">Note</p>'
        '<div class="cookie-consent__actions" data-cookie-consent-layer="summary">'
        '<button type="button" class="cookie-consent__btn" data-testid="cookie-accept-all">Accept all</button>'
        '<button type="button" class="cookie-consent__btn" data-testid="cookie-reject-all">Reject all</button>'
        '<button type="button" class="cookie-consent__btn" data-testid="cookie-customize">Customize</button>'
        "</div>"
        '<h2 id="cookie-consent-customize-title" class="cookie-consent__title" '
        'data-cookie-consent-layer="customize" hidden>Choose your cookie preferences</h2>'
        '<ul class="cookie-consent__categories" data-cookie-consent-layer="customize" hidden>'
        + _category(
            "necessary",
            "Strictly necessary",
            "Required for the site to work — login, cart and checkout. Always on.",
            checked=True,
            disabled=True,
        )
        + _category(
            "statistics",
            "Statistics",
            "Help us understand how visitors use the site through anonymous analytics.",
        )
        + "</ul>"
        '<div class="cookie-consent__actions" data-cookie-consent-layer="customize" hidden>'
        '<button type="button" class="cookie-consent__btn" data-testid="cookie-save">Save my choices</button>'
        "</div></div></div>"
        '<button type="button" class="cookie-consent__settings" data-testid="cookie-settings" '
        'aria-label="Cookie settings" hidden>Cookie settings</button>'
    )


def test_every_optional_category_is_editable_by_default_in_policy_order():
    html = _render({"categories": "not-a-list"})

    assert [
        testid for testid in testids(html) if testid.startswith("cookie-toggle")
    ] == [
        "cookie-toggle-necessary",
        "cookie-toggle-preferences",
        "cookie-toggle-statistics",
        "cookie-toggle-marketing",
    ]


@pytest.mark.parametrize(
    "config, bottom",
    [
        ({"position": "bottom"}, True),
        ({"mode": "banner"}, True),
        ({"position": "center", "mode": "banner"}, False),
        ({}, False),
    ],
)
def test_position_bottom_or_legacy_banner_anchors_the_bar(config, bottom):
    html = _render(config)

    assert ("cookie-consent__backdrop--bottom" in html) is bottom


@pytest.mark.parametrize(
    "opacity, rendered",
    [(0.2, "0.2"), (5, "1"), (-1, "0"), ("x", "0.55"), (None, "0.55")],
)
def test_backdrop_opacity_is_clamped(opacity, rendered):
    html = _render({} if opacity is None else {"backdrop_opacity": opacity})

    assert f'style="background: rgba(0, 0, 0, {rendered})"' in html


def test_version_policy_url_and_no_settings_button_are_configurable():
    html = _render(
        {
            "consent_version": 3,
            "privacy_policy_url": "/datenschutz",
            "show_settings_button": False,
        }
    )

    assert 'data-consent-version="3"' in html
    assert 'href="/datenschutz"' in html
    assert "cookie-settings" not in html


def test_admin_css_is_inlined_and_cannot_close_its_style_element():
    html = _render({"css": ".cookie-consent{x:y}</style><b>"})

    assert (
        "<style data-cookie-consent-css>.cookie-consent{x:y}<\\/style><b></style>"
        in html
    )
