"""S152-06b — PostCard / PostList, the shared card markup of every post listing.

Fixtures are written from ``vbwd-fe-user/plugins/cms/src/components/PostCard.vue``
(category mode :8-104, other modes :106-165, computed values :195-372) and
``PostList.vue`` (:1-24); ``CmsImage.vue`` for the image. Toggles default ON
(``utils/archiveDisplay.ts``); tags + reading time are owned by the toggles, not
by ``meta``. Dates are formatted en-US in UTC (the SPA uses the browser locale).
"""
from datetime import datetime, timezone

import pytest

from plugins.theme_cms.tests.unit.dom_contract import canonical
from plugins.theme_cms.tests.unit.template_harness import render, theme_plugin
from plugins.theme_cms.theme_cms.components.post_card import (
    archive_display,
    post_card_view,
    post_list_view,
    time_ago,
)

NOW = datetime(2026, 10, 3, 12, 0, tzinfo=timezone.utc)
POST_ICON = (
    "M2 3.5A1.5 1.5 0 0 1 3.5 2h9A1.5 1.5 0 0 1 14 3.5v9a1.5 1.5 0 0 1-1.5 1.5h-9A1.5 "
    "1.5 0 0 1 2 12.5zM4.75 5a.75.75 0 0 0 0 1.5h6.5a.75.75 0 0 0 0-1.5zm0 3a.75.75 0 0 "
    "0 0 1.5h6.5a.75.75 0 0 0 0-1.5zm0 3a.75.75 0 0 0 0 1.5h3.5a.75.75 0 0 0 0-1.5z"
)
IMAGE = (
    '<picture class="cms-image"><img class="cms-image__img" src="{src}" alt="{alt}" '
    'width="1200" height="675" loading="lazy" fetchpriority="auto" decoding="async">'
    "</picture>"
)


@pytest.fixture(autouse=True)
def isolated_var_directory(tmp_path, monkeypatch):
    monkeypatch.setenv("VBWD_VAR_DIR", str(tmp_path / "var"))


def _post(**fields):
    return {
        "id": "1",
        "type": "post",
        "slug": "blog/hello",
        "title": "Hello",
        "excerpt": "Short excerpt",
        "content_html": "<p>one two three</p>",
        "published_at": "2026-10-01T09:00:00Z",
        **fields,
    }


def _render_list(posts, display, detail_base=None):
    view = post_list_view(posts, display, detail_base, now=NOW)
    return render(
        theme_plugin(),
        {"post_list": view, "language": "en", "default_language": "en"},
        template="cms/components/_post_list.html.j2",
    )


def test_category_mode_card_matches_the_vue_markup():
    post = _post(
        primary_category={
            "name": "News",
            "slug": "news",
            "archive_url": "category/news",
        },
        tags=[
            {"name": "Vue", "slug": "vue", "archive_url": "tag/vue"},
            "plain tag",
            {"slug": "a b"},
        ],
        excerpt_effective="Effective excerpt",
        featured_image_url="/img.jpg",
    )
    display = archive_display({}, default_mode="category", meta=["published_at"])

    html = _render_list([post], display)

    assert canonical(html) == canonical(
        '<div class="post-list post-list--category">'
        '<article class="post-card post-card--category" data-testid="post-card">'
        '<div class="post-card__content">'
        '<a href="/category/news" class="post-card__eyebrow" data-testid="post-category">News</a>'
        '<h2 class="post-card__title"><a href="/blog/hello">Hello</a></h2>'
        '<div class="post-card__meta" data-testid="post-meta">'
        '<span class="post-card__badge post-card__badge--post" data-testid="post-type-badge">'
        '<svg class="post-card__badge-icon" viewBox="0 0 16 16" aria-hidden="true" '
        f'width="12" height="12"><path fill="currentColor" d="{POST_ICON}"></path></svg>'
        "Post</span>"
        '<time class="post-card__meta-item post-card__meta-item--date">Oct 1, 2026</time>'
        '<span class="post-card__meta-item post-card__meta-item--published_at">10/1/2026</span>'
        '<span class="post-card__meta-item post-card__meta-item--reading_time">1 min</span>'
        "</div>"
        '<div class="post-card__tags" data-testid="post-tags">'
        '<a href="/tag/vue" class="post-card__tag" data-testid="post-tag">Vue</a>'
        '<a href="/tag/plain%20tag" class="post-card__tag" data-testid="post-tag">plain tag</a>'
        '<a href="/tag/a%20b" class="post-card__tag" data-testid="post-tag">a b</a>'
        "</div>"
        '<p class="post-card__excerpt">Effective excerpt</p>'
        "</div>"
        '<a href="/blog/hello" class="post-card__thumb" tabindex="-1" aria-hidden="true">'
        + IMAGE.format(src="/img.jpg", alt="Hello")
        + "</a></article></div>"
    )


def test_titles_mode_is_title_plus_the_reading_time_meta_row():
    html = _render_list([_post()], archive_display({}, default_mode="titles"))

    assert canonical(html) == canonical(
        '<div class="post-list post-list--titles">'
        '<article class="post-card post-card--titles" data-testid="post-card">'
        '<h2 class="post-card__title"><a href="/blog/hello">Hello</a></h2>'
        '<div class="post-card__meta" data-testid="post-meta">'
        '<span class="post-card__meta-item post-card__meta-item--reading_time">1 min</span>'
        "</div></article></div>"
    )


def test_excerpt_mode_has_the_lead_image_and_excerpt_and_full_mode_the_body():
    post = _post(og_image_url="/og.jpg", og_image_width=800, og_image_height=400)
    display = archive_display(
        {"show_article_size": False, "show_tags": False}, default_mode="excerpt"
    )

    excerpt = _render_list([post], display)
    full = _render_list([post], {**display, "mode": "full"})

    assert canonical(excerpt) == canonical(
        '<div class="post-list post-list--excerpt">'
        '<article class="post-card post-card--excerpt" data-testid="post-card">'
        '<a href="/blog/hello" class="post-card__media">'
        '<picture class="cms-image"><img class="cms-image__img" src="/og.jpg" alt="Hello" '
        'width="800" height="400" loading="lazy" fetchpriority="auto" decoding="async">'
        "</picture></a>"
        '<h2 class="post-card__title"><a href="/blog/hello">Hello</a></h2>'
        '<p class="post-card__excerpt">Short excerpt</p>'
        "</article></div>"
    )
    assert '<div class="post-card__body"><p>one two three</p></div>' in full


def test_toggles_off_hide_the_eyebrow_tags_and_reading_time():
    post = _post(primary_category={"name": "News", "slug": "news"}, tags=["x"])
    display = archive_display(
        {"show_categories": False, "show_tags": False, "show_article_size": False},
        default_mode="category",
        meta=["published_at"],
    )

    html = _render_list([post], display)

    assert 'data-testid="post-category"' not in html
    assert 'data-testid="post-tags"' not in html
    assert "reading_time" not in html
    assert 'data-testid="post-meta"' in html


def test_legacy_meta_tags_and_reading_time_are_owned_by_the_toggles():
    display = archive_display(
        {
            "meta": ["author", "tags", "reading_time", "time_ago"],
            "show_article_size": False,
        },
        default_mode="titles",
        meta=None,
    )

    view = post_card_view(_post(author_name="Ada"), display, None, now=NOW)

    assert [item["field"] for item in view["meta"]] == ["author", "time_ago"]
    assert [item["value"] for item in view["meta"]] == ["Ada", "2 days ago"]


def test_detail_base_keeps_cards_in_embed_mode():
    view = post_card_view(
        _post(), archive_display({}, "titles"), "/cms/embed/post/post/"
    )

    assert view["detail_path"] == "/cms/embed/post/post/blog/hello"


@pytest.mark.parametrize(
    "category, expected_href",
    [
        ({"name": "N", "archive_url": "category/n", "slug": "x"}, "/category/n"),
        ({"name": "N", "slug": "n"}, "/category/n"),
        ({"name": "N"}, "/blog/hello"),
    ],
)
def test_category_eyebrow_href_prefers_archive_url_then_slug_then_the_post(
    category, expected_href
):
    view = post_card_view(
        _post(primary_category=category), archive_display({}, "category"), None
    )

    assert view["category"] == {"name": "N", "href": expected_href}


def test_tag_chips_encode_like_encode_uri_component_and_skip_nameless_tags():
    view = post_card_view(
        _post(tags=[{"slug": "c++/é"}, {"name": "", "slug": ""}, "", "ok!"]),
        archive_display({}, "titles"),
        None,
    )

    assert view["tags"] == [
        {"name": "c++/é", "href": "/tag/c%2B%2B%2F%C3%A9"},
        {"name": "ok!", "href": "/tag/ok!"},
    ]


def test_type_badge_is_page_icon_for_pages_and_absent_without_a_type():
    page_view = post_card_view(
        _post(type="page"), archive_display({}, "category"), None
    )
    untyped_view = post_card_view(
        _post(type=" "), archive_display({}, "category"), None
    )

    assert page_view["type_badge"] == {"kind": "page", "label": "Page"}
    assert untyped_view["type_badge"] is None


@pytest.mark.parametrize(
    "content_html, minutes",
    [
        ("", 1),
        ("<p>" + "word " * 299 + "</p>", 1),
        ("<p>" + "word " * 300 + "</p>", 2),
        # 2.5 → 3 (Math.round), where banker's rounding would give 2.
        ("<p>" + "word " * 500 + "</p>", 3),
    ],
)
def test_reading_time_rounds_half_up_with_a_one_minute_floor(content_html, minutes):
    view = post_card_view(
        _post(content_html=content_html), archive_display({}, "titles"), None
    )

    assert view["meta"][-1] == {"field": "reading_time", "value": f"{minutes} min"}


@pytest.mark.parametrize(
    "published_at, expected",
    [
        ("2026-10-03T11:59:58Z", "2 seconds ago"),
        ("2026-10-03T12:00:00Z", "now"),
        ("2026-10-03T11:59:00Z", "1 minute ago"),
        ("2026-10-03T10:00:00Z", "2 hours ago"),
        ("2026-10-02T12:00:00Z", "yesterday"),
        ("2026-09-30T12:00:00Z", "3 days ago"),
        ("2026-09-26T12:00:00Z", "last week"),
        ("2026-09-19T12:00:00Z", "2 weeks ago"),
        ("2026-09-01T12:00:00Z", "last month"),
        ("2025-09-01T12:00:00Z", "last year"),
        ("2026-10-05T12:00:00Z", "in 2 days"),
        ("not a date", ""),
        (None, ""),
    ],
)
def test_time_ago_matches_intl_relative_time_format_en_auto(published_at, expected):
    assert time_ago(published_at, NOW) == expected


def test_an_empty_list_is_the_post_list_empty_state():
    html = _render_list([], archive_display({}, "excerpt"))

    assert canonical(html) == canonical(
        '<div class="post-list post-list--excerpt">'
        '<p class="post-list__empty" data-testid="post-list-empty">No posts yet.</p></div>'
    )


def test_card_text_is_escaped():
    html = _render_list(
        [_post(title="<script>x</script>", excerpt="<b>e</b>")],
        archive_display({}, "excerpt"),
    )

    assert "<script>x" not in html and "&lt;script&gt;x" in html
    assert "&lt;b&gt;e&lt;/b&gt;" in html
