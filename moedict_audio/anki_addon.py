"""
Taigi Moedict Audio Addon for Anki

Automatically fetches Taigi pronunciation audio from the Moedict API
and inserts it into the configured audio field when the hanzi field
loses focus (or when manually triggered via the editor button).

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


# --- Addon actions ---

def do_audio_lookup(editor: Editor) -> None:
    """
    Perform the audio lookup for the current note in the editor.

    Reads the source field, queries Moedict, downloads audio,
    stores it in Anki's media folder, and updates the audio field.
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
    audio_field = config["audio_field"]

    # Check fields exist
    field_names = [f["name"] for f in note.note_type()["flds"]]
    if source_field not in field_names:
        tooltip(f"Field \"{source_field}\" not found in note type.")
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

    # Skip if audio field already has content
    if note[audio_field].strip():
        tooltip("Audio field already has content. Clear it to re-fetch.")
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
        tooltip(f"No audio available for 「{hanzi}」.")
        return

    # Select heteronym
    if len(heteronyms) == 1:
        selected = heteronyms[0]
    else:
        selected = prompt_heteronym_selection(hanzi, heteronyms)
        if selected is None:
            return

    # Download audio
    audio_data = download_audio_data(selected)
    if audio_data is None:
        tooltip(f"Could not download audio for 「{hanzi}」 ({selected.display_label()}).")
        return

    # Store in Anki media collection
    filename = audio_filename(hanzi, selected)
    mw.col.media.write_data(filename, audio_data)

    # Update the audio field with [sound:filename]
    note[audio_field] = f"[sound:{filename}]"

    # Refresh the editor to show the change
    editor.loadNoteKeepingFocus()

    tooltip(f"Added audio: {selected.display_label()}")


# --- Hook: auto-lookup when source field loses focus (legacy hook, widely compatible) ---
def on_field_unfocus(changed: bool, note, field_idx: int) -> bool:
    """
    Legacy hook (editFocusLost) triggered when a field loses focus in the editor.

    If the unfocused field is the configured source field, and the audio field
    is empty, trigger the audio lookup.
    """
    config = get_config()

    if not config.get("auto_lookup", True):
        return changed

    # Check note type matches
    note_type_name = note.note_type()["name"]
    if note_type_name != config["note_type"]:
        return changed

    source_field = config["source_field"]
    audio_field = config["audio_field"]

    # Get field names to find indices
    field_names = [f["name"] for f in note.note_type()["flds"]]
    if source_field not in field_names or audio_field not in field_names:
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

    # Skip if audio field already has content
    if note[audio_field].strip():
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

    # Download audio
    audio_data = download_audio_data(selected)
    if audio_data is None:
        return changed

    # Store in Anki media collection
    filename = audio_filename(hanzi, selected)
    mw.col.media.write_data(filename, audio_data)

    # Update the audio field
    note[audio_field] = f"[sound:{filename}]"

    return True  # Signal that we changed the note (editor will reload)


# --- Hook: manual trigger button in editor toolbar ---
def add_editor_button(buttons: list, editor: Editor) -> list:
    """Add a 'Taigi Audio' button to the editor toolbar."""
    button = editor.addButton(
        icon=None,
        cmd="taigi_audio",
        func=lambda e: do_audio_lookup(e),
        tip="Look up Taigi audio from Moedict (Ctrl+Shift+T)",
        keys="Ctrl+Shift+T",
        label="台",
    )
    buttons.append(button)
    return buttons


def init_anki_addon():
    # Register hooks ---
    addHook("editFocusLost", on_field_unfocus)

    gui_hooks.editor_did_init_buttons.append(add_editor_button)
