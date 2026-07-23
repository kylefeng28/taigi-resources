"""Moedict Taigi audio fetcher."""

from .moedict_audio import (
    Heteronym,
    fetch_moedict,
    extract_heteronyms,
    download_audio,
    play_audio,
    lookup_audio,
    interactive_loop,
    parse_reading_type,
    MOEDICT_API_URL,
    AUDIO_BASE_URL,
)

__all__ = [
    "Heteronym",
    "fetch_moedict",
    "extract_heteronyms",
    "download_audio",
    "play_audio",
    "lookup_audio",
    "interactive_loop",
    "parse_reading_type",
    "MOEDICT_API_URL",
    "AUDIO_BASE_URL",
]
