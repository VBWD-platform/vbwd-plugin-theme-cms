"""S152-06b — every selector of the fe-user cms e2e specs exists in the THEMED output.

``SPEC_SELECTORS`` maps each spec line (fe-user ``plugins/cms/tests/e2e/*.spec.ts``
and ``vue/tests/e2e/cms-pages.spec.ts``) to the markup it targets and the seeded
page that must contain it. The quick-search active-row class is set by the
runtime (node:test proves the behaviour); here it must ship in the page. A
drift guard re-reads the specs (when the fe-user checkout is mounted) so a new
``data-testid`` selector cannot appear without an entry here.
"""
import re
from pathlib import Path

import pytest

from plugins.theme_cms.tests.integration.cms_seed import unique

RENDER = {"X-VBWD-Render": "1"}
BACKEND_ROOT = Path(__file__).resolve().parents[4]
FE_USER_ROOT = BACKEND_ROOT.parent / "vbwd-fe-user"
SPEC_FILES = sorted(
    (FE_USER_ROOT / "plugins" / "cms" / "tests" / "e2e").glob("*.spec.ts")
) + [FE_USER_ROOT / "vue" / "tests" / "e2e" / "cms-pages.spec.ts"]
SPEC_TESTID = re.compile(r'data-testid="([^"]+)"')
# Testids that are only one alternative of a selector union whose other branch matches.
UNION_ALTERNATIVES = {
    # cms-pages.spec.ts:131 '.cms-breadcrumb, nav[aria-label="breadcrumb"], …,
    # [data-testid="breadcrumb"]' — the nav[aria-label] branch is the contract (SPA too).
    "breadcrumb",
}

# (spec line, markup that must be present, seeded page key)
SPEC_SELECTORS = [
    ("cms-search-results-flow.spec.ts:32", 'data-testid="post-search-input"', "search"),
    (
        "cms-search-results-flow.spec.ts:33",
        'data-testid="search-empty-query"',
        "search",
    ),
    (
        "cms-search-results-flow.spec.ts:34",
        'data-testid="search-no-results"',
        "search_none",
    ),
    ("cms-search-results-flow.spec.ts:35", 'data-testid="post-card"', "search_hits"),
    (
        "cms-search-quicksearch.spec.ts:35",
        'data-testid="post-search-dropdown"',
        "quicksearch",
    ),
    (
        "cms-search-quicksearch.spec.ts:36",
        'data-testid="post-search-option"',
        "quicksearch",
    ),
    ("cms-search-quicksearch.spec.ts:37", 'data-testid="post-search-input"', "docs"),
    ("cms-search-quicksearch.spec.ts:87", "post-search__option--active", "docs"),
    (
        "cms-breadcrumb-flow.spec.ts:22",
        '<nav class="vbwd-breadcrumb" aria-label="breadcrumb">',
        "post",
    ),
    ("cms-breadcrumb-flow.spec.ts:23", 'class="vbwd-breadcrumb__current"', "post"),
    ("cms-breadcrumb-flow.spec.ts:24", 'data-testid="post-card"', "archive"),
    ("cms-breadcrumb-flow.spec.ts:30", 'data-testid="cookie-accept-all"', "post"),
    ("cms-breadcrumb-flow.spec.ts:34", 'data-testid="cookie-consent-backdrop"', "post"),
    ("cms-pages.spec.ts:131", 'aria-label="breadcrumb"', "about"),
    (
        "cms-pages.spec.ts:134",
        '<a href="/" class="vbwd-breadcrumb__link">Home</a>',
        "about",
    ),
]


@pytest.fixture
def themed_pages(client, cms):
    """Renders every page the selectors live on (seeded through the cms admin API)."""
    token = unique("quicksleuth").replace("-", "")
    cms.post(title=f"Page {token}", content_html=f"<p>{token}</p>")
    breadcrumb = cms.vue_widget("CmsBreadcrumb")
    consent = cms.vue_widget("CookieConsent")
    cms.terms_archive_layout(client, [breadcrumb, cms.vue_widget("TermArchive")])
    post_layout = cms.layout(
        [
            {"name": "crumbs", "type": "header"},
            {"name": "main", "type": "content"},
            {"name": "consent", "type": "footer"},
        ],
        [
            {"widget_id": breadcrumb["id"], "area_name": "crumbs", "sort_order": 0},
            {"widget_id": consent["id"], "area_name": "consent", "sort_order": 0},
        ],
    )
    category = cms.term("category", "Vbwd", unique("vbwd"))
    post = cms.post(
        type="post",
        layout_id=post_layout["id"],
        term_ids=[category["id"]],
        content_html=f"<p>{token}</p>",
    )
    search = cms.page_with_widgets(
        [cms.vue_widget("Search"), cms.vue_widget("SearchResults")]
    )
    docs = cms.page_with_widgets([cms.vue_widget("Search", {"quicksearch": True})])
    about = cms.page_with_widgets([cms.vue_widget("CmsBreadcrumb")], title="About")

    def page(path, **query):
        response = client.get(path, headers=RENDER, query_string=query)
        assert response.status_code == 200, path
        return response.get_data(as_text=True)

    return {
        "search": page(f"/{search['slug']}"),
        "search_none": page(f"/{search['slug']}", q=unique("nothing").replace("-", "")),
        "search_hits": page(f"/{search['slug']}", q=token),
        "quicksearch": client.get(
            "/_render/_fragment/cms/search", query_string={"q": token, "listbox": "lb"}
        ).get_data(as_text=True),
        "docs": page(f"/{docs['slug']}"),
        "post": page(f"/{post['slug']}"),
        "archive": page("/" + post["slug"].rsplit("/", 1)[0]),
        "about": page(f"/{about['slug']}"),
    }


@pytest.mark.parametrize(
    "spec_line, markup, page_key",
    SPEC_SELECTORS,
    ids=[entry[0] for entry in SPEC_SELECTORS],
)
def test_every_e2e_selector_is_in_the_themed_page(
    themed_pages, spec_line, markup, page_key
):
    assert markup in themed_pages[page_key], spec_line


def test_no_page_says_page_not_found(themed_pages):
    # cms-pages.spec.ts:27-81 — themed pages never carry the SPA's not-found copy.
    assert all("Page not found" not in html for html in themed_pages.values())


def test_every_spec_testid_has_a_contract_entry():
    if not all(spec.is_file() for spec in SPEC_FILES):
        pytest.skip("fe-user checkout not mounted next to vbwd-backend")
    spec_testids = {
        testid
        for spec in SPEC_FILES
        for testid in SPEC_TESTID.findall(spec.read_text(encoding="utf-8"))
    }
    covered = {
        match
        for _line, markup, _page in SPEC_SELECTORS
        for match in SPEC_TESTID.findall(markup)
    }

    assert spec_testids - covered - UNION_ALTERNATIVES == set()
