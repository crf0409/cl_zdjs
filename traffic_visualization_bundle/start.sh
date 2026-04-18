#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$ROOT_DIR/app"
VENV_DIR="$APP_DIR/.venv"

if command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN="python3"
elif command -v python >/dev/null 2>&1; then
  PYTHON_BIN="python"
else
  echo "Python not found. Install Python 3.10+ first."
  exit 1
fi

cd "$APP_DIR"

if [ ! -d "$VENV_DIR" ]; then
  "$PYTHON_BIN" -m venv .venv
fi

# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

python -m pip install --upgrade pip
pip install -r requirements-visualization.txt
python manage.py migrate

echo
echo "Open: http://127.0.0.1:8000/"
echo "Login: http://127.0.0.1:8000/users/login/"
echo

python manage.py runserver 0.0.0.0:8000
