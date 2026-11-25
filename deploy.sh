#!/bin/bash
# Copy this folder to the Pi. Run from the laptop, then SSH in to test.
set -euo pipefail

rsync -avz \
  --exclude ".git" \
  --exclude "logs/" \
  --exclude "__pycache__/" \
  --exclude "*.pyc" \
  ./ pi@pi.local:~/robros-v2/
