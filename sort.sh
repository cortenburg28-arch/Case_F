#!/usr/bin/env bash
# Sort the students from the CSVs in data/ into output/Project_Pomfret_Rosters.xlsx
cd "$(dirname "$0")" && python3 -m sorter run --data data "$@"
