"""S152-06b — CmsBreadcrumb: ``buildCmsBreadcrumbTrail`` + core ``VbwdBreadcrumb`` markup.

Trail cases are copied from fe-user ``plugins/cms/tests/unit/useCmsBreadcrumbTrail.spec.ts``;
the markup from ``vbwd-fe-core/src/components/breadcrumb/VbwdBreadcrumb.vue``
(nav.vbwd-breadcrumb, separator spans, links, the current span, label
truncation at ``max_label_length`` default 60, optional inline ``css``).
The e2e ``cms-breadcrumb-flow.spec.ts`` reads ``nav.vbwd-breadcrumb > a`` and
``> span.vbwd-breadcrumb__current``.
"""
import pytest

from plugins.theme_cms.tests.unit.dom_contract import canonical
from plugins.theme_cms.tests.unit.template_harness import render_component, theme_plugin
from plugins.theme_cms.theme_cms.components.breadcrumb import (
    build_breadcrumb_context,
    build_cms_breadcrumb_trail,
    slug_to_label,
)

TEMPLATE = "cms/components/breadcrumb.html.j2"


class _Request:
    def __init__(self, path):
        self.path = path


@pytest.fixture(autouse=True)
def isolated_var_directory(tmp_path, monkeypatch):
    monkeypatch.setenv("VBWD_VAR_DIR", str(tmp_path / "var"))


def test_a_blog_post_gets_the_full_cumulative_prefix_trail():
    trail = build_cms_breadcrumb_trail(
        "/blog/2026/news/vbwd-v26-7-0-released",
        {"type": "post", "title": "VBWD v26.7.0 released…"},
    )

    assert trail == [
        {"label": "Home", "to": "/"},
        {"label": "Blog", "to": "/blog"},
        {"label": "2026", "to": "/blog/2026"},
        {"label": "News", "to": "/blog/2026/news"},
        {"label": "VBWD v26.7.0 released…", "current": True},
    ]


def test_a_prefix_archive_ends_with_its_last_segment_current():
    trail = build_cms_breadcrumb_trail(
        "/blog/2026",
        {"type": "archive", "archive_prefix": "blog/2026", "title": "2026"},
    )

    assert trail == [
        {"label": "Home", "to": "/"},
        {"label": "Blog", "to": "/blog"},
        {"label": "2026", "current": True},
    ]


def test_a_normal_page_is_home_then_its_title():
    assert build_cms_breadcrumb_trail(
        "/about", {"type": "page", "title": "About Us"}
    ) == [
        {"label": "Home", "to": "/"},
        {"label": "About Us", "current": True},
    ]


def test_a_category_term_name_wins_over_the_title_cased_segment():
    trail = build_cms_breadcrumb_trail(
        "/blog/2026/news/hello",
        {
            "type": "post",
            "title": "Hello",
            "terms": [
                {"term_type": "category", "slug": "news", "name": "Company News"}
            ],
        },
    )

    assert {"label": "Company News", "to": "/blog/2026/news"} in trail


def test_a_nested_term_slug_matches_on_its_leaf_and_tags_never_label_a_segment():
    trail = build_cms_breadcrumb_trail(
        "/blog/guides/hello",
        {
            "type": "post",
            "title": "Hello",
            "terms": [
                {"term_type": "tag", "slug": "blog", "name": "Tag Blog"},
                {"term_type": "category", "slug": "docs/guides", "name": "Guides!"},
            ],
        },
    )

    assert trail[1] == {"label": "Blog", "to": "/blog"}
    assert trail[2] == {"label": "Guides!", "to": "/blog/guides"}


def test_a_post_without_a_title_uses_its_name_then_the_segment():
    named = build_cms_breadcrumb_trail("/blog/x-y", {"type": "post", "name": "Named"})
    bare = build_cms_breadcrumb_trail("/blog/x-y", {"type": "post"})

    assert named[-1] == {"label": "Named", "current": True}
    assert bare[-1] == {"label": "X Y", "current": True}


def test_no_page_or_a_titleless_page_is_no_trail():
    assert build_cms_breadcrumb_trail("/dashboard", None) is None
    assert build_cms_breadcrumb_trail("/x", {"type": "page"}) is None


@pytest.mark.parametrize(
    "slug, label",
    [("news", "News"), ("my-cat", "My Cat"), ("2026", "2026"), ("vbwd", "Vbwd")],
)
def test_slug_to_label_title_cases_like_the_spa(slug, label):
    assert slug_to_label(slug) == label


def test_the_markup_is_the_core_vbwd_breadcrumb():
    context = build_breadcrumb_context(
        {"separator": "›", "css": ".vbwd-breadcrumb{gap:2px}"},
        {"type": "post", "title": "Hello <World>"},
        {},
        _Request("/blog/hello"),
    )

    html = render_component(theme_plugin(), TEMPLATE, context)

    assert canonical(html) == canonical(
        '<nav class="vbwd-breadcrumb" aria-label="breadcrumb">'
        "<style>.vbwd-breadcrumb{gap:2px}</style>"
        '<a href="/" class="vbwd-breadcrumb__link">Home</a>'
        '<span class="vbwd-breadcrumb__separator" aria-hidden="true">›</span>'
        '<a href="/blog" class="vbwd-breadcrumb__link">Blog</a>'
        '<span class="vbwd-breadcrumb__separator" aria-hidden="true">›</span>'
        '<span class="vbwd-breadcrumb__current">Hello &lt;World&gt;</span>'
        "</nav>"
    )


def test_labels_truncate_at_max_label_length_and_the_separator_defaults_to_slash():
    context = build_breadcrumb_context(
        {"max_label_length": 5},
        {"type": "page", "title": "Abcdefgh"},
        {},
        _Request("/a"),
    )

    html = render_component(theme_plugin(), TEMPLATE, context)

    assert '<span class="vbwd-breadcrumb__current">Abcde…</span>' in html
    assert (
        '<span class="vbwd-breadcrumb__separator" aria-hidden="true">/</span>' in html
    )
    assert "<style>" not in html


def test_no_trail_renders_an_empty_nav():
    context = build_breadcrumb_context({}, {"type": "page"}, {}, _Request("/x"))

    html = render_component(theme_plugin(), TEMPLATE, context)

    assert canonical(html) == canonical(
        '<nav class="vbwd-breadcrumb" aria-label="breadcrumb"></nav>'
    )


def test_breadcrumb_css_cannot_close_its_style_element():
    context = build_breadcrumb_context(
        {"css": "a{}</style><script>x</script>"}, {"title": "T"}, {}, _Request("/t")
    )

    html = render_component(theme_plugin(), TEMPLATE, context)

    assert "</style><script>" not in html
    assert html.count("</style>") == 1
