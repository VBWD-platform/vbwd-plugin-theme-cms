"""NativePricingPlans (→ landing1 ``Landing1View.vue``) and AddonCatalog (S152-06b).

Both list another plugin's sellables through its public API — ``GET
/api/v1/tarif-plans`` and ``GET /api/v1/addons/`` — via ``call_api`` (an
in-process HTTP call, never an import). A 404 means the plugin is absent (or the
category unknown): the empty state. Prices follow fe-core ``formatMoney`` in
en-US: rounded half up to cents, the operating currency (EUR) when the payload
names none.
"""
import math
from typing import Any, Callable, Dict, List, Mapping, Optional

from plugins.theme.theme.theme_api import NOT_FOUND, ThemeApiError, call_api

from ..markup import style_text

PublicApiGet = Callable[[Any, str, Optional[Mapping[str, Any]]], Any]

TARIF_PLANS_PATH = "/api/v1/tarif-plans"
ADDONS_PATH = "/api/v1/addons/"
OPERATING_CURRENCY = "EUR"
CENTS_EPSILON = 1e-9
CENTS_PER_UNIT = 100
# The en-US ``Intl.NumberFormat`` currency prefixes; other codes print "CODE ".
CURRENCY_SYMBOLS = {
    "USD": "$",
    "EUR": "€",
    "GBP": "£",
    "JPY": "¥",
    "CNY": "CN¥",
    "INR": "₹",
    "CAD": "CA$",
    "AUD": "A$",
    "BRL": "R$",
    "MXN": "MX$",
    "KRW": "₩",
    "ILS": "₪",
    "HKD": "HK$",
    "NZD": "NZ$",
    "TWD": "NT$",
    "VND": "₫",
    "PHP": "₱",
}
NON_BREAKING_SPACE = " "
ALLOWED_THEMES = ("default", "light", "dark", "teal", "indigo", "emerald")
DEFAULT_THEME = "default"
CATEGORY_MODE = "category"
PLANS_MODE = "plans"
PLANS_ERROR_MESSAGE = "Failed to load plans"
ADDONS_ERROR_MESSAGE = "Failed to load add-ons"
BILLING_PERIOD_LABELS = {
    "monthly": "month",
    "yearly": "year",
    "annual": "year",
    "weekly": "week",
    "MONTHLY": "month",
    "YEARLY": "year",
}
DEFAULT_BILLING_PERIOD = "month"


def public_api_get(
    theme_request: Any, path: str, query: Optional[Mapping[str, Any]] = None
) -> Any:
    return call_api(theme_request, "GET", path, query=query)


def _round_to_cents(value: float) -> float:
    return math.floor((value + CENTS_EPSILON) * CENTS_PER_UNIT + 0.5) / CENTS_PER_UNIT


def format_money(value: Any, currency: Optional[str] = None) -> str:
    """fe-core ``formatMoney`` with the en-US locale."""
    try:
        amount = float(value) if value is not None else 0.0
    except (TypeError, ValueError):
        amount = 0.0
    if math.isnan(amount):
        amount = 0.0
    rounded = _round_to_cents(amount)
    code = (currency or OPERATING_CURRENCY).upper()
    prefix = CURRENCY_SYMBOLS.get(code, code + NON_BREAKING_SPACE)
    sign = "-" if rounded < 0 else ""
    return f"{sign}{prefix}{abs(rounded):,.2f}"


def format_billing_period(period: Optional[str]) -> str:
    if not period:
        return DEFAULT_BILLING_PERIOD
    return BILLING_PERIOD_LABELS.get(period, period.lower())


def _text(widget_config: Mapping[str, Any], key: str) -> Optional[str]:
    """A non-blank string config value, else ``None`` (the SPA's ``str()`` helper)."""
    value = widget_config.get(key)
    return value if isinstance(value, str) and value.strip() else None


def _category(widget_config: Mapping[str, Any], mode: str) -> Optional[str]:
    if mode != CATEGORY_MODE:
        return None
    legacy_props = widget_config.get("props") or {}
    return widget_config.get("category") or legacy_props.get("category")


def _plan_view(
    plan: Mapping[str, Any], highlight_slug: Optional[str]
) -> Dict[str, Any]:
    return {
        "name": plan.get("name") or "",
        "slug": plan.get("slug") or "",
        "description": plan.get("description") or "",
        "price_label": format_money(
            plan.get("display_price"), plan.get("display_currency")
        ),
        "billing_label": (
            format_billing_period(plan["billing_period"])
            if plan.get("billing_period")
            else None
        ),
        "is_featured": bool(highlight_slug) and plan.get("slug") == highlight_slug,
    }


def _load_plans(
    public_api: PublicApiGet, theme_request: Any, category: Optional[str]
) -> List[Mapping[str, Any]]:
    try:
        body = public_api(
            theme_request,
            TARIF_PLANS_PATH,
            {"category": category} if category else None,
        )
    except ThemeApiError as api_error:
        if api_error.status == NOT_FOUND:
            return []
        raise
    return [
        plan for plan in body.get("plans") or [] if plan.get("is_active") is not False
    ]


def build_native_pricing_plans_context(
    widget_config: Mapping[str, Any],
    page: Mapping[str, Any],
    route_params: Mapping[str, Any],
    theme_request: Any,
    public_api: PublicApiGet = public_api_get,
) -> Dict[str, Any]:
    mode = widget_config.get("mode") or CATEGORY_MODE
    raw_slugs = widget_config.get("plan_slugs")
    plan_slugs = raw_slugs if mode == PLANS_MODE and isinstance(raw_slugs, list) else []
    theme = _text(widget_config, "theme")
    features = widget_config.get("features")
    context: Dict[str, Any] = {
        "theme": theme if theme in ALLOWED_THEMES else DEFAULT_THEME,
        "heading": (_text(widget_config, "heading") or "").strip(),
        "subtitle": (_text(widget_config, "subtitle") or "").strip(),
        "cta_label": (_text(widget_config, "cta_label") or "").strip(),
        "badge": (_text(widget_config, "highlight_badge") or "").strip(),
        "image_url": _text(widget_config, "image_url"),
        "features": [
            str(feature).strip()
            for feature in (features if isinstance(features, list) else [])
            if str(feature).strip()
        ],
        "css": style_text(widget_config.get("css")),
        "retry_href": theme_request.path,
        "error": None,
        "plans": [],
    }
    try:
        plans = _load_plans(public_api, theme_request, _category(widget_config, mode))
    except ThemeApiError:
        context["error"] = PLANS_ERROR_MESSAGE
        return context
    if plan_slugs:
        plans = [plan for plan in plans if plan.get("slug") in plan_slugs]
    highlight_slug = _text(widget_config, "highlight_slug")
    context["plans"] = [_plan_view(plan, highlight_slug) for plan in plans]
    return context


def _addon_view(addon: Mapping[str, Any]) -> Dict[str, Any]:
    price_info = addon.get("price_info") or {}
    gross_amount = price_info.get("gross_amount")
    return {
        "name": addon.get("name") or "",
        "description": addon.get("description") or "",
        "price_label": format_money(
            gross_amount if gross_amount is not None else addon.get("price"),
            (price_info.get("price") or {}).get("currency"),
        ),
    }


def build_addon_catalog_context(
    widget_config: Mapping[str, Any],
    page: Mapping[str, Any],
    route_params: Mapping[str, Any],
    theme_request: Any,
    public_api: PublicApiGet = public_api_get,
) -> Dict[str, Any]:
    context: Dict[str, Any] = {
        "heading": widget_config.get("heading") or "",
        "error": None,
        "addons": [],
    }
    try:
        body = public_api(theme_request, ADDONS_PATH, None)
    except ThemeApiError as api_error:
        if api_error.status != NOT_FOUND:
            context["error"] = api_error.message or ADDONS_ERROR_MESSAGE
        return context
    context["addons"] = [_addon_view(addon) for addon in body.get("addons") or []]
    return context
