"""D13 — the CMS defines which languages a themed page may render in.

``CmsLanguagePolicy`` implements the theme's ``ThemeLanguagePolicy`` port from
the SAVED cms config (``current_app.config_store``, read-only, D3): cms keeps
``enabled_languages`` as a comma string (legacy) or a list (the admin dual-list
field) and ``default_language`` as one code. When nothing (or an empty list) is
saved, cms offers its descriptor default (``plugins/cms/config.json``), so the
policy falls back to that same default through core's ``schema_reader`` — never
by importing cms (D3). Read on every call, so an admin's change applies without
a restart. ``theme_cms`` registers it through ``ThemePlugin.set_language_policy``
from ``on_enable``.
"""
from typing import Any, Mapping, Tuple

from flask import current_app

CMS_PLUGIN_NAME = "cms"
ENABLED_LANGUAGES_KEY = "enabled_languages"
DEFAULT_LANGUAGE_KEY = "default_language"
FALLBACK_DEFAULT_LANGUAGE = "en"
LANGUAGE_SEPARATOR = ","


def read_cms_config() -> Mapping[str, Any]:
    """The saved cms config (empty when nothing is saved or no store exists)."""
    config_store = getattr(current_app, "config_store", None)
    if config_store is None:
        return {}
    return config_store.get_config(CMS_PLUGIN_NAME) or {}


def _cms_descriptor_default(key: str) -> Any:
    """The ``default`` of a cms descriptor field (``None`` without a schema reader)."""
    schema_reader = getattr(current_app, "schema_reader", None)
    if schema_reader is None:
        return None
    field = schema_reader.get_config_schema(CMS_PLUGIN_NAME).get(key) or {}
    return field.get("default")


def _language_codes(raw_value: Any) -> Tuple[str, ...]:
    """Trimmed, non-empty codes of a comma string or a list, in configured order."""
    if isinstance(raw_value, str):
        candidates = raw_value.split(LANGUAGE_SEPARATOR)
    elif isinstance(raw_value, list):
        candidates = raw_value
    else:
        candidates = []
    codes = (str(candidate).strip() for candidate in candidates)
    return tuple(dict.fromkeys(code for code in codes if code))


class CmsLanguagePolicy:
    """The cms ``enabled_languages`` (always including the default) and ``default_language``."""

    def enabled_languages(self, theme_request: Any) -> Tuple[str, ...]:
        cms_config = read_cms_config()
        default_language = self._default_language(cms_config)
        enabled_languages = _language_codes(
            cms_config.get(ENABLED_LANGUAGES_KEY)
        ) or _language_codes(_cms_descriptor_default(ENABLED_LANGUAGES_KEY))
        if default_language in enabled_languages:
            return enabled_languages
        return enabled_languages + (default_language,)

    def default_language(self, theme_request: Any) -> str:
        return self._default_language(read_cms_config())

    @staticmethod
    def _default_language(cms_config: Mapping[str, Any]) -> str:
        configured = str(cms_config.get(DEFAULT_LANGUAGE_KEY) or "").strip()
        return configured or FALLBACK_DEFAULT_LANGUAGE
