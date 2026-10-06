"""S152-09 — the facet half of the catalogue list contract, shared by the adapters.

ProductCatalog.vue and BookingCatalogue.vue both load ``GET …/filters`` and then
each facet's ``options_endpoint`` (the answer's first array as ``{value,
label}``), tolerating a missing endpoint. The descriptor endpoints are absolute
(``/api/v1/…``); the SPA strips the prefix for its axios client, ``call_api``
takes the full path — an absolute endpoint is kept, a relative one prefixed once.
"""
import pytest

from plugins.theme.theme.theme_api import ThemeApiError
from plugins.theme_cms.theme_cms.components.catalogue_filters import (
    load_facets,
    map_options,
    options_api_path,
)


@pytest.mark.parametrize(
    "endpoint", ["/api/v1/booking/tags", "/booking/tags", "booking/tags"]
)
def test_an_options_endpoint_resolves_to_one_api_path(endpoint):
    assert options_api_path(endpoint) == "/api/v1/booking/tags"


def test_options_are_the_first_array_as_value_and_label():
    response = {
        "meta": {"ignored": True},
        "tags": [
            {"slug": "quiet", "name": "Quiet"},
            {"value": "v", "label": "L"},
            {"value": "only-value"},
            {},
        ],
    }

    assert map_options(response) == [
        {"value": "quiet", "label": "Quiet"},
        {"value": "v", "label": "L"},
        {"value": "only-value", "label": "only-value"},
        {"value": "", "label": ""},
    ]
    assert map_options({"nothing": "here"}) == []


class _FacetApi:
    def __init__(self, filters, options):
        self._filters = filters
        self._options = options
        self.option_calls = []

    def filters(self):
        if isinstance(self._filters, Exception):
            raise self._filters
        return self._filters

    def options(self, endpoint):
        self.option_calls.append(endpoint)
        answer = self._options[endpoint]
        if isinstance(answer, Exception):
            raise answer
        return answer


def test_facets_carry_their_resolved_options():
    api = _FacetApi(
        {
            "facets": [
                {"key": "tags", "control": "chips", "options_endpoint": "/api/v1/t"},
                {"key": "availability", "control": "date-range"},
                {"key": "type", "control": "select", "options_endpoint": "/api/v1/s"},
            ]
        },
        {
            "/api/v1/t": {"tags": [{"slug": "a", "name": "A"}]},
            "/api/v1/s": ThemeApiError(500, "down"),
        },
    )

    facets = load_facets(api)

    assert [facet["key"] for facet in facets] == ["tags", "availability", "type"]
    assert facets[0]["options"] == [{"value": "a", "label": "A"}]
    assert facets[1]["options"] == [] and facets[2]["options"] == []
    assert api.option_calls == ["/api/v1/t", "/api/v1/s"]


def test_a_missing_filters_endpoint_means_no_facets():
    assert load_facets(_FacetApi(ThemeApiError(404, "x"), {})) == []
