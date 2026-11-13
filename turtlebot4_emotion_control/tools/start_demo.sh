#!/usr/bin/env bash
set -eo pipefail
cd "$(dirname "$0")/../../.."
source /opt/ros/humble/setup.bash
source install/setup.bash
export ROS_DOMAIN_ID=47
export FASTDDS_BUILTIN_TRANSPORTS=UDPv4
export LIBGL_ALWAYS_SOFTWARE=1
runtime_dir="$PWD/reports/bai_tap_bieu_cam_khuon_mat/runtime"
mkdir -p "$runtime_dir"
start_process() {
  local name="$1"
  shift
  if [[ -f "$runtime_dir/$name.pid" ]] && kill -0 "$(cat "$runtime_dir/$name.pid")" 2>/dev/null; then
    echo "$name already running"
    return
  fi
  setsid "$@" >"$runtime_dir/$name.log" 2>&1 < /dev/null &
  echo "$!" >"$runtime_dir/$name.pid"
  echo "$name PID=$!"
}
start_process simulation ros2 launch turtlebot4_gesture_control gesture_sim.launch.py gui:=true
start_process emotion bash src/turtlebot4_emotion_control/tools/run.sh \
  camera_source:=file:///mnt/c/Users/khoa8/Downloads/turtlebot4_emotion_runtime/camera.frame
echo 'Demo domain: ROS_DOMAIN_ID=47. Allow the simulator controllers and model to initialize.'
