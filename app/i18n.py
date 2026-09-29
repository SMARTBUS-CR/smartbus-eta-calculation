import json
from pathlib import Path
from fastapi import Request

_translations = {}
LOCALES_DIR = Path(__file__).parent / "api" / "locales"

# Carga de archivos JSON en memoria
if LOCALES_DIR.exists():
    for file_path in LOCALES_DIR.glob("*.json"):
        lang_code = file_path.stem
        with open(file_path, "r", encoding="utf-8") as f:
            _translations[lang_code] = json.load(f)

def get_locale(request: Request) -> str:
    """Extrae el idioma del header de forma genérica."""
    lang = request.headers.get("Accept-Language", "en").lower()
    return "es" if "es" in lang else "en"

def __(key: str, request: Request) -> str:
    locale = get_locale(request)
    
    # Busca directamente la llave plana (ej. "errors.internal_server_title")
    value = _translations.get(locale, {})
    return value.get(key, key)