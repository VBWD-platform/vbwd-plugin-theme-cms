"""ContactForm (ContactForm.vue) and its POST fragment (S152-06b).

The page renders the form from the widget config. htmx posts it to
``POST /_render/_fragment/cms/contact``, which re-reads the widget's public
config, validates required fields like ``validateForm`` and calls the same
endpoint as the Vue component, ``POST /api/v1/contact`` with
``{widget_slug, _hp, fields}``. It answers the whole widget again: the success
state, or the form with its values and the field / global errors.
"""
from typing import Any, Callable, Dict, List, Mapping, Optional

from markupsafe import Markup

from plugins.theme.theme.theme_api import ThemeApiError

from ..cms_api import CmsApi
from ..markup import style_text

CmsApiFactory = Callable[[Any], Any]

CONTACT_FRAGMENT_PATH = "/_render/_fragment/cms/contact"
CHECKBOX_FIELD_TYPE = "checkbox"
RATE_LIMITED_STATUS = 429
HONEYPOT_FIELD = "_hp"
WIDGET_SLUG_FIELD = "widget_slug"
RATE_LIMITED_MESSAGE_KEY = "contactForm.rateLimited"
GENERIC_ERROR_MESSAGE_KEY = "common.errors.generic"


def _fields(widget_config: Mapping[str, Any]) -> List[Dict[str, Any]]:
    raw_fields = widget_config.get("fields")
    if not isinstance(raw_fields, list):
        return []
    return [
        {
            "id": str(field.get("id") or ""),
            "type": field.get("type") or "text",
            "label": field.get("label") or "",
            "required": field.get("required"),
            "options": list(field.get("options") or []),
        }
        for field in raw_fields
        if isinstance(field, Mapping)
    ]


def build_contact_form_context(
    widget_config: Mapping[str, Any],
    page: Mapping[str, Any],
    route_params: Mapping[str, Any],
    theme_request: Any,
    values: Optional[Mapping[str, Any]] = None,
    field_errors: Optional[List[str]] = None,
    global_error: Optional[Mapping[str, str]] = None,
    submitted: bool = False,
) -> Dict[str, Any]:
    """The widget in one of its states (the page render is the empty form)."""
    return {
        "action": CONTACT_FRAGMENT_PATH,
        "widget_slug": widget_config.get(WIDGET_SLUG_FIELD) or "",
        "is_configured": bool(widget_config.get("recipient_email")),
        "success_message": widget_config.get("success_message") or "",
        "fields": _fields(widget_config),
        "captcha_html": Markup(widget_config.get("captcha_html") or ""),
        "analytics_html": Markup(widget_config.get("analytics_html") or ""),
        "css": style_text(widget_config.get("css")),
        "values": dict(values or {}),
        "field_errors": list(field_errors or []),
        "global_error": global_error,
        "submitted": submitted,
    }


def _submitted_values(form: Any, fields: List[Dict[str, Any]]) -> Dict[str, Any]:
    values: Dict[str, Any] = {}
    for field in fields:
        if field["type"] == CHECKBOX_FIELD_TYPE:
            values[field["id"]] = form.getlist(field["id"])
        else:
            values[field["id"]] = form.get(field["id"]) or ""
    return values


def _missing_required(
    fields: List[Dict[str, Any]], values: Mapping[str, Any]
) -> List[str]:
    missing = []
    for field in fields:
        value = values.get(field["id"])
        is_empty = (
            len(value) == 0 if isinstance(value, list) else not str(value or "").strip()
        )
        if field["required"] and is_empty:
            missing.append(field["id"])
    return missing


def _global_error(api_error: ThemeApiError) -> Dict[str, str]:
    if api_error.status == RATE_LIMITED_STATUS:
        return {"key": RATE_LIMITED_MESSAGE_KEY, "message": ""}
    return {"key": GENERIC_ERROR_MESSAGE_KEY, "message": api_error.message}


def build_contact_fragment_context(
    theme_request: Any, cms_api_factory: CmsApiFactory = CmsApi
) -> Dict[str, Any]:
    """Validate + submit one posted form; the widget's next state."""
    form = theme_request.query_args
    widget_slug = str(form.get(WIDGET_SLUG_FIELD) or "")
    cms_api = cms_api_factory(theme_request)
    widget = cms_api.widget_by_slug(widget_slug)
    widget_config = {**(widget.get("config") or {}), WIDGET_SLUG_FIELD: widget_slug}
    fields = _fields(widget_config)
    values = _submitted_values(form, fields)
    state: Dict[str, Any] = {"values": values}
    missing = _missing_required(fields, values)
    if missing:
        state["field_errors"] = missing
    else:
        payload = {
            WIDGET_SLUG_FIELD: widget_slug,
            HONEYPOT_FIELD: form.get(HONEYPOT_FIELD) or "",
            "fields": values,
        }
        try:
            cms_api.submit_contact(payload)
            state["submitted"] = True
        except ThemeApiError as api_error:
            state["global_error"] = _global_error(api_error)
    return {
        "component_context": build_contact_form_context(
            widget_config, {}, {}, theme_request, **state
        )
    }
