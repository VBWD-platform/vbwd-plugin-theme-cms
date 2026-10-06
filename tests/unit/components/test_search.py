"""S152-06b — Search (PostSearch.vue), SearchResults (PostSearchResults.vue) and the
quick-search fragment.

* The box is a real GET form (``?q=`` → ``target_path`` or the current page), so
  the classic flow works without JS, exactly the URL the SPA's ``router.push`` writes.
* ``quicksearch: true`` makes the input an htmx island over
  ``GET /_render/_fragment/cms/search`` (350 ms debounce, as the SPA), which calls
  ``GET /api/v1/cms/search`` with the scope's ``type`` and the clamped limit.
* SearchResults renders server-side from ``?q=``: hint / no-results / count + PostList.
Testids kept: post-search-input/-submit/-dropdown/-option, search-empty-query,
search-no-results, search-result-count (the SPA's transient ``search-loading``
never exists in a server render).
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
from plugins.theme_cms.tests.unit.template_harness import (
    render,
    render_component,
    theme_plugin,
)
from plugins.theme_cms.theme_cms.components.search import (
    SEARCH_FRAGMENT_PATH,
    build_quicksearch_fragment_context,
    build_search_box_context,
    build_search_results_context,
    resolve_scope,
    scope_to_type,
)

SEARCH_ICON = (
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
    'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">'
    '<circle cx="11" cy="11" r="8"></circle><path d="m21 21-4.3-4.3"></path></svg>'
)


@pytest.fixture(autouse=True)
def isolated_var_directory(tmp_path, monkeypatch):
    monkeypatch.setenv("VBWD_VAR_DIR", str(tmp_path / "var"))


def _render(template, context):
    return render_component(
        theme_plugin(), f"cms/components/{template}.html.j2", context
    )


@pytest.mark.parametrize(
    "scope, legacy_type, expected",
    [
        ("pages", None, "pages"),
        ("posts", "page", "posts"),
        ("both", "post", "both"),
        ("bogus", "page", "pages"),
        (None, "post", "posts"),
        (None, "event", "both"),
        (None, None, "both"),
    ],
)
def test_resolve_scope_matches_search_scope_ts(scope, legacy_type, expected):
    assert resolve_scope(scope, legacy_type) == expected


def test_scope_to_type_maps_pages_posts_and_omits_both():
    assert [scope_to_type(scope) for scope in ("pages", "posts", "both")] == [
        "page",
        "post",
        None,
    ]


def test_the_classic_box_is_a_get_form_to_the_target_path_prefilled_from_q():
    context = build_search_box_context(
        {"placeholder": "Find…", "target_path": "/search", "widget_slug": "box"},
        {},
        {},
        FakeThemeRequest(path="/docs", query={"q": "a&b"}),
    )

    html = _render("search", context)

    assert canonical(html) == canonical(
        '<div class="post-search">'
        '<form class="post-search__form" role="search" method="get" action="/search">'
        '<input type="search" class="post-search__input" placeholder="Find…" '
        'data-testid="post-search-input" role="combobox" aria-autocomplete="list" '
        'aria-expanded="false" aria-controls="post-search-listbox-box" name="q" value="a&amp;b">'
        '<button type="submit" class="post-search__submit" aria-label="Search" '
        f'data-testid="post-search-submit">{SEARCH_ICON}</button>'
        "</form></div>"
    )


def test_without_a_target_path_the_box_submits_to_the_current_page():
    context = build_search_box_context({}, {}, {}, FakeThemeRequest(path="/docs/intro"))

    assert context["action"] == "/docs/intro"
    assert context["placeholder"] == "Search…"
    assert context["quicksearch"] is None


def test_quicksearch_makes_the_input_an_htmx_island_with_scope_and_clamped_limit():
    context = build_search_box_context(
        {
            "quicksearch": True,
            "scope": "posts",
            "quicksearch_limit": 99,
            "widget_slug": "docs",
        },
        {},
        {},
        FakeThemeRequest(path="/docs"),
    )

    html = _render("search", context)

    assert context["quicksearch"] == {
        "url": SEARCH_FRAGMENT_PATH,
        "values": '{"type": "post", "limit": 20, "listbox": "post-search-listbox-docs"}',
    }
    assert f'hx-get="{SEARCH_FRAGMENT_PATH}"' in html
    assert 'hx-trigger="input changed delay:350ms, search"' in html
    assert 'hx-target="#post-search-listbox-docs"' in html
    assert 'hx-swap="outerHTML"' in html
    assert "hx-vals=" in html and "&#34;limit&#34;: 20" in html
    # The closed dropdown is an empty placeholder: never the dropdown testid.
    assert (
        '<ul id="post-search-listbox-docs" class="post-search__dropdown" role="listbox" hidden></ul>'
        in html
    )
    assert testids(html) == ["post-search-input", "post-search-submit"]


@pytest.mark.parametrize("raw_limit, expected", [(0, 1), (3.7, 3), ("x", 6), (None, 6)])
def test_quicksearch_limit_is_clamped_like_the_spa(raw_limit, expected):
    config = {"quicksearch": True, "widget_slug": "w"}
    if raw_limit is not None:
        config["quicksearch_limit"] = raw_limit

    context = build_search_box_context(config, {}, {}, FakeThemeRequest())

    assert f'"limit": {expected}' in context["quicksearch"]["values"]


def test_the_fragment_lists_the_top_results_as_keyboard_options():
    cms_api = FakeCmsApi(
        search=listing([post("a", "Alpha"), post("b", "<B>"), post("c")])
    )
    request = FakeThemeRequest(
        query={
            "q": " quick ",
            "type": "page",
            "limit": "2",
            "listbox": "post-search-listbox-x",
        }
    )

    context = build_quicksearch_fragment_context(request, cms_api.factory)
    html = render(
        theme_plugin(),
        {**context, "language": "en", "default_language": "en"},
        template="cms/fragments/quicksearch.html.j2",
    )

    assert cms_api.calls == [
        ("search", {"q": "quick", "page": 1, "per_page": 2, "type": "page"})
    ]
    assert canonical(html) == canonical(
        '<ul id="post-search-listbox-x" class="post-search__dropdown" role="listbox" '
        'data-testid="post-search-dropdown">'
        '<li id="post-search-listbox-x-option-0" class="post-search__option" role="option" '
        'aria-selected="false" data-testid="post-search-option" data-href="/a">Alpha</li>'
        '<li id="post-search-listbox-x-option-1" class="post-search__option" role="option" '
        'aria-selected="false" data-testid="post-search-option" data-href="/b">&lt;B&gt;</li>'
        "</ul>"
    )


@pytest.mark.parametrize(
    "query, answer",
    [
        ({"q": "  ", "listbox": "post-search-listbox-x"}, listing([post("a")])),
        ({"q": "none", "listbox": "post-search-listbox-x"}, listing([])),
        ({"q": "boom", "listbox": "post-search-listbox-x"}, ThemeApiError(500, "x")),
    ],
)
def test_an_empty_query_no_results_or_a_failure_closes_the_dropdown(query, answer):
    cms_api = FakeCmsApi(search=answer)

    context = build_quicksearch_fragment_context(
        FakeThemeRequest(query=query), cms_api.factory
    )
    html = render(
        theme_plugin(),
        {**context, "language": "en", "default_language": "en"},
        template="cms/fragments/quicksearch.html.j2",
    )

    assert html.strip() == (
        '<ul id="post-search-listbox-x" class="post-search__dropdown" role="listbox" hidden></ul>'
    )


def test_an_unsafe_listbox_id_is_reduced_to_safe_characters():
    context = build_quicksearch_fragment_context(
        FakeThemeRequest(query={"q": "", "listbox": 'x"><script>'}),
        FakeCmsApi().factory,
    )

    assert context["listbox_id"] == "xscript"


def test_search_results_without_q_is_the_prompt():
    context = build_search_results_context(
        {}, {}, {}, FakeThemeRequest(), FakeCmsApi().factory
    )

    assert canonical(_render("search_results", context)) == canonical(
        '<div class="post-search-results"><p class="post-search-results__hint" '
        'data-testid="search-empty-query">Type a search term to begin.</p></div>'
    )


def test_search_results_counts_and_lists_the_matches_with_the_config_scope():
    cms_api = FakeCmsApi(search=listing([post("a", "Alpha")], total=1))
    config = {
        "types": [" page ", "", "post"],
        "per_page": 5,
        "scope_term_type": "category",
        "scope_term_slug": "news",
    }

    context = build_search_results_context(
        config, {}, {}, FakeThemeRequest(query={"q": " ai "}), cms_api.factory
    )
    html = _render("search_results", context)

    assert cms_api.calls == [
        (
            "search",
            {
                "q": "ai",
                "page": 1,
                "per_page": 5,
                "types": "page,post",
                "term_type": "category",
                "term_slug": "news",
            },
        )
    ]
    assert (
        '<p class="post-search-results__count" data-testid="search-result-count">'
        "Showing 1 result for &#34;ai&#34;</p>"
    ) in html
    assert testids(html)[:2] == ["search-result-count", "post-card"]


def test_pinned_types_supersede_the_scope():
    cms_api = FakeCmsApi(search=listing([post("a")]))

    build_search_results_context(
        {"types": ["post"], "scope": "pages"},
        {},
        {},
        FakeThemeRequest(query={"q": "x"}),
        cms_api.factory,
    )

    assert cms_api.calls[0][1]["types"] == "post" and "type" not in cms_api.calls[0][1]


def test_search_results_uses_the_legacy_scope_when_no_types_are_pinned():
    cms_api = FakeCmsApi(search=listing([post("a"), post("b")], total=12))

    context = build_search_results_context(
        {"type": "page"}, {}, {}, FakeThemeRequest(query={"q": "x"}), cms_api.factory
    )

    assert cms_api.calls[0][1]["type"] == "page" and "types" not in cms_api.calls[0][1]
    assert context["count_label"] == 'Showing 12 results for "x"'


@pytest.mark.parametrize("answer", [listing([]), ThemeApiError(500, "boom")])
def test_search_results_without_matches_is_the_no_results_state(answer):
    context = build_search_results_context(
        {},
        {},
        {},
        FakeThemeRequest(query={"q": "nothing"}),
        FakeCmsApi(search=answer).factory,
    )

    assert canonical(_render("search_results", context)) == canonical(
        '<div class="post-search-results"><p class="post-search-results__empty" '
        'data-testid="search-no-results">No results found.</p></div>'
    )
