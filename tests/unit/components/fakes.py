"""Test doubles for the component context builders (same contract as ``CmsApi``).

``FakeCmsApi`` answers like the cms public API and records every call; an
answer that is an exception instance is raised, as ``call_api`` raises
``ThemeApiError`` on a non-2xx status.
"""
from types import MappingProxyType


class FakeThemeRequest:
    def __init__(self, path="/", query=None, view_args=None, user_id=None):
        from plugins.theme.theme.viewer import ANONYMOUS_VIEWER, Viewer

        self.path = path
        self.query_args = MappingProxyType(dict(query or {}))
        self.view_args = MappingProxyType(dict(view_args or {}))
        self.viewer = (
            Viewer(user_id=user_id, access_level_slugs=frozenset(), permissions=())
            if user_id
            else ANONYMOUS_VIEWER
        )
        self.language = "en"


def listing(items, page=1, pages=1, total=None, per_page=20):
    return {
        "items": list(items),
        "page": page,
        "pages": pages,
        "total": len(items) if total is None else total,
        "per_page": per_page,
    }


class FakeCmsApi:
    def __init__(self, **answers):
        self.answers = answers
        self.calls = []

    def _answer(self, name, *arguments):
        self.calls.append((name,) + arguments)
        answer = self.answers.get(name)
        if isinstance(answer, Exception):
            raise answer
        return answer

    def posts(self, query):
        return self._answer("posts", dict(query))

    def search(self, query):
        return self._answer("search", dict(query))

    def widget_by_slug(self, slug):
        return self._answer("widget_by_slug", slug)

    def submit_contact(self, payload):
        return self._answer("submit_contact", payload)

    def factory(self, theme_request):
        self.theme_request = theme_request
        return self


def post(slug, title=None, **fields):
    return {
        "id": slug,
        "type": "post",
        "slug": slug,
        "title": title or slug.title(),
        **fields,
    }
