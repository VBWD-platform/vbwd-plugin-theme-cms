"""S152-06a §5 + W1 — which widgets an area renders (mirror of ``CmsLayoutRenderer.widgetsFor``).

* page assignments that carry a widget replace ALL layout widgets of that area;
* otherwise the layout's assignments are used;
* every widget of the chosen set renders, stable-sorted by ``sort_order``;
* a page assignment's ``config_override`` is applied per widget type
  (``applyPageOverride``); layout assignments are never overridden.
"""
import base64

from plugins.theme_cms.theme_cms.layout_areas import (
    apply_page_override,
    widgets_for_area,
)


def _widget(slug, widget_type="html", **fields):
    return {"id": f"id-{slug}", "slug": slug, "widget_type": widget_type, **fields}


def _assignment(area_name, sort_order, widget, **fields):
    return {
        "area_name": area_name,
        "sort_order": sort_order,
        "widget": widget,
        **fields,
    }


def _slugs(widgets):
    return [widget["slug"] for widget in widgets]


def test_layout_widgets_of_an_area_render_all_in_sort_order_stable_on_ties():
    layout_assignments = [
        _assignment("header", 2, _widget("c")),
        _assignment("header", 1, _widget("b-first")),
        _assignment("footer", 0, _widget("other-area")),
        _assignment("header", 1, _widget("b-second")),
        _assignment("header", 0, _widget("a")),
    ]

    widgets = widgets_for_area("header", layout_assignments, [])

    assert _slugs(widgets) == ["a", "b-first", "b-second", "c"]


def test_assignments_without_a_widget_are_skipped():
    layout_assignments = [
        _assignment("header", 0, None),
        _assignment("header", 1, _widget("x")),
    ]

    assert _slugs(widgets_for_area("header", layout_assignments, None)) == ["x"]


def test_page_assignments_replace_every_layout_widget_of_that_area_only():
    layout_assignments = [
        _assignment("sidebar", 0, _widget("layout-1")),
        _assignment("sidebar", 1, _widget("layout-2")),
        _assignment("footer", 0, _widget("layout-footer")),
    ]
    page_assignments = [
        _assignment("sidebar", 5, _widget("page-2")),
        _assignment("sidebar", 1, _widget("page-1")),
    ]

    assert _slugs(
        widgets_for_area("sidebar", layout_assignments, page_assignments)
    ) == [
        "page-1",
        "page-2",
    ]
    assert _slugs(widgets_for_area("footer", layout_assignments, page_assignments)) == [
        "layout-footer"
    ]


def test_page_assignments_without_widgets_fall_back_to_the_layout():
    layout_assignments = [_assignment("sidebar", 0, _widget("layout-1"))]
    page_assignments = [_assignment("sidebar", 0, None)]

    assert _slugs(
        widgets_for_area("sidebar", layout_assignments, page_assignments)
    ) == ["layout-1"]


def test_page_assignment_override_is_applied_but_layout_ones_never_are():
    widget = _widget("v", "vue-component", config={"a": 1, "b": 2}, source_css="x{}")
    override = {"config": {"b": 3}, "source_css": "y{}"}
    page_widgets = widgets_for_area(
        "hero", [], [_assignment("hero", 0, widget, config_override=override)]
    )
    layout_widgets = widgets_for_area(
        "hero", [_assignment("hero", 0, widget, config_override=override)], []
    )

    assert page_widgets[0]["config"] == {"a": 1, "b": 3}
    assert page_widgets[0]["source_css"] == "y{}"
    assert layout_widgets[0] is widget
    assert widget["config"] == {"a": 1, "b": 2}


def test_html_override_replaces_the_content_as_utf8_base64():
    widget = _widget(
        "h", content_json={"content": "old", "keep": True}, source_css="a{}"
    )

    merged = apply_page_override(widget, {"content_html": "<p>Grüße</p>"})

    assert base64.b64decode(merged["content_json"]["content"]).decode("utf-8") == (
        "<p>Grüße</p>"
    )
    assert merged["content_json"]["keep"] is True
    assert merged["source_css"] == "a{}"
    assert widget["content_json"]["content"] == "old"


def test_menu_override_replaces_items_and_css():
    widget = _widget("m", "menu", menu_items=[{"id": "1"}], source_css="a{}")

    merged = apply_page_override(
        widget, {"menu_items": [{"id": "2"}], "source_css": "b{}"}
    )

    assert merged["menu_items"] == [{"id": "2"}]
    assert merged["source_css"] == "b{}"


def test_absent_override_or_other_types_return_the_widget_unchanged():
    slideshow = _widget("s", "slideshow", source_css="a{}")
    html = _widget("h")

    assert apply_page_override(html, None) is html
    assert apply_page_override(html, {}) is html
    assert apply_page_override(slideshow, {"source_css": "b{}"}) is slideshow


def test_non_string_override_values_are_ignored():
    widget = _widget("h", content_json={"content": "old"}, source_css="a{}")

    merged = apply_page_override(widget, {"content_html": 7, "source_css": None})

    assert merged["content_json"]["content"] == "old"
    assert merged["source_css"] == "a{}"
