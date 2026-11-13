#!/usr/bin/env bash
set -eo pipefail
export EMOTION_LAUNCH_FILE=emotion_demo.launch.py
export LP_NUM_THREADS=1
exec bash "$(dirname "$0")/run.sh" "$@"
