"""S152-06a §6 — what each widget type hands its template (mirror of ``CmsWidgetRenderer``).

* html: ``content_json.content`` base64 → UTF-8 (``decodeURIComponent(escape(atob()))``),
  the raw value when it does not decode; scripts stay (they run natively in SSR);
* menu: root items + ONE child level; href = ``url`` || ``/<page_slug>`` || ``#``;
  a parent's own link is ``#``; target defaults to ``_self``; ``config.show_cart``
  asks for the ``CartBadge`` component (absent → an empty cart item);
* slideshow: ``content_json.images`` → url/alt/caption;
* vue-component: ``content_json.component`` (legacy ``config.component_name``)
  resolved in the component registry; missing → the missing marker; an SPA-only
  plugin's component → an SPA link card; an unregistered component whose themed
  twin is still pending (S153) hands the whole page to the SPA (404, D5);
* every widget's ``source_css`` is a style text that cannot close its ``<style>``.
"""
import base64

import pytest

from plugins.theme.theme.theme_api import NOT_FOUND, ThemeApiError
from plugins.theme_cms.theme_cms.registries import (
    ComponentTemplate,
    ComponentTemplateRegistry,
)
from plugins.theme_cms.theme_cms.widget_views import WidgetViewBuilder

PAGE = {"slug": "about", "title": "About"}


def _builder(registry=None, route_params=None):
    return WidgetViewBuilder(
        registry or ComponentTemplateRegistry(),
        page=PAGE,
        route_params=route_params or {},
        theme_request="the-theme-request",
    )


def _encoded(html):
    return base64.b64encode(html.encode("utf-8")).decode("ascii")


def test_html_content_is_base64_utf8_decoded_with_scripts_kept():
    html = "<p>Grüße</p><script>window.x = 1</script>"
    view = _builder().build(
        {
            "slug": "h",
            "widget_type": "html",
            "content_json": {"content": _encoded(html)},
        }
    )

    assert view["html"] == html


def test_html_that_does_not_decode_is_used_raw_and_absent_is_empty():
    builder = _builder()

    assert (
        builder.build(
            {"widget_type": "html", "content_json": {"content": "<b>not b64"}}
        )["html"]
        == "<b>not b64"
    )
    assert builder.build({"widget_type": "html", "content_json": None})["html"] == ""


def test_widget_css_cannot_close_its_style_element():
    view = _builder().build(
        {"widget_type": "html", "source_css": "a > b{} </STYLE><script>x</script>"}
    )

    assert "</STYLE" not in view["css"] and "</style" not in view["css"].lower()
    assert "a > b{}" in view["css"]


def test_menu_has_root_items_one_child_level_and_the_href_rule():
    items = [
        {
            "id": "1",
            "parent_id": None,
            "label": "Docs",
            "url": None,
            "page_slug": "docs",
            "target": None,
            "icon": None,
        },
        {
            "id": "2",
            "parent_id": "1",
            "label": "API",
            "url": "https://x/api",
            "page_slug": None,
            "target": "_blank",
            "icon": "*",
        },
        {
            "id": "3",
            "parent_id": "1",
            "label": "Guide",
            "url": None,
            "page_slug": "guide",
            "target": None,
            "icon": None,
        },
        {
            "id": "4",
            "parent_id": "2",
            "label": "Deep",
            "url": None,
            "page_slug": None,
            "target": None,
            "icon": None,
        },
        {
            "id": "5",
            "parent_id": None,
            "label": "About",
            "url": None,
            "page_slug": "about",
            "target": None,
            "icon": None,
        },
        {
            "id": "6",
            "parent_id": None,
            "label": "Nowhere",
            "url": None,
            "page_slug": None,
            "target": None,
            "icon": None,
        },
    ]
    view = _builder().build(
        {"slug": "main-menu", "widget_type": "menu", "menu_items": items}
    )

    root_items = view["menu_items"]
    assert [item["label"] for item in root_items] == ["Docs", "About", "Nowhere"]
    docs, about, nowhere = root_items
    assert docs["href"] == "#" and docs["has_children"] is True
    assert [
        (child["label"], child["href"], child["target"]) for child in docs["children"]
    ] == [
        ("API", "https://x/api", "_blank"),
        ("Guide", "/guide", "_self"),
    ]
    assert about["href"] == "/about" and about["children"] == []
    assert nowhere["href"] == "#" and nowhere["has_children"] is False
    assert view["show_cart"] is False


def _registry_with(*names, build_context=None):
    registry = ComponentTemplateRegistry()
    for name in names:
        registry.register(
            ComponentTemplate(
                name=name,
                template=f"cms/components/{name}.html.j2",
                build_context=build_context or (lambda *args: {"built": True}),
            )
        )
    return registry


def test_menu_show_cart_asks_for_the_cart_badge_component():
    menu = {"widget_type": "menu", "menu_items": [], "config": {"show_cart": True}}

    without_badge = _builder().build(menu)
    with_badge = _builder(_registry_with("CartBadge")).build(menu)

    assert without_badge["show_cart"] is True and without_badge["cart_badge"] is None
    assert with_badge["cart_badge"]["template"] == "cms/components/CartBadge.html.j2"


def test_slideshow_images_are_listed_with_defaults():
    view = _builder().build(
        {
            "widget_type": "slideshow",
            "content_json": {"images": [{"url": "/a.jpg", "caption": "A"}, {}]},
        }
    )

    assert view["slides"] == [
        {"url": "/a.jpg", "alt": "", "caption": "A"},
        {"url": "", "alt": "", "caption": ""},
    ]


def test_vue_component_resolves_by_content_json_then_legacy_config_name():
    received = []

    def build_context(widget_config, page, route_params, theme_request):
        received.append((widget_config, page, route_params, theme_request))
        return {"title": "crumbs"}

    registry = _registry_with("CmsBreadcrumb", build_context=build_context)
    builder = _builder(registry, route_params={"slug": "about"})

    canonical = builder.build(
        {
            "slug": "crumbs",
            "widget_type": "vue-component",
            "content_json": {"component": "CmsBreadcrumb"},
            "config": {"a": 1},
        }
    )
    legacy = builder.build(
        {
            "slug": "legacy",
            "widget_type": "vue-component",
            "content_json": None,
            "config": {"component_name": "CmsBreadcrumb"},
        }
    )

    assert canonical["component"] == {
        "template": "cms/components/CmsBreadcrumb.html.j2",
        "context": {"title": "crumbs"},
    }
    assert legacy["component"]["template"] == "cms/components/CmsBreadcrumb.html.j2"
    assert received[0] == (
        {"a": 1, "widget_slug": "crumbs"},
        PAGE,
        {"slug": "about"},
        "the-theme-request",
    )


def test_an_unknown_vue_component_is_missing_and_names_itself_safely():
    view = _builder().build(
        {
            "widget_type": "vue-component",
            "content_json": {"component": "Evil--><script>"},
        }
    )

    assert view["component"] is None and view["spa_link_href"] is None
    assert view["component_name"] == "Evilscript"


def test_an_spa_only_plugin_component_becomes_an_spa_link():
    view = _builder().build(
        {
            "widget_type": "vue-component",
            "content_json": {"component": "TukTukIntakeWidget"},
        }
    )

    assert view["component"] is None
    assert view["spa_link_href"] == "/tuktuk/chat"


@pytest.mark.parametrize(
    "component_name",
    ["GhrmCatalogueContent", "GhrmPackageDetail", "MeinchatChatWidget"],
)
def test_a_pending_adapter_component_hands_the_page_to_the_spa(component_name):
    # S152-11c: ghrm's catalogue page (`/software`) rendered with its catalogue
    # missing is a broken page; the SPA renders it whole, so the theme 404s and
    # nginx falls back to the SPA (D5).
    with pytest.raises(ThemeApiError) as raised:
        _builder().build(
            {
                "widget_type": "vue-component",
                "content_json": {"component": component_name},
            }
        )

    assert raised.value.status == NOT_FOUND


def test_a_registered_twin_of_a_pending_component_renders_instead_of_handing_off():
    view = _builder(_registry_with("GhrmCatalogueContent")).build(
        {
            "widget_type": "vue-component",
            "content_json": {"component": "GhrmCatalogueContent"},
        }
    )

    assert (
        view["component"]["template"] == "cms/components/GhrmCatalogueContent.html.j2"
    )
