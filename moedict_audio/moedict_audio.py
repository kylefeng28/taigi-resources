#!/usr/bin/env python3
"""
Fetch Taigi audio from the Moedict API.

Given a hanzi, queries the Moedict Taigi API, extracts audio IDs,
and downloads the corresponding MP3 files. Plays audio via mpv.

Usage:
    python -m moedict_audio              # Interactive mode (prompts for hanzi)
    python -m moedict_audio 劑           # Single lookup
    python -m moedict_audio 三 ./audio   # Single lookup, save to ./audio/
"""

from __future__ import annotations

import re
import sys
import urllib.request
import urllib.error
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


MOEDICT_API_URL = "https://www.moedict.tw/api/'{hanzi}.json"
AUDIO_BASE_URL = "https://r2-assets.moedict.tw/audio/t/{audio_id}.mp3"


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
        We try the 5-digit padded first, then the unpadded.
        """
        eid = self.effective_audio_id
        if eid is None:
            return []

        urls = []
        if eid.isdigit():
            padded = eid.zfill(5)
            if padded != eid:
                urls.append(AUDIO_BASE_URL.format(audio_id=padded))
        urls.append(AUDIO_BASE_URL.format(audio_id=eid))

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


def parse_reading_type(reading_html: str | None) -> str | None:
    """
    Extract the reading type (白, 文, 替, 俗, etc.) from the HTML `reading` field.
    """
    if not reading_html:
        return None
    # Match the text content between > and </a>
    # e.g. <a href="./#'白">白</a>
    match = re.search(r">([^<]+)</a>", reading_html)
    if match:
        return match.group(1)
    return None


def fetch_moedict(hanzi: str) -> dict:
    """
    Fetch the Moedict API response for a given hanzi.
    """
    # URL-encode the hanzi for the request path
    from urllib.parse import quote
    encoded_hanzi = quote(hanzi, safe="")
    url = MOEDICT_API_URL.format(hanzi=encoded_hanzi)
    req = urllib.request.Request(url, headers={"User-Agent": "moedict-audio-cli/1.0"})
    with urllib.request.urlopen(req) as response:
        data = response.read().decode("utf-8")
    return json.loads(data)


def extract_heteronyms(api_response: dict) -> list[Heteronym]:
    """
    Parse the API response and extract heteronyms that have audio available.
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


def download_audio(url: str, output_path: Path) -> None:
    """
    Download an MP3 file from the given URL and save it to output_path.
    """
    req = urllib.request.Request(url, headers={"User-Agent": "moedict-audio-cli/1.0"})
    with urllib.request.urlopen(req) as response:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "wb") as f:
            f.write(response.read())


# --- CLI interface ---

def prompt_select_heteronym(hanzi: str, heteronyms: list[Heteronym]) -> Heteronym | None:
    """
    If there are multiple heteronyms, prompt the user to select one.
    If there's only one, return it directly.
    Returns None if user cancels.
    """
    if len(heteronyms) == 1:
        return heteronyms[0]

    print(f"\nMultiple readings found for 「{hanzi}」:")
    for i, h in enumerate(heteronyms, start=1):
        print(f"  {i}. {h.display_label()}")
    print("  0. Cancel")

    while True:
        try:
            choice = input("\nSelect a reading [1]: ").strip()
            if choice == "":
                # Default to first option
                return heteronyms[0]
            if choice == "0":
                return None
            idx = int(choice) - 1
            if 0 <= idx < len(heteronyms):
                return heteronyms[idx]
            print(f"  Please enter a number between 0 and {len(heteronyms)}.")
        except ValueError:
            print("  Please enter a valid number.")
        except (EOFError, KeyboardInterrupt):
            print()
            return None


def play_audio(path: Path) -> None:
    """Play an MP3 file using the system mpv player."""
    import subprocess
    try:
        subprocess.run(["mpv", "--no-video", str(path)], check=True)
    except FileNotFoundError:
        print("  Warning: mpv not found. Install mpv to enable audio playback.")
    except subprocess.CalledProcessError as e:
        print(f"  Warning: mpv exited with code {e.returncode}")


def lookup_audio(hanzi: str, output_dir: Path | None = None, interactive: bool = True, play: bool = False) -> Path | None:
    """
    Main entry point: look up a hanzi, select a heteronym, and download the audio.

    Args:
        hanzi: The character(s) to look up.
        output_dir: Directory to save MP3 files. Defaults to current directory.
        interactive: If True, prompt for heteronym selection. If False, use first available.
        play: If True, play the audio with mpv after downloading.

    Returns:
        Path to the downloaded MP3 file, or None if lookup/download failed.
    """
    if output_dir is None:
        output_dir = Path(".")

    # Fetch from API
    print(f"Looking up 「{hanzi}」...")
    try:
        response = fetch_moedict(hanzi)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            print(f"  Error: 「{hanzi}」 not found in Moedict.")
        else:
            print(f"  Error: API returned HTTP {e.code}")
        return None
    except Exception as e:
        print(f"  Error fetching API: {e}")
        return None

    # Extract heteronyms with audio
    heteronyms = extract_heteronyms(response)
    if not heteronyms:
        print(f"  No audio available for 「{hanzi}」.")
        return None

    # Select heteronym
    if interactive and len(heteronyms) > 1:
        selected = prompt_select_heteronym(hanzi, heteronyms)
    else:
        selected = heteronyms[0]

    if selected is None:
        print("  Cancelled.")
        return None

    # Download audio
    audio_urls = selected.audio_urls
    if not audio_urls:
        print("  No audio URL for selected reading.")
        return None

    # Build output filename: {hanzi}_{trs}_{id}.mp3
    safe_trs = re.sub(r"[^\w]", "", selected.trs)
    eid = selected.effective_audio_id
    filename = f"{hanzi}_{safe_trs}_{eid}.mp3"
    output_path = output_dir / filename

    print(f"  Reading: {selected.display_label()}")

    # Try each candidate URL
    downloaded = False
    for url in audio_urls:
        print(f"  Trying: {url}")
        try:
            download_audio(url, output_path)
            downloaded = True
            break
        except urllib.error.HTTPError as e:
            if e.code == 404 and url != audio_urls[-1]:
                continue
            if not downloaded:
                print(f"  Error: Download failed with HTTP {e.code}")
                return None
        except Exception as e:
            print(f"  Error downloading: {e}")
            return None

    if not downloaded:
        print(f"  Error: Could not find audio file at any URL for {eid}.")
        return None

    print(f"  Saved to: {output_path}")

    # Play audio if requested
    if play:
        play_audio(output_path)

    return output_path


def interactive_loop(output_dir: Path) -> None:
    """Interactive REPL: prompt the user for hanzi, look up and play audio."""
    print("Moedict Taigi Audio Lookup")
    print("Type a hanzi to look up its audio. Ctrl+C or empty input to quit.\n")

    while True:
        try:
            hanzi = input("漢字: ").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if not hanzi:
            break

        lookup_audio(hanzi, output_dir=output_dir, interactive=True, play=True)
        print()


def main():
    # If hanzi is provided as argument, run in single-shot mode
    if len(sys.argv) >= 2:
        hanzi = sys.argv[1]
        output_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(".")
        result = lookup_audio(hanzi, output_dir=output_dir, interactive=True, play=True)
        if result is None:
            sys.exit(1)
    else:
        # No arguments: interactive mode
        interactive_loop(output_dir=Path("."))


if __name__ == "__main__":
    main()
