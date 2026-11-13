import pytest
import numpy as np
from turtlebot4_emotion_control.opencv_backend import LABELS, probabilities


def test_expression_order_and_stable_softmax():
    assert LABELS == ('angry', 'disgust', 'fear', 'happy', 'neutral', 'sad', 'surprise')
    scores = probabilities([1000, -1000, 0, 1001, 0, 0, 0])
    assert scores.argmax() == 3
    assert np.isfinite(scores).all()
    assert scores.sum() == pytest.approx(1)


def test_network_probability_output_is_not_softmaxed_twice():
    output = [0.02, 0.01, 0.02, 0.9, 0.02, 0.01, 0.02]
    assert probabilities(output) == pytest.approx(output)


@pytest.mark.parametrize('output', [[1, 2], [0, 0, 0, float('nan'), 0, 0, 0]])
def test_corrupt_network_output_is_rejected(output):
    with pytest.raises(ValueError):
        probabilities(output)
