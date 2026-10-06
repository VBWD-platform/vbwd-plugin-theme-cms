"""S152-06b — the post-listing widgets: PostArchive, TermArchive, TagArchive, Category.

Mirrors (fe-user ``plugins/cms/src/components``):
* ``PostArchiveWidget.vue`` — ``GET /cms/posts ?type&page&per_page``, defaults
  type=post / mode=category / 20 per page / paginate on, meta [published_at];
* ``TermArchiveWidget.vue`` — term from the catch-all slug ``category|tag/<slug>``,
  name/description from the resolved ``term_archive``, prefix-archive mode lists
  the page's parked items, per-mode empty copy, pagination only for terms;
* ``TagArchive.vue`` — ``?tag=`` slug, title-cased heading, excerpt mode;
* ``PostTermListWidget.vue`` (Category / PostTermList) — config-pinned term, RSS link.
Pagination buttons become ``?page=N`` links (no JS needed); a failed fetch is an
empty list, as ``usePosts`` swallows errors.
"""
import pytest

from plugins.theme.theme.theme_api import ThemeApiError
from plugins.theme_cms.tests.unit.components.fakes import (
    FakeCmsApi,
    FakeThemeRequest,
    listing,
    post,
)
from plugins.theme_cms.tests.unit.dom_contract import canonical, testids
from plugins.theme_cms.tests.unit.template_harness import render_component, theme_plugin
from plugins.theme_cms.theme_cms.components.archives import (
    build_post_archive_context,
    build_tag_archive_context,
    build_term_archive_context,
    build_term_list_context,
)


@pytest.fixture(autouse=True)
def isolated_var_directory(tmp_path, monkeypatch):
    monkeypatch.setenv("VBWD_VAR_DIR", str(tmp_path / "var"))


def _render(template, context):
    return render_component(
        theme_plugin(), f"cms/components/{template}.html.j2", context
    )


# ── PostArchive ─────────────────────────────────────────────────────────────


def test_post_archive_fetches_every_post_of_the_type_with_the_page_from_the_url():
    cms_api = FakeCmsApi(posts=listing([post("a")], page=2, pages=3))

    context = build_post_archive_context(
        {"posts_per_page": 5},
        {},
        {},
        FakeThemeRequest(query={"page": "2"}),
        cms_api_factory=cms_api.factory,
    )

    assert cms_api.calls == [("posts", {"type": "post", "page": 2, "per_page": 5})]
    assert context["post_list"]["mode"] == "category"
    assert context["pagination"] == {
        "page": 2,
        "pages": 3,
        "previous_href": "?page=1",
        "next_href": "?page=3",
    }


def test_post_archive_markup_with_pagination_links():
    cms_api = FakeCmsApi(posts=listing([post("a", "Alpha")], page=1, pages=2))
    context = build_post_archive_context(
        {"mode": "titles", "show_article_size": False},
        {},
        {},
        FakeThemeRequest(),
        cms_api_factory=cms_api.factory,
    )

    html = _render("post_archive", context)

    assert canonical(html) == canonical(
        '<div class="post-archive-widget">'
        '<div class="post-list post-list--titles">'
        '<article class="post-card post-card--titles" data-testid="post-card">'
        '<h2 class="post-card__title"><a href="/a">Alpha</a></h2>'
        # PostArchive pins meta to [published_at]; a post without one keeps the empty item.
        '<div class="post-card__meta" data-testid="post-meta">'
        '<span class="post-card__meta-item post-card__meta-item--published_at"></span></div>'
        "</article></div>"
        '<div class="post-archive-widget__pagination">'
        '<a data-testid="post-archive-prev" aria-disabled="true">‹</a>'
        '<span class="post-archive-widget__page-indicator">1 / 2</span>'
        '<a data-testid="post-archive-next" href="?page=2">›</a>'
        "</div></div>"
    )


def test_post_archive_without_paginate_or_a_single_page_has_no_pagination():
    one_page = FakeCmsApi(posts=listing([post("a")]))
    many_pages = FakeCmsApi(posts=listing([post("a")], pages=4))

    single = build_post_archive_context(
        {}, {}, {}, FakeThemeRequest(), one_page.factory
    )
    switched_off = build_post_archive_context(
        {"paginate": False}, {}, {}, FakeThemeRequest(), many_pages.factory
    )

    assert single["pagination"] is None and switched_off["pagination"] is None


@pytest.mark.parametrize(
    "raw_page, expected", [("0", 1), ("-3", 1), ("x", 1), (None, 1)]
)
def test_a_bad_page_parameter_is_the_first_page(raw_page, expected):
    cms_api = FakeCmsApi(posts=listing([]))

    build_post_archive_context(
        {},
        {},
        {},
        FakeThemeRequest(query={"page": raw_page} if raw_page else {}),
        cms_api.factory,
    )

    assert cms_api.calls[0][1]["page"] == expected


def test_a_failed_listing_is_the_empty_state():
    cms_api = FakeCmsApi(posts=ThemeApiError(500, "boom"))
    context = build_post_archive_context(
        {}, {}, {}, FakeThemeRequest(), cms_api.factory
    )

    html = _render("post_archive", context)

    assert testids(html) == ["post-list-empty"]


# ── TermArchive ─────────────────────────────────────────────────────────────


def _term_page(term_type="category", slug="news", name="News", description="All news"):
    return {
        "type": "page",
        "term_archive": {
            "term_type": term_type,
            "slug": slug,
            "name": name,
            "description": description,
        },
    }


def test_term_archive_lists_the_route_term_with_the_resolved_name_and_description():
    cms_api = FakeCmsApi(posts=listing([post("a")], pages=2))

    context = build_term_archive_context(
        {}, _term_page(), {"slug": "category/news"}, FakeThemeRequest(), cms_api.factory
    )
    html = _render("term_archive", context)

    assert cms_api.calls == [
        (
            "posts",
            {
                "type": "post",
                "term_type": "category",
                "term_slug": "news",
                "page": 1,
                "per_page": 20,
            },
        )
    ]
    found = testids(html)
    assert found[:3] == [
        "term-archive-heading",
        "term-archive-description",
        "post-card",
    ]
    assert found[-2:] == ["term-archive-prev", "term-archive-next"]
    assert canonical(html).startswith(
        canonical(
            '<div class="term-archive"><header class="term-archive__header">'
            '<h1 class="term-archive__heading" data-testid="term-archive-heading">News</h1>'
            '<p class="term-archive__description" data-testid="term-archive-description">'
            "All news</p></header>"
        )
    )
    assert 'data-testid="term-archive-prev"' in html
    assert 'data-testid="term-archive-next" href="?page=2"' in html


def test_term_archive_falls_back_to_the_title_cased_leaf_slug():
    cms_api = FakeCmsApi(posts=listing([]))

    context = build_term_archive_context(
        {},
        {},
        {"slug": "tag/guides/getting-started"},
        FakeThemeRequest(),
        cms_api.factory,
    )

    assert context["heading"] == "Getting Started"
    assert context["description"] == ""
    assert cms_api.calls[0][1]["term_type"] == "tag"
    assert cms_api.calls[0][1]["term_slug"] == "guides/getting-started"


@pytest.mark.parametrize(
    "slug, empty_text",
    [
        ("category/none", "No posts in this category yet."),
        ("tag/none", "No posts in this tag yet."),
    ],
)
def test_term_archive_empty_copy_per_term_type(slug, empty_text):
    cms_api = FakeCmsApi(posts=listing([]))
    context = build_term_archive_context(
        {}, {}, {"slug": slug}, FakeThemeRequest(), cms_api.factory
    )

    html = _render("term_archive", context)

    assert (
        f'<p class="term-archive__empty" data-testid="term-archive-empty">{empty_text}</p>'
        in html
    )


def test_term_archive_in_prefix_archive_mode_lists_the_parked_items_without_a_fetch():
    page = {
        "type": "archive",
        "archive_prefix": "blog/2026",
        "title": "2026",
        "items": [post("blog/2026/a", "A")],
        "archive_pages": 3,
    }
    cms_api = FakeCmsApi()

    context = build_term_archive_context(
        {}, page, {"slug": "blog/2026"}, FakeThemeRequest(), cms_api.factory
    )
    html = _render("term_archive", context)

    assert cms_api.calls == []
    assert context["heading"] == "2026"
    assert context["pagination"] is None
    assert 'href="/blog/2026/a"' in html
    assert "term-archive-description" not in html


def test_term_archive_prefix_archive_without_items_says_so():
    page = {
        "type": "archive",
        "archive_prefix": "blog/1999",
        "title": "1999",
        "items": [],
    }
    context = build_term_archive_context(
        {}, page, {"slug": "blog/1999"}, FakeThemeRequest(), FakeCmsApi().factory
    )

    assert "No posts in this archive yet." in _render("term_archive", context)


def test_term_archive_without_a_term_or_archive_is_the_prompt():
    context = build_term_archive_context(
        {},
        {"type": "page"},
        {"slug": "about"},
        FakeThemeRequest(),
        FakeCmsApi().factory,
    )

    html = _render("term_archive", context)

    assert canonical(html) == canonical(
        '<div class="term-archive"><p class="term-archive__hint" '
        'data-testid="term-archive-prompt">No term selected.</p></div>'
    )


def test_a_resolved_term_of_another_slug_is_not_used():
    page = _term_page(slug="other", name="Other")
    context = build_term_archive_context(
        {},
        page,
        {"slug": "category/news"},
        FakeThemeRequest(),
        FakeCmsApi(posts=listing([])).factory,
    )

    assert context["heading"] == "News"


# ── TagArchive ──────────────────────────────────────────────────────────────


def test_tag_archive_reads_the_tag_query_and_title_cases_it():
    cms_api = FakeCmsApi(posts=listing([post("a", "Alpha", excerpt="Ex")]))

    context = build_tag_archive_context(
        {"limit": 7},
        {},
        {},
        FakeThemeRequest(query={"tag": " getting-started "}),
        cms_api.factory,
    )
    html = _render("tag_archive", context)

    assert cms_api.calls == [
        (
            "posts",
            {
                "type": "post",
                "term_type": "tag",
                "term_slug": "getting-started",
                "page": 1,
                "per_page": 7,
            },
        )
    ]
    assert (
        '<h1 class="tag-archive__heading" data-testid="tag-archive-heading">'
        "Posts tagged &#34;Getting Started&#34;</h1>"
    ) in html or (
        '<h1 class="tag-archive__heading" data-testid="tag-archive-heading">'
        "Posts tagged &quot;Getting Started&quot;</h1>"
    ) in html
    assert 'class="post-list post-list--excerpt"' in html
    assert '<p class="post-card__excerpt">Ex</p>' in html


def test_tag_archive_without_a_tag_is_the_prompt_and_without_posts_the_empty_state():
    no_tag = build_tag_archive_context(
        {}, {}, {}, FakeThemeRequest(), FakeCmsApi().factory
    )
    no_posts = build_tag_archive_context(
        {},
        {},
        {},
        FakeThemeRequest(query={"tag": "x"}),
        FakeCmsApi(posts=listing([])).factory,
    )

    assert canonical(_render("tag_archive", no_tag)) == canonical(
        '<div class="tag-archive"><p class="tag-archive__hint" '
        'data-testid="tag-archive-prompt">Select a tag.</p></div>'
    )
    assert testids(_render("tag_archive", no_posts)) == [
        "tag-archive-heading",
        "tag-archive-empty",
    ]


# ── Category / PostTermList ─────────────────────────────────────────────────


def test_term_list_lists_the_configured_term_with_its_rss_link():
    cms_api = FakeCmsApi(posts=listing([post("a", "Alpha")]))
    config = {
        "type": "post",
        "term_type": "category",
        "term_slug": "news & views",
        "limit": 3,
    }

    context = build_term_list_context(
        config, {}, {}, FakeThemeRequest(), cms_api.factory
    )
    html = _render("term_list", context)

    assert cms_api.calls == [
        (
            "posts",
            {
                "type": "post",
                "term_type": "category",
                "term_slug": "news & views",
                "page": 1,
                "per_page": 3,
            },
        )
    ]
    assert canonical(html).startswith(
        canonical(
            '<div class="post-term-list-widget">'
            '<a class="post-term-list-widget__rss" '
            'href="/api/v1/cms/rss.xml?type=post&amp;term_type=category&amp;term_slug=news+%26+views" '
            'data-testid="post-term-rss-link" title="Subscribe via RSS">'
            '<span aria-hidden="true">🔖</span>RSS</a>'
            '<div class="post-list post-list--titles">'
        )
    )


def test_an_incomplete_term_config_fetches_nothing_and_shows_the_empty_list():
    cms_api = FakeCmsApi()

    context = build_term_list_context(
        {"type": "post"}, {}, {}, FakeThemeRequest(), cms_api.factory
    )

    assert cms_api.calls == []
    assert testids(_render("term_list", context)) == ["post-list-empty"]
