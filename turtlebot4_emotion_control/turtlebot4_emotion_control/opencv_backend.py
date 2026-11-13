"""Small OpenCV Zoo ONNX models for CPU facial-expression recognition.

Model source and preprocessing reference:
https://github.com/opencv/opencv_zoo/tree/main/models/facial_expression_recognition
The OpenCV Zoo models are distributed under Apache-2.0.
"""
import hashlib
from pathlib import Path
import urllib.request


MODELS = {
    'face_detection_yunet_2023mar.onnx': (
        'face_detection_yunet',
        '8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4'),
    'facial_expression_recognition_mobilefacenet_2022july.onnx': (
        'facial_expression_recognition',
        '4f61307602fc089ce20488a31d4e4614e3c9753a7d6c41578c854858b183e1a9'),
}
LABELS = ('angry', 'disgust', 'fear', 'happy', 'neutral', 'sad', 'surprise')


def ensure_models(directory=None):
    directory = Path(directory).expanduser() if directory else Path.home()/'.cache/turtlebot4_emotion_control'
    directory.mkdir(parents=True, exist_ok=True)
    for name, (folder, expected) in MODELS.items():
        target = directory/name
        if target.is_file() and hashlib.sha256(target.read_bytes()).hexdigest() == expected:
            continue
        url = f'https://media.githubusercontent.com/media/opencv/opencv_zoo/main/models/{folder}/{name}'
        request = urllib.request.Request(url, headers={'User-Agent': 'TurtleBotEmotion/1.0'})
        with urllib.request.urlopen(request, timeout=60) as response:
            payload = response.read(12_000_000)
        if hashlib.sha256(payload).hexdigest() != expected:
            raise RuntimeError(f'Model checksum mismatch: {name}')
        temporary = target.with_suffix('.tmp')
        temporary.write_bytes(payload)
        temporary.replace(target)
    return directory


def probabilities(output):
    import numpy as np
    scores = np.asarray(output, dtype=np.float64).reshape(-1)
    if scores.size != len(LABELS) or not np.isfinite(scores).all():
        raise ValueError('Invalid expression network output')
    if (scores >= 0).all() and (scores <= 1).all() and abs(float(scores.sum())-1) < 1e-4:
        return scores
    values = np.exp(scores-scores.max())
    return values/values.sum()


class OpenCVEmotion:
    def __init__(self, directory=None):
        import cv2
        import numpy as np
        self.cv2, self.np = cv2, np
        directory = ensure_models(directory)
        self.detector = cv2.FaceDetectorYN.create(
            str(directory/'face_detection_yunet_2023mar.onnx'), '', (320, 240),
            score_threshold=0.80, nms_threshold=0.3, top_k=100)
        self.network = cv2.dnn.readNetFromONNX(
            str(directory/'facial_expression_recognition_mobilefacenet_2022july.onnx'))
        self.network.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
        self.network.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)
        self.reference = np.array([[38.2946, 51.6963], [73.5318, 51.5014],
                                   [56.0252, 71.7366], [41.5493, 92.3655],
                                   [70.7299, 92.2041]], dtype=np.float32)

    def analyze(self, frame):
        from .vision import Result
        image = frame.image
        height, width = image.shape[:2]
        self.detector.setInputSize((width, height))
        faces = self.detector.detect(image)[1]
        if faces is None or len(faces) != 1:
            return Result(frame.seq, frame.captured_at, 'unknown', 0.0,
                          detail='Show exactly one face')
        face = faces[0]
        points = face[4:14].reshape(5, 2)
        # Fit a similarity transform from all five landmarks to the reference face.
        matrix = self.np.zeros((10, 4), dtype=self.np.float64)
        matrix[0::2, 0], matrix[0::2, 1], matrix[0::2, 2] = points[:, 0], -points[:, 1], 1
        matrix[1::2, 0], matrix[1::2, 1], matrix[1::2, 3] = points[:, 1], points[:, 0], 1
        a, b, tx, ty = self.np.linalg.lstsq(matrix, self.reference.reshape(-1), rcond=None)[0]
        transform = self.np.array([[a, -b, tx], [b, a, ty]])
        aligned = self.cv2.warpAffine(image, transform, (112, 112))
        blob = self.cv2.dnn.blobFromImage(aligned, 1/127.5, (112, 112),
                                          (127.5, 127.5, 127.5), swapRB=True)
        self.network.setInput(blob)
        scores = probabilities(self.network.forward())
        index = int(scores.argmax())
        label, confidence = LABELS[index], float(scores[index])
        box = tuple(round(float(v)) for v in face[:4])
        if label == 'disgust':
            return Result(frame.seq, frame.captured_at, 'unknown', 0.0, (box,),
                          'Unsupported expression: disgust')
        return Result(frame.seq, frame.captured_at, label, confidence, (box,))
