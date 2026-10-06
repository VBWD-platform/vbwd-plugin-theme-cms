"""S152-06b — the embed archive (CmsEmbedArchive.vue) renders the real PostCard markup.

Display: excerpt mode, meta [published_at], toggles on; cards link back into
embed mode (``/cms/embed/<type>/post/<slug>``); an empty category fails loud
(``cms-embed-archive-empty``); the pager uses the cms-embed-archive-* testids.
"""
import pytest

from plugins.theme_cms.tests.unit.components.fakes import listing, post
from plugins.theme_cms.tests.unit.dom_contract import canonical, testids
from plugins.theme_cms.tests.unit.template_harness import render, theme_plugin
from plugins.theme_cms.theme_cms.pages import embed_archive_view


@pytest.fixture(autouse=True)
def isolated_var_directory(tmp_path, monkeypatch):
    monkeypatch.setenv("VBWD_VAR_DIR", str(tmp_path / "var"))


def _render(context):
    return render(
        theme_plugin(),
        {**context, "page_title": "", "language": "en", "default_language": "en"},
        template="cms/embed_archive.html.j2",
    )


def test_cards_are_post_cards_in_excerpt_mode_linking_into_embed_mode():
    view = embed_archive_view(
        listing(
            [post("hello", "Hello", excerpt="Ex", published_at="2026-10-01T00:00:00Z")],
            pages=2,
        ),
        "post",
    )

    html = _render(view)
    body = html.partition('<div class="cms-embed-archive">')[2]

    assert canonical(body).startswith(
        canonical(
            '<div class="post-list post-list--excerpt">'
            '<article class="post-card post-card--excerpt" data-testid="post-card">'
            '<h2 class="post-card__title"><a href="/cms/embed/post/post/hello">Hello</a></h2>'
            '<div class="post-card__meta" data-testid="post-meta">'
            '<span class="post-card__meta-item post-card__meta-item--published_at">10/1/2026</span>'
            '<span class="post-card__meta-item post-card__meta-item--reading_time">1 min</span>'
            "</div>"
            '<p class="post-card__excerpt">Ex</p></article></div>'
            '<div class="cms-embed-archive__pagination">'
            '<a data-testid="cms-embed-archive-prev" aria-disabled="true">‹</a>'
            '<span class="cms-embed-archive__page-indicator">1 / 2</span>'
            '<a data-testid="cms-embed-archive-next" href="?page=2">›</a></div>'
        )
    )


def test_an_empty_category_fails_loud():
    html = _render(embed_archive_view(listing([]), "post"))

    assert testids(html.partition("<body")[2]) == ["cms-embed-archive-empty"]
