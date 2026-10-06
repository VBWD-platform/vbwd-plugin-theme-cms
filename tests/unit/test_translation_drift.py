"""S152-06b — the theme_cms English catalog never drifts from the SPA's copy.

* Every message a theme_cms template asks for (``_('…')``, plus the cookie
  categories it builds dynamically) is in ``translations/en.json``.
* Every catalog entry is the SPA's English for the same key — from fe-user
  ``plugins/cms/locales/en.json``, ``plugins/landing1/locales/en.json`` or the
  core ``vue/src/i18n/locales/en.json`` — with ``%(name)s`` ≡ ``{name}``. The
  fe-user half skips when the checkout is not next to vbwd-backend (plugin CI).
"""
import json
import re
from pathlib import Path

import pytest

from plugins.theme.tests.catalog_contract import translated_catalog_paths
from plugins.theme_cms.theme_cms.components.contact_form import (
    GENERIC_ERROR_MESSAGE_KEY,
    RATE_LIMITED_MESSAGE_KEY,
)
from plugins.theme_cms.theme_cms.components.cookie_consent import (
    NECESSARY_CATEGORY,
    OPTIONAL_CATEGORIES,
)
from plugins.theme_cms.theme_cms.plugin_paths import (
    TEMPLATES_DIRECTORY,
    TRANSLATIONS_DIRECTORY,
)

BACKEND_ROOT = Path(__file__).resolve().parents[4]
FE_USER_ROOT = BACKEND_ROOT.parent / "vbwd-fe-user"
FE_USER_CATALOGS = (
    FE_USER_ROOT / "plugins" / "cms" / "locales" / "en.json",
    FE_USER_ROOT / "plugins" / "landing1" / "locales" / "en.json",
    FE_USER_ROOT / "vue" / "src" / "i18n" / "locales" / "en.json",
)
# Theme-only copy with no SPA counterpart (the SPA mounts the component itself).
THEME_ONLY_KEYS = {"cms.spaLink.open"}
TRANSLATION_CALL = re.compile(r"""_\(\s*'([A-Za-z0-9_.]+)'\s*[,)]""")
THEME_PARAMETER = re.compile(r"%\((\w+)\)s")


def _theme_catalog():
    return json.loads((TRANSLATIONS_DIRECTORY / "en.json").read_text(encoding="utf-8"))


def _flatten(prefix, node):
    for key, value in node.items():
        if isinstance(value, dict):
            yield from _flatten(f"{prefix}{key}.", value)
        else:
            yield f"{prefix}{key}", value


def _template_keys():
    keys = set()
    for template in TEMPLATES_DIRECTORY.rglob("*.j2"):
        keys.update(TRANSLATION_CALL.findall(template.read_text(encoding="utf-8")))
    # Chosen in Python, rendered with ``_(form.global_error.key)``.
    keys.update({GENERIC_ERROR_MESSAGE_KEY, RATE_LIMITED_MESSAGE_KEY})
    for category in (NECESSARY_CATEGORY, *OPTIONAL_CATEGORIES):
        keys.update(
            {
                f"cms.cookieConsent.categories.{category}.name",
                f"cms.cookieConsent.categories.{category}.purpose",
            }
        )
    return keys


def test_every_message_a_template_uses_is_in_the_catalog():
    missing = sorted(_template_keys() - set(_theme_catalog()))

    assert missing == []


def test_the_catalog_has_no_message_no_template_uses():
    assert sorted(set(_theme_catalog()) - _template_keys()) == []


def test_every_catalog_entry_is_the_spa_english_for_the_same_key():
    if not all(catalog.is_file() for catalog in FE_USER_CATALOGS):
        pytest.skip("fe-user checkout not mounted next to vbwd-backend")
    spa_messages = {}
    for catalog in reversed(FE_USER_CATALOGS):
        spa_messages.update(
            _flatten("", json.loads(catalog.read_text(encoding="utf-8")))
        )

    drift = {
        key: (text, spa_messages.get(key))
        for key, text in _theme_catalog().items()
        if key not in THEME_ONLY_KEYS
        and THEME_PARAMETER.sub(r"{\1}", text) != spa_messages.get(key)
    }

    assert drift == {}


def _spa_translations(language):
    """The SPA's messages in ``language``, merged in the same order as English."""
    spa = {}
    for path in reversed(FE_USER_CATALOGS):
        localized = path.with_name(f"{language}.json")
        if localized.is_file():
            spa.update(_flatten("", json.loads(localized.read_text(encoding="utf-8"))))
    return spa


def test_every_translated_entry_equals_the_spa_translation():
    if not all(path.is_file() for path in FE_USER_CATALOGS):
        pytest.skip("fe-user is not next to vbwd-backend (plugin CI)")
    drifted = {}
    for catalog_path in translated_catalog_paths(TRANSLATIONS_DIRECTORY):
        spa = _spa_translations(catalog_path.stem)
        catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
        for key, value in catalog.items():
            if THEME_PARAMETER.sub(r"{\1}", value) != spa.get(key):
                drifted[f"{catalog_path.stem}:{key}"] = (value, spa.get(key))

    assert not drifted, drifted
