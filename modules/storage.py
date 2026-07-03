from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any, Dict

from .protocol_model import ensure_protocol_shape


def load_protocol_from_bytes(data: bytes) -> Dict[str, Any]:
    try:
        raw = json.loads(data.decode("utf-8"))
    except UnicodeDecodeError as exc:
        raise ValueError("Die JSON-Datei konnte nicht als UTF-8 gelesen werden.") from exc
    except json.JSONDecodeError as exc:
        raise ValueError("Die Datei ist kein gültiger JSON-Arbeitsstand.") from exc
    if not isinstance(raw, dict):
        raise ValueError("Der JSON-Arbeitsstand hat ein ungültiges Format.")
    return ensure_protocol_shape(raw)


def protocol_to_json_bytes(protocol: Dict[str, Any]) -> bytes:
    clean = ensure_protocol_shape(protocol)
    return json.dumps(clean, ensure_ascii=False, indent=2).encode("utf-8")


def safe_filename(value: str, fallback: str = "buv_protokoll") -> str:
    value = value.strip().lower()
    value = value.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    value = re.sub(r"[^a-z0-9_-]+", "_", value)
    value = re.sub(r"_+", "_", value).strip("_")
    return value or fallback


def build_base_filename(protocol: Dict[str, Any]) -> str:
    stammdaten = protocol.get("stammdaten", {})
    name = safe_filename(stammdaten.get("laa_name", "laa"), "laa")
    buv_nummer = safe_filename(str(stammdaten.get("buv_nummer", "1")), "1")
    timestamp = datetime.now().strftime("%Y%m%d")
    return f"{name}_buv_{buv_nummer}_{timestamp}"
