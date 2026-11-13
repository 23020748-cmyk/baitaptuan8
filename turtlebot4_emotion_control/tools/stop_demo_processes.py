"""Stop only the dedicated emotion-demo ROS domain, including orphan processes."""
import os
from pathlib import Path
import signal
import time

domain = ('ROS_DOMAIN_ID='+os.environ.get('ROS_DOMAIN_ID', '47')).encode()
targets = {}
for item in Path('/proc').iterdir():
    if not item.name.isdecimal() or int(item.name) == os.getpid():
        continue
    try:
        command = (item/'cmdline').read_bytes().replace(b'\0', b' ').decode()
        environment = (item/'environ').read_bytes().split(b'\0')
    except (OSError, UnicodeError):
        continue
    if domain not in environment:
        continue
    if any(token in command for token in (
        'ros2 launch turtlebot4_emotion_control',
        'ros2 launch turtlebot4_gesture_control gesture_sim.launch.py',
        'emotion_control_node', 'ign gazebo',
        '/opt/ros/humble/lib/ros_gz_bridge/', '/opt/ros/humble/lib/robot_state_publisher/',
        '/opt/ros/humble/lib/tf2_ros/', '/opt/ros/humble/lib/controller_manager/spawner',
    )):
        targets[int(item.name)] = command
for process in targets:
    try:
        os.kill(process, signal.SIGINT)
    except ProcessLookupError:
        pass
time.sleep(1)
for process in targets:
    try:
        if Path(f'/proc/{process}/stat').read_text().split()[2] != 'Z':
            os.kill(process, signal.SIGTERM)
    except (OSError, ProcessLookupError):
        pass
time.sleep(0.5)
for process in targets:
    try:
        if Path(f'/proc/{process}/stat').read_text().split()[2] != 'Z':
            os.kill(process, signal.SIGKILL)
    except (OSError, ProcessLookupError):
        pass
print(f'Stopped {len(targets)} old demo processes')
