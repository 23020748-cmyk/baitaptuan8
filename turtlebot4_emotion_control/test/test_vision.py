import pytest

from turtlebot4_emotion_control.vision import Frame, analyze_frame


class Image:
    def copy(self):
        return self


def face(label='happy', score=92.0):
    return dict(dominant_emotion=label, emotion={label: score},
                region=dict(x=10, y=20, w=50, h=60))


def test_deepface_result_and_api_arguments():
    frame = Frame(5, 10.0, Image())

    def analyze(**kwargs):
        assert kwargs['actions'] == ['emotion']
        assert kwargs['enforce_detection'] is True
        assert kwargs['detector_backend'] == 'opencv'
        return [face()]

    result = analyze_frame(frame, analyze)
    assert result.label == 'happy'
    assert result.confidence == pytest.approx(0.92)
    assert result.captured_at == 10.0
    assert result.boxes == ((10, 20, 50, 60),)


@pytest.mark.parametrize('faces', [[], [face(), face()], [face('disgust')],
                                   [face(score=float('nan'))]])
def test_unsupported_ambiguous_or_invalid_face_stops(faces):
    result = analyze_frame(Frame(1, 10.0, Image()), lambda **kw: faces)
    assert result.label == 'unknown'
    assert result.confidence == 0.0


def test_no_face_is_not_treated_as_neutral():
    def no_face(**kwargs):
        raise ValueError('Face could not be detected')

    result = analyze_frame(Frame(1, 10.0, Image()), no_face)
    assert result.label == 'unknown'
    assert 'detected' in result.detail
