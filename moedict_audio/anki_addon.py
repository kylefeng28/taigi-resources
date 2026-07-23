"""
Taigi Moedict Audio Addon for Anki

Automatically fetches Taigi pronunciation and audio from the Moedict API
and inserts them into the configured Tai-Lo and Audio fields when the hanzi
field loses focus (or when manually triggered via the editor button).

Hooks:
- editFocusLost (legacy): auto-lookup when the source field loses focus
- editor_did_init_buttons: adds a manual "Taigi Audio" button to the editor toolbar

Requires the moedict_audio package to be importable. Either:
- Install it on Anki's Python path, or
- Place/symlink the moedict_audio/ directory inside this addon folder.
"""

from __future__ import annotations

import re
import sys
import os
from typing import Optional, List

from .core import (
    Heteronym,
    fetch_moedict,
    extract_heteronyms,
    download_audio_data,
    audio_filename,
)

import urllib.error

from aqt import mw, gui_hooks
from aqt.editor import Editor
from aqt.utils import showInfo, showWarning, tooltip
from aqt.qt import QInputDialog
from anki.hooks import addHook


# --- Config helper ---

def get_config() -> dict:
    """Load addon config, falling back to defaults."""
    return mw.addonManager.getConfig(__name__) or {
        "note_type": "Taigi",
        "source_field": "Hanzi",
        "tailo_field": "Pronunciation (Tai-lô)",
        "audio_field": "Audio",
        "auto_lookup": True,
    }


# --- Utilities ---

def strip_html(text: str) -> str:
    """Remove HTML tags and decode entities to get plain text from a field value."""
    # Remove HTML tags
    text = re.sub(r"<[^>]+>", "", text)
    # Decode common HTML entities
    text = text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    text = text.replace("&nbsp;", " ").replace("&quot;", '"')
    return text.strip()


def prompt_heteronym_selection(hanzi: str, heteronyms: List[Heteronym]) -> Optional[Heteronym]:
    """
    Show a dialog for the user to select among multiple heteronyms.

    Returns the selected Heteronym, or None if cancelled.
    """
    items = [h.display_label() for h in heteronyms]
    item, ok = QInputDialog.getItem(
        mw,
        f"Select Reading for 「{hanzi}」",
        f"Multiple readings found for 「{hanzi}」.\nSelect one:",
        items,
        0,       # default selection index
        False,   # not editable
    )
    if ok and item:
        idx = items.index(item)
        return heteronyms[idx]
    return None


def field_needs_fill(note, field_name: str, field_names: List[str]) -> bool:
    """Check if a field exists in the note type and is currently empty."""
    if field_name not in field_names:
        return False
    return not note[field_name].strip()


# --- Addon actions ---

def do_lookup(editor: Editor) -> None:
    """
    Perform the Moedict lookup for the current note in the editor.

    Reads the source field, queries Moedict, and populates the Tai-Lo
    and Audio fields based on the selected heteronym. Fields that already
    have content are skipped.
    """
    config = get_config()
    note = editor.note
    if note is None:
        return

    # Check note type matches
    note_type_name = note.note_type()["name"]
    if note_type_name != config["note_type"]:
        tooltip(f"Note type \"{note_type_name}\" doesn't match configured \"{config['note_type']}\".")
        return

    source_field = config["source_field"]
    tailo_field = config["tailo_field"]
    audio_field = config["audio_field"]

    # Check source field exists
    field_names = [f["name"] for f in note.note_type()["flds"]]
    if source_field not in field_names:
        tooltip(f"Field \"{source_field}\" not found in note type.")
        return
    if tailo_field not in field_names:
        tooltip(f"Field \"{tailo_field}\" not found in note type.")
        return
    if audio_field not in field_names:
        tooltip(f"Field \"{audio_field}\" not found in note type.")
        return

    # Get hanzi from source field
    raw_value = note[source_field]
    hanzi = strip_html(raw_value)
    if not hanzi:
        tooltip("Source field is empty.")
        return

    # Determine which fields need filling
    needs_tailo = field_needs_fill(note, tailo_field, field_names)
    needs_audio = field_needs_fill(note, audio_field, field_names)

    if not needs_tailo and not needs_audio:
        tooltip("Tai-Lo and Audio fields already filled. Clear them to re-fetch.")
        return

    # Fetch from API
    try:
        response = fetch_moedict(hanzi)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            tooltip(f"「{hanzi}」 not found in Moedict.")
        else:
            tooltip(f"Moedict API error: HTTP {e.code}")
        return
    except Exception as e:
        tooltip(f"Moedict API error: {e}")
        return

    # Extract heteronyms with audio
    heteronyms = extract_heteronyms(response)
    if not heteronyms:
        tooltip(f"No data available for 「{hanzi}」.")
        return

    # Select heteronym
    if len(heteronyms) == 1:
        selected = heteronyms[0]
    else:
        selected = prompt_heteronym_selection(hanzi, heteronyms)
        if selected is None:
            return

    # Populate Tai-Lo field if needed
    if needs_tailo:
        note[tailo_field] = selected.trs

    # Populate Audio field if needed
    if needs_audio:
        audio_data = download_audio_data(selected)
        if audio_data is not None:
            filename = audio_filename(hanzi, selected)
            mw.col.media.write_data(filename, audio_data)
            note[audio_field] = f"[sound:{filename}]"
        else:
            tooltip(f"Could not download audio for 「{hanzi}」 ({selected.display_label()}).")

    # Refresh the editor to show the changes
    editor.loadNoteKeepingFocus()

    # Build summary of what was filled
    filled = []
    if needs_tailo:
        filled.append(f"Tai-Lo: {selected.trs}")
    if needs_audio and note[audio_field].strip():
        filled.append("Audio ✓")
    tooltip(f"{selected.display_label()} → {', '.join(filled)}")


# --- Hook: auto-lookup when source field loses focus (legacy hook, widely compatible) ---

def on_field_unfocus(changed: bool, note, field_idx: int) -> bool:
    """
    Legacy hook (editFocusLost) triggered when a field loses focus in the editor.

    If the unfocused field is the configured source field, and either the
    Tai-Lo or Audio field is empty, trigger the lookup.
    """
    config = get_config()

    if not config.get("auto_lookup", True):
        return changed

    # Check note type matches
    note_type_name = note.note_type()["name"]
    if note_type_name != config["note_type"]:
        return changed

    source_field = config["source_field"]
    tailo_field = config["tailo_field"]
    audio_field = config["audio_field"]

    # Get field names to find indices
    field_names = [f["name"] for f in note.note_type()["flds"]]
    if source_field not in field_names:
        return changed

    source_idx = field_names.index(source_field)

    # Only trigger when the source field loses focus
    if field_idx != source_idx:
        return changed

    # Get hanzi from source field
    raw_value = note[source_field]
    hanzi = strip_html(raw_value)
    if not hanzi:
        return changed

    # Determine which fields need filling
    needs_tailo = field_needs_fill(note, tailo_field, field_names)
    needs_audio = field_needs_fill(note, audio_field, field_names)

    # Skip if nothing to do
    if not needs_tailo and not needs_audio:
        return changed

    # Fetch from API
    try:
        response = fetch_moedict(hanzi)
    except Exception:
        return changed

    # Extract heteronyms with audio
    heteronyms = extract_heteronyms(response)
    if not heteronyms:
        return changed

    # If single heteronym, auto-fill; if multiple, prompt
    if len(heteronyms) == 1:
        selected = heteronyms[0]
    else:
        selected = prompt_heteronym_selection(hanzi, heteronyms)
        if selected is None:
            return changed

    # Populate Tai-Lo field if needed
    if needs_tailo:
        note[tailo_field] = selected.trs

    # Populate Audio field if needed
    if needs_audio:
        audio_data = download_audio_data(selected)
        if audio_data is not None:
            filename = audio_filename(hanzi, selected)
            mw.col.media.write_data(filename, audio_data)
            note[audio_field] = f"[sound:{filename}]"

    return True  # Signal that we changed the note (editor will reload)


# --- Hook: manual trigger button in editor toolbar ---

def add_editor_button(buttons: list, editor: Editor) -> list:
    """Add a 'Taigi Lookup' button to the editor toolbar."""
    button = editor.addButton(
        icon=None,
        cmd="taigi_lookup",
        func=lambda e: do_lookup(e),
        tip="Look up Taigi reading + audio from Moedict (Ctrl+Shift+T)",
        keys="Ctrl+Shift+T",
        label="台",
    )
    buttons.append(button)
    return buttons


def init_anki_addon():
    # Register hooks ---
    addHook("editFocusLost", on_field_unfocus)

    gui_hooks.editor_did_init_buttons.append(add_editor_button)
