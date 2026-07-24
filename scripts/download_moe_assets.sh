#!/bin/bash

set -euo pipefail

BASE_URL="https://sutian.moe.edu.tw/media/senn"

DICTIONARY="ods/kautian.ods"
AUDIO_ENTRIES_MP3="sutiau-mp3.zip"
AUDIO_EXAMPLES_MP="leku-mp3.zip"

OUTPUT_DIR="./data"

mkdir -p $OUTPUT_DIR

fetch() {
  curl -LO "$BASE_URL/$1" --output-dir $OUTPUT_DIR --skip-existing
}

fetch $DICTIONARY
fetch $AUDIO_ENTRIES_MP3
fetch $AUDIO_EXAMPLES_MP

