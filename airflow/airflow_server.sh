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
DAG_DIR="${AIRFLOW_DAG_DIR:-${AIRFLOW_HOME:-$HOME/airflow}/dags}"

SERVICES=("api-server" "scheduler" "dag-processor" "triggerer")

activate_env() {
  if ! command -v pyenv >/dev/null; then
    echo "[ERROR] pyenv not found in PATH" >&2
    exit 1
  fi
  eval "$(pyenv init -)"   >/dev/null
  eval "$(pyenv virtualenv-init -)" >/dev/null
  pyenv activate "$PYENV_VENV"
  export AIRFLOW__DATABASE__SQL_ALCHEMY_CONN="postgresql+psycopg2://airflow:airflow@localhost:5432/airflow"
  export  AIRFLOW__CORE__LOAD_EXAMPLES=false
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
  [[ -n "${AIRFLOW__DATABASE__SQL_ALCHEMY_CONN:-}" ]] || \
    echo "[WARN] AIRFLOW__DATABASE__SQL_ALCHEMY_CONN not set. Will use SQLite."
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

link_dags() {
  echo ">>> Linking local DAGs into $DAG_DIR"
  mkdir -p "$DAG_DIR"

  shopt -s nullglob
  local matched=()

  for f in "$ROOT_DIR"/airflow/*_dag.py; do
    matched+=("$f")
    base=$(basename "$f")
    ln -sf "$f" "$DAG_DIR/$base"
    echo "    ↪ linked $base"
  done

  shopt -u nullglob

  if [[ ${#matched[@]} -eq 0 ]]; then
    echo -e "\033[0;33m[WARN] No DAG files matched the patterns in $ROOT_DIR\033[0m"
  else
    echo ">>> Total DAGs linked: ${#matched[@]}"
  fi
}


bg_start() {
  local name=$1; shift
  "$@" >"$LOG_DIR/$name.out" 2>&1 &
  echo $! >"$PID_DIR/$name.pid"
}

start_services() {
  local already=false
  for svc in "${SERVICES[@]}"; do
    pid_file="$PID_DIR/${svc}.pid"
    if [[ -f "$pid_file" ]] && kill -0 "$(cat "$pid_file")" 2>/dev/null; then
      echo "[INFO] $svc already running (pid $(cat "$pid_file"))"
      already=true
    fi
  done
  $already && { echo "[WARN] Airflow services are already active; aborting start."; return; }

  make_dirs
  link_dags
  check_db_url
  init_or_migrate_db

  echo ">>> Starting api-server (port $WEB_PORT)"
  bg_start api-server airflow api-server --port "$WEB_PORT"

  echo ">>> Starting scheduler"
  bg_start scheduler airflow scheduler

  echo ">>> Starting dag-processor"
  bg_start dag-processor airflow dag-processor

  echo ">>> Starting triggerer"
  bg_start triggerer airflow triggerer

  status_services
  show_admin_password

  conn="${AIRFLOW__DATABASE__SQL_ALCHEMY_CONN:-}"
  if [[ "$conn" =~ postgresql\+psycopg2://([^:]+):([^@]+)@ ]]; then
    user="${BASH_REMATCH[1]}"
    pass="${BASH_REMATCH[2]}"
    if [[ "$user" == "airflow" && "$pass" == "airflow" ]]; then
      echo -e "\033[0;31m[WARNING] Your PostgreSQL username and password are both 'airflow'."
      echo -e "Please change them IMMEDIATELY:"
      echo -e "psql -c \"ALTER USER airflow WITH PASSWORD '<your-strong-password>';\" -U postgres\033[0m"
    elif [[ "$pass" == "airflow" ]]; then
      echo -e "\033[0;31m[WARNING] Your PostgreSQL password is 'airflow'."
      echo -e "Please change it IMMEDIATELY:"
      echo -e "psql -c \"ALTER USER $user WITH PASSWORD '<your-strong-password>';\" -U postgres\033[0m"
    fi
  fi
}

stop_services() {
  echo ">>> Stopping Airflow processes"
  for svc in "${SERVICES[@]}"; do
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
  for svc in "${SERVICES[@]}"; do
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
    echo "[INFO] Password file not generated yet; check again after first boot."
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
