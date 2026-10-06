"""S152-06a §3–5, §8, D13 — the template context of one resolved CMS page.

* body = ``content_html`` else the TipTap render of ``content_json``;
* page type template from the registry (unknown → page);
* layout areas in ``layout.areas`` order: content areas carry their
  ``content_blocks[name].content_html`` (else the main body), widget areas their
  W1 widget views;
* one page style = resolved style CSS + post ``source_css`` (``\\n``-joined, empties
  dropped); ``content_blocks[*].source_css`` is never applied;
* SEO head fields (``injectSeoMeta``): title = meta_title || name || title,
  og:title falls back to the title; canonical follows the cms rule (stored
  override, else ``public_base_url`` + ``/<slug>``, ``/`` for the home slug);
* ``language_alternates`` = the W3 ``translations``; ``page_language`` = post language;
* the post hero: on unless ``type_data.show_featured_hero`` is false, tag terms
  only, image URL stripped of CSS-breakout characters.
"""
import base64

from plugins.theme_cms.theme_cms.page_context import (
    CmsPageContextBuilder,
    CmsSiteSettings,
    derive_canonical_url,
)
from plugins.theme_cms.theme_cms.page_resolver import ResolvedCmsPage
from plugins.theme_cms.theme_cms.registries import (
    ComponentTemplateRegistry,
    default_page_type_registry,
)

SITE = CmsSiteSettings(
    public_base_url="https://site.example/",
    home_slug="index",
    global_head_html='<meta name="v" content="1">',
)


def _build(page, layout=None, style_css=None, site=SITE):
    builder = CmsPageContextBuilder(
        default_page_type_registry(),
        ComponentTemplateRegistry(),
        site,
        route_params={"slug": page.get("slug")},
        theme_request=None,
    )
    return builder.build(ResolvedCmsPage(page, layout, style_css))


def _page(**fields):
    return {
        "id": "p",
        "slug": "about",
        "type": "page",
        "title": "About",
        "language": "de",
        **fields,
    }


def test_body_prefers_content_html_then_tiptap():
    with_html = _build(_page(content_html="<p>raw</p>", content_json={"type": "doc"}))
    with_json = _build(
        _page(
            content_html="",
            content_json={"type": "doc", "content": [{"type": "paragraph"}]},
        )
    )

    assert with_html["cms_body_html"] == "<p>raw</p>"
    assert with_json["cms_body_html"] == "<p>&nbsp;</p>"


def test_page_type_template_and_unknown_type_fallback():
    assert (
        _build(_page(type="post"))["page_type_template"]
        == "cms/page_types/post.html.j2"
    )
    assert (
        _build(_page(type="video"))["page_type_template"]
        == "cms/page_types/page.html.j2"
    )


def test_layout_areas_keep_order_with_content_blocks_and_widgets():
    widget = {
        "id": "w",
        "slug": "hello",
        "widget_type": "html",
        "content_json": {"content": base64.b64encode(b"<b>hi</b>").decode()},
    }
    layout = {
        "slug": "two-col",
        "head_html": "<script>h()</script>",
        "areas": [
            {"name": "header", "type": "header"},
            {"name": "main", "type": "content"},
            {"name": "aside", "type": "content"},
            {"name": "footer", "type": "footer"},
        ],
        "assignments": [{"area_name": "header", "sort_order": 0, "widget": widget}],
    }
    page = _page(
        content_html="<p>main</p>",
        content_blocks={
            "aside": {"content_html": "<p>aside</p>", "source_css": ".never{}"}
        },
    )

    context = _build(page, layout)

    areas = context["cms_layout"]["areas"]
    assert [(area["name"], area["type"], area["is_content"]) for area in areas] == [
        ("header", "header", False),
        ("main", "content", True),
        ("aside", "content", True),
        ("footer", "footer", False),
    ]
    assert areas[0]["widgets"][0]["html"] == "<b>hi</b>"
    assert areas[1]["block_html"] is None
    assert areas[2]["block_html"] == "<p>aside</p>"
    assert areas[3]["widgets"] == []
    assert context["cms_layout"]["slug"] == "two-col"
    assert context["cms_layout_head_html"] == "<script>h()</script>"
    assert ".never" not in context["cms_page_style_css"]


def test_no_layout_means_no_layout_context():
    context = _build(_page())

    assert context["cms_layout"] is None
    assert context["cms_layout_head_html"] == ""


def test_page_style_is_style_css_then_source_css():
    assert _build(_page(source_css=".post{}"), style_css=".style{}")[
        "cms_page_style_css"
    ] == (".style{}\n.post{}")
    assert (
        _build(_page(source_css=None), style_css=".style{}")["cms_page_style_css"]
        == ".style{}"
    )
    assert _build(_page(source_css=""))["cms_page_style_css"] == ""


def test_seo_fields_mirror_inject_seo_meta():
    page = _page(
        meta_title="SEO title",
        meta_description="desc",
        robots="noindex",
        og_title=None,
        og_description="og d",
        og_image_url="/og.png",
        schema_json={"@type": "WebPage", "name": "</script>"},
    )

    context = _build(page)

    assert context["page_title"] == "SEO title"
    seo = context["cms_seo"]
    assert seo["description"] == "desc" and seo["robots"] == "noindex"
    assert seo["og_title"] == "SEO title" and seo["og_description"] == "og d"
    assert seo["og_image"] == "/og.png"
    assert (
        "</script>" not in seo["schema_json"]
        and "\\u003c/script>" in seo["schema_json"]
    )
    assert context["cms_global_head_html"] == SITE.global_head_html


def test_title_falls_back_to_name_then_title():
    assert (
        _build(_page(meta_title=None, name="Legacy name"))["page_title"]
        == "Legacy name"
    )
    assert _build(_page(meta_title=None))["page_title"] == "About"
    assert _build(_page(meta_title=None))["cms_seo"]["schema_json"] is None


def test_canonical_rule_matches_the_cms_one():
    assert (
        derive_canonical_url("https://x/override", "a", "https://site/", "index")
        == "https://x/override"
    )
    assert (
        derive_canonical_url(None, "docs/intro", "https://site/", "index")
        == "https://site/docs/intro"
    )
    assert (
        derive_canonical_url(None, "index", "https://site", "index") == "https://site/"
    )
    assert derive_canonical_url(None, "", "", "index") == "/"
    assert derive_canonical_url(None, "about", "", None) == "/about"


def test_language_alternates_current_url_and_page_language():
    translations = [
        {"language": "en", "slug": "about-en", "url": "https://site.example/about-en"}
    ]

    context = _build(_page(translations=translations))

    assert context["language_alternates"] == translations
    assert context["current_url"] == "https://site.example/about"
    assert context["page_language"] == "de"


def test_synthetic_pages_set_no_page_language():
    context = _build(
        {
            "id": "term-archive:tag:x",
            "slug": "tag/x",
            "type": "page",
            "title": "X",
            "term_archive": {"term_type": "tag", "slug": "x", "name": "X"},
        }
    )

    assert "page_language" not in context
    assert context["page_type_template"] == "cms/page_types/term_archive.html.j2"


def test_post_hero_defaults_on_with_tag_terms_only_and_safe_image_url():
    page = _page(
        type="post",
        excerpt="Short",
        featured_image_url='/u/a"b(c).jpg',
        terms=[
            {"term_type": "tag", "slug": "vue js", "name": "Vue"},
            {"term_type": "category", "slug": "news", "name": "News"},
        ],
    )

    hero = _build(page)["cms_post_hero"]

    assert hero == {
        "enabled": True,
        "title": "About",
        "excerpt": "Short",
        "image_url": "/u/abc.jpg",
        "tags": [{"name": "Vue", "href": "/tag/vue%20js"}],
    }


def test_post_hero_is_off_only_when_explicitly_disabled():
    assert (
        _build(_page(type_data={"show_featured_hero": False}))["cms_post_hero"][
            "enabled"
        ]
        is False
    )
    assert _build(_page(type_data={}))["cms_post_hero"]["enabled"] is True


def test_core_tags_and_custom_fields_rows():
    page = _page(
        tags=["alpha", {"slug": "b", "name": "Beta"}],
        custom_fields={"size": "L", "ok": True, "empty": ""},
        custom_field_defs=[
            {"key": "ok", "label": "OK?", "type": "bool", "sort_order": 2},
            {"key": "size", "label": "Size", "type": "text", "sort_order": 1},
            {"key": "absent", "label": "Absent", "type": "text"},
        ],
    )

    block = _build(page)["cms_tags_custom_fields"]

    assert block["tags"] == ["alpha", "Beta"]
    assert block["custom_fields"] == [
        {"label": "Size", "display": "L"},
        {"label": "OK?", "display": "Yes"},
    ]
    assert _build(_page())["cms_tags_custom_fields"] is None
