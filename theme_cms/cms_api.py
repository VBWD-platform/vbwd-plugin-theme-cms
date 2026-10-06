"""The cms public API, as the fe-user cms plugin calls it — always through core C2 (D3).

Every method is one ``/api/v1/cms/*`` endpoint the SPA uses (plus the contact
form's ``/api/v1/contact``); a non-2xx answer
raises the theme's ``ThemeApiError`` with the HTTP status. Style CSS is served as
``text/css``, so those two calls read the body as text.
"""
import json
from typing import Any, Dict, List, Mapping, Optional
from urllib.parse import quote

from vbwd.services.internal_api import resolve_internal_api_client

from plugins.theme.theme.theme_api import (
    HTTP_SUCCESS_RANGE,
    ThemeApiError,
    call_api,
)
from plugins.theme.theme.theme_request import ThemeRequest

CMS_API_PREFIX = "/api/v1/cms"
# ContactForm.vue posts to this absolute path (it is not under /cms).
CONTACT_FORM_PATH = "/api/v1/contact"
PATH_SAFE_CHARACTERS = "/"


def _path_segment(value: str) -> str:
    """A slug/path as a URL path (nested ``a/b`` paths keep their ``/``)."""
    return quote(str(value), safe=PATH_SAFE_CHARACTERS)


def _json_object(text: str) -> Dict[str, Any]:
    try:
        body = json.loads(text)
    except ValueError:
        return {}
    return body if isinstance(body, dict) else {}


class CmsApi:
    """The cms read endpoints for one themed request (its headers are forwarded)."""

    def __init__(self, theme_request: ThemeRequest) -> None:
        self._theme_request = theme_request

    def _get(self, path: str, query: Optional[Mapping[str, Any]] = None) -> Any:
        return call_api(
            self._theme_request, "GET", f"{CMS_API_PREFIX}{path}", query=query
        )

    def _get_text(self, path: str) -> str:
        response = resolve_internal_api_client().request(
            "GET",
            f"{CMS_API_PREFIX}{path}",
            forward_from=self._theme_request.http_request,
        )
        if response.status not in HTTP_SUCCESS_RANGE:
            raise ThemeApiError(response.status, response.text)
        return response.text

    def post(
        self,
        slug: str,
        preview_token: Optional[str] = None,
        post_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        query = {"type": post_type, "preview_token": preview_token}
        return self._get(
            f"/posts/{_path_segment(slug)}",
            {name: value for name, value in query.items() if value},
        )

    def term(self, term_type: str, slug: str) -> Dict[str, Any]:
        return self._get(f"/terms/{_path_segment(term_type)}/{_path_segment(slug)}")

    def archive(self, path: str) -> Dict[str, Any]:
        return self._get(f"/archive/{_path_segment(path)}")

    def layout(self, layout_id: str) -> Dict[str, Any]:
        return self._get(f"/layouts/{_path_segment(layout_id)}")

    def layout_by_slug(self, slug: str) -> Dict[str, Any]:
        return self._get(f"/layouts/by-slug/{_path_segment(slug)}")

    def style_css(self, style_id: str) -> str:
        return self._get_text(f"/styles/{_path_segment(style_id)}/css")

    def default_style_css(self) -> str:
        return self._get_text("/styles/default/css")

    def site_config(self) -> Dict[str, Any]:
        return self._get("/config")

    def posts(self, query: Mapping[str, Any]) -> Dict[str, Any]:
        return self._get(
            "/posts", {name: value for name, value in query.items() if value}
        )

    def search(self, query: Mapping[str, Any]) -> Dict[str, Any]:
        return self._get(
            "/search", {name: value for name, value in query.items() if value}
        )

    def widget_by_slug(self, slug: str) -> Dict[str, Any]:
        return self._get(f"/widgets/by-slug/{quote(str(slug), safe='')}")

    def submit_contact(self, payload: Mapping[str, Any]) -> Dict[str, Any]:
        """``POST /api/v1/contact``; a refusal carries only the body's ``error``."""
        response = resolve_internal_api_client().request(
            "POST",
            CONTACT_FORM_PATH,
            forward_from=self._theme_request.http_request,
            json=dict(payload),
        )
        body = _json_object(response.text)
        if response.status not in HTTP_SUCCESS_RANGE:
            raise ThemeApiError(response.status, str(body.get("error") or ""))
        return body

    def categories(self) -> List[Dict[str, Any]]:
        body = self._get("/categories")
        return body.get("items", []) if isinstance(body, dict) else body or []
