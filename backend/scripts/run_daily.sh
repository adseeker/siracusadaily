#!/bin/zsh
set -euo pipefail

PROJECT_DIR="${0:A:h:h}"
RUNTIME_DIR="$PROJECT_DIR/runtime"
ENV_FILE="${SIRACUSA_ENV_FILE:-$PROJECT_DIR/.env.local}"
LOCK_DIR="$RUNTIME_DIR/run.lock"
TIMESTAMP="$(date '+%Y%m%d-%H%M%S')"
LOG_FILE="$RUNTIME_DIR/logs/run-$TIMESTAMP.log"

mkdir -p "$RUNTIME_DIR/data" "$RUNTIME_DIR/output" "$RUNTIME_DIR/logs"

if ! mkdir "$LOCK_DIR" 2>/dev/null; then
  print "Esecuzione annullata: un altro run risulta già attivo ($LOCK_DIR)" >&2
  exit 75
fi
trap 'rmdir "$LOCK_DIR" 2>/dev/null || true' EXIT INT TERM

if [[ ! -f "$ENV_FILE" ]]; then
  print "Configurazione mancante: $ENV_FILE" >&2
  exit 78
fi

set -a
source "$ENV_FILE"
set +a

: "${OPENAI_API_KEY:?OPENAI_API_KEY non configurata in $ENV_FILE}"
: "${BREVO_API_KEY:?BREVO_API_KEY non configurata in $ENV_FILE}"

if [[ ! -x "$PROJECT_DIR/.venv/bin/siracusa-daily" ]]; then
  print "Ambiente Python mancante. Esegui prima scripts/setup_local.sh" >&2
  exit 78
fi

{
  print "[$(date -Iseconds)] Avvio pipeline SiracusaDaily"
  "$PROJECT_DIR/.venv/bin/siracusa-daily" \
    --source-map "$PROJECT_DIR/data/source_map.csv" \
    --endpoint-map "$PROJECT_DIR/data/endpoint_map.csv" \
    --database "$RUNTIME_DIR/data/siracusa_daily.db" \
    run \
    --writer openai \
    --model gpt-5-mini \
    --lookback-hours 168 \
    --item-limit 30 \
    --limit 10 \
    --event-limit 8 \
    --opportunity-limit 6 \
    --minimum-items 6 \
    --output "$RUNTIME_DIR/output/newsletter.html" \
    --facebook-output-dir "$RUNTIME_DIR/output" \
    --skip-existing-brevo-date \
    --brevo-draft
  print "[$(date -Iseconds)] Pipeline completata"
} 2>&1 | tee "$LOG_FILE"

exit "${pipestatus[1]}"
