from __future__ import annotations

import json
from datetime import datetime
from typing import Any

import streamlit as st
from streamlit_local_storage import LocalStorage

from modules.protocol_model import ensure_protocol_shape
from modules.storage import load_protocol_from_bytes, protocol_to_json_bytes


AUTOSAVE_PROTOCOL_KEY = "buv_assistent_protocol_autosave_v1"
AUTOSAVE_META_KEY = "buv_assistent_protocol_autosave_meta_v1"


def get_local_storage() -> LocalStorage:
    """
    Liefert Zugriff auf den Browser-LocalStorage.
    Die Daten liegen im Browser des Nutzers, nicht auf dem Server.
    """
    return LocalStorage(key="buv_assistent_local_storage")


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
        einzel.get("datum", ""),
        einzel.get("fach", ""),
        einzel.get("klasse", ""),
        einzel.get("thema", ""),
        einzel.get("zusammenfassung_weiterarbeit", ""),
        doppel.get("datum", ""),
        doppel.get("zusammenfassung_weiterarbeit", ""),
        kompetenzen.get("handlungs_und_sachkompetenz", ""),
        kompetenzen.get("einbringen_schule_und_seminar", ""),
    ]

    for value in relevant_values:
        if isinstance(value, str) and value.strip():
            return True

    # Beobachtungsraster prüfen
    for buv_part in [einzel, doppel.get("stunde_1", {}), doppel.get("stunde_2", {})]:
        beobachtungen = buv_part.get("beobachtungen", {})
        for fields in beobachtungen.values():
            if not isinstance(fields, dict):
                continue
            for key in ["positive_feststellungen", "beratungspunkte", "memo"]:
                if str(fields.get(key, "")).strip():
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

    local_storage.setItem(
        AUTOSAVE_PROTOCOL_KEY,
        json_text,
        key="buv_autosave_protocol_set",
    )

    local_storage.setItem(
        AUTOSAVE_META_KEY,
        meta_text,
        key="buv_autosave_meta_set",
    )

    return True


def get_browser_autosave() -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """
    Liest vorhandene Browser-Sicherung.
    Rückgabe: (protocol, meta)
    """
    local_storage = get_local_storage()
    local_storage.refreshItems()

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
