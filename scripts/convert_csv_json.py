#!/usr/bin/env python3

import csv
import json
import sys
import os
import unicodedata
from collections import defaultdict

from convert_ods_csv import ENTRIES_CSV, DEFINITIONS_CSV, EXAMPLES_CSV
from convert_ods_csv import (
    COL_ENTRY_ID, COL_ENTRY_TYPE, COL_HANZI, COL_TAILO, COL_HUAYU, COL_READING, COL_TYPE, COL_AUDIO_FILE,  COL_DEF_ID, COL_POS, COL_DEFINITION, COL_EXAMPLE_ORDER, COL_EXAMPLE_AUDIO_FILE,
)

DICT_MANDARIN_JSON = 'dict-revised.json'

# Unicode Interlinear Annotation characters used in example formatting
# https://en.wikipedia.org/wiki/Specials_(Unicode_block)
# https://en.wikipedia.org/wiki/Interlinear_gloss
IAA_BEGIN = '\uFFF9'
IAA_SEP = '\uFFFA'
IAA_END = '\uFFFB'

# Entry types to include in the main dictionary output
# 主詞目 = main entries
MAIN_TYPES = {'主詞目'}
# 附錄 (appendix) with 首字 = proverbs
APPENDIX = '附錄'
PROVERB_MARKER = '首字'

EXT_TYPES = {'單字不成詞者', '臺華共同詞'}

DICT_MAIN_JSON = 'dict-twblg.json'
DICT_EXT_JSON = 'dict-twblg-ext.json'

def load_entries(data_dir, filename):
    """Load entries csv → dict keyed by 詞目id."""
    entries = {}
    with open(os.path.join(data_dir, filename), encoding='utf-8') as f:
        for row in csv.DictReader(f):
            entries[row[COL_ENTRY_ID]] = row
    return entries


def load_definitions(data_dir, filename):
    """Load definitions csv → dict keyed by 詞目id → list of definitions."""
    defs = defaultdict(list)
    with open(os.path.join(data_dir, filename), encoding='utf-8') as f:
        for row in csv.DictReader(f):
            defs[row[COL_ENTRY_ID]].append(row)
    return defs


def load_examples(data_dir, filename):
    """Load examples csv → dict keyed by (詞目id, 義項id) → list of examples."""
    examples = defaultdict(list)
    with open(os.path.join(data_dir, filename), encoding='utf-8') as f:
        for row in csv.DictReader(f):
            key = (row[COL_ENTRY_ID], row[COL_DEF_ID])
            examples[key].append(row)
    # Sort each group by 例句順序
    for key in examples:
        examples[key].sort(key=lambda r: int(r[COL_EXAMPLE_ORDER]))
    return examples


def format_example(row):
    """Format an example row into the interlinear annotation string."""
    hanji = row[COL_HANZI]
    lomaji = row[COL_TAILO]
    chinese = row.get(COL_HUAYU, '')
    return f'{IAA_BEGIN}{hanji}{IAA_SEP}{lomaji}{IAA_END}{chinese}'


def should_include(entry, variant):
    """Determine if an entry should appear in the dictionary output for the given output variant."""
    entry_type = entry[COL_ENTRY_TYPE]

    if variant == 'main':
        if entry_type in MAIN_TYPES:
            return True
        if entry_type == APPENDIX and PROVERB_MARKER in entry.get(COL_TYPE, ''):
            return True
        return False

    elif variant == 'ext':
        return entry_type in EXT_TYPES
    return False



def build_dict(data_dir, variant, mandarin=None):
    """Build the dictionary structure from CSVs."""
    entries = load_entries(data_dir, ENTRIES_CSV)
    definitions = load_definitions(data_dir, DEFINITIONS_CSV)
    examples = load_examples(data_dir, EXAMPLES_CSV)

    # Group entries by 漢字 for heteronym grouping
    # Multiple entries with same 漢字 but different readings are heteronyms
    by_title = defaultdict(list)
    for entry_id, entry in entries.items():
        if should_include(entry, variant):
            by_title[entry[COL_HANZI]].append((entry_id, entry))

    result = []
    for title in sorted(by_title.keys()):
        entry_group = by_title[title]
        # Sort heteronyms by id
        entry_group.sort(key=lambda x: int(x[0]))

        item = {'title': title, 'heteronyms': []}

        for entry_id, entry in entry_group:
            heteronym = {
                'id': entry_id,
                'trs': entry[COL_TAILO],
            }

            # Add reading type if present
            reading = entry.get(COL_READING)
            if reading:
                heteronym['reading'] = reading

            # Add audio information
            audio_file = entry.get(COL_AUDIO_FILE)
            if audio_file:
                heteronym['audio_file'] = audio_file

            # Build definitions
            entry_defs = definitions.get(entry_id, [])
            het_definitions = []
            for defn in entry_defs:
                d = {}
                pos = defn[COL_POS]
                if pos:
                    d['type'] = pos
                d['def'] = defn[COL_DEFINITION]

                # Add examples
                ex_key = (entry_id, defn[COL_DEF_ID])
                ex_rows = examples.get(ex_key, [])
                if ex_rows:
                    d['example'] = [format_example(r) for r in ex_rows]

                het_definitions.append(d)

            # For ext entries with no definitions, pull from Mandarin dict
            if variant == 'ext' and not het_definitions and title in mandarin:
                het_definitions = mandarin_definitions(mandarin[title])

            heteronym['definitions'] = het_definitions
            item['heteronyms'].append(heteronym)

        result.append(item)

    return result


def load_mandarin_dict(data_dir):
    path = os.path.join(data_dir, DICT_MANDARIN_JSON)
    if not os.path.exists(path):
        return {}

    print(f"  Loading Mandarin definitions from {DICT_MANDARIN_JSON}...")
    with open(path, encoding='utf-8') as f:
        data = json.load(f)

    by_title = {entry['title']: entry for entry in data}
    print(f"    {len(by_title)} Mandarin entries loaded")
    return by_title


def mandarin_definitions(mandarin_entry):
    het_definitions = []
    for heteronym in mandarin_entry.get('heteronyms', []):
        for defn in heteronym.get('definitions', []):
            d = {}
            if defn.get('type'):
                d['type'] = defn['type']
            if defn.get('def'):
                d['def'] = defn['def']
            else:
                continue
            het_definitions.append(d)
    return het_definitions


def main():
    data_dir = sys.argv[1] if len(sys.argv) > 1 else 'data'
    output_main = sys.argv[2] if len(sys.argv) > 2 else DICT_MAIN_JSON
    output_ext = sys.argv[3] if len(sys.argv) > 3 else DICT_EXT_JSON

    # For ext variant, load Mandarin definitions to fill empty entries
    mandarin = load_mandarin_dict(data_dir)

    for needed in [ENTRIES_CSV, DEFINITIONS_CSV, EXAMPLES_CSV]:
        path = os.path.join(data_dir, needed)
        if not os.path.exists(path):
            print(f"Error: {path} not found. Run convert_ods_csv.py first.", file=sys.stderr)
            sys.exit(1)

    print(f"Loading CSVs from {data_dir}/...")

    result_main = build_dict(data_dir, variant='main')
    print(f"  {output_main}: {len(result_main)} entries (主詞目 + 諺語)")
    write_json(result_main, output_main)

    result_ext = build_dict(data_dir, variant='ext', mandarin=mandarin)
    print(f"  {output_ext}: {len(result_ext)} entries (單字不成詞者 + 臺華共同詞)")
    write_json(result_ext, output_ext)

def write_json(data, output_file):
    # Write JSON with NFD normalization
    json_str = json.dumps(data, ensure_ascii=False, indent=2)
    json_str = unicodedata.normalize('NFD', json_str)
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(json_str)
    print(f"  Written to {output_file}")


if __name__ == '__main__':
    main()
