"""The facet half of the catalogue list contract (S152-09), shared by the adapters.

Every catalogue view of the SPA (ProductCatalog.vue, BookingCatalogue.vue, …)
loads ``GET …/filters`` and then each facet's ``options_endpoint``, mapping the
answer's first array to ``{value, label}``; fe-core ``CatalogueFilterBar``
renders the result (its twin is ``cms/macros/catalogue_filter_bar.html.j2``).
A descriptor endpoint is absolute (``/api/v1/booking/tags``): the SPA strips
``/api/v1`` because its axios client prepends it, while ``call_api`` takes the
full path — so an absolute endpoint is used as is and a relative one gets the
prefix exactly once.
"""
from typing import Any, Dict, List, Mapping

from plugins.theme.theme.theme_api import ThemeApiError

API_PREFIX = "/api/v1"


def options_api_path(endpoint: str) -> str:
    """The full ``/api/v1/…`` path of a facet's ``options_endpoint``."""
    if endpoint.startswith(f"{API_PREFIX}/"):
        return endpoint
    return f"{API_PREFIX}/{endpoint.lstrip('/')}"


def map_options(response: Mapping[str, Any]) -> List[Dict[str, str]]:
    """``mapOptions``: the answer's first array as ``{value, label}``."""
    options = next(
        (value for value in response.values() if isinstance(value, list)), []
    )
    return [
        {
            "value": str(option.get("value") or option.get("slug") or ""),
            "label": str(
                option.get("label")
                or option.get("name")
                or option.get("value")
                or option.get("slug")
                or ""
            ),
        }
        for option in options
    ]


def load_facets(api: Any) -> List[Dict[str, Any]]:
    """``loadFacets``: each facet with its resolved ``options`` ([] when unreachable).

    ``api`` answers ``filters()`` and ``options(endpoint)`` (raising
    ``ThemeApiError`` on a refusal); a missing filters endpoint means no facets.
    """
    try:
        facets = api.filters().get("facets") or []
    except ThemeApiError:
        return []
    views = []
    for facet in facets:
        options: List[Dict[str, str]] = []
        if facet.get("options_endpoint"):
            try:
                options = map_options(api.options(facet["options_endpoint"]))
            except ThemeApiError:
                options = []
        views.append({**facet, "options": options})
    return views
