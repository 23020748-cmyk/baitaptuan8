"""Motion policy, independent of ROS and machine learning dependencies."""
from dataclasses import dataclass, fields
import math


EMOTIONS = {'happy', 'sad', 'neutral', 'angry', 'surprise', 'fear'}


@dataclass(frozen=True)
class Config:
    linear_speed: float = 0.10
    arc_angular_speed: float = 0.35
    reverse_speed: float = 0.08
    step_duration: float = 1.5
    spin_speed: float = 0.60
    confidence_threshold: float = 0.60
    stable_samples: int = 3
    stable_duration: float = 0.35
    observation_timeout: float = 1.5
    camera_timeout: float = 0.4
    odom_timeout: float = 0.5
    spin_tolerance: float = 0.03

    def __post_init__(self):
        for field in fields(self):
            value = getattr(self, field.name)
            if not math.isfinite(value) or value <= 0:
                raise ValueError(f'{field.name} must be finite and positive')
        if not 0 < self.confidence_threshold <= 1:
            raise ValueError('confidence_threshold must be in (0, 1]')
        if type(self.stable_samples) is not int:
            raise ValueError('stable_samples must be an integer')
        if self.spin_tolerance >= math.pi:
            raise ValueError('spin_tolerance must be less than pi')


class Controller:
    def __init__(self, config=Config()):
        self.config = config
        self.active = None
        self.reason = 'waiting_for_face'
        self.candidate = None
        self.count = 0
        self.since = 0.0
        self.last_observation = None
        self.last_trigger = None
        self.started = 0.0
        self.odom_yaw = None
        self.odom_at = None
        self.spin_last_yaw = None
        self.rotation = 0.0

    def stop(self, reason):
        self.active = None
        self.candidate = None
        self.count = 0
        self.reason = reason
        # Preserve last_trigger: a dropped frame must not repeat a completed step.
        return 0.0, 0.0

    def observe(self, label, confidence, captured_at, now):
        c = self.config
        if (not all(math.isfinite(v) for v in (confidence, captured_at, now))
                or not 0 <= now - captured_at <= c.observation_timeout
                or (self.last_observation is not None
                    and captured_at <= self.last_observation)):
            self.stop('stale_or_invalid_result')
            return
        if (self.last_observation is not None
                and captured_at - self.last_observation > c.observation_timeout):
            self.stop('recognition_timeout')
        self.last_observation = captured_at
        if label not in EMOTIONS or not c.confidence_threshold <= confidence <= 1:
            self.stop('uncertain_or_no_face')
            return
        if label == 'neutral':
            self.last_trigger = None
            self.stop('neutral')
            return
        if label != self.candidate:
            self.stop('stabilizing')
            self.candidate, self.since, self.count = label, captured_at, 0
        self.count += 1
        if self.count < c.stable_samples or captured_at - self.since < c.stable_duration:
            return
        if self.active == label:
            return
        if label in ('happy', 'sad'):
            self.last_trigger = None
        elif self.last_trigger == label:
            self.reason = 'action_done_change_expression'
            return
        else:
            self.last_trigger = label
        if label == 'surprise':
            if self.odom_at is None or now - self.odom_at > c.odom_timeout:
                self.stop('waiting_for_odometry_change_expression')
                return
            self.spin_last_yaw = self.odom_yaw
            self.rotation = 0.0
        self.active, self.started, self.reason = label, now, label

    def update_odometry(self, yaw, now):
        if not all(math.isfinite(v) for v in (yaw, now)):
            self.stop('invalid_odometry')
            return
        if self.odom_at is not None and now <= self.odom_at:
            self.stop('invalid_odometry_time')
            return
        if self.active == 'surprise':
            if now - self.odom_at > self.config.odom_timeout:
                self.stop('odometry_timeout')
            else:
                delta = yaw - self.spin_last_yaw
                self.rotation += math.atan2(math.sin(delta), math.cos(delta))
                self.spin_last_yaw = yaw
        self.odom_yaw, self.odom_at = yaw, now

    def tick(self, now, camera_fresh=True):
        c = self.config
        if not camera_fresh:
            return self.stop('camera_unavailable')
        if self.last_observation is None or now - self.last_observation > c.observation_timeout:
            return self.stop('recognition_timeout')
        if self.active is None:
            return 0.0, 0.0
        if self.active in ('angry', 'fear'):
            if now - self.started >= c.step_duration:
                return self.stop('action_done_change_expression')
            return (-c.reverse_speed if self.active == 'angry' else c.linear_speed), 0.0
        if self.active == 'happy':
            return c.linear_speed, c.arc_angular_speed
        if self.active == 'sad':
            return c.linear_speed, -c.arc_angular_speed
        if self.active == 'surprise':
            if self.odom_at is None or now - self.odom_at > c.odom_timeout:
                return self.stop('odometry_timeout')
            if self.rotation >= 2 * math.pi - c.spin_tolerance:
                return self.stop('action_done_change_expression')
            if now - self.started > 2 * math.pi / c.spin_speed * 2 + 2:
                return self.stop('spin_timeout')
            return 0.0, c.spin_speed
        return self.stop('unknown_action')
