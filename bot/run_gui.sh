#!/bin/bash
set -e

cd "$(dirname "$0")"

echo "Starting GUI at $(date)"
echo "Using Python: $(uv run which python)"
caffeinate -dims uv run python gui_app.py
