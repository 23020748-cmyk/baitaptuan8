#!/usr/bin/env bash
set -eo pipefail
cd "$(dirname "$0")/../../.."
exec python3 src/turtlebot4_emotion_control/tools/stop_demo_processes.py
