"""S152-06c — the SPA's component CSS is ported to theme_cms's contributed stylesheets.

* Coverage: every class a theme_cms template (or runtime script) uses that has a
  rule in the Vue component it mirrors has a rule in the ported CSS. Skips when
  the fe-user / fe-core checkouts are not next to vbwd-backend (plugin CI), like
  the drift tests.
* Colour tokens (S152-06d): a literal colour appears ONLY as the fallback of a
  ``var(--vbwd-…, <literal>)`` token (or of the SPA's own ``--color-*`` chain,
  kept verbatim); every SPA colour of a used rule is ported with its exact
  literal; every ``--vbwd-cms-*`` token is documented in the theme guide.
* The stylesheets are contributed to the theme on enable, so the served
  ``theme.css`` carries them after basic's CSS and before the token block.
"""
from pathlib import Path

import pytest

from plugins.theme import ThemePlugin
from plugins.theme_cms import ThemeCmsPlugin
from plugins.theme.theme.theme_registry import TOKEN_NAME_PATTERN
from plugins.theme.tests.colour_tokens import (
    adapter_token_fallbacks,
    documented_colour_tokens,
    token_fallback_mismatches,
    unported_spa_colours,
)
from plugins.theme.tests.css_inventory import (
    hard_coded_colours,
    is_used,
    resolve_fallbacks,
    rule_classes,
    script_classes,
    template_class_usage,
    text_outside_token_fallbacks,
    vue_style_text,
)
from plugins.theme_cms.theme_cms.plugin_paths import (
    STYLESHEETS_DIRECTORY,
    TEMPLATES_DIRECTORY,
)

BACKEND_ROOT = Path(__file__).resolve().parents[4]
FE_USER_ROOT = BACKEND_ROOT.parent / "vbwd-fe-user"
FE_CORE_ROOT = BACKEND_ROOT.parent / "vbwd-fe-core"
CMS_SOURCE = FE_USER_ROOT / "plugins" / "cms" / "src"
# Every Vue component / stylesheet whose DOM the theme_cms templates mirror.
SOURCE_STYLE_FILES = (
    CMS_SOURCE / "components" / "CmsLayoutRenderer.vue",
    CMS_SOURCE / "components" / "CmsWidgetRenderer.vue",
    CMS_SOURCE / "views" / "CmsPage.vue",
    CMS_SOURCE / "views" / "CmsPageTypeBase.vue",
    CMS_SOURCE / "views" / "CmsPageIndex.vue",
    CMS_SOURCE / "views" / "CmsEmbedArchive.vue",
    CMS_SOURCE / "components" / "CmsImage.vue",
    CMS_SOURCE / "components" / "CustomCodeWidget.vue",
    CMS_SOURCE / "components" / "PostCard.vue",
    CMS_SOURCE / "components" / "PostList.vue",
    CMS_SOURCE / "components" / "PostArchiveWidget.vue",
    CMS_SOURCE / "components" / "TermArchiveWidget.vue",
    CMS_SOURCE / "components" / "TagArchive.vue",
    CMS_SOURCE / "components" / "PostTermListWidget.vue",
    CMS_SOURCE / "components" / "PostSearch.vue",
    CMS_SOURCE / "components" / "PostSearchResults.vue",
    CMS_SOURCE / "components" / "SuperHeader.vue",
    CMS_SOURCE / "components" / "ContactForm.vue",
    CMS_SOURCE / "components" / "CookieConsent.vue",
    CMS_SOURCE / "components" / "AddonCatalog.vue",
    CMS_SOURCE / "components" / "ImageLightbox.vue",
    CMS_SOURCE / "components" / "RichTextBlock.vue",
    FE_USER_ROOT / "plugins" / "landing1" / "Landing1View.vue",
    FE_USER_ROOT / "vue" / "src" / "assets" / "vbwd-ui.css",
    FE_CORE_ROOT / "src" / "components" / "breadcrumb" / "VbwdBreadcrumb.vue",
    FE_CORE_ROOT / "src" / "components" / "ui" / "TagChips.vue",
    FE_CORE_ROOT / "src" / "components" / "ui" / "CustomFieldsDisplay.vue",
    FE_CORE_ROOT / "src" / "components" / "catalogue" / "CatalogueFilterBar.vue",
)
ADAPTER = "cms"

needs_spa_checkouts = pytest.mark.skipif(
    not (CMS_SOURCE.is_dir() and FE_CORE_ROOT.is_dir()),
    reason="fe-user / fe-core checkouts are not next to vbwd-backend",
)


def _ported_css() -> str:
    return "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted(STYLESHEETS_DIRECTORY.rglob("*.css"))
    )


def _source_classes() -> set:
    classes: set = set()
    for source in SOURCE_STYLE_FILES:
        text = source.read_text(encoding="utf-8")
        classes |= rule_classes(
            vue_style_text(text) if source.suffix == ".vue" else text
        )
    return classes


def _used_styled_classes() -> set:
    static_classes, prefixes = template_class_usage(TEMPLATES_DIRECTORY.rglob("*.j2"))
    static_classes |= script_classes(TEMPLATES_DIRECTORY.rglob("*.js"))
    return {
        class_name
        for class_name in _source_classes()
        if is_used(class_name, static_classes, prefixes)
    }


def coverage_report() -> dict:
    used_styled = _used_styled_classes()
    ported = rule_classes(_ported_css())
    return {
        "used_styled": sorted(used_styled),
        "ported": sorted(used_styled & ported),
        "missing": sorted(used_styled - ported),
    }


@needs_spa_checkouts
def test_all_source_style_files_exist():
    assert [str(path) for path in SOURCE_STYLE_FILES if not path.is_file()] == []


@needs_spa_checkouts
def test_every_used_styled_class_has_a_ported_rule():
    assert coverage_report()["missing"] == []


@needs_spa_checkouts
def test_every_ported_class_is_used_and_styled_in_the_spa():
    """No dead or invented rules: the port mirrors the SPA, nothing more."""
    assert rule_classes(_ported_css()) - _used_styled_classes() == set()


@needs_spa_checkouts
def test_every_spa_colour_of_a_used_rule_is_ported_with_its_literal():
    """The default rendering is the SPA's: overlay dim, shadows, hero scrim, presets."""
    assert (
        unported_spa_colours(SOURCE_STYLE_FILES, _ported_css(), _used_styled_classes())
        == []
    )


@needs_spa_checkouts
def test_every_cms_token_fallback_is_the_spa_literal():
    assert token_fallback_mismatches(SOURCE_STYLE_FILES, _ported_css(), ADAPTER) == []


def test_every_cms_token_is_documented_with_its_default_and_vice_versa():
    used = {
        token: sorted(fallbacks)
        for token, fallbacks in adapter_token_fallbacks(_ported_css(), ADAPTER).items()
    }
    documented = {
        token: [default] for token, default in documented_colour_tokens(ADAPTER).items()
    }

    assert used and used == documented


def test_every_cms_token_is_a_tokens_json_name():
    tokens = adapter_token_fallbacks(_ported_css(), ADAPTER)

    assert [name for name in tokens if not TOKEN_NAME_PATTERN.match(name)] == []


def test_the_ported_css_ports_the_overlay_shadow_and_hero_scrim_tokens():
    tokens = adapter_token_fallbacks(_ported_css(), ADAPTER)

    assert tokens["--vbwd-cms-menu-overlay"] == {"rgba(0,0,0,0.4)"}
    assert tokens["--vbwd-cms-post-hero-scrim-start"] == {"rgba(0, 0, 0, 0.62)"}
    assert tokens["--vbwd-cms-landing1-dark-card-bg"] == {"#1f2937"}


def test_the_ported_css_has_rules_for_the_core_widgets():
    ported = rule_classes(_ported_css())

    for class_name in ("cms-burger", "cms-slideshow", "cms-post-hero", "post-card"):
        assert class_name in ported


def test_the_ported_css_carries_no_hard_coded_colour():
    assert hard_coded_colours(_ported_css()) == []


@pytest.mark.parametrize(
    "css_text",
    [
        ".a{color:#fff}",
        ".a{background:rgba(0,0,0,.4)}",
        ".a{border:1px solid red}",
        ".a{box-shadow:0 1px 2px hsl(0 0% 0%)}",
        ".a{--x:#123456}",
        "@media (max-width: 1px){.a{color:white}}",
        # a literal outside the token's fallback
        ".a{box-shadow:0 1px var(--vbwd-cms-a) rgba(0,0,0,.1)}",
        ".a{background:linear-gradient(var(--vbwd-cms-a, #000), #fff)}",
        # the fallback of a name that is no --vbwd-* token (nor an SPA --color-* chain)
        ".a{color:var(--l1-primary, #3b82f6)}",
        ".a{color:var(--brand, #fff)}",
        ".a{color:var(--l1-a, var(--l1-b, #fff))}",
    ],
)
def test_the_colour_check_catches_literals(css_text):
    assert hard_coded_colours(css_text) != []


@pytest.mark.parametrize(
    "css_text",
    [
        ".a{background:var(--vbwd-cms-menu-overlay, rgba(0, 0, 0, 0.5))}",
        ".a{box-shadow:0 8px 24px var(--vbwd-cms-dropdown-shadow, rgba(0,0,0,.12))}",
        ".a{background:linear-gradient(to top, var(--vbwd-cms-a, #000) 0%, "
        "var(--vbwd-cms-b, rgba(0,0,0,.1)) 100%)}",
        ".a{--l1-primary:var(--vbwd-cms-landing1-dark-primary, #3b82f6)}",
        ".a{background:var(--vbwd-surface, var(--color-surface, #fff))}",
        ".a{background:var(--l1-a, var(--vbwd-cms-b, #fff))}",
        # the SPA's own --color-* chains are kept verbatim
        ".a{color:var(--color-text, #0f172a)}",
        ".a{background:transparent;color:currentColor;border:none}",
        ".a{color:var(--l1-primary)}",
        ".a:hover{opacity:.75}",
    ],
)
def test_the_colour_check_allows_token_fallbacks_and_keywords(css_text):
    assert hard_coded_colours(css_text) == []


def test_text_outside_token_fallbacks_keeps_only_unguarded_text():
    assert text_outside_token_fallbacks(
        "1px solid var(--vbwd-a, var(--b, #fff)) x"
    ).split() == ["1px", "solid", "x"]
    assert "#fff" in text_outside_token_fallbacks("var(--brand, #fff)")


def test_resolve_fallbacks_renders_the_default_value():
    assert (
        resolve_fallbacks("0 4px var(--vbwd-a, var(--b, rgba(0, 0, 0, 0.1))) x")
        == "0 4px rgba(0, 0, 0, 0.1) x"
    )


def test_on_enable_contributes_the_stylesheets_to_the_theme(monkeypatch):
    theme_plugin = ThemePlugin()
    theme_plugin.on_enable()
    monkeypatch.setattr("plugins.theme_cms.resolve_theme_plugin", lambda: theme_plugin)

    ThemeCmsPlugin().on_enable()

    registry = theme_plugin.theme_registry
    assert STYLESHEETS_DIRECTORY in registry.contributed_stylesheet_paths()
    css_text = theme_plugin.renderer.static_assets.stylesheet("basic").css_text
    assert (
        css_text.index('[data-auth="pending"]')
        < css_text.index(".cms-burger")
        < css_text.index(":root")
    )
