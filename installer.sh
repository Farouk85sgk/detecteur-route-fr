#!/usr/bin/env bash
# Installation sous macOS / Linux : bash installer.sh
set -e
cd "$(dirname "$0")"
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
echo "Installation terminée. Lancez : bash lancer.sh"
