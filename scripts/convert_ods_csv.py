#!/usr/bin/env python3

import csv
import os
import re
import sys
import zipfile
import xml.etree.ElementTree as ET

# --- ODS Parsing ---

TABLE_NS = '{urn:oasis:names:tc:opendocument:xmlns:table:1.0}'
OFFICE_NS = '{urn:oasis:names:tc:opendocument:xmlns:office:1.0}'
TEXT_NS = '{urn:oasis:names:tc:opendocument:xmlns:text:1.0}'
NS = {
    'table': TABLE_NS[1:-1],
    'office': OFFICE_NS[1:-1],
    'text': TEXT_NS[1:-1],
}


# --- Sheet names ---
ENTRIES_SHEET = '詞目'
DEFINITIONS_SHEET = '義項'
EXAMPLES_SHEET = '例句'


# --- Output CSV names ---
ENTRIES_CSV = "sutiau.csv"  # 詞條
DEFINITIONS_CSV = "gihang.csv"  # 義項
EXAMPLES_CSV = "lehku.csv"  # 列句


# --- Column names ---
COL_ENTRY_ID = '詞目id'
COL_ENTRY_TYPE = '詞目類型'
COL_HANZI = '漢字'
COL_TAILO = '羅馬字'
COL_HUAYU = '華語'
COL_READING = '文白屬性'
COL_TYPE = '分類'
COL_AUDIO_FILE = '羅馬字音檔檔名'

COL_DEF_ID = '義項id'
COL_POS = '詞性'
COL_DEFINITION = '解說'
COL_EXAMPLE_ORDER = '例句順序'
COL_EXAMPLE_AUDIO_FILE = '音檔檔名'

def parse_ods(ods_path, sheet_names=None):
    """Parse an ODS file. Returns {sheet_name: [rows]} (header + data)."""
    with zipfile.ZipFile(ods_path, 'r') as z:
        with z.open('content.xml') as f:
            tree = ET.parse(f)
            root = tree.getroot()

    result = {}
    for table in root.findall('.//table:table', NS):
        name = table.get(f'{TABLE_NS}name')
        if sheet_names and name not in sheet_names:
            continue
        result[name] = _parse_table(table)
    return result


def _parse_table(table):
    rows = []
    for row_el in table.findall('table:table-row', NS):
        repeat = row_el.get(f'{TABLE_NS}number-rows-repeated')
        row_repeat = int(repeat) if repeat else 1
        row = _parse_row(row_el)
        if row_repeat > 100 and all(c == '' for c in row):
            continue
        for _ in range(row_repeat):
            rows.append(row)
    return rows


def _parse_row(row_el):
    cells = []
    for cell in row_el.findall('table:table-cell', NS):
        repeat = cell.get(f'{TABLE_NS}number-columns-repeated')
        col_repeat = int(repeat) if repeat else 1
        value = cell.get(f'{OFFICE_NS}value')
        if value is None:
            value = _extract_text(cell)
        if col_repeat > 50 and not value:
            continue
        for _ in range(col_repeat):
            cells.append(value or '')
    return cells


def _extract_text(cell):
    texts = []
    for p in cell.findall(f'.//text:p', NS):
        texts.append(_collect_text(p))
    return '\n'.join(texts)


def _collect_text(element):
    result = []
    if element.text:
        result.append(element.text)
    for child in element:
        result.append(_collect_text(child))
        if child.tail:
            result.append(child.tail)
    return ''.join(result)


# --- Marker handling ---

MARKER_TO_READING = {
    '文': '文',
    '白': '白',
    '俗': '俗',
    '替': '替',
}


def strip_markers(hanji, lomaji):
    """Strip 文白俗替 markers. Returns (clean_hanji, clean_lomaji, reading_type)."""
    reading_type = ''

    # 【替】 appears in 漢字
    if '【替】' in hanji:
        hanji = hanji.replace('【替】', '')
        reading_type = '替'

    # 【文】【白】【俗】 appear in 羅馬字
    for marker, reading in MARKER_TO_READING.items():
        tag = f'【{marker}】'
        if tag in lomaji:
            lomaji = lomaji.replace(tag, '')
            reading_type = reading
            break

    return hanji, lomaji, reading_type


# --- Main conversion ---

def convert(ods_path, output_dir):
    print(f"Reading {ods_path}...")
    sheets = parse_ods(ods_path, sheet_names=[ENTRIES_SHEET, DEFINITIONS_SHEET, EXAMPLES_SHEET])
    print(f"  Sheets loaded: {list(sheets.keys())}")

    os.makedirs(output_dir, exist_ok=True)

    # --- Entries (sutiau) --
    entries_rows = sheets[ENTRIES_SHEET][1:]  # skip header
    entries_csv = os.path.join(output_dir, ENTRIES_CSV)
    with open(entries_csv, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow([COL_ENTRY_ID, COL_ENTRY_TYPE, COL_HANZI, COL_TAILO, COL_READING, COL_TYPE, COL_AUDIO_FILE])
        count = 0
        for row in entries_rows:
            if len(row) < 4:
                continue
            entry_id = row[0]
            entry_type = row[1]
            hanji_raw = row[2]
            lomaji_raw = row[3]
            category = row[4] if len(row) > 4 else ''
            audio = row[5] if len(row) > 5 else ''

            hanji, lomaji, reading_type = strip_markers(hanji_raw, lomaji_raw)
            w.writerow([entry_id, entry_type, hanji, lomaji, reading_type, category, audio])
            count += 1
    print(f"  {entries_csv}: {count} entries")

    # --- Definitions (gihang) ---
    defs_rows = sheets[DEFINITIONS_SHEET][1:]
    definitions_path = os.path.join(output_dir, DEFINITIONS_CSV)
    with open(definitions_path, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow([COL_ENTRY_ID, COL_DEF_ID, COL_POS, COL_DEFINITION])
        count = 0
        for row in defs_rows:
            if len(row) < 4:
                continue
            w.writerow([row[0], row[1], row[2], row[3]])
            count += 1
    print(f"  {definitions_path}: {count} definitions")

    # --- Examples (lehku) ---
    examples_rows = sheets[EXAMPLES_SHEET][1:]
    examples_path = os.path.join(output_dir, EXAMPLES_CSV)
    with open(examples_path, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow([COL_ENTRY_ID, COL_DEF_ID, COL_EXAMPLE_ORDER, COL_HANZI, COL_TAILO, COL_HUAYU, COL_EXAMPLE_AUDIO_FILE])
        count = 0
        for row in examples_rows:
            if len(row) < 6:
                continue
            entry_id = row[0]
            def_id = row[1]
            order = row[2]
            hanji = row[3]
            lomaji = row[4]
            chinese = row[5]
            audio = row[6] if len(row) > 6 else ''
            w.writerow([entry_id, def_id, order, hanji, lomaji, chinese, audio])
            count += 1
    print(f"  {examples_path}: {count} examples")

    print("Done!")


if __name__ == '__main__':
    ods_path = sys.argv[1] if len(sys.argv) > 1 else 'data/kautian.ods'
    output_dir = sys.argv[2] if len(sys.argv) > 2 else 'data'

    if not os.path.exists(ods_path):
        print(f"Error: {ods_path} not found", file=sys.stderr)
        sys.exit(1)

    convert(ods_path, output_dir)
