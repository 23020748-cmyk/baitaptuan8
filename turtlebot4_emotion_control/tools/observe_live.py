"""Read-only live diagnostics for facial-expression control."""
import argparse
from collections import Counter
import json
from pathlib import Path
import time

import rclpy
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from rclpy.qos import qos_profile_sensor_data
from std_msgs.msg import String

p = argparse.ArgumentParser()
p.add_argument('--seconds', type=float, default=12)
p.add_argument('--output', default='')
args = p.parse_args()
rclpy.init()
node = rclpy.create_node('emotion_live_observer')
labels, states = Counter(), Counter()
commands, odometry, ages, errors = [], [], [], Counter()
last_status = None

def status(message):
    global last_status
    last_status = json.loads(message.data)
    labels[last_status['emotion']] += 1
    states[last_status['state']] += 1
    if last_status['result_age'] is not None:
        ages.append(last_status['result_age'])
    for key in ('camera_error', 'model_error'):
        if last_status[key]:
            errors[last_status[key]] += 1

node.create_subscription(String, '/emotion_control/status', status, 10)
node.create_subscription(Twist, '/cmd_vel',
                         lambda msg: commands.append((msg.linear.x, msg.angular.z)), 10)
node.create_subscription(Odometry, '/odom', lambda msg: odometry.append(
    (msg.pose.pose.position.x, msg.pose.pose.position.y)), qos_profile_sensor_data)
started = time.monotonic()
while time.monotonic()-started < args.seconds:
    rclpy.spin_once(node, timeout_sec=0.1)
result = dict(seconds=round(time.monotonic()-started, 2), labels=dict(labels),
              states=dict(states), errors=dict(errors), commands=len(commands),
              nonzero_commands=sum(abs(v)+abs(w)>1e-6 for v,w in commands),
              last_command=commands[-1] if commands else None,
              odom_samples=len(odometry), first_odom=odometry[0] if odometry else None,
              last_odom=odometry[-1] if odometry else None,
              max_result_age=max(ages) if ages else None, last_status=last_status)
if args.output:
    Path(args.output).write_text(json.dumps(result, indent=2, ensure_ascii=False))
print(json.dumps(result, indent=2, ensure_ascii=False))
node.destroy_node()
rclpy.shutdown()
