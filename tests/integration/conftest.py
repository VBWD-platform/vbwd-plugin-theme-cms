"""Integration fixtures: a real ``create_app`` in theme mode with cms + theme + theme_cms.

* Boot is narrowed to exactly cms, theme, theme_cms and a test-only adapter
  (``fake_shop_adapter.py``, a higher-priority ``/shop`` page): the stand-in for
  ``load_persisted_state`` validates + enables them in dependency order, the
  same calls the core makes.
* The fe-user manifest (``VBWD_FE_USER_PLUGINS_JSON``) enables fe-user "cms".
* Data lives in the shared ``*_test`` database; each test runs in a rolled-back
  transaction (core ``rollback_isolation``) — the rollback is the cleanup. The
  inner C2 calls run in their own app context but on the same bound connection,
  so they see the test's writes.
* cms content is seeded through the cms admin HTTP API (``cms_seed.py``):
  theme adapters may not import ``plugins.cms`` — not even in tests (the S152
  D3 oracle walks every theme_* file).
* cms config keys a test needs are overlaid on the real config store
  (read-through, never written to disk).
"""
import json
import os

import pytest

from vbwd.plugins.manager import PluginManager

from plugins.theme_cms.tests.integration.fake_shop_adapter import (
    FAKE_SHOP_ADAPTER_NAME,
    FakeShopAdapterPlugin,
)

BOOT_ORDER = ("cms", "theme", "theme_cms", FAKE_SHOP_ADAPTER_NAME)
CMS_TEST_CONFIG = {
    "enabled_languages": "en,de",
    "default_language": "en",
    "home_slug": "index",
    "public_base_url": "https://site.example",
    "global_head_html": '<meta name="site-verification" content="theme-cms-test">',
    "seo_prerender_enabled": True,
    "prerender_service_url": "",
}


def _test_database_url() -> str:
    base = os.getenv("DATABASE_URL", "postgresql://vbwd:vbwd@postgres:5432/vbwd")
    prefix, _, database_name = base.rpartition("/")
    return f"{prefix}/{database_name.split('?')[0]}_test"


def _enable_only_the_cms_theme_stack(plugin_manager: PluginManager) -> None:
    """Stands in for ``load_persisted_state``: enable cms, theme, theme_cms, the fake adapter."""
    plugin_manager.register_plugin(FakeShopAdapterPlugin())
    plugin_manager.initialize_plugin(FAKE_SHOP_ADAPTER_NAME)
    for plugin_name in BOOT_ORDER:
        plugin = plugin_manager.get_plugin(plugin_name)
        plugin.validate_environment()
        plugin.enable()


class OverlayConfigStore:
    """Reads through to the real store with per-plugin overrides on top."""

    def __init__(self, real_store, overrides):
        self._real_store = real_store
        self.overrides = overrides

    def get_config(self, plugin_name):
        return {
            **(self._real_store.get_config(plugin_name) or {}),
            **self.overrides.get(plugin_name, {}),
        }

    def __getattr__(self, name):
        return getattr(self._real_store, name)


@pytest.fixture(scope="module")
def var_directory(tmp_path_factory):
    return tmp_path_factory.mktemp("theme-cms-var")


@pytest.fixture(scope="module")
def app(var_directory):
    from vbwd.app import create_app
    from vbwd.extensions import db
    from vbwd.testing.integration_db import ensure_schema_and_baseline

    manifest_path = var_directory / "fe-user-plugins.json"
    manifest_path.write_text(
        json.dumps({"plugins": {"cms": {"enabled": True}}}), encoding="utf-8"
    )
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(
            PluginManager, "load_persisted_state", _enable_only_the_cms_theme_stack
        )
        patch.setenv("VBWD_FRONTEND_MODE", "theme")
        patch.setenv("VBWD_VAR_DIR", str(var_directory))
        patch.setenv("VBWD_FE_USER_PLUGINS_JSON", str(manifest_path))
        application = create_app(
            {
                "TESTING": True,
                "SQLALCHEMY_DATABASE_URI": _test_database_url(),
                "SQLALCHEMY_TRACK_MODIFICATIONS": False,
                "RATELIMIT_ENABLED": False,
            }
        )
        application.config_store = OverlayConfigStore(
            application.config_store, {"cms": dict(CMS_TEST_CONFIG)}
        )
        with application.app_context():
            ensure_schema_and_baseline(db)
        yield application
        with application.app_context():
            db.engine.dispose()


@pytest.fixture
def db(app):
    """Each test in a rolled-back transaction, with the core test admin + user seeded inside it."""
    from vbwd.extensions import db as database
    from vbwd.testing.integration_db import rollback_isolation
    from vbwd.testing.test_data_seeder import TestDataSeeder

    with app.app_context():
        with rollback_isolation(database):
            previous_seed_flag = os.environ.get("TEST_DATA_SEED")
            os.environ["TEST_DATA_SEED"] = "true"
            try:
                TestDataSeeder(database.session).seed()
            finally:
                if previous_seed_flag is None:
                    os.environ.pop("TEST_DATA_SEED", None)
                else:
                    os.environ["TEST_DATA_SEED"] = previous_seed_flag
            yield database


@pytest.fixture
def client(app, db):
    return app.test_client()


@pytest.fixture
def cms(client):
    from plugins.theme_cms.tests.integration.cms_seed import CmsAdminSeeder

    return CmsAdminSeeder(client)


@pytest.fixture
def cms_config(app):
    """The overlaid cms config; changes are undone after the test."""
    overrides = app.config_store.overrides["cms"]
    saved = dict(overrides)
    yield overrides
    overrides.clear()
    overrides.update(saved)
