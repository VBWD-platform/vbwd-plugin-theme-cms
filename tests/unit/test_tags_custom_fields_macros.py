"""S152-08 — fe-core ``TagChips`` / ``CustomFieldsDisplay`` markup as shared macros.

The CMS page block and the adapters' detail pages (shop ProductDetail, dataset
DatasetDetail) render the same two fe-core components; the macros are their one
home. A caller's class lands on the component root, as Vue merges a parent's
``class`` attribute onto it.
"""
import pytest

from plugins.theme_cms.tests.unit.template_harness import render, theme_plugin

MACRO_TEST_TEMPLATE = "cms/components/test_tags_custom_fields.html.j2"
ROWS = [{"label": "Size", "display": "L"}]


@pytest.fixture(autouse=True)
def isolated_var_directory(tmp_path, monkeypatch):
    monkeypatch.setenv("VBWD_VAR_DIR", str(tmp_path / "var"))


def _render(tags, rows, extra_class=""):
    return render(
        theme_plugin(),
        {
            "tags": tags,
            "rows": rows,
            "extra_class": extra_class,
            "language": "en",
            "default_language": "en",
        },
        template=MACRO_TEST_TEMPLATE,
    )


def test_the_macros_render_the_fe_core_markup_with_the_callers_class():
    html = _render(["alpha"], ROWS, "product-detail__tags")

    assert html == (
        '<div class="vbwd-tag-chips product-detail__tags" data-testid="tag-chips">'
        '<span class="vbwd-tag-chip" data-testid="tag-chip">alpha</span></div>'
        '<dl class="vbwd-custom-fields-display product-detail__tags" '
        'data-testid="custom-fields-display"><div class="vbwd-custom-field-row" '
        'data-testid="custom-field-row"><dt class="vbwd-custom-field-label">Size</dt>'
        '<dd class="vbwd-custom-field-value">L</dd></div></dl>'
    )


def test_without_a_class_the_root_keeps_only_the_component_class():
    html = _render(["alpha"], ROWS)

    assert '<div class="vbwd-tag-chips" data-testid="tag-chips">' in html
    assert '<dl class="vbwd-custom-fields-display" data-testid=' in html


def test_empty_inputs_render_nothing():
    assert _render([], []) == ""
