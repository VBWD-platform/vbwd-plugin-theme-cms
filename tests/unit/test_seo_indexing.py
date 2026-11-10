"""S154 D7 — the one reading of a domain payload's ``seo_indexable`` flag.

Domain plugins (cms, shop, booking) put their per-type fe-admin switch on the
public detail payload as ``seo_indexable``; every theme adapter reads it here:
``False`` ⇒ ``noindex,follow``; ``True`` or absent (an older backend) ⇒
indexable ``index,follow``.
"""
import pytest

from plugins.theme_cms.theme_cms.seo_indexing import (
    INDEXABLE_ROBOTS,
    SWITCHED_OFF_ROBOTS,
    indexable_switch_robots,
    is_seo_indexable,
)


@pytest.mark.parametrize(
    "payload, expected",
    [({"seo_indexable": True}, True), ({}, True), ({"seo_indexable": False}, False)],
)
def test_is_seo_indexable(payload, expected):
    assert is_seo_indexable(payload) is expected


def test_switch_robots():
    assert indexable_switch_robots({"seo_indexable": True}) == INDEXABLE_ROBOTS
    assert indexable_switch_robots({}) == "index,follow"
    assert indexable_switch_robots({"seo_indexable": False}) == SWITCHED_OFF_ROBOTS
    assert SWITCHED_OFF_ROBOTS == "noindex,follow"
