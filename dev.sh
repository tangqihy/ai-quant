#!/usr/bin/env bash
# 本地前后端一键启停
#
# 用法:
#   ./dev.sh              # 前台同时跑前后端（Ctrl+C 一起停）
#   ./dev.sh open         # macOS：Terminal 新窗口启动（推荐）
#   ./dev.sh start        # 后台启动（关终端也继续跑）
#   ./dev.sh stop         # 停止后台进程
#   ./dev.sh restart      # 重启后台进程
#   ./dev.sh status
#   ./dev.sh logs [backend|frontend|all]
#   ./dev.sh backend      # 前台只跑后端
#   ./dev.sh frontend     # 前台只跑前端
#
# 依赖:
#   - 项目根目录 .env（至少含 QUANT_AUTH_PASSWORD、TUSHARE_TOKEN）
#   - Python 3.11+ / Node 20+

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEV_DIR="$ROOT_DIR/.dev"
BACKEND_PID_FILE="$DEV_DIR/backend.pid"
FRONTEND_PID_FILE="$DEV_DIR/frontend.pid"
BACKEND_LOG="$DEV_DIR/backend.log"
FRONTEND_LOG="$DEV_DIR/frontend.log"
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"
VENV_DIR="$ROOT_DIR/.venv"

mkdir -p "$DEV_DIR"

# ---------- helpers ----------

log()  { printf '[\033[0;32mdev\033[0m] %s\n' "$*"; }
warn() { printf '[\033[0;33mdev\033[0m] %s\n' "$*" >&2; }
err()  { printf '[\033[0;31mdev\033[0m] %s\n' "$*" >&2; }

load_env() {
  if [[ ! -f "$ROOT_DIR/.env" ]]; then
    err "缺少 $ROOT_DIR/.env"
    err "请先: cp .env.example .env 并填写 QUANT_AUTH_PASSWORD / TUSHARE_TOKEN"
    exit 1
  fi
  set -a
  # shellcheck disable=SC1091
  source "$ROOT_DIR/.env"
  set +a

  if [[ -z "${QUANT_AUTH_PASSWORD:-}" ]]; then
    err ".env 中未设置 QUANT_AUTH_PASSWORD，前端无法登录"
    exit 1
  fi
  if [[ -z "${TUSHARE_TOKEN:-}" ]]; then
    warn ".env 中未设置 TUSHARE_TOKEN，行情/K线接口可能不可用"
  fi
}

ensure_venv() {
  if [[ ! -x "$VENV_DIR/bin/python" ]]; then
    log "创建虚拟环境 .venv ..."
    python3 -m venv "$VENV_DIR"
  fi
  if ! "$VENV_DIR/bin/python" -c "import fastapi, uvicorn" >/dev/null 2>&1; then
    log "安装后端依赖 ..."
    "$VENV_DIR/bin/python" -m pip install -q -r "$ROOT_DIR/requirements.txt"
  fi
}

pnpm_cmd() {
  if command -v pnpm >/dev/null 2>&1; then
    echo "pnpm"
    return
  fi
  echo "npx --yes pnpm@10"
}

ensure_frontend_deps() {
  if [[ ! -d "$ROOT_DIR/frontend/node_modules" ]] || [[ ! -x "$ROOT_DIR/frontend/node_modules/.bin/vite" ]]; then
    log "安装前端依赖 ..."
    (
      cd "$ROOT_DIR/frontend"
      export npm_config_cache="${npm_config_cache:-/tmp/ai-quant-npm-cache}"
      # shellcheck disable=SC2086
      $(pnpm_cmd) install
    )
  fi
}

vite_bin() {
  echo "$ROOT_DIR/frontend/node_modules/.bin/vite"
}

pid_alive() {
  local pid="${1:-}"
  [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null
}

read_pid() {
  local file="$1"
  if [[ -f "$file" ]]; then
    tr -d '[:space:]' <"$file"
  fi
}

port_pids() {
  local port="$1"
  lsof -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null || true
}

kill_port() {
  local port="$1"
  local pids
  pids="$(port_pids "$port")"
  if [[ -n "$pids" ]]; then
    # shellcheck disable=SC2086
    kill $pids 2>/dev/null || true
    sleep 0.3
    pids="$(port_pids "$port")"
    if [[ -n "$pids" ]]; then
      # shellcheck disable=SC2086
      kill -9 $pids 2>/dev/null || true
    fi
  fi
}

stop_pid_file() {
  local name="$1"
  local file="$2"
  local port="$3"
  local pid
  pid="$(read_pid "$file")"
  if pid_alive "$pid"; then
    log "停止 $name (pid=$pid) ..."
    # uvicorn --reload 会有子进程，先杀进程组
    kill -- -"$pid" 2>/dev/null || kill "$pid" 2>/dev/null || true
    for _ in 1 2 3 4 5; do
      pid_alive "$pid" || break
      sleep 0.2
    done
    pid_alive "$pid" && kill -9 "$pid" 2>/dev/null || true
  fi
  rm -f "$file"
  kill_port "$port"
}

# ---------- launch commands ----------

backend_cmd() {
  # 输出可直接 exec 的命令参数（通过 bash -c）
  printf '%s' "cd \"$ROOT_DIR\" && export PYTHONPATH=\"$ROOT_DIR\" && set -a && source \"$ROOT_DIR/.env\" && set +a && exec \"$VENV_DIR/bin/python\" -m uvicorn app.main:app --reload --host 0.0.0.0 --port \"$BACKEND_PORT\""
}

frontend_cmd() {
  local vb
  vb="$(vite_bin)"
  printf '%s' "cd \"$ROOT_DIR/frontend\" && exec \"$vb\" --host 0.0.0.0 --port \"$FRONTEND_PORT\""
}

# 后台启动并脱离当前 shell
run_detached() {
  local pid_file="$1"
  local log_file="$2"
  local cmd="$3"

  # macOS 无 setsid 时用 nohup；用独立 bash 进程 + disown
  nohup bash -c "$cmd" >"$log_file" 2>&1 < /dev/null &
  local pid=$!
  echo "$pid" >"$pid_file"
  disown "$pid" 2>/dev/null || true
}

start_backend_bg() {
  local pid
  pid="$(read_pid "$BACKEND_PID_FILE")"
  if pid_alive "$pid"; then
    log "后端已在运行 (pid=$pid) http://localhost:$BACKEND_PORT"
    return
  fi
  ensure_venv
  kill_port "$BACKEND_PORT"
  : >"$BACKEND_LOG"
  log "启动后端 -> http://localhost:$BACKEND_PORT"
  run_detached "$BACKEND_PID_FILE" "$BACKEND_LOG" "$(backend_cmd)"
  sleep 1
  pid="$(read_pid "$BACKEND_PID_FILE")"
  if pid_alive "$pid"; then
    log "后端已启动 (pid=$pid)，日志: $BACKEND_LOG"
  else
    err "后端启动失败，请查看 $BACKEND_LOG"
    exit 1
  fi
}

start_frontend_bg() {
  local pid vb
  vb="$(vite_bin)"
  pid="$(read_pid "$FRONTEND_PID_FILE")"
  if pid_alive "$pid"; then
    log "前端已在运行 (pid=$pid) http://localhost:$FRONTEND_PORT"
    return
  fi
  ensure_frontend_deps
  if [[ ! -x "$vb" ]]; then
    err "未找到 $vb"
    exit 1
  fi
  kill_port "$FRONTEND_PORT"
  : >"$FRONTEND_LOG"
  log "启动前端 -> http://localhost:$FRONTEND_PORT"
  run_detached "$FRONTEND_PID_FILE" "$FRONTEND_LOG" "$(frontend_cmd)"
  sleep 1.2
  pid="$(read_pid "$FRONTEND_PID_FILE")"
  if pid_alive "$pid"; then
    log "前端已启动 (pid=$pid)，日志: $FRONTEND_LOG"
  else
    err "前端启动失败，请查看 $FRONTEND_LOG"
    exit 1
  fi
}

print_ready() {
  echo
  log "全部就绪"
  log "  前端: http://localhost:$FRONTEND_PORT"
  log "  后端: http://localhost:$BACKEND_PORT"
  log "  文档: http://localhost:$BACKEND_PORT/docs"
  log "  登录密码: .env 中的 QUANT_AUTH_PASSWORD"
}

# 前台同时跑（推荐）：当前终端保持打开，Ctrl+C 一起停
cmd_run() {
  load_env
  ensure_venv
  ensure_frontend_deps

  # 若已有后台实例，先停掉避免端口冲突
  stop_pid_file "后端" "$BACKEND_PID_FILE" "$BACKEND_PORT" >/dev/null 2>&1 || true
  stop_pid_file "前端" "$FRONTEND_PID_FILE" "$FRONTEND_PORT" >/dev/null 2>&1 || true
  kill_port "$BACKEND_PORT"
  kill_port "$FRONTEND_PORT"

  : >"$BACKEND_LOG"
  : >"$FRONTEND_LOG"

  local backend_pid frontend_pid

  cleanup() {
    trap - INT TERM EXIT
    echo
    log "正在停止..."
    if [[ -n "${backend_pid:-}" ]]; then
      kill -- -"$backend_pid" 2>/dev/null || kill "$backend_pid" 2>/dev/null || true
    fi
    if [[ -n "${frontend_pid:-}" ]]; then
      kill "$frontend_pid" 2>/dev/null || true
    fi
    kill_port "$BACKEND_PORT"
    kill_port "$FRONTEND_PORT"
    rm -f "$BACKEND_PID_FILE" "$FRONTEND_PID_FILE"
    log "已停止"
    exit 0
  }
  trap cleanup INT TERM

  log "启动后端 -> http://localhost:$BACKEND_PORT"
  bash -c "$(backend_cmd)" >>"$BACKEND_LOG" 2>&1 &
  backend_pid=$!
  echo "$backend_pid" >"$BACKEND_PID_FILE"

  log "启动前端 -> http://localhost:$FRONTEND_PORT"
  bash -c "$(frontend_cmd)" >>"$FRONTEND_LOG" 2>&1 &
  frontend_pid=$!
  echo "$frontend_pid" >"$FRONTEND_PID_FILE"

  sleep 1.2
  if ! pid_alive "$backend_pid"; then
    err "后端启动失败，请查看 $BACKEND_LOG"
    cleanup
  fi
  if ! pid_alive "$frontend_pid"; then
    err "前端启动失败，请查看 $FRONTEND_LOG"
    cleanup
  fi

  print_ready
  log "日志实时输出中（Ctrl+C 停止）"
  echo

  # 实时合并输出日志
  touch "$BACKEND_LOG" "$FRONTEND_LOG"
  tail -n +1 -f "$BACKEND_LOG" "$FRONTEND_LOG" 2>/dev/null &
  local tail_pid=$!

  # 任一服务退出则整体退出
  while pid_alive "$backend_pid" && pid_alive "$frontend_pid"; do
    sleep 1
  done

  kill "$tail_pid" 2>/dev/null || true
  if ! pid_alive "$backend_pid"; then
    err "后端已退出，请查看 $BACKEND_LOG"
  fi
  if ! pid_alive "$frontend_pid"; then
    err "前端已退出，请查看 $FRONTEND_LOG"
  fi
  cleanup
}

cmd_start() {
  load_env
  start_backend_bg
  start_frontend_bg
  print_ready
  log "后台模式。停止: ./dev.sh stop   日志: ./dev.sh logs"
}

cmd_stop() {
  stop_pid_file "后端" "$BACKEND_PID_FILE" "$BACKEND_PORT"
  stop_pid_file "前端" "$FRONTEND_PID_FILE" "$FRONTEND_PORT"
  log "已停止"
}

cmd_status() {
  local bpid fpid
  bpid="$(read_pid "$BACKEND_PID_FILE")"
  fpid="$(read_pid "$FRONTEND_PID_FILE")"

  if pid_alive "$bpid"; then
    log "后端: 运行中 pid=$bpid  http://localhost:$BACKEND_PORT"
  elif [[ -n "$(port_pids "$BACKEND_PORT")" ]]; then
    log "后端: 端口 $BACKEND_PORT 被占用（非本脚本启动）"
  else
    log "后端: 未运行"
  fi

  if pid_alive "$fpid"; then
    log "前端: 运行中 pid=$fpid  http://localhost:$FRONTEND_PORT"
  elif [[ -n "$(port_pids "$FRONTEND_PORT")" ]]; then
    log "前端: 端口 $FRONTEND_PORT 被占用（非本脚本启动）"
  else
    log "前端: 未运行"
  fi
}

cmd_logs() {
  local target="${1:-all}"
  case "$target" in
    backend|be|b)
      [[ -f "$BACKEND_LOG" ]] || { err "无后端日志"; exit 1; }
      exec tail -n 80 -f "$BACKEND_LOG"
      ;;
    frontend|fe|f)
      [[ -f "$FRONTEND_LOG" ]] || { err "无前端日志"; exit 1; }
      exec tail -n 80 -f "$FRONTEND_LOG"
      ;;
    all|*)
      touch "$BACKEND_LOG" "$FRONTEND_LOG"
      log "跟踪日志（Ctrl+C 退出）"
      trap 'kill 0' INT TERM
      tail -n 40 -f "$BACKEND_LOG" | sed 's/^/[backend] /' &
      tail -n 40 -f "$FRONTEND_LOG" | sed 's/^/[frontend] /' &
      wait
      ;;
  esac
}

run_backend_fg() {
  ensure_venv
  kill_port "$BACKEND_PORT"
  log "前台启动后端 http://localhost:$BACKEND_PORT （Ctrl+C 退出）"
  bash -c "$(backend_cmd)"
}

run_frontend_fg() {
  local vb
  vb="$(vite_bin)"
  ensure_frontend_deps
  if [[ ! -x "$vb" ]]; then
    err "未找到 $vb"
    exit 1
  fi
  kill_port "$FRONTEND_PORT"
  log "前台启动前端 http://localhost:$FRONTEND_PORT （Ctrl+C 退出）"
  bash -c "$(frontend_cmd)"
}

# macOS：在系统 Terminal 新窗口中前台启动（最稳妥）
cmd_open() {
  if [[ "$(uname -s)" != "Darwin" ]]; then
    err "open 仅支持 macOS，请直接运行: ./dev.sh"
    exit 1
  fi
  load_env
  osascript <<EOF
tell application "Terminal"
  do script "cd $(printf %q "$ROOT_DIR") && exec ./dev.sh"
  activate
end tell
EOF
  log "已在 Terminal 新窗口中启动"
  log "  前端: http://localhost:$FRONTEND_PORT"
  log "  后端: http://localhost:$BACKEND_PORT"
}

usage() {
  cat <<'EOF'
本地开发启停脚本

用法:
  ./dev.sh              前台同时跑前后端（推荐，Ctrl+C 一起停）
  ./dev.sh open         macOS：在 Terminal 新窗口启动（推荐）
  ./dev.sh start        后台启动（关终端也继续跑）
  ./dev.sh stop         停止后台进程
  ./dev.sh restart      重启后台进程
  ./dev.sh status
  ./dev.sh logs [backend|frontend|all]
  ./dev.sh backend      前台只跑后端
  ./dev.sh frontend     前台只跑前端

环境:
  读取项目根目录 .env（需 QUANT_AUTH_PASSWORD、TUSHARE_TOKEN）
  端口可用 BACKEND_PORT / FRONTEND_PORT 覆盖（默认 8000 / 5173）
EOF
}

# ---------- main ----------

cmd="${1:-run}"
shift || true

case "$cmd" in
  run|fg)
    cmd_run
    ;;
  open|terminal)
    cmd_open
    ;;
  start|up|daemon|bg)
    cmd_start
    ;;
  stop|down)
    cmd_stop
    ;;
  restart)
    cmd_stop
    cmd_start
    ;;
  status)
    cmd_status
    ;;
  logs|log)
    cmd_logs "${1:-all}"
    ;;
  backend|be|api)
    load_env
    run_backend_fg
    ;;
  frontend|fe|web)
    load_env
    run_frontend_fg
    ;;
  -h|--help|help)
    usage
    ;;
  *)
    err "未知命令: $cmd"
    usage
    exit 1
    ;;
esac
