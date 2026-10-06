"""theme_cms refuses to enable without cms, through the real plugin manager.

Uses the production ``PluginManager`` + ``DependencyResolver`` (no fakes): the
declared ``dependencies`` are the only thing standing between an adapter and a
missing domain plugin, so the contract is exercised end to end.
"""
import pytest

from plugins.theme import ThemePlugin
from plugins.theme_cms import ThemeCmsPlugin
from vbwd.plugins.base import PluginStatus
from vbwd.plugins.errors import PluginDependencyError
from vbwd.plugins.manager import PluginManager


def _manager_with_theme_enabled_and_no_cms() -> PluginManager:
    manager = PluginManager()
    manager.register_plugin(ThemePlugin())
    manager.register_plugin(ThemeCmsPlugin())
    manager.initialize_plugin("theme")
    manager.initialize_plugin("theme_cms")
    manager.enable_plugin("theme")
    return manager


def test_enabling_theme_cms_without_cms_raises_dependency_error():
    manager = _manager_with_theme_enabled_and_no_cms()

    with pytest.raises(PluginDependencyError, match="'cms' is not enabled"):
        manager.enable_plugin("theme_cms")

    assert manager.get_plugin("theme_cms").status == PluginStatus.INITIALIZED
