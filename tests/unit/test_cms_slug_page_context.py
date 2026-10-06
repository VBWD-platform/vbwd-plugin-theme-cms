"""S152-08 — adapters render a plugin route inside its CMS page (S152-06 §7).

fe-user mounts ``/shop/product/:slug`` as ``CmsPage`` with the fixed prop
``slug: 'shop-product-detail'``: the CMS page is chosen by that slug, while the
widgets inside it read the ROUTE's params (the product slug). The themed seam
``CmsPages.cms_slug_page_context(theme_request, cms_slug)`` does the same: it
resolves ``cms_slug`` and hands the request's own ``view_args`` to every
component as its route params.
"""
import json
from types import MappingProxyType

import pytest
from flask import Flask

from plugins.theme.theme import theme_api
from plugins.theme.theme.theme_api import ThemeApiError
from plugins.theme.theme.viewer import ANONYMOUS_VIEWER
from plugins.theme_cms.theme_cms import cms_api as cms_api_module
from plugins.theme_cms.theme_cms.pages import CmsPages
from plugins.theme_cms.theme_cms.registries import (
    ComponentTemplate,
    ComponentTemplateRegistry,
    default_page_type_registry,
)

LAYOUT = {
    "id": "layout-1",
    "slug": "shop-product-detail",
    "areas": [{"name": "product-detail", "type": "vue"}],
    "assignments": [
        {
            "area_name": "product-detail",
            "sort_order": 0,
            "widget": {
                "widget_type": "vue-component",
                "slug": "product-detail",
                "content_json": {"component": "RouteEcho"},
            },
        }
    ],
}
ANSWERS = {
    "/api/v1/cms/posts/shop-product-detail": {
        "slug": "shop-product-detail",
        "title": "Product",
        "type": "page",
        "resolved_layout_id": "layout-1",
    },
    "/api/v1/cms/layouts/layout-1": LAYOUT,
    "/api/v1/cms/config": {"home_slug": "index"},
}


class _Response:
    def __init__(self, status, body):
        self.status = status
        self.text = json.dumps(body)

    def json(self):
        return json.loads(self.text)


class _Client:
    def __init__(self):
        self.paths = []

    def request(self, method, path, **options):
        self.paths.append(path)
        if path in ANSWERS:
            return _Response(200, ANSWERS[path])
        return _Response(404, {"error": "Not found"})


class _ThemeRequest:
    def __init__(self, view_args):
        self.path = "/shop/product/mug"
        self.view_args = MappingProxyType(view_args)
        self.query_args = MappingProxyType({})
        self.viewer = ANONYMOUS_VIEWER
        self.http_request = None


@pytest.fixture
def client(monkeypatch):
    stub = _Client()
    monkeypatch.setattr(theme_api, "resolve_internal_api_client", lambda: stub)
    monkeypatch.setattr(cms_api_module, "resolve_internal_api_client", lambda: stub)
    return stub


def _cms_pages():
    components = ComponentTemplateRegistry()
    components.register(
        ComponentTemplate(
            "RouteEcho",
            "cms/components/route_echo.html.j2",
            lambda config, page, route_params, request: {
                "route_params": dict(route_params)
            },
        )
    )
    return CmsPages(default_page_type_registry(), components)


def _component_context(context):
    widget = context["cms_layout"]["areas"][0]["widgets"][0]
    return widget["component"]["context"]


def test_the_cms_page_is_chosen_by_slug_and_widgets_get_the_route_params(client):
    with Flask(__name__).app_context():
        context = _cms_pages().cms_slug_page_context(
            _ThemeRequest({"slug": "mug"}), "shop-product-detail"
        )

    assert context["cms_page"]["slug"] == "shop-product-detail"
    assert _component_context(context) == {"route_params": {"slug": "mug"}}
    assert "/api/v1/cms/posts/shop-product-detail" in client.paths


def test_an_unknown_cms_page_is_a_404_for_the_spa_fallback(client):
    with Flask(__name__).app_context(), pytest.raises(ThemeApiError) as raised:
        _cms_pages().cms_slug_page_context(_ThemeRequest({}), "no-such-page")

    assert raised.value.status == 404
