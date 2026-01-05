#!/bin/bash
# Wrapper script to run the Telegram signal copier bot
# This script loads environment variables and runs with caffeinate

set -e

# Change to project directory
cd "$(dirname "$0")"

# Load environment variables from .env file
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi

# Create logs directory if needed
mkdir -p logs

# Run the bot with caffeinate to prevent sleep
# -d: prevent display sleep
# -i: prevent idle sleep
# -m: prevent disk sleep
# -s: prevent system sleep
echo "Starting bot at $(date)"
echo "Using Python: $(uv run which python)"
caffeinate -dims uv run python -m tania_signal_copier.bot

echo "Bot exited at $(date)"
