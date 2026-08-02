#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

ENV_FILE="$ROOT_DIR/.env"
if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck source=/dev/null
  source "$ENV_FILE"
  set +a
fi

HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8001}"
ACTION="${1:-restart}"
RUN_DIR="$ROOT_DIR/.local"
PID_FILE="$RUN_DIR/les-management-${PORT}.pid"
LOG_FILE="$RUN_DIR/les-management-${PORT}.log"

if [[ -x "$ROOT_DIR/env/bin/python" ]]; then
  PYTHON="${PYTHON:-$ROOT_DIR/env/bin/python}"
elif [[ -x "$ROOT_DIR/.venv/bin/python" ]]; then
  PYTHON="${PYTHON:-$ROOT_DIR/.venv/bin/python}"
else
  PYTHON="${PYTHON:-python3}"
fi

mkdir -p "$RUN_DIR"

is_running() {
  local pid="$1"
  [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null
}

stop_pid() {
  local pid="$1"
  local label="$2"

  if ! is_running "$pid"; then
    return 0
  fi

  echo "Stopping $label process $pid..."
  kill "$pid" 2>/dev/null || true

  for _ in {1..20}; do
    if ! is_running "$pid"; then
      return 0
    fi
    sleep 0.25
  done

  echo "Process $pid did not stop after SIGTERM. Set FORCE=1 to kill it."
  if [[ "${FORCE:-0}" == "1" ]]; then
    kill -9 "$pid" 2>/dev/null || true
  else
    return 1
  fi
}

stop_server() {
  if [[ -f "$PID_FILE" ]]; then
    local pid
    pid="$(cat "$PID_FILE")"
    stop_pid "$pid" "tracked"
    rm -f "$PID_FILE"
  fi

  if command -v lsof >/dev/null 2>&1; then
    local port_pids
    port_pids="$(lsof -ti TCP:"$PORT" -sTCP:LISTEN 2>/dev/null || true)"
    for pid in $port_pids; do
      stop_pid "$pid" "port $PORT"
    done
  fi
}

start_server() {
  echo "Starting Les Management System on http://$HOST:$PORT ..."
  PORT="$PORT" HOST="$HOST" nohup "$PYTHON" -m backend.app.main >"$LOG_FILE" 2>&1 &
  local pid="$!"
  echo "$pid" > "$PID_FILE"

  sleep 0.75
  if ! is_running "$pid"; then
    echo "Server failed to start. Recent log:"
    tail -40 "$LOG_FILE" || true
    exit 1
  fi

  echo "Server ready."
  echo "PID: $pid"
  echo "Log: $LOG_FILE"
  echo "Client dashboard: http://$HOST:$PORT/"
  echo "Provider simulation: http://$HOST:$PORT/provider/chat-simulations"
}

foreground_server() {
  stop_server
  echo "Starting Les Management System in foreground on http://$HOST:$PORT ..."
  echo "Client dashboard: http://$HOST:$PORT/"
  echo "Provider simulation: http://$HOST:$PORT/provider/chat-simulations"
  echo "Press Ctrl+C to stop."
  PORT="$PORT" HOST="$HOST" exec "$PYTHON" -m backend.app.main
}

status_server() {
  if [[ -f "$PID_FILE" ]] && is_running "$(cat "$PID_FILE")"; then
    echo "Server is running."
    echo "PID: $(cat "$PID_FILE")"
    echo "Client dashboard: http://$HOST:$PORT/"
    echo "Provider simulation: http://$HOST:$PORT/provider/chat-simulations"
    exit 0
  fi

  if command -v lsof >/dev/null 2>&1 && lsof -ti TCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1; then
    echo "Port $PORT is in use, but not by the tracked PID file."
    lsof -nP -i TCP:"$PORT" -sTCP:LISTEN
    exit 0
  fi

  echo "Server is not running on port $PORT."
}

case "$ACTION" in
  restart|reload)
    stop_server
    start_server
    ;;
  start)
    start_server
    ;;
  foreground|fg)
    foreground_server
    ;;
  stop)
    stop_server
    echo "Server stopped."
    ;;
  status)
    status_server
    ;;
  *)
    echo "Usage: ./reload_local.sh [restart|reload|start|foreground|fg|stop|status]"
    exit 2
    ;;
esac
