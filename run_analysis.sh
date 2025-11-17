#!/bin/bash

# Timestamp for this run (used in report filenames)
ts=$(date '+%Y%m%d-%H%M%S')

# Input audio directory and output locations
audio_dir="examples/audio"
report_dir="reports"
json_dir="reports/json_results"

# Ensure output directories exist
mkdir -p "$report_dir"
mkdir -p "$json_dir"

# Run batch analysis
python main.py batch "$audio_dir" \
  --thresholds thresholds.yaml \
  --out "$report_dir/report-$ts.md" \
  --out-json "$json_dir/results-$ts.json" \
  --jobs 4

# Print locations of the generated reports
echo "Analysis complete. Reports generated:"
echo "Markdown report: $report_dir/report-$ts.md"
echo "JSON results: $json_dir/results-$ts.json"