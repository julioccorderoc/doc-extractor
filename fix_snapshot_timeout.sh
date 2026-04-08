#!/bin/bash
export SKIP_EXISTING_SNAPSHOTS=1

# Process one file at a time using bash loop to avoid timeout constraints
for file in test_docs/*; do
  if [[ "$file" == *.pdf ]] || [[ "$file" == *.png ]] || [[ "$file" == *.jpg ]] || [[ "$file" == *.jpeg ]] || [[ "$file" == *.webp ]]; then
    filename=$(basename "$file")
    stem="${filename%.*}"
    if [ ! -f "evals/snapshots/datalab/$stem.json" ]; then
      echo "Processing $filename..."
      uv run python evals/snapshot.py --engine datalab approve "$file"
    fi
  fi
done
