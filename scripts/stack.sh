#!/usr/bin/env bash
#
# Dev stack helper — start/stop the whole local stack and tail the service logs,
# so day-to-day development is one command instead of the README's three-terminal
# dance (docker compose + uvicorn + npm run dev). Run `scripts/stack.sh help` for
# the command list.
#
# Local dev convenience only; it has no production role and touches no secrets.
# Linux/WSL/macOS (bash) — same shells the README already assumes.
#
# Backend and frontend run in the background; their output goes to the gitignored
# .stack/ dir (one .log + .pid per process). Each is launched in its own process
# group so `down` cleanly stops the whole tree (uvicorn --reload's workers, vite's
# children), not just the parent.

repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
run_dir=${STACK_RUN_DIR:-$repo_root/.stack}

usage() {
  cat <<'EOF'
Dev stack helper — one command for the local stack instead of three terminals.

Usage: scripts/stack.sh <command>

  up       infra (docker compose -d) + backend + frontend (backgrounded)
  down     stop backend + frontend, then docker compose down
  logs     tail the neo4j + postgres service logs (pass service names to narrow)
  status   show what is running
  help     this message

Backend/frontend output goes to the gitignored .stack/ dir (one .log + .pid each).
EOF
}

# is_alive <name> — true if the recorded pid for <name> is a live process.
is_alive() {
  local pidfile=$run_dir/$1.pid pid
  [[ -f $pidfile ]] || return 1
  pid=$(cat "$pidfile") || return 1
  [[ -n $pid ]] && kill -0 "$pid" 2>/dev/null
}

# port_busy <port> — true if something is already listening on 127.0.0.1:<port>.
# Uses bash's /dev/tcp so it needs no ss/lsof (portable across Linux/WSL/macOS bash).
port_busy() {
  (exec 3<>"/dev/tcp/127.0.0.1/$1") 2>/dev/null
}

# start_bg <name> <workdir> <cmd...> — launch cmd in <workdir>, backgrounded in its
# own process group, output to .stack/<name>.log, pid recorded in .stack/<name>.pid.
start_bg() {
  local name=$1 workdir=$2
  shift 2
  local logfile=$run_dir/$name.log pidfile=$run_dir/$name.pid
  if is_alive "$name"; then
    echo "  $name already running (pid $(cat "$pidfile"))"
    return 0
  fi
  mkdir -p "$run_dir"
  echo "  starting $name → ${logfile#"$repo_root"/}"
  # Enable job control so the backgrounded job gets its own process group (pgid == pid),
  # which lets `down` signal the whole tree. Restore the prior setting afterwards.
  local had_monitor=0
  case $- in *m*) had_monitor=1 ;; *) set -m ;; esac
  ( cd "$workdir" && exec "$@" ) >"$logfile" 2>&1 &
  local pid=$!
  ((had_monitor)) || set +m
  echo "$pid" >"$pidfile"
}

# stop_bg <name> — TERM (then KILL) the process group recorded for <name>.
stop_bg() {
  local name=$1
  local pidfile=$run_dir/$name.pid pid
  if [[ ! -f $pidfile ]]; then
    echo "  $name not running"
    return 0
  fi
  pid=$(cat "$pidfile")
  if [[ -n $pid ]] && kill -0 "$pid" 2>/dev/null; then
    echo "  stopping $name (pid $pid)"
    kill -s TERM -- "-$pid" 2>/dev/null || kill -s TERM "$pid" 2>/dev/null || true
    local waited=0
    while kill -0 "$pid" 2>/dev/null && ((waited < 20)); do
      sleep 0.25
      ((waited += 1))
    done
    if kill -0 "$pid" 2>/dev/null; then
      kill -s KILL -- "-$pid" 2>/dev/null || kill -s KILL "$pid" 2>/dev/null || true
    fi
  else
    echo "  $name already stopped (stale pidfile)"
  fi
  rm -f "$pidfile"
}

# up_app <name> <port> <workdir> <cmd...> — start_bg the process, but if its port is
# already taken by something this script didn't start (e.g. a hand-launched server),
# warn and skip rather than spawn a duplicate that dies silently into the log.
up_app() {
  local name=$1 port=$2
  shift 2
  if ! is_alive "$name" && port_busy "$port"; then
    echo "  ! $name: port $port already in use by a process stack.sh didn't start — skipping"
    return 0
  fi
  start_bg "$name" "$@"
}

cmd_up() {
  echo "▶ infra — docker compose up -d"
  docker compose up -d
  echo "▶ app"
  up_app backend 8000 "$repo_root/backend" uv run uvicorn story_forge.main:app --reload --port 8000
  up_app frontend 5173 "$repo_root/frontend" npm run dev
  echo
  echo "  backend  → http://localhost:8000  (health: /health)"
  echo "  frontend → http://localhost:5173"
  echo "  app logs → tail -f .stack/backend.log .stack/frontend.log"
  echo "  svc logs → scripts/stack.sh logs"
  echo
  echo "  Note: a real extract/curate run also needs the model + embedding groups —"
  echo "  cd backend && uv sync --group models --group embeddings && uv run alembic upgrade head"
}

cmd_down() {
  echo "▶ app"
  stop_bg frontend
  stop_bg backend
  echo "▶ infra — docker compose down"
  docker compose down
}

cmd_logs() {
  local -a svcs=("$@")
  ((${#svcs[@]})) || svcs=(neo4j postgres)
  exec docker compose logs -f --tail=100 "${svcs[@]}"
}

cmd_status() {
  echo "▶ app processes"
  local name
  for name in backend frontend; do
    if is_alive "$name"; then
      echo "  $name: running (pid $(cat "$run_dir/$name.pid"))"
    else
      echo "  $name: stopped"
    fi
  done
  echo
  echo "▶ infra containers"
  docker compose ps
}

main() {
  set -euo pipefail
  local cmd=${1:-help}
  [[ $# -gt 0 ]] && shift || true
  case $cmd in
    up) cmd_up ;;
    down) cmd_down ;;
    logs) cmd_logs "$@" ;;
    status | ps) cmd_status ;;
    help | -h | --help) usage ;;
    *)
      echo "unknown command: $cmd" >&2
      usage
      exit 2
      ;;
  esac
}

# Run main only when executed directly, so the functions above can be sourced in tests.
if [[ ${BASH_SOURCE[0]} == "${0}" ]]; then
  main "$@"
fi
