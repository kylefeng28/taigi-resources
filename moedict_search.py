#!/usr/bin/env python3
"""
Search dict-twblg.json / dict-twblg-ext.json for matching entries.

For each match, prints the character (Han-ji), Tai-lo pronunciation,
examples (Han-ji / Tai-lo / Mandarin), the entry's audio_file, and each
example's example_audio_file, resolved to their on-disk mp3 paths.

Examples:
    moedict_search.py tshiann
    moedict_search.py --hanji 請
    moedict_search.py --tailo tshiann
    moedict_search.py --example tshit-thô
"""

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path

DEFAULT_FILES = ["dict-twblg.json", "dict-twblg-ext.json"]

# U+FFF9 ANCHOR, U+FFFA SEPARATOR, U+FFFB TERMINATOR
EXAMPLE_RE = re.compile("\ufff9(.*?)\ufffa(.*?)\ufffb(.*)", re.DOTALL)

SUTIAU_MP3_DIR = "data/sutiau-mp3"
LEKU_MP3_DIR = "data/leku-mp3"

TYPE = "type"
EXAMPLES = "examples"

# Fields
HANJI = "hanji"
TAILO = "tailo"
MANDARIN = "mandarin"
EXAMPLE = "example"
DEF = "def"


def strip_accents(text):
    """Remove diacritics so â/á/à/etc. all normalize to a, etc."""
    decomposed = unicodedata.normalize("NFD", text)
    return "".join(c for c in decomposed if unicodedata.category(c) != "Mn")


def normalize(text):
    return strip_accents(text).casefold()


def parse_example(raw):
    """Split a raw example string into hanji / tai-lo / mandarin parts."""
    m = EXAMPLE_RE.match(raw)
    if m:
        hanji, tailo, mandarin = (s.strip() for s in m.groups())
        return {HANJI: hanji, TAILO: tailo, MANDARIN: mandarin}
    # Fallback: unexpected format, just keep the raw text
    return {HANJI: raw, TAILO: "", MANDARIN: ""}


def audio_path(audio_file):
    if not audio_file:
        return None
    return str(Path(SUTIAU_MP3_DIR, audio_file[:2], f"{audio_file}.mp3"))


def example_audio_path(example_audio_file):
    if not example_audio_file:
        return None
    prefix = example_audio_file.split("-")[0]
    return str(Path(LEKU_MP3_DIR, prefix[:2], f"{example_audio_file}.mp3"))


def load_entries(paths):
    """Load and merge one or more dict-twblg-style JSON files."""
    entries = []
    for path in paths:
        p = Path(path)
        if not p.exists():
            print(f"warning: {path} not found, skipping", file=sys.stderr)
            continue
        with p.open(encoding="utf-8") as f:
            data = json.load(f)
        entries.extend(data)
    return entries


def build_records(entries):
    """Flatten entries into one record per definition."""
    records = []
    for entry in entries:
        title = entry.get("title", "")
        for het in entry.get("heteronyms", []):
            tailo = het.get("trs", "")
            audio_file = het.get("audio_file")
            het_id = het.get("id")
            for defn in het.get("definitions", []):
                examples = [parse_example(e) for e in defn.get(EXAMPLE, [])]
                example_audio_files = defn.get("example_audio_file", [])
                records.append(
                    {
                        "id": het_id,
                        HANJI: title,
                        TAILO: tailo,
                        TYPE: defn.get(TYPE, ""),
                        DEF: defn.get(DEF, ""),
                        EXAMPLES: examples,
                        "audio_file": audio_path(audio_file),
                        "example_audio_files": [
                            example_audio_path(f) for f in example_audio_files
                        ],
                    }
                )
    return records


def get_records(paths):
    entries = load_entries(paths)
    records = build_records(entries)
    return records


def record_matches(record, query, fields):
    """Check whether the (accent-stripped) query appears in the chosen fields."""
    q = normalize(query)

    haystacks = []
    if HANJI in fields:
        haystacks.append(record[HANJI])
        haystacks.extend(ex[HANJI] for ex in record[EXAMPLES])
    if TAILO in fields:
        haystacks.append(record[TAILO])
        haystacks.extend(ex[TAILO] for ex in record[EXAMPLES])
    if EXAMPLE in fields:
        for ex in record[EXAMPLES]:
            haystacks.extend([ex[HANJI], ex[TAILO], ex[MANDARIN]])
    if DEF in fields:
        haystacks.append(record[DEF])

    return any(q in normalize(h) for h in haystacks if h)


def print_record(record):
    print(f"[{record['id']}] {record[HANJI]}  ({record[TAILO]})")
    if record[TYPE] or record[DEF]:
        print(f"  {record[TYPE]}: {record[DEF]}")
    if record["audio_file"]:
        print(f"  audio_file: {record['audio_file']}")
    for ex, ex_audio in zip(record[EXAMPLES], record["example_audio_files"] or [None] * len(record[EXAMPLES])):
        print("  example:")
        print(f"    hanji:    {ex[HANJI]}")
        print(f"    tai-lo:   {ex[TAILO]}")
        print(f"    mandarin: {ex[MANDARIN]}")
        if ex_audio:
            print(f"    example_audio_file: {ex_audio}")
    print()


def main():
    parser = argparse.ArgumentParser(
        description="Search dict-twblg.json / dict-twblg-ext.json entries."
    )
    parser.add_argument("query", nargs="+", help="Search term (accents ignored)")
    parser.add_argument(
        "--files",
        nargs="+",
        default=DEFAULT_FILES,
        help=f"JSON files to search (default: {' '.join(DEFAULT_FILES)})",
    )
    parser.add_argument("--hanji", action="store_true", help="Search only the character / Han-ji field")
    parser.add_argument("--tailo", action="store_true", help="Search only the Tai-lo pronunciation field")
    parser.add_argument("--example", action="store_true", help="Search only within example sentences")
    parser.add_argument("--json", action="store_true", help="Output raw JSON instead of formatted text")
    parser.add_argument("--limit", type=int, default=None, help="Limit the number of results shown")

    args = parser.parse_args()

    records = get_records(args.files)

    fields = []
    if args.hanji:
        fields.append(HANJI)
    if args.tailo:
        fields.append(TAILO)
    if args.example:
        fields.append(EXAMPLE)
    if not fields:
        fields = [HANJI, TAILO, EXAMPLE, DEF]

    query = " ".join(args.query)

    matches = [r for r in records if record_matches(r, query, fields)]

    if args.limit is not None:
        matches = matches[: args.limit]

    if args.json:
        print(json.dumps(matches, ensure_ascii=False, indent=2))
        return

    if not matches:
        print("No matches found.")
        return

    for record in matches:
        print_record(record)

    print(f"{len(matches)} match(es) found.", file=sys.stderr)


if __name__ == "__main__":
    main()
