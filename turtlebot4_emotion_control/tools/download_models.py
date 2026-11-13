#!/usr/bin/env python3
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from turtlebot4_emotion_control.opencv_backend import ensure_models

parser = argparse.ArgumentParser()
parser.add_argument('--model-dir', default='')
args = parser.parse_args()
print('OpenCV emotion models ready:', ensure_models(args.model_dir))
