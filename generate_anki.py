#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "genanki>=0.13.1",
#     "tqdm>=4.70.1",
# ]
# ///
"""
Build an Anki deck (.apkg) from entries from a CSV file (taigi_vocab.csv).
Pulls the definition, audio, examples, and example audio for each entry from the dict-twblg.json /
dict-twblg-ext.json data.

Usage:
    python build_anki_deck.py
    python build_anki_deck.py --vocab taigi_vocab.csv --output taigi_vocab.apkg
"""

import argparse
import csv
import html
from pathlib import Path

import genanki
from tqdm import tqdm

from moedict_search import get_records, record_matches, DEFAULT_FILES
from moedict_search import HANJI, TAILO, MANDARIN, DEF, AUDIO_FILE, EXAMPLES, EXAMPLE_AUDIO_FILES

DEFAULT_INPUT_CSV_FILE="vocab/taigi_vocab.csv"
DEFAULT_OUTPUT_APKG_FILE="taigi_vocab.apkg"

# Vocab CSV fields
ENGLISH = "english"
CATEGORY = "category"

# Fixed, arbitrary IDs -- keep these stable across runs so re-generating the
# deck updates existing notes/deck in Anki instead of duplicating them.
MODEL_ID = 1607392319
DECK_ID = 2059400110

FRONT_TEMPLATE="""
<div class='hanji'>{{Hanji}}</div>
{{Audio}}
"""

BACK_TEMPLATE="""
<div class='hanji'>{{Hanji}}</div>
<div class='tailo'>{{TaiLo}}</div>
<br>
{{Audio}}

<hr id='answer'>

{{#Category}}<span class='category'>{{Category}}</span>{{/Category}}

<div class='mandarin'>{{Mandarin}}</div>
<div class='english'>{{English}}</div>
{{#Definition}}<div class='def'>{{Definition}}</div>{{/Definition}}
{{#Examples}}<div class='examples'>{{Examples}}</div>{{/Examples}}

"""

STYLE="""
.card { font-family: sans-serif; font-size: 20px; text-align: center; }
.hanji { font-size: 48px; }
.tailo { color: #2a6; font-style: italic; margin-top: 8px; }
.mandarin { margin-top: 4px; }
.english { color: #666; margin-top: 4px; }
.def { margin-top: 12px; font-size: 16px; color: #444; }
.examples { margin-top: 12px; font-size: 15px; }
.example { margin-bottom: 10px; }
.category { margin-top: 12px; font-size: 16px; color: #999; }
"""

MODEL = genanki.Model(
    MODEL_ID,
    "Taigi Vocab",
    fields=[
        {"name": "Hanji"},
        {"name": "TaiLo"},
        {"name": "Mandarin"},
        {"name": "English"},
        {"name": "Category"},
        {"name": "Definition"},
        {"name": "Examples"},
        {"name": "Audio"},
    ],
    templates=[
        {
            "name": "Recognition (Hanji -> meaning)",
            "qfmt": FRONT_TEMPLATE,
            "afmt": BACK_TEMPLATE
        },
    ],
    css=STYLE
)

class CustomNote(genanki.Note):
    def __init__(self, v, record, media_files):
        definition = record[DEF] if record else ""
        examples_html = build_examples_html(record, media_files)
        audio_tag = sound_tag(record[AUDIO_FILE] if record else None, media_files)

        fields=[
            v[HANJI],
            v[TAILO],
            v[MANDARIN],
            v[ENGLISH],
            v[CATEGORY],
            definition,
            examples_html,
            audio_tag,
        ]

        guid = genanki.guid_for(fields[0], fields[1])

        super().__init__(model=MODEL, fields=fields, guid=guid)


def read_vocab(path):
    rows = []
    with open(path, encoding="utf-8-sig") as f:
        r = csv.reader(f)
        next(r, None)  # header
        for row in r:
            if len(row) >= 5:
                rows.append(
                    {
                        CATEGORY: row[0],
                        HANJI: row[1],
                        TAILO: row[2],
                        MANDARIN: row[3],
                        ENGLISH: row[4],
                    }
                )
    return rows


def find_match(records, hanji, tailo):
    """Find the dict-twblg definition matching this hanji + tai-lo.

    Prefers an exact tai-lo match among heteronyms sharing the same
    character (since one character can have multiple readings), and
    falls back to the first definition for that character otherwise.
    """
    candidates = [r for r in records if record_matches(r, hanji, [HANJI], "entire", False)]
    if not candidates:
        return None
    exact = [r for r in candidates if record_matches(r, tailo, [TAILO], "substring", False)]
    return (exact or candidates)[0]


def sound_tag(path, media_files):
    """Return an Anki [sound:...] tag and register the file for bundling,
    or "" if there's no path / the file isn't present on disk."""
    if not path:
        return ""
    elif not Path(path).exists():
        print("warning: missing media path:", path)
        return ""
    media_files.append(path)
    return f"[sound:{Path(path).name}]"


def build_examples_html(record, media_files):
    if not record:
        return ""
    parts = []
    audios = record[EXAMPLE_AUDIO_FILES] or [None] * len(record[EXAMPLES])
    for ex, ex_audio in zip(record[EXAMPLES], audios):
        tag = sound_tag(ex_audio, media_files)
        parts.append(
            "<div class='example'>\n"
            f"<span>{html.escape(ex[HANJI])}<span>\n"
            f"<i>{html.escape(ex[TAILO])}</i>\n"
            "<br>\n"
            f"{html.escape(ex[MANDARIN])}\n"
            f"{tag}\n"
            "</div>"
        )
    return "".join(parts)


def build_deck(vocab_path, dict_files, deck_name, output_path):
    vocab = read_vocab(vocab_path)
    records = get_records(dict_files)

    deck = genanki.Deck(DECK_ID, deck_name)
    media_files = []
    matched = 0
    unmatched = []

    for v in tqdm(vocab):
        record = find_match(records, v[HANJI], v[TAILO])
        if record:
            matched += 1
        else:
            unmatched.append(v)

        note = CustomNote(v, record, media_files)
        deck.add_note(note)

    package = genanki.Package(deck, media_files=media_files)
    package.write_to_file(output_path)

    print(f"Wrote {len(vocab)} notes ({matched} matched to dict-twblg data) -> {output_path}")
    if media_files:
        print(f"Bundled {len(media_files)} audio file(s).")
    if unmatched:
        print(f"{len(unmatched)} entries had no dict-twblg match "
              f"(added with CSV data only, no definition/examples/audio).")
        for record in unmatched:
            print(record)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--vocab", default=DEFAULT_INPUT_CSV_FILE, help="Vocab CSV file")
    parser.add_argument(
        "--dict-files", nargs="+", default=DEFAULT_FILES,
        help="dict-twblg JSON files to pull definitions/audio from",
    )
    parser.add_argument("--deck-name", default="Taigi Vocab", help="Anki deck name")
    parser.add_argument("--output", default=DEFAULT_OUTPUT_APKG_FILE, help="Output .apkg path")
    args = parser.parse_args()

    build_deck(args.vocab, args.dict_files, args.deck_name, args.output)


if __name__ == "__main__":
    main()
