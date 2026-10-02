"""Translation helpers for API error responses."""

import json
from pathlib import Path

from fastapi import Request


LOCALES_DIR = Path(__file__).parent / "api" / "locales"
_translations: dict[str, dict[str, str]] = {}


def _load_translations() -> dict[str, dict[str, str]]:
    """Load JSON translation files from the local API locale directory."""
    translations: dict[str, dict[str, str]] = {}
    if not LOCALES_DIR.exists():
        return translations

    for file_path in LOCALES_DIR.glob("*.json"):
        with file_path.open(encoding="utf-8") as file:
            translations[file_path.stem] = json.load(file)
    return translations


_translations = _load_translations()


def get_locale(request: Request) -> str:
    """Return the supported language selected by the request header."""
    language = request.headers.get("Accept-Language", "en").lower()
    return "es" if "es" in language else "en"


def __(key: str, request: Request) -> str:
    """Return the localized message for a translation key."""
    locale = get_locale(request)
    return _translations.get(locale, {}).get(key, key)
