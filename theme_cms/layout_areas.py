"""Which widgets a layout area renders — the mirror of fe-user ``CmsLayoutRenderer`` (W1).

Page assignments that carry a widget replace ALL layout widgets of the same
area; otherwise the layout's own assignments apply. Every widget of the chosen
set renders, stable-sorted by ``sort_order``. A page assignment's
``config_override`` is applied per widget type (``applyPageOverride``); the
layout path is never overridden. Inputs are the cms public API payloads, which
the cms already filtered by the caller's access levels.
"""
import base64
from typing import Any, Dict, List, Mapping, Optional, Sequence

Widget = Dict[str, Any]
Assignment = Mapping[str, Any]


def _encode_widget_html(html: str) -> str:
    """The encoding the admin HTML editor uses (UTF-8 → base64), so one decoder reads both."""
    return base64.b64encode(html.encode("utf-8")).decode("ascii")


def _with_source_css(widget: Widget, override: Mapping[str, Any]) -> Widget:
    if isinstance(override.get("source_css"), str):
        widget["source_css"] = override["source_css"]
    return widget


def _override_vue_component(widget: Widget, override: Mapping[str, Any]) -> Widget:
    merged = dict(widget)
    merged["config"] = {
        **(widget.get("config") or {}),
        **(override.get("config") or {}),
    }
    return _with_source_css(merged, override)


def _override_html(widget: Widget, override: Mapping[str, Any]) -> Widget:
    merged = dict(widget)
    if isinstance(override.get("content_html"), str):
        merged["content_json"] = {
            **(widget.get("content_json") or {}),
            "content": _encode_widget_html(override["content_html"]),
        }
    return _with_source_css(merged, override)


def _override_menu(widget: Widget, override: Mapping[str, Any]) -> Widget:
    merged = dict(widget)
    if isinstance(override.get("menu_items"), list):
        merged["menu_items"] = override["menu_items"]
    return _with_source_css(merged, override)


_OVERRIDES_BY_WIDGET_TYPE = {
    "vue-component": _override_vue_component,
    "html": _override_html,
    "menu": _override_menu,
}


def apply_page_override(
    widget: Widget, override: Optional[Mapping[str, Any]]
) -> Widget:
    """A NEW widget with the per-page override applied; unchanged when there is none."""
    apply_override = _OVERRIDES_BY_WIDGET_TYPE.get(str(widget.get("widget_type")))
    if not override or apply_override is None:
        return widget
    return apply_override(widget, override)


def _sorted_area_assignments(
    assignments: Optional[Sequence[Assignment]], area_name: str
) -> List[Assignment]:
    area_assignments = [
        assignment
        for assignment in assignments or []
        if assignment.get("area_name") == area_name and assignment.get("widget")
    ]
    # ``sorted`` is stable, so ties keep the API order (as the SPA's sort).
    return sorted(
        area_assignments, key=lambda assignment: assignment.get("sort_order") or 0
    )


def widgets_for_area(
    area_name: str,
    layout_assignments: Optional[Sequence[Assignment]],
    page_assignments: Optional[Sequence[Assignment]],
) -> List[Widget]:
    """The widgets ``area_name`` renders, in order (page assignments win, W1)."""
    chosen_page_assignments = _sorted_area_assignments(page_assignments, area_name)
    if chosen_page_assignments:
        return [
            apply_page_override(assignment["widget"], assignment.get("config_override"))
            for assignment in chosen_page_assignments
        ]
    return [
        assignment["widget"]
        for assignment in _sorted_area_assignments(layout_assignments, area_name)
    ]
