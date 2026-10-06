"""S152-06c — the served theme.css carries theme_cms's ported component CSS.

Order on a real app in theme mode: basic's CSS → theme_cms's contributed
stylesheets → (child themes) → the ``:root`` token block; a CMS page links its
own CMS style after the stylesheet, so CMS styles keep the final say.
"""
STYLESHEET_PATH = "/_render/_theme/public/theme.css"
RENDER = {"X-VBWD-Render": "1"}


def test_theme_css_serves_the_cms_component_rules_between_basic_and_tokens(client):
    response = client.get(STYLESHEET_PATH)

    css_text = response.get_data(as_text=True)
    assert response.status_code == 200
    basic_position = css_text.index('[data-auth="pending"] .vbwd-private-chrome')
    tokens_position = css_text.index(":root")
    for cms_rule in (".cms-post-hero {", ".cms-burger {", ".post-card {"):
        assert basic_position < css_text.index(cms_rule) < tokens_position


def test_a_cms_page_links_its_style_after_the_theme_stylesheet(client, cms):
    style = cms.style(".theme-cms-style-wins{display:block}")
    page = cms.post(content_html="<p>BODY</p>", style_id=style["id"])

    html = client.get(f"/{page['slug']}", headers=RENDER).get_data(as_text=True)

    assert html.index(STYLESHEET_PATH) < html.index(".theme-cms-style-wins")
