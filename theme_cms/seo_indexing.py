"""The one reading of a domain payload's ``seo_indexable`` flag (S154 D7).

Each domain plugin (cms, shop, booking) puts the fe-admin "indexable" switch of
a content type on its public detail payload as ``seo_indexable``. A switched-off
type keeps its links crawlable but stays out of the index: ``noindex,follow``.
An absent flag (an older backend) reads as indexable, today's behaviour.
"""
from typing import Any, Mapping

SEO_INDEXABLE_FIELD = "seo_indexable"
INDEXABLE_ROBOTS = "index,follow"
SWITCHED_OFF_ROBOTS = "noindex,follow"


def is_seo_indexable(payload: Mapping[str, Any]) -> bool:
    """False only when the payload says its type is switched off."""
    return payload.get(SEO_INDEXABLE_FIELD) is not False


def indexable_switch_robots(payload: Mapping[str, Any]) -> str:
    """The robots of an adapter route that owns its head (product, resource …)."""
    return INDEXABLE_ROBOTS if is_seo_indexable(payload) else SWITCHED_OFF_ROBOTS
