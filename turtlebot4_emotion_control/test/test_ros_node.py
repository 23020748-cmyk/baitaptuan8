"""Exercise DDS on unique test topics; never publish to the robot's /cmd_vel."""
import time
import uuid

import pytest

rclpy = pytest.importorskip('rclpy')
from geometry_msgs.msg import Twist
from rclpy.executors import SingleThreadedExecutor
from rclpy.node import Node
from rclpy.parameter import Parameter

from turtlebot4_emotion_control.emotion_control_node import EmotionControlNode
from turtlebot4_emotion_control.vision import Frame, Result


class FakeVision:
    def __init__(self):
        self.seq = 0
        self.frame = None
        self.result = None

    def start(self):
        pass

    def advance(self, label, infer=True):
        self.seq += 1
        now = time.monotonic()
        self.frame = Frame(self.seq, now, None)
        if infer:
            self.result = Result(self.seq, now, label, 0.95)

    def snapshot(self):
        return self.frame, self.result, '', ''

    def close(self):
        pass


def test_ros_motion_watchdogs_neutral_and_shutdown():
    rclpy.init()
    executor = SingleThreadedExecutor()
    vision = FakeVision()
    prefix = '/emotion_test_' + uuid.uuid4().hex
    node = EmotionControlNode(vision=vision, parameter_overrides=[
        Parameter('show_window', value=False),
        Parameter('cmd_vel_topic', value=prefix + '/cmd_vel'),
        Parameter('odom_topic', value=prefix + '/odom'),
        Parameter('stable_duration', value=0.05),
        Parameter('camera_timeout', value=0.2),
        Parameter('observation_timeout', value=0.3),
    ])
    observer = Node('emotion_test_observer_' + uuid.uuid4().hex)
    received = []
    subscription = observer.create_subscription(
        Twist, prefix + '/cmd_vel',
        lambda msg: received.append((msg.linear.x, msg.angular.z)), 10)
    executor.add_node(node)
    executor.add_node(observer)

    def spin_for(seconds, label=None, infer=True):
        until = time.monotonic() + seconds
        while time.monotonic() < until:
            if label:
                vision.advance(label, infer=infer)
            executor.spin_once(timeout_sec=0.01)

    try:
        # Wait for actual DDS discovery rather than assuming immediate delivery.
        deadline = time.monotonic() + 3
        while node.cmd.get_subscription_count() == 0 and time.monotonic() < deadline:
            executor.spin_once(timeout_sec=0.01)
        assert node.cmd.get_subscription_count() > 0
        spin_for(0.35, 'happy')
        assert received[-1] == pytest.approx((0.1, 0.35))

        # Camera is still delivering, but the model has stalled.
        spin_for(0.4, 'happy', infer=False)
        assert received[-1] == (0.0, 0.0)
        assert node.engine.reason == 'recognition_timeout'

        spin_for(0.35, 'sad')
        assert received[-1] == pytest.approx((0.1, -0.35))
        # Camera worker has stalled; no new frames or inference arrive.
        spin_for(0.25)
        assert received[-1] == (0.0, 0.0)

        spin_for(0.35, 'happy')
        spin_for(0.1, 'neutral')
        assert received[-1] == (0.0, 0.0)
        assert node.engine.reason == 'neutral'

        spin_for(0.35, 'happy')
        node.safe_stop()
        executor.remove_node(node)
        spin_for(0.1)
        assert received[-1] == (0.0, 0.0)
    finally:
        node.close()
        executor.shutdown()
        node.destroy_node()
        observer.destroy_node()
        rclpy.shutdown()
