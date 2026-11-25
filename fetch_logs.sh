#!/bin/bash
# Copy logs from the Pi back to the laptop for inspection.
set -euo pipefail

mkdir -p ./logs
rsync -avz pi@pi.local:~/robros-v2/logs/ ./logs/
