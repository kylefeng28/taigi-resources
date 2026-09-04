"""Moedict Taigi audio fetcher."""

from .core import (
    Heteronym,
    fetch_moedict,
    extract_heteronyms,
    download_audio_data,
    audio_filename,
    parse_reading_type,
    MOEDICT_API_URL,
    AUDIO_BASE_URL,
)

from .moedict_audio import (
    lookup_audio,
    interactive_loop,
    play_audio,
)

__all__ = [
    "Heteronym",
    "fetch_moedict",
    "extract_heteronyms",
    "download_audio_data",
    "audio_filename",
    "lookup_audio",
    "interactive_loop",
    "play_audio",
    "parse_reading_type",
    "MOEDICT_API_URL",
    "AUDIO_BASE_URL",
]

try:
    import aqt
    IN_ANKI = True
except ImportError:
    IN_ANKI = False

if IN_ANKI and __name__ != "__main__":
    from .anki_addon import init_anki_addon
    init_anki_addon()

