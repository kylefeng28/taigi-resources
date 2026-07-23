"""
Core utilities for fetching Taigi audio from the Moedict API.

This module contains the shared logic used by both the CLI tool
and the Anki addon: data classes, API fetching, heteronym extraction,
and audio downloading.
"""

from __future__ import annotations

import re
import json
import urllib.request
import urllib.error
from dataclasses import dataclass
from urllib.parse import quote
from typing import Optional, List


# --- Constants ---

MOEDICT_API_URL = "https://www.moedict.tw/api/'{hanzi}.json"
AUDIO_BASE_URL = "https://r2-assets.moedict.tw/audio/t/{audio_id}.mp3"


# --- Data classes ---

@dataclass
class Heteronym:
    """Represents a single heteronym (pronunciation variant) of a character."""
    trs: str  # Tâi-lô romanization
    audio_id: str | None  # Dedicated audio ID (preferred)
    entry_id: str | None  # Entry ID (fallback for audio)
    reading_type: str | None  # 白, 文, 替, 俗, etc.

    @property
    def effective_audio_id(self) -> str | None:
        """Return the audio ID to use: audio_id if present, otherwise entry id."""
        return self.audio_id or self.entry_id

    @property
    def audio_urls(self) -> list[str]:
        """
        Return candidate audio URLs to try in order.

        The Moedict R2 bucket is inconsistent with zero-padding:
        some files use the raw numeric ID, others need 5-digit zero-padding.
        We try unpadded first, then 5-digit padded as fallback.
        """
        eid = self.effective_audio_id
        if eid is None:
            return []
        urls = [AUDIO_BASE_URL.format(audio_id=eid)]
        # If it's a numeric ID, also try 5-digit zero-padded version
        if eid.isdigit():
            padded = eid.zfill(5)
            if padded != eid:
                urls.append(AUDIO_BASE_URL.format(audio_id=padded))
        return urls

    def display_label(self) -> str:
        """Human-readable label for heteronym selection prompts."""
        parts = []
        if self.reading_type:
            parts.append(f"[{self.reading_type}]")
        parts.append(self.trs)
        eid = self.effective_audio_id
        if eid:
            parts.append(f"({eid})")
        return " ".join(parts)


# --- Core logic ---

def parse_reading_type(reading_html: str | None) -> str | None:
    """
    Extract the reading type (白, 文, 替, 俗, etc.) from the HTML `reading` field.

    The field looks like: <a href="./#'白">白</a>
    We extract the link text.
    """
    if not reading_html:
        return None
    match = re.search(r">([^<]+)</a>", reading_html)
    if match:
        return match.group(1)
    return None


def fetch_moedict(hanzi: str) -> dict:
    """
    Fetch the Moedict API response for a given hanzi.

    Raises:
        urllib.error.HTTPError: if the API returns an error (e.g. 404 for unknown characters)
        json.JSONDecodeError: if the response is not valid JSON
    """
    encoded_hanzi = quote(hanzi, safe="")
    url = MOEDICT_API_URL.format(hanzi=encoded_hanzi)
    req = urllib.request.Request(url, headers={"User-Agent": "moedict-audio/1.0"})
    with urllib.request.urlopen(req) as response:
        data = response.read().decode("utf-8")
    return json.loads(data)


def extract_heteronyms(api_response: dict) -> list[Heteronym]:
    """
    Parse the API response and extract heteronyms that have audio available.

    Heteronyms without both audio_id and id are filtered out (they have no audio).
    """
    heteronyms = []
    for h in api_response.get("heteronyms", []):
        trs = h.get("trs", "")
        audio_id = h.get("audio_id")
        entry_id = h.get("id")
        reading_type = parse_reading_type(h.get("reading"))

        # Skip heteronyms that have no audio source at all
        if not audio_id and not entry_id:
            continue

        heteronyms.append(Heteronym(
            trs=trs,
            audio_id=audio_id,
            entry_id=entry_id,
            reading_type=reading_type,
        ))

    return heteronyms


def download_audio_data(heteronym: Heteronym) -> Optional[bytes]:
    """
    Download the MP3 data for a heteronym, trying candidate URLs.

    Returns the raw MP3 bytes, or None if all URLs fail.
    """
    for url in heteronym.audio_urls:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "moedict-audio/1.0"})
            with urllib.request.urlopen(req) as response:
                return response.read()
        except urllib.error.HTTPError as e:
            if e.code == 404:
                continue
            return None
        except Exception:
            return None
    return None


def audio_filename(hanzi: str, heteronym: Heteronym) -> str:
    """
    Generate a standard filename for the audio file.

    Format: moedict_taigi_{hanzi}_{id}.mp3
    """
    eid = heteronym.effective_audio_id
    return f"moedict_taigi_{hanzi}_{eid}.mp3"
