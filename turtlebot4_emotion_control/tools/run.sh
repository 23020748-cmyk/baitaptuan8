#!/usr/bin/env bash
set -eo pipefail
cd "$(dirname "$0")/../../.."
source /opt/ros/humble/setup.bash
source install/setup.bash
if [[ ! -x .venv-emotion/bin/python ]]; then
  echo 'Run: bash src/turtlebot4_emotion_control/tools/install_vision.sh' >&2
  exit 2
fi
export PYTHONNOUSERSITE=1
export FASTDDS_BUILTIN_TRANSPORTS=UDPv4
export ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-47}"
export TF_CPP_MIN_LOG_LEVEL=3
export TF_NUM_INTRAOP_THREADS=2
export TF_NUM_INTEROP_THREADS=1
export OMP_NUM_THREADS=2
export OPENBLAS_NUM_THREADS=1
export PYTHONPATH="$PWD/.venv-emotion/lib/python3.10/site-packages:${PYTHONPATH:-}"
exec ros2 launch turtlebot4_emotion_control "${EMOTION_LAUNCH_FILE:-emotion_control.launch.py}" "$@"
