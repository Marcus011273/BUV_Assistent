from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any

import streamlit as st
from streamlit_local_storage import LocalStorage

from modules.protocol_model import ensure_protocol_shape
from modules.storage import load_protocol_from_bytes, protocol_to_json_bytes


AUTOSAVE_PROTOCOL_KEY = "buv_assistent_protocol_autosave_v1"
AUTOSAVE_META_KEY = "buv_assistent_protocol_autosave_meta_v1"

LOCAL_STORAGE_WIDGET_KEY = "buv_assistent_local_storage"
LOCAL_STORAGE_OBJECT_KEY = "_buv_assistent_local_storage_object"


def get_local_storage() -> LocalStorage:
    """
    Liefert genau eine LocalStorage-Instanz pro Streamlit-Session.
    """
    if LOCAL_STORAGE_WIDGET_KEY not in st.session_state:
        st.session_state[LOCAL_STORAGE_WIDGET_KEY] = {}

    if LOCAL_STORAGE_OBJECT_KEY not in st.session_state:
        st.session_state[LOCAL_STORAGE_OBJECT_KEY] = LocalStorage(
            key=LOCAL_STORAGE_WIDGET_KEY
        )

    return st.session_state[LOCAL_STORAGE_OBJECT_KEY]


def protocol_has_content(protocol: dict[str, Any]) -> bool:
    """
    Verhindert, dass ein komplett leeres neues Protokoll sofort
    eine vorhandene Browser-Sicherung überschreibt.
    """
    protocol = ensure_protocol_shape(protocol)

    stammdaten = protocol.get("stammdaten", {})
    einzel = protocol.get("einzel_buv", {})
    doppel = protocol.get("doppel_buv", {})
    kompetenzen = protocol.get("kompetenzen", {})

    relevant_values = [
        stammdaten.get("laa_name", ""),
        stammdaten.get("schule", ""),
        stammdaten.get("bemerkungen", ""),
        einzel.get("datum", ""),
        einzel.get("fach", ""),
        einzel.get("klasse", ""),
        einzel.get("thema", ""),
        einzel.get("zusammenfassung_weiterarbeit", ""),
        einzel.get("zielvereinbarungen_laa", ""),
        doppel.get("datum", ""),
        doppel.get("zusammenfassung_weiterarbeit", ""),
        doppel.get("zielvereinbarungen_laa", ""),
        kompetenzen.get("handlungs_und_sachkompetenz", ""),
        kompetenzen.get("einbringen_schule_und_seminar", ""),
    ]

    for value in relevant_values:
        if isinstance(value, str) and value.strip():
            return True

    for buv_part in [
        einzel,
        doppel.get("stunde_1", {}),
        doppel.get("stunde_2", {}),
    ]:
        beobachtungen = buv_part.get("beobachtungen", {})

        for fields in beobachtungen.values():
            if not isinstance(fields, dict):
                continue

            for key in ["positive_feststellungen", "beratungspunkte", "memo"]:
                if str(fields.get(key, "")).strip():
                    return True

    erzieh = kompetenzen.get("erzieherische_kompetenz", {})
    for key in ["positive_feststellungen", "beratungspunkte"]:
        if str(erzieh.get(key, "")).strip():
            return True

    schriftwesen = kompetenzen.get("schriftwesen", {})
    for row in schriftwesen.values():
        if not isinstance(row, dict):
            continue

        status = str(row.get("status", "")).strip()
        bemerkung = str(row.get("bemerkung", "")).strip()

        if bemerkung:
            return True

        if status and status not in ["OK", "--"]:
            return True

    return False


def build_autosave_meta(protocol: dict[str, Any]) -> dict[str, str]:
    protocol = ensure_protocol_shape(protocol)

    stammdaten = protocol.get("stammdaten", {})
    einzel = protocol.get("einzel_buv", {})
    doppel = protocol.get("doppel_buv", {})

    return {
        "saved_at": datetime.now().strftime("%d.%m.%Y, %H:%M:%S"),
        "laa_name": str(stammdaten.get("laa_name", "")).strip(),
        "buv_nummer": str(stammdaten.get("buv_nummer", "")).strip(),
        "schule": str(stammdaten.get("schule", "")).strip(),
        "einzel_datum": str(einzel.get("datum", "")).strip(),
        "doppel_datum": str(doppel.get("datum", "")).strip(),
    }


def _short_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def save_protocol_to_browser(protocol: dict[str, Any]) -> bool:
    """
    Speichert den aktuellen Arbeitsstand im Browser-LocalStorage.
    Gibt True zurück, wenn gespeichert wurde.
    """
    protocol = ensure_protocol_shape(protocol)

    if not protocol_has_content(protocol):
        return False

    local_storage = get_local_storage()

    json_text = protocol_to_json_bytes(protocol).decode("utf-8")
    meta_text = json.dumps(build_autosave_meta(protocol), ensure_ascii=False)

    content_hash = _short_hash(json_text)

    last_saved_hash = st.session_state.get("_last_browser_autosave_hash")

    if last_saved_hash == content_hash:
        return True

    local_storage.setItem(
        AUTOSAVE_PROTOCOL_KEY,
        json_text,
        key=f"buv_autosave_protocol_set_{content_hash}",
    )

    local_storage.setItem(
        AUTOSAVE_META_KEY,
        meta_text,
        key=f"buv_autosave_meta_set_{content_hash}",
    )

    st.session_state["_last_browser_autosave_hash"] = content_hash
    st.session_state["_last_browser_autosave_time"] = datetime.now().strftime("%H:%M:%S")

    return True


def get_browser_autosave() -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """
    Liest vorhandene Browser-Sicherung.
    Rückgabe: protocol, meta
    """
    local_storage = get_local_storage()

    try:
        local_storage.refreshItems()
    except Exception:
        pass

    protocol_text = local_storage.getItem(AUTOSAVE_PROTOCOL_KEY)
    meta_text = local_storage.getItem(AUTOSAVE_META_KEY)

    if not protocol_text:
        return None, None

    try:
        protocol = load_protocol_from_bytes(str(protocol_text).encode("utf-8"))
    except Exception:
        return None, None

    meta: dict[str, Any] | None = None

    if meta_text:
        try:
            meta = json.loads(str(meta_text))
        except Exception:
            meta = None

    return protocol, meta


def erase_browser_autosave() -> None:
    """
    Löscht die Browser-Sicherung.
    """
    local_storage = get_local_storage()

    local_storage.eraseItem(
        AUTOSAVE_PROTOCOL_KEY,
        key="buv_autosave_protocol_erase",
    )

    local_storage.eraseItem(
        AUTOSAVE_META_KEY,
        key="buv_autosave_meta_erase",
    )

    st.session_state.pop("_last_browser_autosave_hash", None)
    st.session_state.pop("_last_browser_autosave_time", None)


def render_browser_autosave_box() -> dict[str, Any] | None:
    """
    Zeigt in der Sidebar eine Box zur Wiederherstellung.
    Gibt ein wiederherzustellendes Protokoll zurück, wenn der Button geklickt wurde.
    """
    saved_protocol, meta = get_browser_autosave()

    st.divider()
    st.header("Browser-Sicherung")

    if saved_protocol is None:
        st.caption("Keine Browser-Sicherung gefunden.")
        return None

    if meta:
        saved_at = meta.get("saved_at", "unbekannt")
        laa_name = meta.get("laa_name", "")
        buv_nummer = meta.get("buv_nummer", "")
        schule = meta.get("schule", "")

        st.success(f"Browser-Sicherung gefunden: {saved_at}")

        details = []

        if laa_name:
            details.append(f"LAA: {laa_name}")

        if buv_nummer:
            details.append(f"BUV: {buv_nummer}")

        if schule:
            details.append(f"Schule: {schule}")

        if details:
            st.caption(" · ".join(details))
    else:
        st.success("Browser-Sicherung gefunden.")

    if st.button(
        "Browser-Sicherung wiederherstellen",
        use_container_width=True,
        key="restore_browser_autosave",
    ):
        return saved_protocol

    if st.button(
        "Browser-Sicherung löschen",
        use_container_width=True,
        key="delete_browser_autosave",
    ):
        erase_browser_autosave()
        st.success("Browser-Sicherung wurde gelöscht.")
        st.rerun()

    return None
