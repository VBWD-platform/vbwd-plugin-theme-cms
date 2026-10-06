"""S152-06a — themed CMS pages on a real app (cms + theme + theme_cms, theme mode).

Resolution order (page → post → term archive → prefix archive → 404, 403,
preview), the home slug, layouts/areas (W1, page override, config_override),
the style cascade and head, hreflang vs the cms prerender head, embeds,
catch-all priority, page language (and its UI strings) and access-filtered
areas via /regions.
"""
import re
import uuid

import pytest

from plugins.theme_cms.tests.integration.cms_seed import unique

RENDER = {"X-VBWD-Render": "1"}
REGIONS_PATH = "/_render/_fragment/regions"
HREFLANG = re.compile(r'<link rel="alternate" hreflang="([^"]+)" href="([^"]+)"')
TEST_PASSWORD = "SecurePassword123!"


def _get(client, path, **options):
    return client.get(path, headers=RENDER, **options)


def _markup(html):
    return html.partition("<body")[2].partition("<script")[0]


def test_a_page_renders_with_its_layout_widgets_and_style(client, cms):
    style = cms.style(".theme-cms-style{color:red}")
    header = cms.html_widget("<b>HEADER-WIDGET</b>")
    layout = cms.layout(
        [{"name": "header", "type": "header"}, {"name": "main", "type": "content"}],
        [{"widget_id": header["id"], "area_name": "header", "sort_order": 0}],
    )
    page = cms.post(
        content_html="<p>PAGE-BODY</p>",
        layout_id=layout["id"],
        style_id=style["id"],
        source_css=".post-css{}",
    )

    response = _get(client, f"/{page['slug']}")

    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert f'<div class="cms-layout cms-layout--{layout["slug"]}">' in html
    assert "PAGE-BODY" in _markup(html) and "HEADER-WIDGET" in _markup(html)
    assert (
        "<style data-cms-page-style>.theme-cms-style{color:red}\n.post-css{}</style>"
        in html
    )
    assert '<meta name="vbwd-frontend" content="theme">' in html


def test_a_post_resolves_through_the_type_post_retry_with_its_hero(client, cms):
    post = cms.post(
        type="post",
        title="Hello Theme",
        excerpt="Lead",
        content_html="<p>POST-BODY</p>",
    )

    html = _get(client, f"/{post['slug']}").get_data(as_text=True)

    assert '<header class="cms-post-hero cms-post-hero--gradient">' in html
    assert '<h1 class="cms-post-title">Hello Theme</h1>' in html and "POST-BODY" in html


def test_a_category_slug_resolves_to_the_term_archive(client, cms):
    term_slug = unique("cat")
    created = client.post(
        "/api/v1/admin/cms/terms",
        headers=cms.headers,
        json={"term_type": "category", "name": "Theme Cat", "slug": term_slug},
    )
    assert created.status_code == 201, created.get_json()

    response = _get(client, f"/category/{term_slug}")

    assert response.status_code == 200
    assert "<title>Theme Cat</title>" in response.get_data(as_text=True)


def test_a_path_prefix_resolves_to_the_prefix_archive(client, cms):
    prefix = unique("archive")
    cms.post(type="post", slug=f"{prefix}/first", title="First")
    article = cms.post(type="post", slug=f"{prefix}/second", title="Second")
    archive_path = article["slug"].rsplit("/", 1)[0]

    response = _get(client, f"/{archive_path}")

    assert response.status_code == 200
    assert (
        f"<title>{archive_path.rsplit('/', 1)[-1].replace('-', ' ').title()}</title>"
        in (response.get_data(as_text=True))
    )


def test_an_unknown_slug_is_a_404_so_nginx_falls_back_to_the_spa(client):
    assert _get(client, f"/{unique('nothing-here')}").status_code == 404


def test_a_draft_previews_with_its_token_and_a_wrong_token_is_access_denied(
    client, cms
):
    draft = cms.post(status="draft", content_html="<p>DRAFT-BODY</p>")

    previewed = _get(client, f"/{draft['slug']}?preview_token={draft['preview_token']}")
    refused = _get(client, f"/{draft['slug']}?preview_token=wrong")
    anonymous = _get(client, f"/{draft['slug']}")

    assert "DRAFT-BODY" in previewed.get_data(as_text=True)
    refused_html = refused.get_data(as_text=True)
    assert refused.status_code == 200
    assert '<div class="cms-page__access-denied">' in refused_html
    assert '<a href="/login" class="cms-page__login-link">' in refused_html
    assert "DRAFT-BODY" not in refused_html
    assert anonymous.status_code == 404


def test_home_renders_the_configured_home_slug_in_place(client, cms, cms_config):
    home = cms.post(content_html="<p>HOME-BODY</p>")
    cms_config["home_slug"] = home["slug"]

    html = _get(client, "/").get_data(as_text=True)

    assert "HOME-BODY" in html
    assert '<link rel="canonical" href="https://site.example/" data-seo="ssr">' in html


def test_multi_widget_area_order_and_page_override_with_config_override(client, cms):
    first = cms.html_widget("<i>W-FIRST</i>")
    second = cms.html_widget("<i>W-SECOND</i>")
    footer = cms.html_widget("<i>W-FOOTER</i>")
    layout = cms.layout(
        [
            {"name": "header", "type": "header"},
            {"name": "main", "type": "content"},
            {"name": "aside", "type": "page-widget"},
            {"name": "footer", "type": "footer"},
        ],
        [
            {"widget_id": second["id"], "area_name": "header", "sort_order": 2},
            {"widget_id": first["id"], "area_name": "header", "sort_order": 1},
            {"widget_id": footer["id"], "area_name": "footer", "sort_order": 0},
        ],
    )
    plain = cms.post(layout_id=layout["id"], content_html="<p>x</p>")
    overridden = cms.post(layout_id=layout["id"], content_html="<p>y</p>")
    replacement = cms.html_widget("<i>W-PAGE</i>")
    cms.post_widgets(
        overridden["id"],
        [
            {"widget_id": replacement["id"], "area_name": "header", "sort_order": 0},
            {
                "widget_id": first["id"],
                "area_name": "aside",
                "sort_order": 0,
                "config_override": {"content_html": "<i>W-OVERRIDDEN</i>"},
            },
        ],
    )

    plain_html = _markup(_get(client, f"/{plain['slug']}").get_data(as_text=True))
    overridden_html = _markup(
        _get(client, f"/{overridden['slug']}").get_data(as_text=True)
    )

    assert plain_html.index("W-FIRST") < plain_html.index("W-SECOND")
    assert "cms-area--page-widget" not in plain_html
    assert "W-PAGE" in overridden_html and "W-SECOND" not in overridden_html
    assert '<div class="cms-area cms-area--page-widget">' in overridden_html
    assert "W-OVERRIDDEN" in overridden_html and "W-FOOTER" in overridden_html


def test_menu_slideshow_and_vue_component_widgets(client, cms):
    menu = cms.widget("menu", slug=unique("menu"))
    cms.menu(
        menu["id"],
        [{"id": "a", "label": "About", "page_slug": "about", "sort_order": 0}],
    )
    slideshow = cms.widget(
        "slideshow", content_json={"images": [{"url": "/1.jpg"}, {"url": "/2.jpg"}]}
    )
    missing = cms.widget("vue-component", content_json={"component": "ProductGrid"})
    spa_only = cms.widget(
        "vue-component", config={"component_name": "TukTukIntakeWidget"}
    )
    areas = [{"name": name, "type": "header"} for name in ("a", "b", "c", "d")]
    widgets = (menu, slideshow, missing, spa_only)
    layout = cms.layout(
        areas,
        [
            {"widget_id": widget["id"], "area_name": area["name"], "sort_order": 0}
            for widget, area in zip(widgets, areas)
        ],
    )
    page = cms.post(layout_id=layout["id"])

    html = _markup(_get(client, f"/{page['slug']}").get_data(as_text=True))

    assert (
        f'<nav class="cms-widget cms-widget--menu cms-widget--{menu["slug"]}">' in html
    )
    assert '<a href="/about" target="_self" class="cms-menu__link">About</a>' in html
    assert '<div class="cms-slide cms-slide--active"><img src="/1.jpg"' in html
    assert '<!-- cms widget component "ProductGrid" not available -->' in html
    assert 'href="/tuktuk/chat"' in html


def test_layout_head_html_and_global_head_html_are_in_the_head(client, cms):
    layout = cms.layout(
        [{"name": "main", "type": "content"}],
        head_html="<script>window.themeCmsHead=1</script>",
    )
    page = cms.post(layout_id=layout["id"])

    head = (
        _get(client, f"/{page['slug']}").get_data(as_text=True).partition("</head>")[0]
    )

    assert "<script>window.themeCmsHead=1</script>" in head
    assert '<meta name="site-verification" content="theme-cms-test">' in head
    assert head.index("window.themeCmsHead") < head.index("site-verification")


def _prerender_hreflang(var_directory, slug):
    prerendered = (var_directory / "seo" / f"{slug}.html").read_text(encoding="utf-8")
    return re.findall(
        r'<link rel="alternate" hreflang="([^"]+)" href="([^"]+)"', prerendered
    )


def test_hreflang_equals_the_cms_seo_head_with_and_without_siblings(
    client, cms, var_directory
):
    group_id = str(uuid.uuid4())
    english = cms.post(
        language="en",
        translation_group_id=group_id,
        canonical_url="https://site.example/en-page",
    )
    german = cms.post(
        language="de",
        translation_group_id=group_id,
        canonical_url="https://site.example/de-seite",
    )
    lonely = cms.post(language="en")
    # Re-save the first post so its prerender sees the sibling created after it.
    cms._send("PUT", f"/posts/{english['id']}", {"title": english["title"]}, 200)

    themed = HREFLANG.findall(
        _get(client, f"/{english['slug']}").get_data(as_text=True)
    )
    themed_lonely = HREFLANG.findall(
        _get(client, f"/{lonely['slug']}").get_data(as_text=True)
    )

    assert themed == _prerender_hreflang(var_directory, english["slug"])
    assert themed == [
        ("en", "https://site.example/en-page"),
        ("de", german["canonical_url"]),
        ("x-default", "https://site.example/en-page"),
    ]
    assert themed_lonely == _prerender_hreflang(var_directory, lonely["slug"])
    assert [language for language, _url in themed_lonely] == ["en", "x-default"]


def test_page_language_comes_from_the_post_capped_to_cms_languages(
    client, cms, cms_config
):
    german = cms.post(language="de")

    assert '<html lang="de">' in _get(client, f"/{german['slug']}").get_data(
        as_text=True
    )
    cms_config["enabled_languages"] = "en"
    assert '<html lang="en">' in _get(client, f"/{german['slug']}").get_data(
        as_text=True
    )


def test_ui_strings_follow_the_post_language(client, cms):
    """S152-05b: the generated ``de.json`` reaches the page; ``en`` stays English."""
    consent = cms.vue_widget("CookieConsent")
    german = cms.page_with_widgets([consent], language="de")
    english = cms.page_with_widgets([consent], language="en")

    german_html = _markup(_get(client, f"/{german['slug']}").get_data(as_text=True))
    english_html = _markup(_get(client, f"/{english['slug']}").get_data(as_text=True))

    assert "Ihre Privatsphäre ist uns wichtig" in german_html
    assert "We value your privacy" not in german_html
    assert "We value your privacy" in english_html


def test_the_language_cookie_is_capped_by_the_cms_policy(client, cms, cms_config):
    synthetic_term = unique("lang-cat")
    client.post(
        "/api/v1/admin/cms/terms",
        headers=cms.headers,
        json={"term_type": "category", "name": "L", "slug": synthetic_term},
    )
    client.set_cookie("vbwd_lang", "de")

    assert '<html lang="de">' in _get(client, f"/category/{synthetic_term}").get_data(
        as_text=True
    )
    cms_config["enabled_languages"] = "en,fr"
    assert '<html lang="en">' in _get(client, f"/category/{synthetic_term}").get_data(
        as_text=True
    )


def test_a_more_specific_themed_page_wins_over_the_catch_all(client):
    response = _get(client, "/shop")

    assert response.status_code == 200
    assert "FAKE-SHOP-PAGE" in response.get_data(as_text=True)


def test_the_catch_all_never_answers_spa_only_paths(client, cms):
    cms.post(slug="dashboard/x")

    assert _get(client, "/dashboard/x").status_code == 404


def test_the_catch_all_answers_only_nginx_marked_requests(client, cms):
    page = cms.post()

    assert client.get(f"/{page['slug']}").status_code == 404


def test_embed_detail_renders_the_post_with_its_layout(client, cms):
    layout = cms.layout([{"name": "main", "type": "content"}])
    post = cms.post(
        type="post", layout_id=layout["id"], content_html="<p>EMBED-BODY</p>"
    )

    html = _get(client, f"/cms/embed/post/post/{post['slug']}").get_data(as_text=True)

    assert f"cms-layout--{layout['slug']}" in html and "EMBED-BODY" in html


def test_embed_archive_lists_the_category_posts_and_empty_fails_loud(client, cms):
    category = unique("embed-cat")
    term = client.post(
        "/api/v1/admin/cms/terms",
        headers=cms.headers,
        json={"term_type": "category", "name": "Embed", "slug": category},
    ).get_json()
    post = cms.post(type="post", title="Embedded One")
    cms._send("PUT", f"/posts/{post['id']}/terms", {"term_ids": [term["id"]]}, 200)

    listed = _get(client, f"/cms/embed/post/{category}").get_data(as_text=True)
    empty = _get(client, f"/cms/embed/post/{unique('none')}").get_data(as_text=True)

    assert 'data-testid="post-card"' in listed and "Embedded One" in listed
    assert f'href="/cms/embed/post/post/{post["slug"]}"' in listed
    assert 'data-testid="cms-embed-archive-empty"' in empty


def test_pages_index_lists_published_pages(client, cms):
    page = cms.post(title="Indexed Page", meta_description="Indexed desc")

    html = _get(client, "/pages", query_string={"per_page": 100}).get_data(as_text=True)

    assert '<div class="cms-index">' in html
    assert f'href="/{page["slug"]}"' in html or "cms-index__pagination" in html


@pytest.fixture
def user_with_level(app, db):
    from vbwd.repositories.user_repository import UserRepository
    from vbwd.services.auth_service import AuthService
    from vbwd.services.user_access_level_service import UserAccessLevelService

    def create(level):
        user_repository = UserRepository(db.session)
        auth_service = AuthService(user_repository=user_repository)
        result = auth_service.register(
            f"theme-cms-{uuid.uuid4().hex}@example.com", TEST_PASSWORD
        )
        assert result.success, result.error
        UserAccessLevelService(db.session).assign(result.user_id, level.id)
        db.session.commit()
        token = auth_service.generate_access_token(
            result.user_id, user_repository.find_by_id(result.user_id).email
        )
        return {"Authorization": f"Bearer {token}"}

    return create


def test_an_access_gated_widget_is_hidden_anonymously_and_shown_via_regions(
    client, cms, user_with_level
):
    level = cms.access_level(unique("theme-cms-pro"))
    gated = cms.html_widget("<b>GATED-PRO-WIDGET</b>")
    public = cms.html_widget("<b>PUBLIC-WIDGET</b>")
    layout = cms.layout(
        [
            {"name": "header", "type": "header"},
            {"name": "main", "type": "content"},
            {"name": "promo", "type": "cta-bar"},
        ],
        [
            {"widget_id": public["id"], "area_name": "header", "sort_order": 0},
            {
                "widget_id": gated["id"],
                "area_name": "promo",
                "sort_order": 0,
                "required_access_level_ids": [str(level.id)],
            },
        ],
    )
    page = cms.post(layout_id=layout["id"])
    headers = user_with_level(level)

    anonymous = _get(client, f"/{page['slug']}").get_data(as_text=True)
    regions = client.get(
        REGIONS_PATH, query_string={"path": f"/{page['slug']}"}, headers=headers
    )

    assert "GATED-PRO-WIDGET" not in anonymous
    assert '<div data-vbwd-region="r2"></div>' in anonymous
    payload = regions.get_json()
    assert regions.status_code == 200, payload
    assert "GATED-PRO-WIDGET" in payload["regions"]["r2"]
    assert "PUBLIC-WIDGET" in payload["regions"]["r1"]


def test_adapters_reach_the_component_registry(app):
    from plugins.theme_cms.theme_cms.registries import (
        resolve_component_template_registry,
    )

    with app.app_context():
        registry = resolve_component_template_registry()
        assert registry is app.plugin_manager.get_plugin("theme_cms").component_registry
