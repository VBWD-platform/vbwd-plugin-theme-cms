"""S152-06a / D13 — ``CmsLanguagePolicy``: the languages a themed page may use come from cms config.

cms stores ``enabled_languages`` as a comma string (legacy) or a list (the
dual-list admin field) and ``default_language`` as a code. The policy reads the
SAVED cms config through ``current_app.config_store`` (read-only, D3) on every
call, so an admin's change applies without a restart.
"""
from types import SimpleNamespace

import pytest
from flask import Flask

from plugins.theme_cms.theme_cms.language_policy import CmsLanguagePolicy


class _ConfigStore:
    def __init__(self, configs):
        self.configs = configs
        self.requested_names = []

    def get_config(self, plugin_name):
        self.requested_names.append(plugin_name)
        return self.configs.get(plugin_name, {})


@pytest.fixture
def app():
    return Flask(__name__)


def _policy_answers(app, cms_config):
    app.config_store = _ConfigStore({"cms": cms_config})
    policy = CmsLanguagePolicy()
    theme_request = SimpleNamespace()
    with app.app_context():
        return (
            policy.enabled_languages(theme_request),
            policy.default_language(theme_request),
        )


def test_comma_string_is_split_trimmed_and_ordered(app):
    enabled, default = _policy_answers(
        app, {"enabled_languages": " en, de ,ru,", "default_language": "de"}
    )

    assert enabled == ("en", "de", "ru")
    assert default == "de"


def test_list_value_is_accepted(app):
    enabled, _default = _policy_answers(
        app, {"enabled_languages": ["en", "th"], "default_language": "en"}
    )

    assert enabled == ("en", "th")


def test_default_language_is_always_enabled(app):
    enabled, default = _policy_answers(
        app, {"enabled_languages": "de,ru", "default_language": "en"}
    )

    assert default == "en"
    assert enabled == ("de", "ru", "en")


class _SchemaReader:
    def __init__(self, schemas):
        self.schemas = schemas

    def get_config_schema(self, plugin_name):
        return self.schemas.get(plugin_name, {})


CMS_DESCRIPTOR = {"enabled_languages": {"type": "string", "default": "en,de,ru"}}


def test_missing_config_falls_back_to_the_cms_descriptor_default(app):
    # cms offers its descriptor default (en,de,ru) when nothing is saved; a
    # themed page must accept the same languages (S152-11c, D13).
    app.schema_reader = _SchemaReader({"cms": CMS_DESCRIPTOR})

    enabled, default = _policy_answers(app, {})

    assert enabled == ("en", "de", "ru")
    assert default == "en"


def test_an_empty_saved_value_falls_back_to_the_cms_descriptor_default(app):
    app.schema_reader = _SchemaReader({"cms": CMS_DESCRIPTOR})

    enabled, _default = _policy_answers(app, {"enabled_languages": []})

    assert enabled == ("en", "de", "ru")


def test_a_saved_value_wins_over_the_descriptor_default(app):
    app.schema_reader = _SchemaReader({"cms": CMS_DESCRIPTOR})

    enabled, _default = _policy_answers(app, {"enabled_languages": "en,th"})

    assert enabled == ("en", "th")


def test_without_a_schema_reader_only_the_default_language_is_enabled(app):
    enabled, default = _policy_answers(app, {})

    assert enabled == ("en",)
    assert default == "en"


def test_reads_the_cms_config_on_every_call(app):
    app.config_store = _ConfigStore({"cms": {"default_language": "en"}})
    policy = CmsLanguagePolicy()
    with app.app_context():
        policy.default_language(SimpleNamespace())
        app.config_store.configs["cms"] = {"default_language": "de"}

        assert policy.default_language(SimpleNamespace()) == "de"
    assert set(app.config_store.requested_names) == {"cms"}
