#!/usr/bin/env python3

import csv
import json
import re
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path


def normalize_unicode(text: str) -> str:
    """Normalize Unicode to NFC for consistent comparison."""
    return unicodedata.normalize('NFC', text)


def normalize_pronunciation(text: str) -> str:
    # Replace single hyphen (-) with space, but not double hyphen (--)
    return re.sub(r'(?<!-)-(?!-)', ' ', text)

def load_dictionaries(dict_files: list[Path]) -> dict[str, list]:
    dictionary = defaultdict(list)
    
    for file_path in dict_files:
        if not file_path.exists():
            print(f"Warning: Dictionary file not found: {file_path}", file=sys.stderr)
            continue
            
        with open(file_path, 'r', encoding='utf-8') as f:
            entries = json.load(f)
            for entry in entries:
                title = normalize_unicode(entry.get('title', ''))
                if title:
                    dictionary[title] += entry.get('heteronyms', [])
    
    return dictionary


def extract_pronunciations(heteronyms: list) -> set[str]:
    pronunciations = set()
    for heteronym in heteronyms:
        trs = normalize_unicode(heteronym.get('trs', '').strip())
        if trs:
            for variant in trs.split('/'):
                pronunciations.add(normalize_pronunciation(variant))
    return pronunciations


def validate_vocabulary(csv_path: Path, dictionary: dict[str, list]) -> tuple:
    """
    Validate CSV entries against dictionary.
    
    Returns: (valid_entries, mismatches, missing_entries)
    """
    valid = []
    mismatches = []
    missing = []
    
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row_num, row in enumerate(reader, start=2):  # start=2 because header is row 1
            taiwanese = normalize_unicode(row.get('Taiwanese', '').strip())
            tailo = normalize_unicode(row.get('Tai-lo', '').strip())
            
            if not taiwanese or not tailo:
                continue
            
            # Check if entry exists in dictionary
            if taiwanese not in dictionary:
                missing.append({
                    'row': row_num,
                    'entry': taiwanese,
                    'tailo': tailo,
                    'reason': 'Entry not found in dictionary'
                })
                continue
            
            # Check if Tai-lo matches any pronunciation
            dict_pronunciations = extract_pronunciations(dictionary[taiwanese])
            
            normalized_tailo = normalize_pronunciation(tailo)

            if normalized_tailo in dict_pronunciations:
                valid.append({
                    'row': row_num,
                    'entry': taiwanese,
                    'tailo': tailo
                })
            else:
                mismatches.append({
                    'row': row_num,
                    'entry': taiwanese,
                    'csv_tailo': tailo,
                    'dict_pronunciations': sorted(dict_pronunciations),
                    'reason': "Tai-lo mismatch"
                })
    
    return valid, mismatches, missing


def main():
    # Set up paths
    script_dir = Path(__file__).parent
    csv_path = script_dir / 'taigi_vocab.csv'
    dict_files = [
        script_dir.parent / 'dict-twblg.json',
        script_dir.parent / 'dict-twblg-ext.json'
    ]
    
    # Validate paths
    if not csv_path.exists():
        print(f"Error: CSV file not found: {csv_path}", file=sys.stderr)
        sys.exit(1)
    
    print("Loading dictionaries...")
    dictionary = load_dictionaries(dict_files)
    print(f"Loaded {len(dictionary)} entries from dictionaries\n")
    
    print(f"Validating {csv_path}...")
    valid, mismatches, missing = validate_vocabulary(csv_path, dictionary)
    
    # Print results
    print(f"\n{'='*60}")
    print("VALIDATION RESULTS")
    print(f"{'='*60}")
    print(f"✓ Valid entries: {len(valid)}")
    print(f"✗ Mismatches: {len(mismatches)}")
    print(f"✗ Missing from dictionary: {len(missing)}")
    print(f"{'='*60}\n")
    
    LIMIT = 20
    if mismatches:
        print("MISMATCHES (Tai-lo doesn't match dictionary):")
        print(f"{'-'*60}")
        for item in mismatches[:LIMIT]:
            print(f"Row {item['row']}: {item['entry']}")
            print(f"  CSV Tai-lo: {item['csv_tailo']}")
            print(f"  Dictionary pronunciations: {', '.join(item['dict_pronunciations'])}")
        if len(mismatches) > LIMIT:
            print(f"  ... and {len(mismatches) - LIMIT} more")
        print()
    
    if missing:
        print("MISSING FROM DICTIONARY:")
        print(f"{'-'*60}")
        for item in missing[:LIMIT]:
            print(f"Row {item['row']}: {item['entry']} ({item['tailo']})")
        if len(missing) > LIMIT:
            print(f"  ... and {len(missing) - LIMIT} more")
        print()
    
    # Return non-zero exit code if there are issues
    if mismatches or missing:
        sys.exit(1)
    else:
        print("All entries validated successfully!")
        sys.exit(0)


if __name__ == '__main__':
    main()
