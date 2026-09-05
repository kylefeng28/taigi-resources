#!/bin/bash
cat taigi_vocab.csv | column -s, -t | fzf --reverse --header-lines=1
