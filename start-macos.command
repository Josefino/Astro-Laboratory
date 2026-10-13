#!/bin/bash
set -e
cd "$(dirname "$0")"
if [ ! -d .venv ]; then
  python3 -m venv .venv
fi
.venv/bin/python -m pip install -r requirements.txt
if [ -f settings.env ]; then
  set -a
  source settings.env
  set +a
fi
open http://127.0.0.1:8765
.venv/bin/python app.py
