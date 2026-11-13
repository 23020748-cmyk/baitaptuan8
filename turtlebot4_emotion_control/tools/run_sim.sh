#!/usr/bin/env bash
set -eo pipefail
cd "$(dirname "$0")/../../.."
source /opt/ros/humble/setup.bash
source install/setup.bash
export ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-47}"
export FASTDDS_BUILTIN_TRANSPORTS=UDPv4
export LIBGL_ALWAYS_SOFTWARE=1
export LP_NUM_THREADS=1
export OMP_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
exec ros2 launch turtlebot4_gesture_control gesture_sim.launch.py gui:="${1:-true}"
