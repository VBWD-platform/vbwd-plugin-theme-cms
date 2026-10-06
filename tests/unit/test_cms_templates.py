"""S152-06a — the DOM/class contract of the theme_cms templates (the SPA's markup).

Renders through the real theme renderer: page types (post hero both variants,
hero off, no-layout article), the layout + area wrappers (content areas, widget
areas as personalised regions, empty areas skipped), each widget type, the head
(SEO tags, style cascade, layout head_html, global head HTML, hreflang) and the
access-denied partial. Everything is in the HTML: the page works without JS.
"""
import base64
import re

import pytest

from plugins.theme.theme.viewer import Viewer
from plugins.theme_cms.theme_cms.registries import (
    ComponentTemplate,
    ComponentTemplateRegistry,
)
from plugins.theme_cms.tests.unit.template_harness import (
    page_context,
    render,
    render_with_regions,
    theme_plugin,
)


@pytest.fixture(autouse=True)
def isolated_var_directory(tmp_path, monkeypatch):
    monkeypatch.setenv("VBWD_VAR_DIR", str(tmp_path / "var"))


@pytest.fixture
def plugin():
    return theme_plugin()


def _post(**fields):
    return {
        "id": "p",
        "slug": "news/hello",
        "type": "post",
        "title": "My Great Post",
        "excerpt": "A short summary.",
        "content_html": "<p>Body copy</p>",
        "language": "en",
        "terms": [
            {"term_type": "tag", "slug": "vue", "name": "Vue"},
            {"term_type": "category", "slug": "news", "name": "News"},
        ],
        **fields,
    }


def _body(html):
    return html.partition("<body")[2]


def _markup(html):
    """The body markup without the scripts (the runtime JS names the same classes)."""
    return _body(html).partition("<script")[0]


def test_post_hero_with_an_image(plugin):
    html = render(plugin, page_context(_post(featured_image_url="/uploads/hero.jpg")))

    assert (
        '<header class="cms-post-hero cms-post-hero--image" '
        'style="background-image: url(&quot;/uploads/hero.jpg&quot;);">'
        '<div class="cms-post-hero__scrim"></div>'
        '<div class="cms-post-hero__content">'
        '<div class="cms-post-hero__contrast"><h1 class="cms-post-title">My Great Post</h1>'
        '<p class="cms-post-excerpt">A short summary.</p></div>'
        '<div class="cms-post-tags" aria-label="Tags"><a class="cms-post-tag" href="/tag/vue">Vue</a></div>'
        "</div></header><p>Body copy</p>"
    ) in html
    assert "News" not in _body(html)


def test_post_hero_gradient_without_an_image(plugin):
    html = render(plugin, page_context(_post(excerpt="", terms=[])))

    assert (
        '<header class="cms-post-hero cms-post-hero--gradient"><div class="cms-post-hero__content">'
        '<div class="cms-post-hero__contrast"><h1 class="cms-post-title">My Great Post</h1></div>'
        "</div></header>"
    ) in html
    assert "background-image" not in html


def test_post_with_the_hero_off_gets_the_plain_header(plugin):
    html = render(
        plugin,
        page_context(
            _post(
                type_data={"show_featured_hero": False},
                featured_image_url="/uploads/hero.jpg",
            )
        ),
    )

    assert (
        '<header class="cms-post-header"><h1 class="cms-post-title">My Great Post</h1>'
        '<div class="cms-post-tags" aria-label="Tags"><a class="cms-post-tag" href="/tag/vue">Vue</a></div>'
        "</header>"
    ) in html
    assert "cms-post-hero" not in html and "cms-post-excerpt" not in html


def test_a_page_without_a_layout_renders_the_article_fallback(plugin):
    html = render(
        plugin,
        page_context(
            {
                "id": "p",
                "slug": "about",
                "type": "page",
                "title": "About",
                "content_html": "<p>About us</p>",
            }
        ),
    )

    assert (
        '<article class="cms-page__content"><h1 class="cms-page__title">About</h1>'
        '<div class="cms-page__body"><p>About us</p></div></article>'
    ) in html
    assert '<div class="cms-page">' in html
    assert "cms-post-hero" not in html


def _html_widget(slug, text, **fields):
    encoded = base64.b64encode(text.encode()).decode()
    return {
        "id": slug,
        "slug": slug,
        "widget_type": "html",
        "content_json": {"content": encoded},
        **fields,
    }


LAYOUT = {
    "id": "L",
    "slug": "main-layout",
    "head_html": "<script>window.layoutHead=1</script>",
    "areas": [
        {"name": "header", "type": "header"},
        {"name": "main", "type": "content"},
        {"name": "sidebar", "type": "two-column"},
        {"name": "footer", "type": "footer"},
    ],
    "assignments": [
        {
            "area_name": "header",
            "sort_order": 2,
            "widget": _html_widget("second", "<b>2</b>"),
        },
        {
            "area_name": "header",
            "sort_order": 1,
            "widget": _html_widget("first", "<b>1</b>", source_css="a > b{}"),
        },
        {
            "area_name": "footer",
            "sort_order": 0,
            "widget": _html_widget("foot", "<i>f</i>"),
        },
    ],
}


def _laid_out_page(**fields):
    return {
        "id": "p",
        "slug": "about",
        "type": "page",
        "title": "About",
        "content_html": "<p>About us</p>",
        **fields,
    }


def test_layout_root_content_area_and_widget_areas_in_order(plugin):
    html = render(plugin, page_context(_laid_out_page(), layout=LAYOUT))

    assert '<div class="cms-layout cms-layout--main-layout">' in html
    assert (
        '<main class="cms-area cms-area--content cms-area--main"><div class="container">'
        '<div class="cms-page__body"><p>About us</p></div></div></main>'
    ) in html
    header_start = html.index(
        '<div class="cms-area cms-area--header"><div class="container">'
    )
    assert (
        header_start
        < html.index("<b>1</b>")
        < html.index("<b>2</b>")
        < html.index("cms-area--content")
    )
    assert (
        '<div class="cms-widget cms-widget--html"><style>a > b{}</style><div><b>1</b></div></div>'
        in html
    )
    assert (
        html.index("cms-area--header")
        < html.index("cms-area--content")
        < html.index("cms-area--footer")
    )


def test_every_widget_area_is_a_personalised_region_and_empty_ones_render_no_area(
    plugin,
):
    rendered = render_with_regions(
        plugin, page_context(_laid_out_page(), layout=LAYOUT)
    )

    assert list(rendered.regions) == ["r1", "r2", "r3"]
    assert "cms-area--header" in rendered.regions["r1"]
    assert rendered.regions["r2"].strip() == ""
    assert "cms-area--two-column" not in rendered.html
    assert "cms-area--footer" in rendered.regions["r3"]
    assert '<div data-vbwd-region="r1">' in rendered.html


def test_page_assignments_replace_the_layout_widgets_of_an_area(plugin):
    page = _laid_out_page(
        page_assignments=[
            {
                "area_name": "header",
                "sort_order": 0,
                "widget": _html_widget("page-w", "<u>page</u>"),
            },
            {
                "area_name": "sidebar",
                "sort_order": 0,
                "widget": _html_widget("side", "<em>side</em>"),
                "config_override": {"content_html": "<em>overridden</em>"},
            },
        ]
    )

    html = render(plugin, page_context(page, layout=LAYOUT))

    assert "<u>page</u>" in html and "<b>1</b>" not in html
    assert (
        '<div class="cms-area cms-area--two-column">' in html
        and "<em>overridden</em>" in html
    )


def test_a_content_block_feeds_its_named_content_area(plugin):
    layout = {
        **LAYOUT,
        "areas": [
            {"name": "main", "type": "content"},
            {"name": "extra", "type": "content"},
        ],
    }
    page = _laid_out_page(content_blocks={"extra": {"content_html": "<p>Extra</p>"}})

    html = render(plugin, page_context(page, layout=layout))

    assert (
        '<main class="cms-area cms-area--content cms-area--extra">'
        '<div class="container"><div class="cms-page__body"><p>Extra</p>' in html
    )


MENU = {
    "id": "m",
    "slug": "main-menu",
    "widget_type": "menu",
    "config": {"show_cart": True},
    "menu_items": [
        {
            "id": "1",
            "parent_id": None,
            "label": "Docs",
            "url": None,
            "page_slug": None,
            "target": None,
            "icon": None,
        },
        {
            "id": "2",
            "parent_id": "1",
            "label": "Guide",
            "url": None,
            "page_slug": "guide",
            "target": None,
            "icon": "*",
        },
        {
            "id": "3",
            "parent_id": None,
            "label": "About",
            "url": None,
            "page_slug": "about",
            "target": "_blank",
            "icon": None,
        },
    ],
}


def _single_widget_page(plugin, widget, component_registry=None):
    layout = {
        "id": "L",
        "slug": "w",
        "areas": [{"name": "header", "type": "header"}],
        "assignments": [{"area_name": "header", "sort_order": 0, "widget": widget}],
    }
    return render(
        plugin,
        page_context(
            _laid_out_page(), layout=layout, component_registry=component_registry
        ),
    )


def test_menu_widget_markup(plugin):
    html = _single_widget_page(plugin, MENU)

    assert '<nav class="cms-widget cms-widget--menu cms-widget--main-menu">' in html
    assert (
        '<button class="cms-burger" type="button" aria-label="Toggle menu"><span>'
        "</span><span></span><span></span></button>" in html
    )
    assert '<div class="cms-menu-overlay"></div>' in html
    assert '<ul class="cms-menu">' in html
    assert (
        '<li class="cms-menu__item cms-menu__item--has-children">'
        '<a href="#" target="_self" class="cms-menu__link">Docs<span class="cms-menu__arrow">'
        in html
    )
    assert (
        '<ul class="cms-menu__sub"><li class="cms-menu__item">'
        '<a href="/guide" target="_self" class="cms-menu__link">'
        '<span class="cms-menu__icon">*</span>Guide</a></li></ul>' in html
    )
    assert (
        '<li class="cms-menu__item"><a href="/about" target="_blank" class="cms-menu__link">About</a></li>'
        in html
    )
    assert '<li class="cms-menu__item cms-menu__item--cart"></li>' in html


def test_slideshow_widget_markup(plugin):
    widget = {
        "id": "s",
        "slug": "s",
        "widget_type": "slideshow",
        "content_json": {
            "images": [
                {"url": "/1.jpg", "alt": "One", "caption": "First"},
                {"url": "/2.jpg"},
            ]
        },
    }

    html = _single_widget_page(plugin, widget)

    assert (
        '<div class="cms-widget cms-widget--slideshow"><div class="cms-slideshow">'
        in html
    )
    assert (
        '<div class="cms-slide cms-slide--active">'
        '<img src="/1.jpg" alt="One" class="cms-slide__img"><p class="cms-slide__caption">First</p></div>'
        in html
    )
    assert (
        '<div class="cms-slide"><img src="/2.jpg" alt="" class="cms-slide__img"></div>'
        in html
    )
    assert (
        '<button class="cms-slide__prev" type="button">' in html
        and 'class="cms-slide__next"' in html
    )


def test_empty_slideshow_and_single_slide_have_no_controls(plugin):
    empty = _single_widget_page(
        plugin, {"id": "s", "slug": "s", "widget_type": "slideshow", "content_json": {}}
    )
    single = _single_widget_page(
        plugin,
        {
            "id": "s",
            "slug": "s",
            "widget_type": "slideshow",
            "content_json": {"images": [{"url": "/1.jpg"}]},
        },
    )

    assert '<div class="cms-slideshow--empty"></div>' in empty
    assert "cms-slide__prev" not in _markup(single)


def test_unknown_vue_component_renders_the_missing_comment_not_500(plugin):
    html = _single_widget_page(
        plugin,
        {
            "id": "v",
            "slug": "v",
            "widget_type": "vue-component",
            "content_json": {"component": "ProductGrid"},
        },
    )

    assert (
        '<div class="cms-widget cms-widget--vue cms-widget--vue-missing">'
        '<!-- cms widget component "ProductGrid" not available --></div>'
    ) in html


def test_spa_only_component_renders_an_spa_link_card(plugin):
    html = _single_widget_page(
        plugin,
        {
            "id": "t",
            "slug": "report",
            "widget_type": "vue-component",
            "content_json": {"component": "TukTukIntakeWidget"},
        },
    )

    assert (
        '<div class="cms-widget cms-widget--vue cms-widget--report cms-widget--spa-link">'
        in html
    )
    assert '<a class="cms-spa-link-widget" href="/tuktuk/chat"' in html


def test_registered_component_renders_inside_the_vue_wrapper_with_its_css(plugin):
    registry = ComponentTemplateRegistry()
    registry.register(
        ComponentTemplate(
            name="Greeting",
            template="cms/components/test_greeting.html.j2",
            build_context=lambda config, page, route_params, request: {
                "who": config["widget_slug"]
            },
        )
    )

    html = _single_widget_page(
        plugin,
        {
            "id": "g",
            "slug": "greet",
            "widget_type": "vue-component",
            "source_css": ".g{}",
            "content_json": {"component": "Greeting"},
        },
        component_registry=registry,
    )

    assert (
        '<div class="cms-widget cms-widget--vue cms-widget--greet"><style>.g{}</style>'
        '<p class="test-greeting">Hello greet</p>' in html
    )


def test_unknown_widget_type_renders_nothing(plugin):
    html = _single_widget_page(
        plugin, {"id": "x", "slug": "x", "widget_type": "carousel3d"}
    )

    assert (
        '<div class="cms-area cms-area--header"><div class="container"></div></div>'
        in html
    )


def test_head_seo_tags_style_cascade_and_head_snippets(plugin):
    page = _laid_out_page(
        meta_title="SEO title",
        meta_description="Desc",
        robots="index,follow",
        og_image_url="/og.png",
        schema_json={"@type": "WebPage"},
        source_css=".post{}",
    )
    html = render(plugin, page_context(page, layout=LAYOUT, style_css=".style{}"))
    head = html.partition("</head>")[0]

    assert "<title>SEO title</title>" in head
    assert '<meta name="description" content="Desc" data-seo="ssr">' in head
    assert '<meta name="robots" content="index,follow" data-seo="ssr">' in head
    assert (
        '<link rel="canonical" href="https://site.example/about" data-seo="ssr">'
        in head
    )
    assert '<meta property="og:title" content="SEO title" data-seo="ssr">' in head
    assert '<meta property="og:image" content="/og.png" data-seo="ssr">' in head
    assert "og:description" not in head
    assert (
        '<script type="application/ld+json" data-seo="ssr">{"@type": "WebPage"}</script>'
        in head
    )
    assert "<style data-cms-page-style>.style{}\n.post{}</style>" in head
    stylesheet = head.index('rel="stylesheet"')
    page_style = head.index("data-cms-page-style")
    layout_head = head.index("window.layoutHead=1")
    global_head = head.index('name="site-verification"')
    assert stylesheet < page_style < layout_head < global_head


def test_hreflang_and_switcher_from_the_translations(plugin):
    page = _post(
        language="en",
        translations=[
            {
                "language": "de",
                "slug": "de/hallo",
                "url": "https://site.example/de/hallo",
            }
        ],
    )

    html = render(plugin, page_context(page))

    assert '<html lang="en">' in html
    assert re.findall(
        r'<link rel="alternate" hreflang="([^"]+)" href="([^"]+)">', html
    ) == [
        ("en", "https://site.example/news/hello"),
        ("de", "https://site.example/de/hallo"),
        ("x-default", "https://site.example/news/hello"),
    ]
    assert 'data-testid="language-switch-de"' in html


def test_core_tags_and_custom_fields_block(plugin):
    html = render(
        plugin,
        page_context(_laid_out_page(tags=["alpha"], custom_fields={"size": "L"})),
    )

    assert (
        '<div class="cms-page__tags-custom-fields" data-testid="page-tags-custom-fields">'
        in html
    )
    assert '<span class="vbwd-tag-chip" data-testid="tag-chip">alpha</span>' in html
    assert (
        '<dt class="vbwd-custom-field-label">size</dt><dd class="vbwd-custom-field-value">L</dd>'
        in html
    )


def _access_denied_context():
    return {
        "page_type_template": "cms/access_denied.html.j2",
        "page_title": "",
        "language": "en",
        "default_language": "en",
    }


def test_access_denied_anonymously_offers_a_login_link(plugin):
    html = render(plugin, _access_denied_context())

    assert '<div class="cms-page__access-denied">' in html
    # The SPA's fe-user catalog wins over CmsPage.vue's 'Log In' fallback.
    assert '<a href="/login" class="cms-page__login-link">Log in</a>' in html
    assert "Login required" in html


def test_access_denied_for_a_signed_in_viewer_asks_to_upgrade(plugin):
    viewer = Viewer(user_id="u1", access_level_slugs=frozenset(), permissions=())

    html = render(plugin, _access_denied_context(), viewer=viewer)

    assert "Access denied" in html and "cms-page__login-link" not in html


def test_the_page_works_without_javascript(plugin):
    html = render(plugin, page_context(_laid_out_page(), layout=LAYOUT))

    body_before_scripts = _body(html).partition("<script")[0]
    assert "<p>About us</p>" in body_before_scripts
    assert "<b>1</b>" in body_before_scripts
