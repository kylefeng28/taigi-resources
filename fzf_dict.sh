#!/bin/bash
cat dict-twblg.json dict-twblg-ext.json \
  | jq -r '.[] | .title as $t | .heteronyms[] | .id as $id | .trs as $r | .definitions[] | [$id, $t, $r[:20], .type, .def[:20]] | @tsv' \
  | column -s $'\t' -t | fzf --reverse --header=$'Id\tCharacter\tTai-lo\tType\tDefinition'
