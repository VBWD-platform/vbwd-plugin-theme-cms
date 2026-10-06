"""S152-06b — the cms endpoints the components call, through core C2 (D3).

``search`` → ``GET /api/v1/cms/search`` (falsy filters dropped, as axios drops
undefined params), ``widget_by_slug`` → ``GET /api/v1/cms/widgets/by-slug/<slug>``
(SuperHeader, ContactForm), ``submit_contact`` → ``POST /api/v1/contact`` (the
absolute path ContactForm.vue fetches); a refusal raises ``ThemeApiError``
carrying only the body's ``error`` (ContactForm shows ``body.error || generic``).
"""
import json

import pytest

from plugins.theme.theme.theme_api import ThemeApiError
from plugins.theme_cms.theme_cms import cms_api as cms_api_module
from plugins.theme_cms.theme_cms.cms_api import CmsApi


class _Response:
    def __init__(self, status, body):
        self.status = status
        self.text = body if isinstance(body, str) else json.dumps(body)

    def json(self):
        return json.loads(self.text)


class _Client:
    def __init__(self, response):
        self.response = response
        self.requests = []

    def request(self, method, path, **options):
        self.requests.append((method, path, options))
        return self.response


class _ThemeRequest:
    http_request = "incoming-request"


@pytest.fixture
def client(monkeypatch):
    stub = _Client(_Response(200, {"items": []}))
    monkeypatch.setattr(cms_api_module, "resolve_internal_api_client", lambda: stub)
    from plugins.theme.theme import theme_api

    monkeypatch.setattr(theme_api, "resolve_internal_api_client", lambda: stub)
    return stub


def test_search_calls_the_public_search_endpoint_without_empty_filters(client):
    CmsApi(_ThemeRequest()).search({"q": "ai", "type": None, "page": 1, "types": ""})

    assert client.requests == [
        (
            "GET",
            "/api/v1/cms/search",
            {"forward_from": "incoming-request", "query": {"q": "ai", "page": 1}},
        )
    ]


def test_widget_by_slug_quotes_the_slug(client):
    client.response = _Response(200, {"slug": "a b"})

    widget = CmsApi(_ThemeRequest()).widget_by_slug("a b/c")

    assert widget == {"slug": "a b"}
    assert client.requests[0][1] == "/api/v1/cms/widgets/by-slug/a%20b%2Fc"


def test_submit_contact_posts_the_json_payload_to_the_contact_endpoint(client):
    client.response = _Response(200, {"ok": True})

    CmsApi(_ThemeRequest()).submit_contact({"widget_slug": "w", "fields": {}})

    assert client.requests == [
        (
            "POST",
            "/api/v1/contact",
            {
                "forward_from": "incoming-request",
                "json": {"widget_slug": "w", "fields": {}},
            },
        )
    ]


@pytest.mark.parametrize(
    "status, body, message",
    [
        (422, {"error": "Invalid email"}, "Invalid email"),
        (500, {"detail": "x"}, ""),
        (502, "<html>bad gateway</html>", ""),
    ],
)
def test_a_contact_refusal_carries_only_the_body_error(client, status, body, message):
    client.response = _Response(status, body)

    with pytest.raises(ThemeApiError) as raised:
        CmsApi(_ThemeRequest()).submit_contact({"widget_slug": "w"})

    assert raised.value.status == status
    assert raised.value.message == message
