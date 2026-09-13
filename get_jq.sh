#!/bin/bash
if [ "$#" -ge 1 ]; then
  SELECT=" | select(\$t == \"$1\") | "
else
  SELECT="|"
fi

cat dict-twblg.json dict-twblg-ext.json \
  | jq -c -r '.[] | .title as $t | .heteronyms[] | .id as $id | .trs as $r | .definitions[]'"$SELECT"'[$id, $t, $r, .type, .def]'
