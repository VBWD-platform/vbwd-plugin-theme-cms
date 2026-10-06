"""Where theme_cms's contributed templates, translations and stylesheets live."""
from pathlib import Path

PACKAGE_DIRECTORY = Path(__file__).resolve().parent
TEMPLATES_DIRECTORY = PACKAGE_DIRECTORY / "templates"
TRANSLATIONS_DIRECTORY = PACKAGE_DIRECTORY / "translations"
# ``_shared/`` + ``public/`` CSS: the SPA component CSS, structural only (S152-06c).
STYLESHEETS_DIRECTORY = PACKAGE_DIRECTORY / "stylesheets"
