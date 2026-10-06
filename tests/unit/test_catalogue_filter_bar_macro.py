"""S152-09 — the fe-core ``CatalogueFilterBar`` markup as one shared macro.

ProductGrid (theme_shop) and BookingCatalogue (theme_booking) render the same
fe-core component inside their own GET form; the macro is its one home. Every
control is a named form field, so the bar works without JavaScript: a select
or a date bound submits its value, a chip submits ``toggle_tag``.
"""
import re

import pytest

from plugins.theme_cms.tests.unit.template_harness import render, theme_plugin

MACRO_TEST_TEMPLATE = "cms/components/test_catalogue_filter_bar.html.j2"
FACETS = [
    {
        "key": "type",
        "label": "Type",
        "control": "select",
        "options": [
            {"value": "room", "label": "Room"},
            {"value": "desk", "label": "Desk"},
        ],
    },
    {
        "key": "tags",
        "label": "Tags",
        "control": "chips",
        "options": [
            {"value": "quiet", "label": "Quiet"},
            {"value": "sunny", "label": "Sunny"},
        ],
    },
    {
        "key": "availability",
        "label": "Availability",
        "control": "date-range",
        "options": [],
    },
]
FILTERS = {
    "type": "desk",
    "tags": ["sunny"],
    "availability_from": "2026-11-02",
    "availability_to": "",
}


@pytest.fixture(autouse=True)
def isolated_var_directory(tmp_path, monkeypatch):
    monkeypatch.setenv("VBWD_VAR_DIR", str(tmp_path / "var"))


def _render(facets=FACETS, filters=FILTERS, all_label="All"):
    return render(
        theme_plugin(),
        {
            "facets": facets,
            "filters": filters,
            "all_label": all_label,
            "language": "en",
            "default_language": "en",
        },
        template=MACRO_TEST_TEMPLATE,
    )


def test_the_bar_root_and_one_field_per_facet():
    html = _render()

    assert re.search(
        r'<div class="vbwd-catalogue-filter-bar" data-testid="catalogue-filter-bar">',
        html,
    )
    assert html.count('class="vbwd-filter-field') == 3
    assert '<div class="vbwd-filter-field vbwd-filter-field--chips">' in html
    assert re.search(r'<span class="vbwd-filter-label">\s*Type\s*</span>', html)


def test_a_select_lists_all_then_its_options_with_the_value_selected():
    html = _render(all_label="Alle")
    select = re.search(
        r'<select name="type" class="vbwd-filter-select" '
        r'data-testid="catalogue-facet-select-type">(.*?)</select>',
        html,
        re.S,
    ).group(1)

    assert re.findall(r"<option[^>]*>([^<]*)</option>", select) == [
        "Alle",
        "Room",
        "Desk",
    ]
    assert '<option value="desk" selected>' in select
    assert '<option value="room">' in select


def test_a_chip_submits_its_tag_toggle_and_marks_the_active_one():
    html = _render()

    assert '<div class="vbwd-chips" data-testid="catalogue-facet-chips-tags">' in html
    assert re.search(
        r'<button type="submit" name="toggle_tag" value="sunny" '
        r'class="vbwd-chip vbwd-chip--active" '
        r'data-testid="catalogue-facet-chip-tags-sunny">Sunny</button>',
        html,
    )
    assert (
        'class="vbwd-chip" data-testid="catalogue-facet-chip-tags-quiet">Quiet<' in html
    )


def test_a_date_range_is_two_named_date_bounds():
    html = _render()

    assert re.search(
        r'<div class="vbwd-daterange" role="group" '
        r'data-testid="catalogue-facet-daterange-availability">',
        html,
    )
    assert re.search(
        r'<input type="date" name="availability_from" class="vbwd-daterange-input" '
        r'aria-label="Availability from" '
        r'data-testid="catalogue-facet-daterange-availability-from" value="2026-11-02">',
        html,
    )
    assert re.search(
        r'<input type="date" name="availability_to" class="vbwd-daterange-input" '
        r'aria-label="Availability to" '
        r'data-testid="catalogue-facet-daterange-availability-to" value="">',
        html,
    )
    assert '<span class="vbwd-daterange-sep">–</span>' in html


def test_no_facets_renders_nothing():
    assert _render(facets=[]).strip() == ""
