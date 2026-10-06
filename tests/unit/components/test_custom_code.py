"""S152-06b — CustomCode (CustomCodeWidget.vue + utils/customCode.ts).

The admin-pasted ``config.code`` is the cms widget trust model's one raw output:
like ``buildCustomCodeScripts`` only its ``<script>`` elements are kept (inline
body or ``src`` + every attribute), any other markup is dropped; in server HTML
the scripts simply run. Wrapper: ``div.cms-custom-code[data-testid=cms-custom-code]``.
"""
import pytest

from plugins.theme_cms.tests.unit.components.fakes import FakeThemeRequest
from plugins.theme_cms.tests.unit.dom_contract import canonical
from plugins.theme_cms.tests.unit.template_harness import render_component, theme_plugin
from plugins.theme_cms.theme_cms.components.custom_code import (
    build_custom_code_context,
    custom_code_scripts,
)

TEMPLATE = "cms/components/custom_code.html.j2"
GTAG = (
    '<!-- Google tag -->\n<script async src="https://www.googletagmanager.com/gtag/js?id=G-1&amp;x=y"></script>\n'
    "<script>\n  window.dataLayer = window.dataLayer || [];\n  if (a < b && c > d) {}\n</script>"
    "<p>visible markup is dropped</p>"
)


@pytest.fixture(autouse=True)
def isolated_var_directory(tmp_path, monkeypatch):
    monkeypatch.setenv("VBWD_VAR_DIR", str(tmp_path / "var"))


def test_only_the_script_elements_are_kept_with_their_attributes_and_raw_bodies():
    assert custom_code_scripts(GTAG) == (
        '<script async src="https://www.googletagmanager.com/gtag/js?id=G-1&amp;x=y"></script>'
        "<script>\n  window.dataLayer = window.dataLayer || [];\n  if (a < b && c > d) {}\n</script>"
    )


def test_an_external_script_never_keeps_an_inline_body():
    assert custom_code_scripts('<script src="/a.js">alert(1)</script>') == (
        '<script src="/a.js"></script>'
    )


def test_attribute_values_are_re_escaped_so_they_cannot_break_out():
    assert custom_code_scripts("<script data-x='\"><b>'></script>") == (
        '<script data-x="&#34;&gt;&lt;b&gt;"></script>'
    )


@pytest.mark.parametrize("code", [None, "", "   ", "<p>no script</p>"])
def test_no_code_or_no_script_renders_the_empty_wrapper(code):
    context = build_custom_code_context({"code": code}, {}, {}, FakeThemeRequest())

    html = render_component(theme_plugin(), TEMPLATE, context)

    assert canonical(html) == canonical(
        '<div class="cms-custom-code" data-testid="cms-custom-code"></div>'
    )


def test_the_scripts_are_emitted_raw_inside_the_wrapper():
    context = build_custom_code_context({"code": GTAG}, {}, {}, FakeThemeRequest())

    html = render_component(theme_plugin(), TEMPLATE, context)

    assert html.startswith(
        '<div class="cms-custom-code" data-testid="cms-custom-code"><script async'
    )
    assert "if (a < b && c > d) {}" in html
    assert "visible markup" not in html
