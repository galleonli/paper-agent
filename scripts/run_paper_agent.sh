#!/bin/zsh

set -u

MODE="manual"
RUN_HOUR="4"
AGENT_ROOT=""
PYTHON_BIN=""
CONFIG_PATH=""
STATE_DIR="${HOME}/Library/Application Support/PaperAgent/state"
LOG_DIR="${HOME}/Library/Logs/PaperAgent"
ENV_FILE=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --mode)
      MODE="$2"
      shift 2
      ;;
    --run-hour)
      RUN_HOUR="$2"
      shift 2
      ;;
    --agent-root)
      AGENT_ROOT="$2"
      shift 2
      ;;
    --python)
      PYTHON_BIN="$2"
      shift 2
      ;;
    --config)
      CONFIG_PATH="$2"
      shift 2
      ;;
    --state-dir)
      STATE_DIR="$2"
      shift 2
      ;;
    --log-dir)
      LOG_DIR="$2"
      shift 2
      ;;
    --env-file)
      ENV_FILE="$2"
      shift 2
      ;;
    *)
      echo "Unknown argument: $1" >&2
      exit 2
      ;;
  esac
done

if [[ -z "$AGENT_ROOT" || -z "$PYTHON_BIN" || -z "$CONFIG_PATH" ]]; then
  echo "Missing required arguments (--agent-root, --python, --config)." >&2
  exit 2
fi

mkdir -p "$STATE_DIR" "$LOG_DIR"

LOCK_DIR="${STATE_DIR}/run.lock"
LAST_SUCCESS_FILE="${STATE_DIR}/last_success_date"
STATUS_FILE="${STATE_DIR}/last_run_status.json"
TODAY="$(date +%F)"
CURRENT_HOUR="$(date +%H)"
STARTED_AT="$(date '+%Y-%m-%d %H:%M:%S')"
RUN_LOG=""

send_notification() {
  local title="$1"
  local message="$2"
  if [[ "$MODE" != "daily-launchd" ]]; then
    return
  fi
  if [[ ! -x /usr/bin/osascript ]]; then
    return
  fi
  /usr/bin/osascript \
    -e 'on run argv' \
    -e 'display notification (item 2 of argv) with title (item 1 of argv) sound name "Glass"' \
    -e 'end run' \
    "$title" \
    "$message" >/dev/null 2>&1 || true
}

write_status() {
  local status="$1"
  local reason="${2:-}"
  local exit_code="${3:-}"
  local finished_at
  finished_at="$(date '+%Y-%m-%d %H:%M:%S')"
  cat > "$STATUS_FILE" <<EOF
{
  "mode": "${MODE}",
  "date": "${TODAY}",
  "status": "${status}",
  "reason": "${reason}",
  "exit_code": "${exit_code}",
  "started_at": "${STARTED_AT}",
  "finished_at": "${finished_at}",
  "log_path": "${RUN_LOG}",
  "config_path": "${CONFIG_PATH}",
  "agent_root": "${AGENT_ROOT}"
}
EOF
}

if [[ "$MODE" == "daily-launchd" ]]; then
  if ! [[ "$RUN_HOUR" =~ ^[0-9]+$ ]]; then
    echo "Invalid --run-hour: $RUN_HOUR" >&2
    write_status "failed" "invalid-run-hour" "2"
    exit 2
  fi
  if (( 10#$CURRENT_HOUR < 10#$RUN_HOUR )); then
    echo "Skipping daily run before ${RUN_HOUR}:00."
    write_status "skipped" "before-scheduled-hour" "0"
    exit 0
  fi
  if [[ -f "$LAST_SUCCESS_FILE" ]] && [[ "$(<"$LAST_SUCCESS_FILE")" == "$TODAY" ]]; then
    echo "Skipping daily run because today's run already succeeded."
    write_status "skipped" "already-succeeded-today" "0"
    exit 0
  fi
fi

if ! mkdir "$LOCK_DIR" 2>/dev/null; then
  echo "Skipping run because another Paper Agent process is active."
  write_status "skipped" "already-running" "0"
  exit 0
fi

cleanup() {
  rmdir "$LOCK_DIR" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

if [[ -n "$ENV_FILE" && -f "$ENV_FILE" ]]; then
  set -a
  source "$ENV_FILE"
  set +a
fi

TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
RUN_LOG="${LOG_DIR}/${TIMESTAMP}-${MODE}.log"

{
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] mode=${MODE} agent_root=${AGENT_ROOT}"
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] config=${CONFIG_PATH}"
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] python=${PYTHON_BIN}"
} | tee -a "$RUN_LOG"

cd "$AGENT_ROOT" || {
  echo "Failed to enter agent root: $AGENT_ROOT" | tee -a "$RUN_LOG" >&2
  exit 1
}

"$PYTHON_BIN" -m paper_agent run --config "$CONFIG_PATH" 2>&1 | tee -a "$RUN_LOG"
status=${pipestatus[1]}

if [[ $status -eq 0 ]]; then
  echo "$TODAY" > "$LAST_SUCCESS_FILE"
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] completed successfully" | tee -a "$RUN_LOG"
  write_status "success" "" "$status"
  send_notification "Paper Agent finished" "Daily run completed successfully. Log: ${RUN_LOG}"
else
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] failed with exit code $status" | tee -a "$RUN_LOG" >&2
  write_status "failed" "pipeline-exit-nonzero" "$status"
  send_notification "Paper Agent failed" "Daily run failed with exit code ${status}. Check log: ${RUN_LOG}"
fi

exit $status
