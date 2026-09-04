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
import urllib.error
from pathlib import Path

from .core import (
    Heteronym,
    fetch_moedict,
    extract_heteronyms,
    download_audio_data,
    audio_filename,
)


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
    audio_data = download_audio_data(selected)
    if audio_data is None:
        print(f"  Error: Could not download audio for {selected.display_label()}.")
        return None

    # Save to file
    filename = audio_filename(hanzi, selected)
    output_path = output_dir / filename
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "wb") as f:
        f.write(audio_data)

    print(f"  Reading: {selected.display_label()}")
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
