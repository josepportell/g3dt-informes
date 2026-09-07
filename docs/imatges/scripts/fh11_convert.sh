#!/bin/bash
S=/tmp/claude-1000/-home-josep-projects-claudecode-job-clients-g3dt-prod/a25f4f53-8ad8-4eaf-b120-f6cbb34cfb6d/scratchpad
cd /home/josep/g3dt-e2e/projectes
for p in "4001612 BELL-LLOC" "3001631 RUBI" "4001607 LINYOLA" "3001621 CASTELLAR DEL VALLES" "4001670 ALCOLETGE" "4001671 VILANOVA DE SEGRIA" "4001679 ANCILES"; do
  out="$S/fh11/$p"; mkdir -p "$out"
  find "$p" -iname '*.fh11' -not -path '*/validation/*' -print0 | while IFS= read -r -d '' f; do
    t0=$(date +%s)
    soffice --headless --convert-to pdf --outdir "$out" "$f" >/dev/null 2>&1
    echo "$(( $(date +%s) - t0 ))s  $f" >> "$S/fh11/convert.log"
  done
done
echo DONE >> "$S/fh11/convert.log"
