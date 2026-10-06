"""S152-06a §1–2 — ``CmsPageResolver``, the mirror of ``useCmsStore._resolvePageOrTerm``.

Order: ``/cms/posts/<slug>`` → on 404 ``?type=post`` → on 404 a
``category/…``/``tag/…`` slug resolves the term into a synthetic page on the
``terms-archive`` layout with the default style → else ``/cms/archive/<path>``
→ else the original 404 propagates. ``preview_token`` is forwarded and a preview
never falls through to archives. Any non-404 (403) propagates unchanged. Layout
and style failures degrade to "no layout" / "no style", as in the SPA.

The fake API honours the real one's contract: a missing resource raises
``ThemeApiError`` with the HTTP status (Liskov — no ``None`` returns).
"""
import pytest

from plugins.theme.theme.theme_api import ThemeApiError
from plugins.theme_cms.theme_cms.page_resolver import CmsPageResolver, page_type_of


class FakeCmsApi:
    def __init__(
        self,
        posts=None,
        terms=None,
        archives=None,
        layouts=None,
        styles=None,
        layouts_by_slug=None,
        default_style_css=None,
        post_errors=None,
    ):
        self.posts = posts or {}
        self.terms = terms or {}
        self.archives = archives or {}
        self.layouts = layouts or {}
        self.styles = styles or {}
        self.layouts_by_slug = layouts_by_slug or {}
        self.default_css = default_style_css
        self.post_errors = post_errors or {}
        self.calls = []

    @staticmethod
    def _found(table, key):
        if key not in table:
            raise ThemeApiError(404, "not found")
        return table[key]

    def post(self, slug, preview_token=None, post_type=None):
        self.calls.append(("post", slug, preview_token, post_type))
        if (slug, post_type) in self.post_errors:
            raise ThemeApiError(self.post_errors[(slug, post_type)], "refused")
        return dict(self._found(self.posts, (slug, post_type)))

    def term(self, term_type, slug):
        self.calls.append(("term", term_type, slug))
        return self._found(self.terms, (term_type, slug))

    def archive(self, path):
        self.calls.append(("archive", path))
        return self._found(self.archives, path)

    def layout(self, layout_id):
        self.calls.append(("layout", layout_id))
        return self._found(self.layouts, layout_id)

    def layout_by_slug(self, slug):
        self.calls.append(("layout_by_slug", slug))
        return self._found(self.layouts_by_slug, slug)

    def style_css(self, style_id):
        self.calls.append(("style_css", style_id))
        return self._found(self.styles, style_id)

    def default_style_css(self):
        self.calls.append(("default_style_css",))
        if self.default_css is None:
            raise ThemeApiError(404, "no default")
        return self.default_css


ABOUT = {
    "id": "p1",
    "slug": "about",
    "type": "page",
    "resolved_layout_id": "L1",
    "resolved_style_id": "S1",
    "layout_id": None,
    "style_id": None,
}
TERMS_LAYOUT = {"id": "TL", "slug": "terms-archive", "areas": [], "assignments": []}


def test_a_page_resolves_with_its_resolved_layout_and_style():
    api = FakeCmsApi(
        posts={("about", None): ABOUT},
        layouts={"L1": {"id": "L1"}},
        styles={"S1": ".a{}"},
    )

    resolved = CmsPageResolver(api).resolve("about")

    assert resolved.page["id"] == "p1"
    assert resolved.layout == {"id": "L1"}
    assert resolved.style_css == ".a{}"
    assert api.calls == [
        ("post", "about", None, None),
        ("layout", "L1"),
        ("style_css", "S1"),
    ]


def test_raw_ids_are_used_when_the_resolved_ones_are_absent():
    page = {"id": "p", "slug": "x", "layout_id": "L2", "style_id": "S2"}
    api = FakeCmsApi(
        posts={("x", None): page}, layouts={"L2": {"id": "L2"}}, styles={"S2": "b{}"}
    )

    resolved = CmsPageResolver(api).resolve("x")

    assert resolved.layout == {"id": "L2"} and resolved.style_css == "b{}"


def test_no_layout_or_style_id_and_failing_assets_degrade_to_none():
    no_ids = FakeCmsApi(posts={("x", None): {"id": "p", "slug": "x"}})
    missing = FakeCmsApi(posts={("x", None): ABOUT})

    assert CmsPageResolver(no_ids).resolve("x").layout is None
    assert no_ids.calls == [("post", "x", None, None)]
    resolved = CmsPageResolver(missing).resolve("x")
    assert resolved.layout is None and resolved.style_css is None


def test_a_page_404_retries_as_a_post():
    article = {"id": "a1", "slug": "news/hello", "type": "post"}
    api = FakeCmsApi(posts={("news/hello", "post"): article})

    resolved = CmsPageResolver(api).resolve("news/hello")

    assert resolved.page["id"] == "a1"
    assert api.calls[:2] == [
        ("post", "news/hello", None, None),
        ("post", "news/hello", None, "post"),
    ]


def test_preview_token_is_forwarded_and_never_falls_through_to_archives():
    api = FakeCmsApi(
        terms={("category", "x"): {"term_type": "category", "slug": "x", "name": "X"}}
    )

    with pytest.raises(ThemeApiError) as raised:
        CmsPageResolver(api).resolve("category/x", preview_token="tok")

    assert raised.value.status == 404
    assert api.calls == [
        ("post", "category/x", "tok", None),
        ("post", "category/x", "tok", "post"),
    ]


def test_a_403_propagates_without_any_fallback():
    api = FakeCmsApi(post_errors={("draft", None): 403})

    with pytest.raises(ThemeApiError) as raised:
        CmsPageResolver(api).resolve("draft", preview_token="wrong")

    assert raised.value.status == 403
    assert api.calls == [("post", "draft", "wrong", None)]


def test_a_term_slug_becomes_a_synthetic_term_archive_page():
    term = {"term_type": "tag", "slug": "vue", "name": "Vue", "description": "All Vue"}
    api = FakeCmsApi(
        terms={("tag", "vue"): term},
        layouts_by_slug={"terms-archive": TERMS_LAYOUT},
        default_style_css=".default{}",
    )

    resolved = CmsPageResolver(api).resolve("tag/vue")

    assert resolved.layout == TERMS_LAYOUT
    assert resolved.style_css == ".default{}"
    page = resolved.page
    assert page["id"] == "term-archive:tag:vue"
    assert page["slug"] == "tag/vue"
    assert page["type"] == "page"
    assert page["title"] == "Vue" and page["meta_title"] == "Vue"
    assert page["meta_description"] == "All Vue"
    assert page["resolved_layout_id"] == "TL"
    assert page["robots"] == "index,follow"
    assert page["term_archive"] == {
        "term_type": "tag",
        "slug": "vue",
        "name": "Vue",
        "description": "All Vue",
    }
    assert page_type_of(page) == "term_archive"


def test_a_missing_term_falls_through_to_the_prefix_archive():
    archive = {
        "prefix": "category/none",
        "title": "None",
        "items": [{"id": "i"}],
        "total": 1,
        "page": 1,
        "per_page": 20,
        "pages": 1,
    }
    api = FakeCmsApi(archives={"category/none": archive})

    resolved = CmsPageResolver(api).resolve("category/none")

    assert resolved.page["type"] == "archive"
    assert ("term", "category", "none") in api.calls


def test_a_prefix_archive_becomes_a_synthetic_archive_page():
    archive = {
        "prefix": "blog/2026",
        "title": "2026",
        "items": [{"id": "i1"}],
        "total": 3,
        "page": 1,
        "per_page": 20,
        "pages": 1,
    }
    api = FakeCmsApi(
        archives={"blog/2026": archive}, layouts_by_slug={"terms-archive": TERMS_LAYOUT}
    )

    resolved = CmsPageResolver(api).resolve("blog/2026")

    page = resolved.page
    assert page["id"] == "prefix-archive:blog/2026"
    assert page["type"] == "archive" and page_type_of(page) == "archive"
    assert page["title"] == "2026" and page["archive_prefix"] == "blog/2026"
    assert page["items"] == [{"id": "i1"}] and page["archive_total"] == 3
    assert resolved.style_css is None
    assert ("term", "blog", "2026") not in api.calls


def test_nothing_found_re_raises_the_original_404():
    api = FakeCmsApi()

    with pytest.raises(ThemeApiError) as raised:
        CmsPageResolver(api).resolve("nope")

    assert raised.value.status == 404
    assert api.calls[-1] == ("archive", "nope")


def test_page_type_of_a_real_post_is_its_type():
    assert page_type_of({"type": "post"}) == "post"
    assert page_type_of({}) == "page"
