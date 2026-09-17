#!/usr/bin/env bash
# dev.sh —— 接口测试平台本地前后端一键启停（Windows Git Bash / Linux 通用）
#
# 用法:
#   ./dev.sh start            启动后端(uvicorn :8000) + 前端(vite :5173)
#   ./dev.sh stop             停止全部
#   ./dev.sh restart          重启
#   ./dev.sh status           查看运行状态
#   ./dev.sh logs server      跟踪后端日志（Ctrl+C 退出，不影响服务）
#   ./dev.sh logs web         跟踪前端日志
#
# 进程管理以端口为唯一标识（8000/5173 为平台专用端口）：
# 停止时按端口定位真实 PID 并整树终止（npm→node 层级必需）。
#
# 前提:
#   后端: apps/server/.venv 已存在（否则: cd apps/server && python -m venv .venv
#         && .venv/Scripts/pip install -e ".[dev]"）
#   前端: apps/web/node_modules 已存在（否则: cd apps/web && npm install）
#
# 测试会话可用的 demo 仓库: D:/workgit/demo-test-repo
#   base=master  feature=feature/add-empty-order-fallback

set -uo pipefail

APPS_DIR="$(cd "$(dirname "$0")" && pwd)"
SERVER_DIR="$APPS_DIR/server"
WEB_DIR="$APPS_DIR/web"
RUN_DIR="$APPS_DIR/.dev"
LOG_DIR="$RUN_DIR/logs"
mkdir -p "$LOG_DIR"

SERVER_LOG="$LOG_DIR/server.log"
WEB_LOG="$LOG_DIR/web.log"
PY="$SERVER_DIR/.venv/Scripts/python.exe"

case "$(uname -s)" in
  MINGW* | MSYS* | CYGWIN*) IS_WIN=1 ;;
  *) IS_WIN=0 ;;
esac

log() { printf '\033[36m[dev]\033[0m %s\n' "$*"; }
err() { printf '\033[31m[dev]\033[0m %s\n' "$*" >&2; }

# Windows 上 PATH 里的 npm code-server 往往残缺；优先看 WSL ~/.local/code-server
code_server_hint() {
  local p=""
  if command -v wsl.exe >/dev/null 2>&1; then
    p="$(
      wsl.exe --exec /bin/bash --noprofile --norc -c \
        'for p in "$HOME/.local/code-server/bin/code-server" /usr/bin/code-server /usr/lib/code-server/bin/code-server; do [ -x "$p" ] && echo "$p" && exit 0; done; exit 1' \
        2>/dev/null | tr -d '\r' | tail -n 1
    )"
  fi
  if [ -n "$p" ]; then
    log "VS Code 页签: 使用 WSL code-server ($p)"
    return 0
  fi
  if command -v code-server >/dev/null 2>&1; then
    log "VS Code 页签: 使用 PATH 中的 code-server"
    return 0
  fi
  log "提示: 未检测到可用 code-server，VS Code 页签可能不可用；文件/聊天正常"
}

# 监听指定端口的进程 PID 列表（去重，可能为空）
pids_of_port() { # $1=端口
  if [ "$IS_WIN" = 1 ]; then
    netstat -ano 2>/dev/null | grep ":$1 " | grep LISTENING | awk '{print $NF}' | sort -u
  else
    ss -ltnp 2>/dev/null | grep ":$1 " | grep -oP 'pid=\K[0-9]+' | sort -u
  fi
}

port_up() { # $1=端口
  [ -n "$(pids_of_port "$1")" ]
}

kill_tree() { # $1=pid（杀整棵进程树，npm→node 层级必需）
  if [ "$IS_WIN" = 1 ]; then
    taskkill //PID "$1" //T //F >/dev/null 2>&1 || true
  else
    kill -- "-$1" 2>/dev/null || kill "$1" 2>/dev/null || true
  fi
}

stop_port() { # $1=端口 $2=服务名
  local pids p
  pids="$(pids_of_port "$1")"
  if [ -z "$pids" ]; then
    log "$2 未在运行"
    return 0
  fi
  for p in $pids; do
    log "停止 $2 (pid $p, :$1) ..."
    kill_tree "$p"
  done
}

wait_url() { # $1=url $2=超时秒 $3=服务名
  local i=0 max=$(( $2 * 2 ))
  while [ "$i" -lt "$max" ]; do
    if curl -s -m 2 -o /dev/null "$1"; then
      log "$3 就绪: $1"
      return 0
    fi
    sleep 0.5
    i=$((i + 1))
  done
  return 1
}

start_server() {
  if port_up 8000; then
    log "后端已在运行 (:8000)"
    return 0
  fi
  if [ ! -f "$PY" ]; then
    err "未找到 $PY —— 请先: cd apps/server && python -m venv .venv && .venv/Scripts/pip install -e \".[dev]\""
    return 1
  fi
  log "启动后端 uvicorn :8000（--reload，日志 $SERVER_LOG）"
  if [ ! -f "$SERVER_DIR/platform.yaml" ]; then
    log "未找到 platform.yaml，将使用隔离的默认 Claude home（仓库 skills、无 MCP）。生产请复制 platform.yaml.example"
  fi
  LOOP_ARG=()
  if [ "$IS_WIN" = 1 ]; then
    LOOP_ARG=(--loop app.windows_loop:new_proactor)
  fi
  (
    cd "$SERVER_DIR"
    nohup "$PY" -m uvicorn app.main:create_app --factory --reload --reload-dir app --port 8000 "${LOOP_ARG[@]}" >"$SERVER_LOG" 2>&1 &
  )
  if ! wait_url "http://localhost:8000/api/health" 30 后端; then
    err "后端 30s 内未就绪，查看日志: ./dev.sh logs server"
    return 1
  fi
}

start_web() {
  if port_up 5173; then
    log "前端已在运行 (:5173)"
    return 0
  fi
  if [ ! -d "$WEB_DIR/node_modules" ]; then
    err "未找到 $WEB_DIR/node_modules —— 请先: cd apps/web && npm install"
    return 1
  fi
  log "启动前端 vite :5173（日志 $WEB_LOG）"
  (
    cd "$WEB_DIR"
    nohup npm run dev >"$WEB_LOG" 2>&1 &
  )
  if ! wait_url "http://localhost:5173" 30 前端; then
    err "前端 30s 内未就绪，查看日志: ./dev.sh logs web"
    return 1
  fi
}

cmd_start() {
  start_server || return 1
  start_web || { err "前端启动失败（后端保持运行，可用 ./dev.sh stop 全停）"; return 1; }
  log "全部就绪 → 浏览器打开 http://localhost:5173"
  code_server_hint
}

cmd_stop() {
  stop_port 5173 前端
  stop_port 8000 后端
  sleep 1
  local still=0
  port_up 5173 && { log "警告: 5173 仍被占用"; still=1; }
  port_up 8000 && { log "警告: 8000 仍被占用"; still=1; }
  [ "$still" = 0 ] && log "已全部停止"
}

cmd_status() {
  local pids
  if port_up 8000; then
    pids="$(pids_of_port 8000 | xargs)"
    log "后端: 运行中 (pid $pids, :8000)"
  else
    log "后端: 未运行"
  fi
  if port_up 5173; then
    pids="$(pids_of_port 5173 | xargs)"
    log "前端: 运行中 (pid $pids, :5173)"
  else
    log "前端: 未运行"
  fi
}

cmd="${1:-}"
case "$cmd" in
  start) cmd_start ;;
  stop) cmd_stop ;;
  restart) cmd_stop; cmd_start ;;
  status) cmd_status ;;
  logs)
    case "${2:-}" in
      server) [ -f "$SERVER_LOG" ] && tail -f "$SERVER_LOG" || err "暂无后端日志" ;;
      web) [ -f "$WEB_LOG" ] && tail -f "$WEB_LOG" || err "暂无前端日志" ;;
      *) err "用法: ./dev.sh logs server|web" ;;
    esac
    ;;
  *)
    sed -n '2,15p' "$0" | sed 's/^# \{0,1\}//'
    ;;
esac
