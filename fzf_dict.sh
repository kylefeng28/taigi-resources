#!/bin/bash
./get_jq.sh \
  | jq -r '[.[0], .[1][:10], .[2][:20], .[3], .[4][:20]] | @tsv' \
  | column -s $'\t' -t \
  | fzf --reverse --header=$'Id\tCharacter\tTai-lo\tType\tDefinition'
