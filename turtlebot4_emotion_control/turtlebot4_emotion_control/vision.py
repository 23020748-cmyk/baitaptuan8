"""Latest-frame capture and DeepFace inference run outside the ROS timer."""
from dataclasses import dataclass
import json
import math
from pathlib import Path
import threading
import time

from .behavior import EMOTIONS


@dataclass(frozen=True)
class Frame:
    seq: int
    captured_at: float
    image: object


@dataclass(frozen=True)
class Result:
    seq: int
    captured_at: float
    label: str
    confidence: float
    boxes: tuple = ()
    detail: str = ''


def analyze_frame(frame, analyze):
    """Use only emotion; reject no face, multiple faces and unsupported disgust."""
    try:
        faces = analyze(img_path=frame.image.copy(), actions=['emotion'],
                        detector_backend='opencv', enforce_detection=True, silent=True)
    except ValueError as exc:
        return Result(frame.seq, frame.captured_at, 'unknown', 0.0, detail=str(exc))
    if not isinstance(faces, list) or len(faces) != 1:
        return Result(frame.seq, frame.captured_at, 'unknown', 0.0,
                      detail='Show exactly one face')
    face = faces[0]
    region = face['region']
    boxes = ((int(region['x']), int(region['y']), int(region['w']), int(region['h'])),)
    label = str(face['dominant_emotion']).lower()
    confidence = float(face['emotion'][label]) / 100.0
    if label not in EMOTIONS or not math.isfinite(confidence) or not 0 <= confidence <= 1:
        return Result(frame.seq, frame.captured_at, 'unknown', 0.0, boxes,
                      'Unsupported/uncertain expression')
    return Result(frame.seq, frame.captured_at, label, confidence, boxes)


class Vision:
    def __init__(self, source='0', inference_hz=3.0, backend='opencv', model_dir=''):
        if not math.isfinite(inference_hz) or inference_hz <= 0:
            raise ValueError('inference_hz must be finite and positive')
        self.source = str(source)
        if backend not in ('opencv', 'deepface'):
            raise ValueError('backend must be opencv or deepface')
        self.backend, self.model_dir = backend, model_dir
        self.period = 1.0 / inference_hz
        self.lock = threading.Lock()
        self.end = threading.Event()
        self.frame = None
        self.result = None
        self.camera_error = 'Opening camera'
        self.model_error = f'Loading {backend} emotion model'
        self.threads = [threading.Thread(target=target, daemon=True)
                        for target in (self._capture, self._recognize)]

    def start(self):
        import cv2
        cv2.setNumThreads(1)
        for thread in self.threads:
            thread.start()

    def snapshot(self):
        with self.lock:
            return self.frame, self.result, self.camera_error, self.model_error

    def _capture(self):
        cap = None
        try:
            import cv2
            import numpy as np
            file_source = self.source.startswith('file://')
            if not file_source:
                source = int(self.source) if self.source.isdecimal() else self.source
                cap = cv2.VideoCapture(source)
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                if not cap.isOpened():
                    raise RuntimeError(f'Cannot open camera {self.source}; WSL may need Windows bridge')
            seq, last_file_seq = 0, None
            while not self.end.is_set():
                try:
                    age = 0.0
                    if file_source:
                        payload = Path(self.source[7:]).read_bytes()
                        header, jpeg = payload.split(b'\n', 1)
                        meta = json.loads(header)
                        if not math.isfinite(float(meta['stamp'])):
                            raise RuntimeError('Invalid camera timestamp')
                        # Windows and WSL wall clocks can drift when the VM is busy.
                        # Require a sequence change before accepting the first frame,
                        # then use local monotonic receipt times for the watchdog.
                        if last_file_seq is None:
                            last_file_seq = meta['seq']
                            self.end.wait(0.01)
                            continue
                        if meta['seq'] == last_file_seq:
                            self.end.wait(0.01)
                            continue
                        last_file_seq = meta['seq']
                        image = cv2.imdecode(np.frombuffer(jpeg, np.uint8), cv2.IMREAD_COLOR)
                    else:
                        ok, image = cap.read()
                        if not ok:
                            raise RuntimeError('Camera read failed')
                    if image is None:
                        raise RuntimeError('Empty/invalid camera image')
                    seq += 1
                    frame = Frame(seq, time.monotonic() - max(0.0, age), image)
                    with self.lock:
                        self.frame, self.camera_error = frame, ''
                except Exception as exc:
                    with self.lock:
                        self.frame, self.camera_error = None, str(exc)
                    self.end.wait(0.1)
                self.end.wait(0.01)
        except Exception as exc:
            with self.lock:
                self.frame, self.camera_error = None, str(exc)
        finally:
            if cap is not None:
                cap.release()

    def _recognize(self):
        try:
            import cv2
            if self.backend == 'deepface':
                from deepface import DeepFace
                DeepFace.build_model(model_name='Emotion', task='facial_attribute')
                analyze = lambda frame: analyze_frame(frame, DeepFace.analyze)
            else:
                from .opencv_backend import OpenCVEmotion
                analyze = OpenCVEmotion(self.model_dir).analyze
            last_seq = None
            while not self.end.is_set():
                frame = self.snapshot()[0]
                if frame is None or frame.seq == last_seq:
                    self.end.wait(0.02)
                    continue
                last_seq = frame.seq
                started = time.monotonic()
                try:
                    # Keep CPU inference fast; the display retains full resolution.
                    scale = min(1.0, 320.0 / frame.image.shape[1])
                    image = frame.image
                    if scale < 1.0:
                        image = cv2.resize(image, None, fx=scale, fy=scale,
                                           interpolation=cv2.INTER_AREA)
                    result = analyze(Frame(frame.seq, frame.captured_at, image))
                    if scale < 1.0:
                        result = Result(result.seq, result.captured_at, result.label,
                                        result.confidence,
                                        tuple(tuple(round(v/scale) for v in box)
                                              for box in result.boxes), result.detail)
                    with self.lock:
                        self.result, self.model_error = result, ''
                except Exception as exc:
                    with self.lock:
                        self.result, self.model_error = None, f'{self.backend}: {exc}'
                self.end.wait(max(0.0, self.period - (time.monotonic() - started)))
        except Exception as exc:
            with self.lock:
                self.result, self.model_error = None, f'Model unavailable: {exc}'

    def close(self):
        self.end.set()
        for thread in self.threads:
            if thread.ident is not None:
                thread.join(timeout=0.5)
