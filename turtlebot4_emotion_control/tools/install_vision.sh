#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../../.."
export PYTHONNOUSERSITE=1
/usr/bin/python3 -m venv --system-site-packages .venv-emotion
touch .venv-emotion/COLCON_IGNORE
.venv-emotion/bin/python -m pip install -r src/turtlebot4_emotion_control/requirements-vision.txt
.venv-emotion/bin/python src/turtlebot4_emotion_control/tools/download_models.py
if [[ "${1:-}" == '--deepface' ]]; then
  .venv-emotion/bin/python -m pip install -r src/turtlebot4_emotion_control/requirements-deepface.txt
  TF_CPP_MIN_LOG_LEVEL=3 TF_NUM_INTRAOP_THREADS=2 TF_NUM_INTEROP_THREADS=1 \
    .venv-emotion/bin/python -c \
    'from deepface import DeepFace; DeepFace.build_model(model_name="Emotion", task="facial_attribute"); print("DeepFace ready")'
fi
