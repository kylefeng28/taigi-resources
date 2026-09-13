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
import subprocess
import sys
import unicodedata
from pathlib import Path

DEFAULT_FILES = ["dict-twblg.json", "dict-twblg-ext.json"]

# U+FFF9 ANCHOR, U+FFFA SEPARATOR, U+FFFB TERMINATOR
EXAMPLE_RE = re.compile("\ufff9(.*?)\ufffa(.*?)\ufffb(.*)", re.DOTALL)

SUTIAU_MP3_DIR = "data/sutiau-mp3"
LEKU_MP3_DIR = "data/leku-mp3"

# JSON entry / definition fields
ID =  "id"
HANJI = "hanji"
TAILO = "tailo"
TYPE = "type"
MANDARIN = "mandarin"
EXAMPLE = "example"
DEF = "def"
AUDIO_FILE = "audio_file"
EXAMPLE_AUDIO_FILE = "example_audio_file"

# Record fields
EXAMPLES = "examples"
EXAMPLE_AUDIO_FILES = "example_audio_files"


def _strip_accents(decomposed):
    """Remove diacritics so â/á/à/etc. all normalize to a, etc."""
    return "".join(c for c in decomposed if unicodedata.category(c) != "Mn")


def normalize(text, strip_accents: bool):
    nfd = unicodedata.normalize("NFD", text)
    return _strip_accents(nfd).casefold() if strip_accents else nfd.casefold()


def parse_example(raw):
    """Split a raw example string into hanji / tai-lo / mandarin parts."""
    m = EXAMPLE_RE.match(raw)
    if m:
        hanji, tailo, mandarin = (s.strip() for s in m.groups())
        return {HANJI: hanji, TAILO: tailo, MANDARIN: mandarin}
    # Fallback: unexpected format, just keep the raw text
    return {HANJI: raw, TAILO: "", MANDARIN: ""}


def get_audio_path_prefix(id: str):
    # e.g. 2003 -> 2, 20168 -> 20
    return id[:-3]

def audio_path(audio_file):
    if not audio_file:
        return None
    return str(Path(SUTIAU_MP3_DIR, get_audio_path_prefix(audio_file), f"{audio_file}(1).mp3"))


def example_audio_path(example_audio_file):
    if not example_audio_file:
        return None
    prefix = get_audio_path_prefix(example_audio_file.split("-")[0])
    return str(Path(LEKU_MP3_DIR, prefix, f"{example_audio_file}.mp3"))


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
        title = entry.get("title")
        for het in entry.get("heteronyms", []):
            tailo = het.get("trs", "")
            audio_file = het.get(AUDIO_FILE)
            het_id = het.get(ID)
            for defn in het.get("definitions", []):
                examples = [parse_example(e) for e in defn.get(EXAMPLE, [])]
                example_audio_files = defn.get(EXAMPLE_AUDIO_FILE, [])
                records.append(
                    {
                        ID: het_id,
                        HANJI: title,
                        TAILO: tailo,
                        TYPE: defn.get(TYPE, ""),
                        DEF: defn.get(DEF, ""),
                        EXAMPLES: examples,
                        AUDIO_FILE: audio_path(audio_file),
                        EXAMPLE_AUDIO_FILES: [
                            example_audio_path(f) for f in example_audio_files
                        ],
                    }
                )
    return records


def get_records(paths):
    entries = load_entries(paths)
    records = build_records(entries)
    return records


# --- searching -----------------------------------------------------------

def syllable_match(query: str, text: str, strip_accents: bool):
    q = re.escape(normalize(query, strip_accents))
    t = normalize(text, strip_accents)

    pattern = rf"(?<![a-z]){q}(?![a-z])"
    return re.search(pattern, t) is not None

def record_matches(record, query: str, fields: list[str], match_mode: str, strip_accents: bool):
    """Check whether the (accent-stripped) query appears in the chosen fields."""
    q = normalize(query, strip_accents)

    haystacks = []
    if ID in fields:
        haystacks.append(record[ID])
    if HANJI in fields:
        haystacks.append(record[HANJI])
        if EXAMPLE in fields:
            haystacks.extend(ex[HANJI] for ex in record[EXAMPLES])
    if TAILO in fields:
        haystacks.append(record[TAILO])
        if EXAMPLE in fields:
            haystacks.extend(ex[TAILO] for ex in record[EXAMPLES])
    if EXAMPLE in fields:
        for ex in record[EXAMPLES]:
            haystacks.extend([ex[HANJI], ex[TAILO], ex[MANDARIN]])
    if DEF in fields:
        haystacks.append(record[DEF])

    if match_mode == "entire":
        return any(q == normalize(h, strip_accents) for h in haystacks if h)
    elif match_mode == "syllable":
        return any(syllable_match(q, h, strip_accents) for h in haystacks if h)
    elif match_mode == "substring":
        return any(q in normalize(h, strip_accents) for h in haystacks if h)
    else:
        raise Exception("invalid match_mode " + match_mode)


def print_record(record):
    print(f"[{record['id']}] {record[HANJI]}  ({record[TAILO]})")
    if record[TYPE] or record[DEF]:
        print(f"  {record[TYPE]}: {record[DEF]}")
    if record["audio_file"]:
        print(f"  audio_file: {record[AUDIO_FILE]}")
    for ex, ex_audio in zip(record[EXAMPLES], record[EXAMPLE_AUDIO_FILES] or [None] * len(record[EXAMPLES])):
        print("  example:")
        print(f"    hanji:    {ex[HANJI]}")
        print(f"    tai-lo:   {ex[TAILO]}")
        print(f"    mandarin: {ex[MANDARIN]}")
        if ex_audio:
            print(f"    example_audio_file: {ex_audio}")
    print()


# --- fzf integration -----------------------------------------------------

def tsv_line(record):
    example_preview = record[EXAMPLES][0][HANJI] if record[EXAMPLES] else ""
    display = [record[ID], record[HANJI], record[TAILO], record[DEF][:30], example_preview[:30]]
    return "\t".join(display)


def run_fzf(records, script_path):
    lines = "\n".join(tsv_line(r) for r in records)

    preview_cmd = f"{sys.executable} {script_path} --id {{1}}"

    proc = subprocess.run(
        [
            "fzf",
            "--reverse",
            "--delimiter", "\t",
            "--header", "Id\tCharacter\tTai-lo\tDefinition\tExample",
            "--preview", preview_cmd,
            "--preview-window", "down:60%:wrap",
        ],
        input=lines,
        text=True,
    )
    return proc.returncode


# --- CLI -----------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Search dict-twblg.json / dict-twblg-ext.json entries."
    )
    parser.add_argument("query", nargs="*", help="Search term (accents ignored)")
    parser.add_argument(
        "--files",
        nargs="+",
        default=DEFAULT_FILES,
        help=f"JSON files to search (default: {' '.join(DEFAULT_FILES)})",
    )
    parser.add_argument("--id", action="store_true", help="Search by entry ID field")
    parser.add_argument("--hanji", action="store_true", help="Search only the character / Han-ji field")
    parser.add_argument("--tailo", action="store_true", help="Search only the Tai-lo pronunciation field")
    parser.add_argument("--example", action="store_true", help="Search only within example sentences")
    parser.add_argument("--json", action="store_true", help="Output raw JSON instead of formatted text")
    parser.add_argument("--limit", type=int, default=None, help="Limit the number of results shown")
    parser.add_argument("--fzf", action="store_true", help="Interactive fuzzy search via fzf")
    parser.add_argument("--match", choices=["entire",  "substring", "syllable"], default="entire")
    parser.add_argument("--no-strip-accents", action="store_false", dest="strip_accents")

    args = parser.parse_args()

    records = get_records(args.files)

    if args.fzf:
        sys.exit(run_fzf(records, Path(__file__).resolve()))

    if not args.query:
        parser.error("query is required unless --fzf is used")

    fields = []
    if args.id:
        fields.append(ID)
    if args.hanji:
        fields.append(HANJI)
    if args.tailo:
        fields.append(TAILO)
    if args.example:
        fields.append(EXAMPLE)
    if not fields:
        fields = [HANJI, TAILO, EXAMPLE, DEF]

    query = " ".join(args.query)

    matches = [r for r in records if record_matches(r, query, fields, args.match, args.strip_accents)]

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
