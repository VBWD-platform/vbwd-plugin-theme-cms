"""A test-only adapter registering ``/shop`` (higher priority) to prove the cms
catch-all ``/<path:slug>`` never shadows a more specific themed page."""
from pathlib import Path

from vbwd.plugins.base import BasePlugin, PluginMetadata

from plugins.theme.theme.page_registry import ThemePage, resolve_theme_page_registry
from plugins.theme.theme.theme_registry import resolve_theme_registry

FAKE_SHOP_ADAPTER_NAME = "fake_shop_adapter"
FAKE_SHOP_TEMPLATES = Path(__file__).parent / "fake_shop_templates"


class FakeShopAdapterPlugin(BasePlugin):
    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name=FAKE_SHOP_ADAPTER_NAME,
            version="1.0.0",
            author="Test",
            description="Test-only /shop theme page",
            dependencies=["theme"],
        )

    def on_enable(self) -> None:
        resolve_theme_registry().add_contributed_template_path(FAKE_SHOP_TEMPLATES)
        resolve_theme_page_registry().register(
            ThemePage(
                rule="/shop",
                endpoint="fake_shop",
                owner_fe_user_plugin="cms",
                priority=10,
                auth="public",
                template="fake_shop/shop.html.j2",
                build_context=lambda theme_request: {},
            )
        )
