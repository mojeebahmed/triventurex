#!/bin/zsh
# Double-click to open the Question Validator in your browser. Close this window to stop it.
cd "$(dirname "$0")"
if [[ ! -x .venv/bin/qv ]]; then
  echo "Not set up yet: see README.md → Setup (uv venv --python 3.12 && uv pip install -e '.[dev]')."
  read -k1 "?Press a key to close."
  exit 1
fi
( sleep 3; open "http://localhost:8501" ) &
exec .venv/bin/qv ui
