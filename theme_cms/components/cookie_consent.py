"""CookieConsent (CookieConsent.vue) — the server half of the consent dialog (S152-06b).

The record lives in the visitor's localStorage (``vbwd_cookie_consent``), which a
server render cannot read: the dialog ships hidden and the cms runtime
(``partials/cms_cookie_consent_runtime.js``) opens it when a decision is needed,
writing the same record shape and Consent Mode signals as ``useConsent``.
"""
import math
from typing import Any, Dict, List, Mapping

from ..markup import style_text

DEFAULT_CONSENT_VERSION = 1
DEFAULT_PRIVACY_POLICY_URL = "/privacy"
DEFAULT_BACKDROP_OPACITY = 0.55
MIN_OPACITY = 0.0
MAX_OPACITY = 1.0
NECESSARY_CATEGORY = "necessary"
OPTIONAL_CATEGORIES = ("preferences", "statistics", "marketing")
POSITIONS = ("center", "bottom")
BOTTOM_POSITION = "bottom"
LEGACY_BANNER_MODE = "banner"


def _position(widget_config: Mapping[str, Any]) -> str:
    explicit = widget_config.get("position")
    if explicit in POSITIONS:
        return str(explicit)
    return (
        BOTTOM_POSITION if widget_config.get("mode") == LEGACY_BANNER_MODE else "center"
    )


def _backdrop_opacity(widget_config: Mapping[str, Any]) -> str:
    raw = widget_config.get("backdrop_opacity", DEFAULT_BACKDROP_OPACITY)
    try:
        opacity = float(raw if raw is not None else DEFAULT_BACKDROP_OPACITY)
    except (TypeError, ValueError):
        opacity = DEFAULT_BACKDROP_OPACITY
    if math.isnan(opacity):
        opacity = DEFAULT_BACKDROP_OPACITY
    clamped = min(MAX_OPACITY, max(MIN_OPACITY, opacity))
    # The SPA interpolates a JS number: 1 → "1", 0.2 → "0.2".
    return f"{clamped:g}"


def _editable_categories(widget_config: Mapping[str, Any]) -> List[str]:
    configured = widget_config.get("categories")
    if not isinstance(configured, list):
        configured = [NECESSARY_CATEGORY, *OPTIONAL_CATEGORIES]
    return [NECESSARY_CATEGORY] + [
        category for category in OPTIONAL_CATEGORIES if category in configured
    ]


def _consent_version(widget_config: Mapping[str, Any]) -> int:
    version = widget_config.get("consent_version")
    if isinstance(version, bool) or not isinstance(version, (int, float)):
        return DEFAULT_CONSENT_VERSION
    return int(version) if version > 0 else DEFAULT_CONSENT_VERSION


def build_cookie_consent_context(
    widget_config: Mapping[str, Any],
    page: Mapping[str, Any],
    route_params: Mapping[str, Any],
    theme_request: Any,
) -> Dict[str, Any]:
    return {
        "consent_version": _consent_version(widget_config),
        "privacy_policy_url": widget_config.get("privacy_policy_url")
        or DEFAULT_PRIVACY_POLICY_URL,
        "is_bottom": _position(widget_config) == BOTTOM_POSITION,
        "additional_text": widget_config.get("additional_text") or "",
        "backdrop_opacity": _backdrop_opacity(widget_config),
        "show_settings_button": widget_config.get("show_settings_button") is not False,
        "categories": _editable_categories(widget_config),
        "css": style_text(widget_config.get("css")),
    }
