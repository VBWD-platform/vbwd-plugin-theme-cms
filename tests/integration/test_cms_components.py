"""S152-06b — the cms component twins on a real app (cms + theme + theme_cms, theme mode).

Every component's data comes from the REAL public endpoints (seeded through the
cms admin HTTP API, rolled back after each test): ``/cms/posts``, ``/cms/search``,
``/cms/terms``, ``/cms/archive``, ``/cms/widgets/by-slug``, ``/contact``. The
subscription plugin is NOT booted here, so NativePricingPlans / AddonCatalog get
a 404 from ``/tarif-plans`` / ``/addons/`` and render their empty states. Line
references point at the fe-user e2e specs whose selectors each test proves.
"""
from html.parser import HTMLParser

import pytest

from plugins.theme_cms.tests.integration.cms_seed import unique
from plugins.theme_cms.tests.unit.dom_contract import testids
from plugins.theme_cms.theme_cms.components.breadcrumb import slug_to_label

RENDER = {"X-VBWD-Render": "1"}
SEARCH_FRAGMENT = "/_render/_fragment/cms/search"
CONTACT_FRAGMENT = "/_render/_fragment/cms/contact"


def _get(client, path, **options):
    response = client.get(path, headers=RENDER, **options)
    assert response.status_code == 200, (path, response.status_code)
    return response.get_data(as_text=True)


def _markup(html):
    return html.partition("<body")[2].partition("<script")[0]


def _crumbs(html):
    """``nav.vbwd-breadcrumb > a, > span.vbwd-breadcrumb__current`` as (label, href|None)."""
    crumbs = []

    class _Reader(HTMLParser):
        depth = None
        current = None

        def handle_starttag(self, tag, attrs):
            attributes = dict(attrs)
            if tag == "nav" and "vbwd-breadcrumb" in (attributes.get("class") or ""):
                self.depth = 0
            elif self.depth is not None:
                self.depth += 1
                is_crumb = tag == "a" or "vbwd-breadcrumb__current" in (
                    attributes.get("class") or ""
                )
                if self.depth == 1 and is_crumb:
                    self.current = [tag, attributes.get("href"), ""]

        def handle_data(self, data):
            if self.current is not None:
                self.current[2] += data

        def handle_endtag(self, tag):
            if self.depth is None:
                return
            if self.current is not None and self.depth == 1:
                crumbs.append(
                    (
                        self.current[2].strip(),
                        self.current[1] if self.current[0] == "a" else None,
                    )
                )
                self.current = None
            if tag == "nav" and self.depth == 0:
                self.depth = None
            else:
                self.depth -= 1

    _Reader().feed(html)
    return crumbs


@pytest.fixture
def blog(client, cms):
    """A blog post in the permalink space (``blog/<year>/<category>/<slug>``) with the
    breadcrumb widget, and the terms-archive layout listing prefix archives with
    TermArchive — the cms-breadcrumb-flow fixture shape."""
    breadcrumb = cms.vue_widget("CmsBreadcrumb")
    term_archive = cms.vue_widget("TermArchive")
    cms.terms_archive_layout(client, [breadcrumb, term_archive])
    post_layout = cms.layout(
        [{"name": "crumbs", "type": "header"}, {"name": "main", "type": "content"}],
        [{"widget_id": breadcrumb["id"], "area_name": "crumbs", "sort_order": 0}],
    )
    category = cms.term("category", "Vbwd", unique("vbwd"))
    post = cms.post(
        type="post",
        slug=unique("drop-a-file"),
        title="Add a Feature Without Touching Core",
        layout_id=post_layout["id"],
        content_html="<p>body</p>",
        term_ids=[category["id"]],
    )
    cms.categorize(post, category)
    return {"post": post, "category": category, "segments": post["slug"].split("/")}


def test_every_cms_component_renders_its_twin_never_the_missing_marker(client, cms):
    components = [
        "CmsBreadcrumb",
        "NativePricingPlans",
        "ContactForm",
        "Category",
        "PostTermList",
        "Search",
        "SearchResults",
        "TagArchive",
        "TermArchive",
        "PostArchive",
        "AddonCatalog",
        "CustomCode",
        "CookieConsent",
        "SuperHeader",
    ]
    page = cms.page_with_widgets([cms.vue_widget(name) for name in components])

    html = _markup(_get(client, f"/{page['slug']}"))

    assert "cms-widget--vue-missing" not in html
    for root_marker in (
        'class="vbwd-breadcrumb"',
        'data-testid="landing1-root"',
        'class="contact-form-widget"',
        'class="post-term-list-widget"',
        'class="post-search"',
        'class="post-search-results"',
        'class="tag-archive"',
        'class="term-archive"',
        'class="post-archive-widget"',
        'data-testid="addon-catalog"',
        'data-testid="cms-custom-code"',
        'data-testid="cookie-consent"',
        'class="cms-super-header"',
    ):
        assert root_marker in html, root_marker
    # The subscription plugin is absent: its API 404s, the widgets are empty, not broken.
    assert 'data-testid="landing1-empty"' in html
    assert 'data-testid="addon-catalog-empty"' in html


def test_a_blog_post_breadcrumb_is_the_cumulative_prefix_trail(client, blog):
    # cms-breadcrumb-flow.spec.ts:58-80 — Home, Blog, …, the category term name, the
    # post title; every intermediate crumb links to its cumulative prefix; one current.
    segments = blog["segments"]

    crumbs = _crumbs(_get(client, f"/{blog['post']['slug']}"))

    assert segments[0] == "blog" and blog["category"]["slug"] in segments
    assert crumbs[:2] == [("Home", "/"), ("Blog", "/blog")]
    assert [href for _label, href in crumbs[1:-1]] == [
        "/" + "/".join(segments[: index + 1]) for index in range(len(segments) - 1)
    ]
    category_index = segments.index(blog["category"]["slug"]) + 1
    assert crumbs[category_index][0] == "Vbwd"
    assert crumbs[-1] == ("Add a Feature Without Touching Core", None)
    assert [href for _label, href in crumbs].count(None) == 1


def test_a_breadcrumb_prefix_opens_the_archive_listing_with_post_cards(client, blog):
    # cms-breadcrumb-flow.spec.ts:83-123 — the prefix archive lists post cards, its
    # breadcrumb ends with the current segment, and nothing says "not found".
    prefix = "/".join(blog["segments"][:-1])

    html = _markup(_get(client, f"/{prefix}"))

    assert 'data-testid="post-card"' in html
    assert f'href="/{blog["post"]["slug"]}"' in html
    # A prefix archive has no terms: the current crumb is the title-cased segment.
    assert _crumbs(html)[-1] == (slug_to_label(blog["category"]["slug"]), None)
    assert "not found" not in html.lower()


def test_a_normal_page_breadcrumb_is_home_then_title(client, cms):
    # cms-pages.spec.ts:126-136 — nav[aria-label="breadcrumb"] with a Home link to "/".
    page = cms.page_with_widgets([cms.vue_widget("CmsBreadcrumb")], title="About Us")

    html = _markup(_get(client, f"/{page['slug']}"))

    assert '<nav class="vbwd-breadcrumb" aria-label="breadcrumb">' in html
    assert _crumbs(html) == [("Home", "/"), ("About Us", None)]


@pytest.fixture
def search_site(cms):
    """A published page + post and a draft sharing one FTS token (searchFixtures.ts)."""
    token = unique("quicksleuth").replace("-", "")
    cms.post(title=f"Page about {token}", content_html=f"<p>{token} page</p>")
    cms.post(
        type="post", title=f"Post about {token}", content_html=f"<p>{token} post</p>"
    )
    cms.post(
        title=f"Draft about {token}", status="draft", content_html=f"<p>{token}</p>"
    )
    return token


def test_classic_search_flow_prompt_results_and_no_results(client, cms, search_site):
    # cms-search-results-flow.spec.ts:32-35 selectors; :58 prompt, :70-71 cards, :81 none.
    search_page = cms.page_with_widgets(
        [
            cms.vue_widget("Search", {"target_path": "/placeholder"}),
            cms.vue_widget("SearchResults", {"scope": "both"}),
        ]
    )
    path = f"/{search_page['slug']}"

    prompt = _markup(_get(client, path))
    results = _markup(_get(client, path, query_string={"q": search_site}))
    none = _markup(
        _get(client, path, query_string={"q": unique("zzzz").replace("-", "")})
    )

    assert 'data-testid="post-search-input"' in prompt
    assert 'data-testid="search-empty-query"' in prompt
    assert testids(results).count("post-card") == 2
    assert (
        f"Page about {search_site}" in results
        and f"Post about {search_site}" in results
    )
    assert "Draft about" not in results
    assert 'data-testid="search-result-count"' in results
    assert f'value="{search_site}"' in results
    assert 'data-testid="search-no-results"' in none


def test_quicksearch_island_and_its_fragment_over_the_real_search(
    client, cms, search_site
):
    # cms-search-quicksearch.spec.ts:35-37 selectors; :59-66 page + post, draft
    # excluded; :119-134 the scope narrows; :144-147 the limit caps the options.
    host = cms.page_with_widgets(
        [
            cms.vue_widget(
                "Search", {"quicksearch": True, "scope": "both"}, slug=unique("docs")
            )
        ]
    )
    html = _markup(_get(client, f"/{host['slug']}"))
    assert f'hx-get="{SEARCH_FRAGMENT}"' in html

    def options(**values):
        response = client.get(
            SEARCH_FRAGMENT, query_string={"q": search_site, "listbox": "lb", **values}
        )
        assert response.status_code == 200
        return response.get_data(as_text=True)

    both = options(limit=6)
    pages_only = options(limit=6, type="page")
    capped = options(limit=1)

    assert 'data-testid="post-search-dropdown"' in both
    assert testids(both).count("post-search-option") == 2
    assert "Draft about" not in both
    assert testids(pages_only).count("post-search-option") == 1
    assert f"Page about {search_site}" in pages_only
    assert testids(capped).count("post-search-option") == 1


def test_term_and_tag_archives_list_their_posts(client, cms):
    # TermArchiveWidget: heading + description + PostCards with the category eyebrow.
    term_archive = cms.vue_widget("TermArchive")
    cms.terms_archive_layout(client, [term_archive])
    category = cms.term("category", "Release Notes", unique("rel"))
    tag_slug = unique("plug")
    post = cms.post(
        type="post", title="Tagged Post", excerpt="Short", term_ids=[category["id"]]
    )
    cms.categorize(post, category)
    cms.tag(post, tag_slug)

    category_html = _markup(_get(client, f"/category/{category['slug']}"))
    tag_html = _markup(_get(client, f"/tag/{tag_slug}"))

    assert (
        '<h1 class="term-archive__heading" data-testid="term-archive-heading">Release Notes</h1>'
        in category_html
    )
    assert "Tagged Post" in category_html and 'data-testid="post-card"' in category_html
    assert 'data-testid="post-category"' in category_html
    assert 'data-testid="post-tags"' in category_html
    assert "Tagged Post" in tag_html
    assert 'data-testid="term-archive-heading"' in tag_html


def test_tag_archive_reads_the_tag_query(client, cms):
    tag_slug = unique("guide")
    post = cms.post(type="post", title="A Guide", excerpt="How to")
    cms.tag(post, tag_slug)
    page = cms.page_with_widgets([cms.vue_widget("TagArchive")])

    html = _markup(_get(client, f"/{page['slug']}", query_string={"tag": tag_slug}))
    prompt = _markup(_get(client, f"/{page['slug']}"))

    assert 'data-testid="tag-archive-heading"' in html and "A Guide" in html
    assert 'data-testid="tag-archive-prompt"' in prompt


def test_category_widget_lists_its_pinned_term_with_the_rss_link(client, cms):
    category = cms.term("category", "News", unique("news"))
    post = cms.post(type="post", title="Pinned News")
    cms.categorize(post, category)
    widget = cms.vue_widget(
        "Category",
        {"type": "post", "term_type": "category", "term_slug": category["slug"]},
    )

    html = _markup(_get(client, f"/{cms.page_with_widgets([widget])['slug']}"))

    assert "Pinned News" in html
    assert 'data-testid="post-term-rss-link"' in html


def test_post_archive_paginates_with_links(client, cms):
    cms.post(type="post", title="Archive One")
    cms.post(type="post", title="Archive Two")
    page = cms.page_with_widgets([cms.vue_widget("PostArchive", {"posts_per_page": 1})])

    first = _markup(_get(client, f"/{page['slug']}"))
    second = _markup(_get(client, f"/{page['slug']}", query_string={"page": 2}))

    assert testids(first).count("post-card") == 1
    assert 'data-testid="post-archive-next" href="?page=2"' in first
    assert 'data-testid="post-archive-prev" aria-disabled="true"' in first
    assert 'data-testid="post-archive-prev" href="?page=1"' in second


def test_contact_form_validates_and_submits_through_the_contact_endpoint(client, cms):
    slug = unique("contact")
    widget = cms.vue_widget(
        "ContactForm",
        {
            "recipient_email": "team@example.com",
            "success_message": "Thanks, we got it.",
            "fields": [
                {"id": "name", "type": "text", "label": "Name", "required": True},
                {"id": "email", "type": "email", "label": "Email", "required": True},
            ],
        },
        slug=slug,
    )
    page = cms.page_with_widgets([widget])

    html = _markup(_get(client, f"/{page['slug']}"))
    invalid = client.post(CONTACT_FRAGMENT, data={"widget_slug": slug, "name": "Ada"})
    valid = client.post(
        CONTACT_FRAGMENT,
        data={
            "widget_slug": slug,
            "_hp": "",
            "name": "Ada",
            "email": "ada@example.com",
        },
    )

    assert {"cf-form", "cf-field-name", "cf-field-email", "cf-submit"} <= set(
        testids(html)
    )
    assert f'hx-post="{CONTACT_FRAGMENT}"' in html
    assert invalid.status_code == 200
    assert 'data-testid="cf-error-email"' in invalid.get_data(as_text=True)
    assert valid.status_code == 200, valid.get_data(as_text=True)
    assert 'data-testid="cf-success"' in valid.get_data(as_text=True)
    assert "Thanks, we got it." in valid.get_data(as_text=True)


def test_cookie_consent_custom_code_and_super_header(client, cms):
    menu = cms.widget("menu", slug=unique("header-nav"))
    cms.menu(
        menu["id"], [{"id": "a", "label": "Docs", "page_slug": "docs", "sort_order": 0}]
    )
    page = cms.page_with_widgets(
        [
            cms.vue_widget("CookieConsent", {"consent_version": 2}),
            cms.vue_widget(
                "CustomCode", {"code": "<script>window.themedCode = 1</script><p>x</p>"}
            ),
            cms.vue_widget("SuperHeader", {"nav_widget_slug": menu["slug"]}),
        ]
    )

    html = _get(client, f"/{page['slug']}").partition("<body")[2]

    # cms-breadcrumb-flow.spec.ts:30-35 — the consent backdrop + accept button exist.
    assert (
        'data-testid="cookie-consent-backdrop" data-consent-version="2" hidden' in html
    )
    assert 'data-testid="cookie-accept-all"' in html
    assert (
        '<div class="cms-custom-code" data-testid="cms-custom-code"><script>window.themedCode = 1</script></div>'
        in html
    )
    assert '<a href="/docs" target="_self" class="cms-menu__link">Docs</a>' in html
    assert 'data-test-id="super-header-login-icon"' in html


def test_the_cms_document_ships_the_component_runtimes(client, cms):
    page = cms.page_with_widgets([cms.vue_widget("CookieConsent")])

    html = _get(client, f"/{page['slug']}")

    assert "var STORAGE_KEY = 'vbwd_cookie_consent';" in html
    assert "var ACTIVE_CLASS = 'post-search__option--active';" in html


def test_the_component_fragments_are_public_and_answer_without_the_page_marker(client):
    response = client.get(SEARCH_FRAGMENT, query_string={"q": "", "listbox": "lb"})

    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-store"
    assert response.get_data(as_text=True).strip().startswith('<ul id="lb"')
