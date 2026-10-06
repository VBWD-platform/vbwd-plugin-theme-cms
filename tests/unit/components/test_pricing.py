"""S152-06b — NativePricingPlans (→ landing1 ``Landing1View.vue``) and AddonCatalog.

Both read ANOTHER plugin's public API (subscription): ``GET /api/v1/tarif-plans
[?category=]`` and ``GET /api/v1/addons/``, through ``call_api`` (HTTP in-process,
never an import). A 404 — the plugin is absent, or the category unknown — renders
the empty state; another failure the error state. Prices are formatted like
fe-core ``formatMoney`` in en-US (round half up to cents, operating currency EUR
when the payload names none); add-ons show the gross side, as PriceDisplay does
without display-mode props.
"""
import pytest

from plugins.theme.theme.theme_api import ThemeApiError
from plugins.theme_cms.tests.unit.components.fakes import FakeThemeRequest
from plugins.theme_cms.tests.unit.dom_contract import canonical, testids
from plugins.theme_cms.tests.unit.template_harness import render_component, theme_plugin
from plugins.theme_cms.theme_cms.components.pricing import (
    build_addon_catalog_context,
    build_native_pricing_plans_context,
    format_billing_period,
    format_money,
)

CHECK_ICON = (
    '<svg class="plan-features__check" viewBox="0 0 20 20" aria-hidden="true">'
    '<path d="M7.5 13.5 4 10l-1.2 1.2L7.5 16 17 6.5 15.8 5.3z" fill="currentColor"></path></svg>'
)


@pytest.fixture(autouse=True)
def isolated_var_directory(tmp_path, monkeypatch):
    monkeypatch.setenv("VBWD_VAR_DIR", str(tmp_path / "var"))


class FakePublicApi:
    def __init__(self, answer):
        self.answer = answer
        self.calls = []

    def __call__(self, theme_request, path, query=None):
        self.calls.append((path, query))
        if isinstance(self.answer, Exception):
            raise self.answer
        return self.answer


def _render(template, context):
    return render_component(
        theme_plugin(), f"cms/components/{template}.html.j2", context
    )


@pytest.mark.parametrize(
    "amount, currency, expected",
    [
        (1234.5, "USD", "$1,234.50"),
        (19.99, "eur", "€19.99"),
        (1.005, "EUR", "€1.01"),
        (-5, "EUR", "-€5.00"),
        (10, "CHF", "CHF 10.00"),
        (10, None, "€10.00"),
        ("12.3", "GBP", "£12.30"),
        (None, "JPY", "¥0.00"),
    ],
)
def test_format_money_matches_fe_core_format_money_en_us(amount, currency, expected):
    assert format_money(amount, currency) == expected


@pytest.mark.parametrize(
    "period, label",
    [
        ("monthly", "month"),
        ("YEARLY", "year"),
        ("annual", "year"),
        ("Quarterly", "quarterly"),
    ],
)
def test_billing_period_labels(period, label):
    assert format_billing_period(period) == label


PLANS = {
    "plans": [
        {
            "id": "1",
            "name": "Basic",
            "slug": "basic",
            "display_price": 9,
            "display_currency": "EUR",
            "billing_period": "monthly",
            "description": "Starter",
        },
        {
            "id": "2",
            "name": "Pro",
            "slug": "pro",
            "display_price": 29,
            "display_currency": "EUR",
            "billing_period": "yearly",
        },
        {
            "id": "3",
            "name": "Old",
            "slug": "old",
            "display_price": 1,
            "display_currency": "EUR",
            "is_active": False,
        },
    ]
}


def test_category_mode_fetches_the_category_and_renders_the_landing1_cards():
    public_api = FakePublicApi(PLANS)
    config = {
        "category": "root",
        "heading": "Plans",
        "subtitle": "  ",
        "features": ["Fast", " ", "Safe"],
        "highlight_slug": "pro",
        "theme": "teal",
        "cta_label": "Buy",
    }

    context = build_native_pricing_plans_context(
        config, {}, {}, FakeThemeRequest(), public_api
    )
    html = _render("native_pricing_plans", context)

    assert public_api.calls == [("/api/v1/tarif-plans", {"category": "root"})]
    features = (
        '<ul class="plan-features" data-testid="plan-features">'
        f'<li class="plan-features__item">{CHECK_ICON}<span>Fast</span></li>'
        f'<li class="plan-features__item">{CHECK_ICON}<span>Safe</span></li></ul>'
    )
    assert canonical(html) == canonical(
        '<div class="landing1 landing1--teal" data-testid="landing1-root">'
        '<div class="landing1-header"><h1 data-testid="landing1-title">Plans</h1>'
        '<p class="subtitle">Select the plan that works best for you</p></div>'
        '<div class="plans-grid" data-testid="landing1-plans">'
        '<div class="plan-card" data-testid="plan-card-basic">'
        '<h2 class="plan-name">Basic</h2>'
        '<div class="plan-price"><span class="plan-price__amount">€9.00</span>'
        '<span class="billing-period">/month</span></div>'
        '<p class="plan-description">Starter</p>'
        + features
        + '<form method="get" action="/checkout"><input type="hidden" name="tarif_plan_id" value="basic">'
        '<button type="submit" class="choose-plan-btn" data-testid="choose-plan-basic">Buy</button></form>'
        "</div>"
        '<div class="plan-card plan-card--featured" data-testid="plan-card-pro">'
        '<div class="plan-card__badge" data-testid="plan-card-badge">Most Popular</div>'
        '<h2 class="plan-name">Pro</h2>'
        '<div class="plan-price"><span class="plan-price__amount">€29.00</span>'
        '<span class="billing-period">/year</span></div>'
        + features
        + '<form method="get" action="/checkout"><input type="hidden" name="tarif_plan_id" value="pro">'
        '<button type="submit" class="choose-plan-btn" data-testid="choose-plan-pro">Buy</button></form>'
        "</div></div></div>"
    )


def test_plans_mode_filters_by_slug_and_ignores_the_category():
    public_api = FakePublicApi(PLANS)

    context = build_native_pricing_plans_context(
        {"mode": "plans", "plan_slugs": ["pro"], "category": "ignored"},
        {},
        {},
        FakeThemeRequest(),
        public_api,
    )

    assert public_api.calls == [("/api/v1/tarif-plans", None)]
    assert [plan["slug"] for plan in context["plans"]] == ["pro"]
    assert context["theme"] == "default"


def test_the_legacy_props_category_is_honoured():
    public_api = FakePublicApi({"plans": []})

    build_native_pricing_plans_context(
        {"props": {"category": "legacy"}}, {}, {}, FakeThemeRequest(), public_api
    )

    assert public_api.calls == [("/api/v1/tarif-plans", {"category": "legacy"})]


def test_a_missing_subscription_plugin_404_renders_the_empty_state():
    context = build_native_pricing_plans_context(
        {}, {}, {}, FakeThemeRequest(), FakePublicApi(ThemeApiError(404, "Not Found"))
    )

    html = _render("native_pricing_plans", context)

    assert testids(html) == ["landing1-root", "landing1-title", "landing1-empty"]
    assert "No plans available at this time." in html
    assert "Choose Your Plan" in html


def test_another_failure_renders_the_error_state_with_a_retry():
    context = build_native_pricing_plans_context(
        {},
        {},
        {},
        FakeThemeRequest(path="/pricing"),
        FakePublicApi(ThemeApiError(500, "boom")),
    )

    html = _render("native_pricing_plans", context)

    assert (
        '<div class="error-state" data-testid="landing1-error"><p>Failed to load plans</p>'
        '<form method="get" action="/pricing"><button type="submit" class="retry-btn">Retry</button></form></div>'
    ) in html


def test_the_widget_css_is_inlined_safely():
    context = build_native_pricing_plans_context(
        {"css": ".landing1{a:b}</style>"},
        {},
        {},
        FakeThemeRequest(),
        FakePublicApi({"plans": []}),
    )

    assert "<style data-native-pricing-css>.landing1{a:b}<\\/style></style>" in _render(
        "native_pricing_plans", context
    )


ADDONS = {
    "addons": [
        {
            "id": "a",
            "slug": "seo",
            "name": "SEO <Pack>",
            "description": "Rank",
            "price": 10,
            "price_info": {
                "net_amount": "10.00",
                "gross_amount": "11.90",
                "price": {"currency": "EUR"},
            },
        },
        {"id": "b", "slug": "x", "name": "Bare", "description": None, "price": "5"},
    ]
}


def test_addon_catalog_cards_show_the_gross_price():
    public_api = FakePublicApi(ADDONS)

    context = build_addon_catalog_context(
        {"heading": "Add-ons"}, {}, {}, FakeThemeRequest(), public_api
    )
    html = _render("addon_catalog", context)

    assert public_api.calls == [("/api/v1/addons/", None)]
    assert canonical(html) == canonical(
        '<div class="addon-catalog" data-testid="addon-catalog">'
        '<h2 class="addon-catalog__heading">Add-ons</h2>'
        '<div class="addon-catalog__grid" data-testid="addon-catalog-grid">'
        '<div class="addon-card" data-testid="addon-card">'
        '<h3 class="addon-card__name" data-testid="addon-card-name">SEO &lt;Pack&gt;</h3>'
        '<p class="addon-card__description">Rank</p>'
        '<p class="addon-card__price" data-testid="addon-card-price"><span class="price-display">'
        '<span class="price-display__amount" data-testid="price-amount">€11.90</span></span></p>'
        "</div>"
        '<div class="addon-card" data-testid="addon-card">'
        '<h3 class="addon-card__name" data-testid="addon-card-name">Bare</h3>'
        '<p class="addon-card__price" data-testid="addon-card-price"><span class="price-display">'
        '<span class="price-display__amount" data-testid="price-amount">€5.00</span></span></p>'
        "</div></div></div>"
    )


@pytest.mark.parametrize(
    "answer, testid, text",
    [
        (
            ThemeApiError(404, "Not Found"),
            "addon-catalog-empty",
            "No add-ons available.",
        ),
        ({"addons": []}, "addon-catalog-empty", "No add-ons available."),
        (ThemeApiError(500, "Database down"), "addon-catalog-error", "Database down"),
        (ThemeApiError(500, ""), "addon-catalog-error", "Failed to load add-ons"),
    ],
)
def test_addon_catalog_empty_and_error_states(answer, testid, text):
    context = build_addon_catalog_context(
        {}, {}, {}, FakeThemeRequest(), FakePublicApi(answer)
    )

    html = _render("addon_catalog", context)

    assert testids(html) == ["addon-catalog", testid]
    assert text in html
