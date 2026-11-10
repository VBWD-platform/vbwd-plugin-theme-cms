"""A test-only plugin owning public fe-user SPA routes under a configurable base.

Stands in for a domain plugin (S154 D9) without naming one: it declares its
prefixes through ``fe_user_route_prefixes()`` and imports no theme module.
"""
from typing import List

from vbwd.plugins.base import BasePlugin, PluginMetadata

FAKE_ROUTE_OWNER_NAME = "fake_route_owner"
FAKE_ROUTE_OWNER_BASE = "/my-catalogue"


class FakeRouteOwnerPlugin(BasePlugin):
    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name=FAKE_ROUTE_OWNER_NAME,
            version="1.0.0",
            author="Test",
            description="Test-only owner of SPA routes under a configurable base",
            dependencies=[],
        )

    def fe_user_route_prefixes(self) -> List[str]:
        return [FAKE_ROUTE_OWNER_BASE]
