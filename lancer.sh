#!/usr/bin/env bash
# Lance la détection (webcam par défaut). Exemples : bash lancer.sh --source video.mp4   /   --source 1   /   --voix
cd "$(dirname "$0")"
. .venv/bin/activate
python app.py "$@"
