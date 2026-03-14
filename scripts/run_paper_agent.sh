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
LOCK_PID_FILE="${LOCK_DIR}/pid"
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

json_escape() {
  local value="$1"
  value="${value//\\/\\\\}"
  value="${value//\"/\\\"}"
  value="${value//$'\n'/\\n}"
  value="${value//$'\r'/\\r}"
  value="${value//$'\t'/\\t}"
  printf "%s" "$value"
}

write_status() {
  local run_status="$1"
  local reason="${2:-}"
  local exit_code="${3:-}"
  local finished_at
  finished_at="$(date '+%Y-%m-%d %H:%M:%S')"
  local mode_json date_json status_json reason_json exit_json started_json finished_json log_json config_json root_json
  mode_json="$(json_escape "$MODE")"
  date_json="$(json_escape "$TODAY")"
  status_json="$(json_escape "$run_status")"
  reason_json="$(json_escape "$reason")"
  exit_json="$(json_escape "$exit_code")"
  started_json="$(json_escape "$STARTED_AT")"
  finished_json="$(json_escape "$finished_at")"
  log_json="$(json_escape "$RUN_LOG")"
  config_json="$(json_escape "$CONFIG_PATH")"
  root_json="$(json_escape "$AGENT_ROOT")"
  cat > "$STATUS_FILE" <<EOF
{
  "mode": "${mode_json}",
  "date": "${date_json}",
  "status": "${status_json}",
  "reason": "${reason_json}",
  "exit_code": "${exit_json}",
  "started_at": "${started_json}",
  "finished_at": "${finished_json}",
  "log_path": "${log_json}",
  "config_path": "${config_json}",
  "agent_root": "${root_json}"
}
EOF
}

clear_lock_dir() {
  rm -f "$LOCK_PID_FILE" 2>/dev/null || true
  rmdir "$LOCK_DIR" 2>/dev/null
}

is_active_lock_pid() {
  local lock_pid="$1"
  if [[ -z "$lock_pid" ]]; then
    return 1
  fi

  local lock_state=""
  lock_state="$(ps -o state= -p "$lock_pid" 2>/dev/null | tr -d '[:space:]')"
  if [[ -n "$lock_state" && "$lock_state" == Z* ]]; then
    return 1
  fi

  if ! kill -0 "$lock_pid" 2>/dev/null; then
    return 1
  fi

  local lock_cmd=""
  lock_cmd="$(ps -o command= -p "$lock_pid" 2>/dev/null)"
  if [[ "$lock_cmd" == *"run_paper_agent.sh"* ]]; then
    return 0
  fi

  return 1
}

acquire_lock() {
  if mkdir "$LOCK_DIR" 2>/dev/null; then
    echo "$$" > "$LOCK_PID_FILE"
    return 0
  fi

  local lock_pid=""
  if [[ -f "$LOCK_PID_FILE" ]]; then
    lock_pid="$(<"$LOCK_PID_FILE")"
  fi

  if is_active_lock_pid "$lock_pid"; then
    return 1
  fi

  if ! clear_lock_dir; then
    return 1
  fi

  if mkdir "$LOCK_DIR" 2>/dev/null; then
    echo "$$" > "$LOCK_PID_FILE"
    return 0
  fi

  return 1
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

if ! acquire_lock; then
  echo "Skipping run because another Paper Agent process is active."
  write_status "skipped" "already-running" "0"
  exit 0
fi

cleanup() {
  clear_lock_dir || true
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
run_exit_code=${pipestatus[1]}

if [[ $run_exit_code -eq 0 ]]; then
  echo "$TODAY" > "$LAST_SUCCESS_FILE"
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] completed successfully" | tee -a "$RUN_LOG"
  write_status "success" "" "$run_exit_code"
  send_notification "Paper Agent finished" "Daily run completed successfully. Log: ${RUN_LOG}"
else
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] failed with exit code $run_exit_code" | tee -a "$RUN_LOG" >&2
  write_status "failed" "pipeline-exit-nonzero" "$run_exit_code"
  send_notification "Paper Agent failed" "Daily run failed with exit code ${run_exit_code}. Check log: ${RUN_LOG}"
fi

exit $run_exit_code
