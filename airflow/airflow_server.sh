#!/usr/bin/env bash
# 
# Usage:
#   ./airflow_server.sh start
#   ./airflow_server.sh stop
#   ./airflow_server.sh restart
#   ./airflow_server.sh status

set -euo pipefail

PYENV_VENV="airflow"
WEB_PORT=8080
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="$ROOT_DIR/logs/airflow"
PID_DIR="$ROOT_DIR/.pids"
PASSWORD_FILE="${AIRFLOW_HOME:-$HOME/airflow}/simple_auth_manager_passwords.json.generated"

activate_env() {
  if ! command -v pyenv >/dev/null; then
    echo "[ERROR] pyenv not found in PATH" >&2
    exit 1
  fi
  eval "$(pyenv init -)" >/dev/null
  eval "$(pyenv virtualenv-init -)" >/dev/null
  pyenv activate "$PYENV_VENV"
  export AIRFLOW__DATABASE__SQL_ALCHEMY_CONN="postgresql+psycopg2://airflow:airflow@localhost:5432/airflow"
}

assert_airflow3() {
  local v
  v="$(airflow version 2>/dev/null || true)"
  if [[ -z "$v" ]]; then
    echo "[ERROR] airflow CLI not found in this environment." >&2
    exit 1
  fi
  if [[ "${v%%.*}" != "3" ]]; then
    echo "[ERROR] This helper supports Airflow 3.x only (detected $v)." >&2
    exit 1
  fi
}

check_db_url() {
  if [[ -z "${AIRFLOW__DATABASE__SQL_ALCHEMY_CONN:-}" ]]; then
    echo "[WARN] AIRFLOW__DATABASE__SQL_ALCHEMY_CONN not set. Will use SQLite."
  fi
}

init_or_migrate_db() {
  if ! airflow db check >/dev/null 2>&1; then
    echo ">>> First-time setup: initializing metadata DB via migrate"
  fi
  echo ">>> Running airflow db migrate"
  airflow db migrate
}

make_dirs() {
  mkdir -p "$LOG_DIR" "$PID_DIR"
}

bg_start() {
  local name=$1; shift
  "$@" > "$LOG_DIR/$name.out" 2>&1 &
  echo $! > "$PID_DIR/$name.pid"
}

start_services() {
  local already=false
  for svc in api-server scheduler; do
    pid_file="$PID_DIR/${svc}.pid"
    if [[ -f "$pid_file" ]] && kill -0 "$(cat "$pid_file")" 2>/dev/null; then
      echo "[INFO] $svc already running (pid $(cat "$pid_file"))"
      already=true
    fi
  done
  if $already; then
    echo "[WARN] Airflow services are already active; aborting start."
    return 0
  fi
  make_dirs
  check_db_url
  init_or_migrate_db

  echo ">>> Starting api-server (port $WEB_PORT)"
  bg_start api-server airflow api-server --port "$WEB_PORT"

  echo ">>> Starting scheduler"
  bg_start scheduler  airflow scheduler

  status_services
  show_admin_password

  if [[ "$AIRFLOW__DATABASE__SQL_ALCHEMY_CONN" == postgresql+psycopg2://airflow:airflow@localhost:5432/airflow ]]; then
    echo -e "\033[0;31m[WARNING] Your PostgreSQL 'airflow' user password is set to the default 'airflow'."
    echo -e "Please change this database password to a secure value IMMEDIATELY"
    echo -e "psql -c \"ALTER USER airflow WITH PASSWORD '<your-strong-password>';\" -U postgres\033[0m"
  fi
}

stop_services() {
  echo ">>> Stopping Airflow processes"
  for svc in api-server scheduler; do
    pid_file="$PID_DIR/${svc}.pid"
    if [[ -f "$pid_file" ]]; then
      pid=$(cat "$pid_file")
      if kill -0 "$pid" 2>/dev/null; then
        kill "$pid"
        echo "$svc (pid $pid) stopped"
      fi
      rm -f "$pid_file"
    fi
  done
}

status_services() {
  for svc in api-server scheduler; do
    pid_file="$PID_DIR/${svc}.pid"
    if [[ -f "$pid_file" ]] && kill -0 "$(cat "$pid_file")" 2>/dev/null; then
      echo "$svc running (pid $(cat "$pid_file"))"
    else
      echo "$svc NOT running"
    fi
  done
}

show_admin_password() {
  if [[ -f "$PASSWORD_FILE" ]]; then
    echo ">>> SimpleAuth admin passwords:"
    cat "$PASSWORD_FILE"
  else
    echo "[INFO] Password file not generated yet, please check again after first boot."
  fi
}

usage() {
  echo "Usage: $0 {start|stop|restart|status}"
  exit 1
}

main() {
  [[ $# -eq 1 ]] || usage
  action=$1

  activate_env
  assert_airflow3

  case "$action" in
    start)    start_services ;;
    stop)     stop_services ;;
    restart)  stop_services; start_services ;;
    status)   status_services ;;
    *)        usage ;;
  esac
}

main "$@"
