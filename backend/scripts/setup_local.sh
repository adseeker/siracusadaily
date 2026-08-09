#!/bin/zsh
set -euo pipefail

PROJECT_DIR="${0:A:h:h}"

if [[ -n "${SIRACUSA_PYTHON:-}" ]]; then
  PYTHON_BIN="$SIRACUSA_PYTHON"
elif [[ -x /opt/homebrew/bin/python3 ]]; then
  PYTHON_BIN=/opt/homebrew/bin/python3
else
  PYTHON_BIN="$(command -v python3)"
fi

PYTHON_VERSION="$($PYTHON_BIN -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
if ! "$PYTHON_BIN" -c 'import sys; raise SystemExit(sys.version_info < (3, 11))'; then
  print "Python $PYTHON_VERSION non compatibile: serve Python 3.11 o superiore" >&2
  exit 78
fi

"$PYTHON_BIN" -m venv "$PROJECT_DIR/.venv"
"$PROJECT_DIR/.venv/bin/python" -m pip install --upgrade pip
"$PROJECT_DIR/.venv/bin/pip" install -e "$PROJECT_DIR"

mkdir -p "$PROJECT_DIR/runtime/data" "$PROJECT_DIR/runtime/output" "$PROJECT_DIR/runtime/logs"
"$PROJECT_DIR/.venv/bin/siracusa-daily" \
  --database "$PROJECT_DIR/runtime/data/siracusa_daily.db" \
  init

if [[ ! -f "$PROJECT_DIR/.env.local" ]]; then
  cp "$PROJECT_DIR/.env.local.example" "$PROJECT_DIR/.env.local"
  chmod 600 "$PROJECT_DIR/.env.local"
  print "Configurazione creata: $PROJECT_DIR/.env.local"
  print "Inserisci OPENAI_API_KEY e BREVO_API_KEY prima del primo run."
fi

print "Motore locale inizializzato."
