"""Local Windows webcam bridge with explicit frame rate and capture diagnostics."""
import argparse
import json
import os
from pathlib import Path
import time

import cv2

p = argparse.ArgumentParser()
p.add_argument('--output', required=True)
p.add_argument('--index', type=int, default=0)
p.add_argument('--fps', type=float, default=15)
p.add_argument('--backend', choices=('dshow', 'msmf'), default='dshow')
p.add_argument('--seconds', type=float, default=0)
args = p.parse_args()
cv2.setNumThreads(1)
target = Path(args.output)
target.parent.mkdir(parents=True, exist_ok=True)
cap = cv2.VideoCapture(args.index, cv2.CAP_DSHOW if args.backend == 'dshow' else cv2.CAP_MSMF)
if not cap.isOpened():
    raise SystemExit('Cannot open Windows webcam')
cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
cap.set(cv2.CAP_PROP_FPS, args.fps)
cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
print(json.dumps(dict(opened=True, backend=cap.getBackendName(),
                      requested_fps=args.fps, reported_fps=cap.get(cv2.CAP_PROP_FPS))), flush=True)
seq = 0
started = reported = time.monotonic()
reported_seq = 0
try:
    while not args.seconds or time.monotonic()-started < args.seconds:
        tick = time.monotonic()
        ok, image = cap.read()
        captured = time.time()
        if not ok:
            raise RuntimeError('Windows webcam stopped delivering frames')
        ok, jpeg = cv2.imencode('.jpg', image, [cv2.IMWRITE_JPEG_QUALITY, 80])
        if not ok:
            continue
        seq += 1
        temporary = target.with_suffix('.tmp')
        temporary.write_bytes(json.dumps({'stamp': captured, 'seq': seq}).encode()+b'\n'+jpeg.tobytes())
        try:
            os.replace(temporary, target)
        except PermissionError:
            pass
        now = time.monotonic()
        if now-reported >= 3:
            print(json.dumps({'seq': seq, 'actual_fps': round((seq-reported_seq)/(now-reported), 2)}), flush=True)
            reported, reported_seq = now, seq
        time.sleep(max(0, 1/args.fps-(time.monotonic()-tick)))
except KeyboardInterrupt:
    pass
finally:
    cap.release()
