"""ROS 2 node: webcam display, emotion status, odometry and 20 Hz cmd_vel."""
from dataclasses import fields
from collections import deque
import json
import math
import signal
import time

import rclpy
from rclpy.clock import Clock, ClockType
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data, QoSProfile
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from std_msgs.msg import String

from .behavior import Config, Controller
from .vision import Vision


class EmotionControlNode(Node):
    def __init__(self, vision=None, **kwargs):
        super().__init__('emotion_control', **kwargs)
        defaults = Config()
        config = Config(**{f.name: self.declare_parameter(f.name, getattr(defaults, f.name)).value
                           for f in fields(defaults)})
        self.engine = Controller(config)
        self.robot_pose = None
        self.trail = deque(maxlen=500)
        self.show_window = self.declare_parameter('show_window', True).value
        source = self.declare_parameter('camera_source', '0').value
        inference_hz = self.declare_parameter('inference_hz', 3.0).value
        backend = self.declare_parameter('backend', 'opencv').value
        model_dir = self.declare_parameter('model_dir', '').value
        cmd_topic = self.declare_parameter('cmd_vel_topic', '/cmd_vel').value
        odom_topic = self.declare_parameter('odom_topic', '/odom').value
        self.cmd = self.create_publisher(Twist, cmd_topic, QoSProfile(depth=1))
        self.status_pub = self.create_publisher(String, '/emotion_control/status', 1)
        self.odom_sub = self.create_subscription(
            Odometry, odom_topic, self.on_odometry, qos_profile_sensor_data)
        self.vision = vision if vision is not None else Vision(
            source, inference_hz, backend=backend, model_dir=model_dir)
        self.result_seq = None
        self.last_tick = time.monotonic()
        self.last_report = 0.0
        self.last_reason = None
        self.velocity = (0.0, 0.0)
        self.exit_requested = False
        self.vision.start()
        self.timer = self.create_timer(0.05, self.on_timer,
                                      clock=Clock(clock_type=ClockType.STEADY_TIME))
        self.get_logger().info(f'Backend={backend}; camera={source}; velocity={cmd_topic}; odometry={odom_topic}')

    def on_odometry(self, message):
        q = message.pose.pose.orientation
        norm = math.sqrt(q.x*q.x + q.y*q.y + q.z*q.z + q.w*q.w)
        if not math.isfinite(norm) or norm < 1e-6:
            self.engine.stop('invalid_odometry')
            return
        x, y, z, w = q.x/norm, q.y/norm, q.z/norm, q.w/norm
        yaw = math.atan2(2*(w*z + x*y), 1-2*(y*y + z*z))
        position = message.pose.pose.position
        if not all(math.isfinite(v) for v in (position.x, position.y)):
            self.engine.stop('invalid_odometry')
            return
        self.robot_pose = (position.x, position.y, yaw)
        self.trail.append((position.x, position.y))
        self.engine.update_odometry(yaw, time.monotonic())

    def publish_velocity(self, velocity):
        self.velocity = velocity
        message = Twist()
        message.linear.x, message.angular.z = map(float, velocity)
        self.cmd.publish(message)

    def on_timer(self):
        try:
            now = time.monotonic()
            frame, result, camera_error, model_error = self.vision.snapshot()
            fresh = frame is not None and 0 <= now-frame.captured_at <= self.engine.config.camera_timeout
            if now-self.last_tick > 0.3:
                self.engine.stop('control_timer_delayed')
                # Discard a pending result after a scheduler stall; stabilize anew.
                self.result_seq = result.seq if result else self.result_seq
                velocity = (0.0, 0.0)
            elif not fresh or camera_error or model_error:
                velocity = self.engine.stop('camera_or_model_unavailable')
                self.result_seq = result.seq if result else self.result_seq
            else:
                if result is not None and result.seq != self.result_seq:
                    self.result_seq = result.seq
                    self.engine.observe(result.label, result.confidence, result.captured_at, now)
                velocity = self.engine.tick(now, camera_fresh=fresh)
            self.last_tick = now
            self.publish_velocity(velocity)
            if self.engine.reason != self.last_reason:
                self.last_reason = self.engine.reason
                self.get_logger().info(self.engine.reason)
            if now-self.last_report >= 0.2:
                self.last_report = now
                self.status_pub.publish(String(data=json.dumps({
                    'emotion': result.label if result else 'unknown',
                    'confidence': result.confidence if result else 0.0,
                    'result_age': now-result.captured_at if result else None,
                    'action': self.engine.active,
                    'state': self.engine.reason,
                    'linear_x': velocity[0], 'angular_z': velocity[1],
                    'rotation_rad': self.engine.rotation,
                    'camera_error': camera_error, 'model_error': model_error,
                    'detail': result.detail if result else '',
                })))
        except Exception:
            self.safe_stop()
            raise

    def display(self):
        if not self.show_window:
            return
        import cv2
        import numpy as np
        frame, result, camera_error, model_error = self.vision.snapshot()
        now = time.monotonic()
        image = frame.image.copy() if frame else np.zeros((480, 640, 3), np.uint8)
        fresh_result = result and 0 <= now-result.captured_at <= self.engine.config.observation_timeout
        label = f'{result.label.upper()} {result.confidence:.0%}' if fresh_result else 'UNKNOWN / STALE'
        if fresh_result:
            for x, y, w, h in result.boxes:
                cv2.rectangle(image, (x, y), (x+w, y+h), (0, 220, 0), 2)
        lines = [label, f'State: {self.engine.reason}',
                 f'v={self.velocity[0]:.2f} m/s  w={self.velocity[1]:.2f} rad/s',
                 'Q / ESC: stop and exit']
        error = camera_error or model_error or (result.detail if fresh_result else '')
        if error:
            lines.append(error[:85])
        for index, line in enumerate(lines):
            point = (10, 25+25*index)
            cv2.putText(image, line, point, cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 0), 4)
            cv2.putText(image, line, point, cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 255), 1)
        panel = np.full((image.shape[0], 320, 3), 28, dtype=np.uint8)
        center = (160, image.shape[0]//2+20)
        scale = 75
        for offset in range(-2, 3):
            cv2.line(panel, (center[0]+offset*scale, 70),
                     (center[0]+offset*scale, image.shape[0]-30), (55, 55, 55), 1)
            cv2.line(panel, (10, center[1]+offset*scale),
                     (310, center[1]+offset*scale), (55, 55, 55), 1)
        cv2.putText(panel, 'GAZEBO / ODOMETRY', (12, 26),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.58, (255, 230, 140), 1)
        def pixel(x, y):
            return (round(center[0]+scale*max(-10, min(10, x))),
                    round(center[1]-scale*max(-10, min(10, y))))
        if self.robot_pose is not None:
            x, y, yaw = self.robot_pose
            if len(self.trail) > 1:
                points = np.array([pixel(a, b) for a,b in self.trail], dtype=np.int32)
                cv2.polylines(panel, [points], False, (90, 190, 100), 2)
            triangle = np.array([pixel(x+0.16*math.cos(yaw+angle), y+0.16*math.sin(yaw+angle))
                                 for angle in (0, 2.45, -2.45)], dtype=np.int32)
            cv2.fillPoly(panel, [triangle], (0, 230, 255))
            cv2.putText(panel, f'x={x:.2f} m  y={y:.2f} m', (12, 52),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (230, 230, 230), 1)
            cv2.putText(panel, f'yaw={math.degrees(yaw):.1f} deg', (12, image.shape[0]-12),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (230, 230, 230), 1)
        else:
            cv2.putText(panel, 'Waiting for /odom', (24, center[1]),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 170, 255), 1)
        image = np.hstack((image, panel))
        cv2.imshow('TurtleBot - Facial Expression Control', image)
        key = cv2.waitKey(1) & 0xff
        if key in (27, ord('q'), ord('Q')) or cv2.getWindowProperty(
                'TurtleBot - Facial Expression Control', cv2.WND_PROP_VISIBLE) < 1:
            self.exit_requested = True

    def safe_stop(self):
        self.engine.stop('shutdown')
        for _ in range(5):
            self.publish_velocity((0.0, 0.0))

    def close(self):
        self.safe_stop()
        self.vision.close()
        if self.show_window:
            import cv2
            cv2.destroyAllWindows()


def main(args=None):
    rclpy.init(args=args, signal_handler_options=rclpy.signals.SignalHandlerOptions.NO)
    node = None

    def interrupted(signum, frame):
        raise KeyboardInterrupt

    signal.signal(signal.SIGINT, interrupted)
    signal.signal(signal.SIGTERM, interrupted)
    try:
        node = EmotionControlNode()
        while rclpy.ok() and not node.exit_requested:
            rclpy.spin_once(node, timeout_sec=0.02)
            node.display()
    except KeyboardInterrupt:
        pass
    finally:
        try:
            if node is not None:
                node.close()
        finally:
            if node is not None:
                node.destroy_node()
            if rclpy.ok():
                rclpy.shutdown()
