import math

import pytest

from turtlebot4_emotion_control.behavior import Config, Controller


def stabilize(engine, label, start=10.0, odom=False):
    for i in range(3):
        now = start + i * 0.25
        if odom:
            engine.update_odometry(0.0, now)
        engine.observe(label, 0.95, now, now)
    return now


@pytest.mark.parametrize('label,linear,angular', [
    ('happy', 0.1, 0.35), ('sad', 0.1, -0.35),
    ('angry', -0.08, 0.0), ('fear', 0.1, 0.0),
    ('neutral', 0.0, 0.0), ('surprise', 0.0, 0.6),
])
def test_six_required_actions(label, linear, angular):
    engine = Controller()
    now = stabilize(engine, label, odom=True)
    assert engine.tick(now) == pytest.approx((linear, angular))


def test_new_expression_stops_previous_action_before_debounce():
    engine = Controller()
    now = stabilize(engine, 'happy')
    engine.observe('sad', 0.9, now+0.1, now+0.1)
    assert engine.tick(now+0.1) == (0.0, 0.0)
    assert engine.reason == 'stabilizing'


@pytest.mark.parametrize('label,confidence', [('unknown', 0.9), ('disgust', 0.9),
                                            ('happy', 0.2), ('happy', float('nan'))])
def test_invalid_or_uncertain_input_stops_immediately(label, confidence):
    engine = Controller()
    now = stabilize(engine, 'happy')
    engine.observe(label, confidence, now+0.1, now+0.1)
    assert engine.tick(now+0.1) == (0.0, 0.0)


def test_neutral_stops_without_debounce():
    engine = Controller()
    now = stabilize(engine, 'happy')
    engine.observe('neutral', 0.95, now+0.1, now+0.1)
    assert engine.tick(now+0.1) == (0.0, 0.0)
    assert engine.reason == 'neutral'


def test_motion_requires_three_distinct_stable_results():
    engine = Controller()
    engine.observe('happy', 0.95, 10.0, 10.0)
    assert engine.tick(10.0) == (0.0, 0.0)
    engine.observe('happy', 0.95, 10.25, 10.25)
    assert engine.tick(10.25) == (0.0, 0.0)
    engine.observe('happy', 0.95, 10.25, 10.26)
    assert engine.tick(10.26) == (0.0, 0.0)
    assert engine.reason == 'stale_or_invalid_result'


def test_camera_or_inference_stall_stops_motion():
    engine = Controller()
    now = stabilize(engine, 'happy')
    assert engine.tick(now+0.05, camera_fresh=False) == (0.0, 0.0)
    now = stabilize(engine, 'happy', 11.0)
    assert engine.tick(now+1.51) == (0.0, 0.0)


def test_old_inference_result_cannot_restart_robot():
    engine = Controller()
    engine.observe('happy', 0.95, 10.0, 12.0)
    assert engine.tick(12.0) == (0.0, 0.0)
    assert engine.active is None


@pytest.mark.parametrize('label', ['angry', 'fear'])
def test_step_finishes_once_and_requires_new_expression(label):
    engine = Controller()
    now = stabilize(engine, label)
    for i in range(1, 30):
        t = now+i*0.1
        engine.observe(label, 0.95, t, t)
        velocity = engine.tick(t)
        if t >= now+engine.config.step_duration:
            assert velocity == (0.0, 0.0)
    # A camera interruption must not rearm the same step.
    engine.tick(13.5, camera_fresh=False)
    t = stabilize(engine, label, 14.0)
    assert engine.tick(t) == (0.0, 0.0)
    engine.observe('neutral', 0.95, 14.6, 14.6)
    t = stabilize(engine, label, 14.7)
    assert engine.tick(t)[0] != 0.0


def test_surprise_waits_for_odometry():
    engine = Controller()
    now = stabilize(engine, 'surprise')
    assert engine.tick(now) == (0.0, 0.0)
    assert 'odometry' in engine.reason


def test_full_rotation_uses_unwrapped_odometry_and_does_not_repeat():
    engine = Controller()
    now = stabilize(engine, 'surprise', odom=True)
    # Real feedback crosses +pi -> -pi. Keep fresh face results throughout.
    for i in range(1, 65):
        t = now+i*0.1
        yaw = math.atan2(math.sin(i*0.1), math.cos(i*0.1))
        engine.update_odometry(yaw, t)
        engine.observe('surprise', 0.95, t, t)
        velocity = engine.tick(t)
        if i < 63:
            assert velocity == (0.0, 0.6)
        else:
            assert velocity == (0.0, 0.0)
    assert engine.rotation >= 2*math.pi-engine.config.spin_tolerance


def test_odometry_loss_stops_rotation():
    engine = Controller()
    now = stabilize(engine, 'surprise', odom=True)
    engine.observe('surprise', 0.95, now+0.6, now+0.6)
    assert engine.tick(now+0.6) == (0.0, 0.0)
    assert engine.reason == 'odometry_timeout'


@pytest.mark.parametrize('overrides', [dict(linear_speed=-0.1),
                                     dict(confidence_threshold=1.1),
                                     dict(stable_samples=2.5),
                                     dict(observation_timeout=float('nan'))])
def test_invalid_configuration_fails_early(overrides):
    with pytest.raises(ValueError):
        Config(**overrides)
