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
#   后端: 无 apps/server/.venv 时会自动 python -m venv 并 pip install -e ".[dev]"
#   前端: 无 apps/web/node_modules 时会自动 npm install
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

case "$(uname -s)" in
  MINGW* | MSYS* | CYGWIN*) IS_WIN=1 ;;
  *) IS_WIN=0 ;;
esac

if [ "$IS_WIN" = 1 ]; then
  PY="$SERVER_DIR/.venv/Scripts/python.exe"
else
  PY="$SERVER_DIR/.venv/bin/python"
fi

log() { printf '\033[36m[dev]\033[0m %s\n' "$*"; }
err() { printf '\033[31m[dev]\033[0m %s\n' "$*" >&2; }

# 与 vscode.py _WSL_DETECT 保持同一组候选（官方 standalone + 旧路径）
WSL_CODE_SERVER_DETECT='for p in "$HOME/.local/bin/code-server" "$HOME/.local/code-server/bin/code-server" /usr/bin/code-server /usr/lib/code-server/bin/code-server; do [ -x "$p" ] && echo "$p" && exit 0; done; exit 1'
CODE_SERVER_INSTALL_SH='curl -fsSL https://code-server.dev/install.sh | sh -s -- --method=standalone'

prepend_local_bin_path() {
  local local_bin="$HOME/.local/bin"
  case ":$PATH:" in
    *":$local_bin:"*) ;;
    *) export PATH="$local_bin:$PATH" ;;
  esac
}

code_server_broken_windows_npm() {
  local bin="${1:-}" dir pkg
  [ -n "$bin" ] || return 1
  dir="$(cd "$(dirname "$bin")" 2>/dev/null && pwd)" || dir="$(dirname "$bin")"
  pkg="$dir/node_modules/code-server"
  [ -d "$pkg" ] || return 1
  [ -f "$pkg/out/node/entry.js" ] && return 1
  return 0
}

detect_wsl_code_server() {
  local p=""
  command -v wsl.exe >/dev/null 2>&1 || return 1
  p="$(
    wsl.exe --exec /bin/bash --noprofile --norc -c "$WSL_CODE_SERVER_DETECT" \
      2>/dev/null | tr -d '\r' | tail -n 1
  )"
  [ -n "$p" ] || return 1
  printf '%s\n' "$p"
}

wsl_linux_bin_exists() {
  local linux="${1:-}"
  [ -n "$linux" ] || return 1
  command -v wsl.exe >/dev/null 2>&1 || return 1
  wsl.exe --exec /bin/bash --noprofile --norc -c "[ -x \"$linux\" ]" >/dev/null 2>&1
}

detect_native_code_server() {
  local configured="${PLATFORM_CODE_SERVER_BIN:-}" cand found=""
  if [ -n "$configured" ] && [ "${configured#wsl:}" = "$configured" ]; then
    if [ -f "$configured" ] && ! code_server_broken_windows_npm "$configured"; then
      printf '%s\n' "$configured"
      return 0
    fi
  fi
  for cand in "$HOME/.local/bin/code-server" "$HOME/.local/code-server/bin/code-server"; do
    if [ -f "$cand" ]; then
      printf '%s\n' "$cand"
      return 0
    fi
  done
  found="$(command -v code-server 2>/dev/null || true)"
  if [ -n "$found" ] && ! code_server_broken_windows_npm "$found"; then
    printf '%s\n' "$found"
    return 0
  fi
  if [ "$IS_WIN" = 1 ]; then
    found="$(command -v code-server.cmd 2>/dev/null || true)"
    if [ -n "$found" ] && ! code_server_broken_windows_npm "$found"; then
      printf '%s\n' "$found"
      return 0
    fi
  fi
  return 1
}

detect_usable_code_server() {
  local configured="${PLATFORM_CODE_SERVER_BIN:-}" linux p
  if [ -n "$configured" ] && [ "${configured#wsl:}" != "$configured" ]; then
    linux="${configured#wsl:}"
    if [ -n "$linux" ]; then
      if wsl_linux_bin_exists "$linux"; then
        printf 'wsl:%s\n' "$linux"
        return 0
      fi
    else
      p="$(detect_wsl_code_server || true)"
      if [ -n "$p" ]; then
        printf 'wsl:%s\n' "$p"
        return 0
      fi
    fi
  elif [ -n "$configured" ] && [ "${configured#wsl:}" = "$configured" ]; then
    if [ -f "$configured" ] && ! code_server_broken_windows_npm "$configured"; then
      printf '%s\n' "$configured"
      return 0
    fi
  fi
  if [ "$IS_WIN" = 1 ]; then
    p="$(detect_wsl_code_server || true)"
    if [ -n "$p" ]; then
      printf 'wsl:%s\n' "$p"
      return 0
    fi
  fi
  detect_native_code_server
}

run_with_optional_timeout() {
  if [ -x /usr/bin/timeout ]; then
    /usr/bin/timeout 600 "$@"
  else
    "$@"
  fi
}

install_code_server_standalone() {
  if [ "$IS_WIN" = 1 ]; then
    if ! command -v wsl.exe >/dev/null 2>&1; then
      log "未检测到 WSL，无法自动安装 code-server。请安装 WSL 后重新 start，或设置 PLATFORM_CODE_SERVER_BIN。网页仍可使用（无 VS Code 页签）。"
      return 0
    fi
    log "正在 WSL 中安装 code-server（standalone，可能需要几分钟）…"
    if ! run_with_optional_timeout wsl.exe --exec /bin/bash --noprofile --norc -c \
      "$CODE_SERVER_INSTALL_SH"; then
      err "WSL 中安装 code-server 失败。可手工执行: wsl --exec bash -lc '$CODE_SERVER_INSTALL_SH'"
    fi
    return 0
  fi
  log "正在安装 code-server（standalone → ~/.local，可能需要几分钟）…"
  if ! run_with_optional_timeout bash -c "$CODE_SERVER_INSTALL_SH"; then
    err "安装 code-server 失败。可手工执行: $CODE_SERVER_INSTALL_SH"
  fi
  return 0
}

ensure_code_server() {
  prepend_local_bin_path
  local found
  found="$(detect_usable_code_server || true)"
  if [ -n "$found" ]; then
    log "VS Code 页签: 使用 $found"
    return 0
  fi
  log "未检测到可用 code-server，尝试自动安装"
  install_code_server_standalone
  prepend_local_bin_path
  found="$(detect_usable_code_server || true)"
  if [ -n "$found" ]; then
    log "VS Code 页签: 使用 $found"
    return 0
  fi
  log "提示: 未检测到可用 code-server，VS Code 页签可能不可用；文件/聊天正常"
  return 0
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

pick_host_python() {
  local cand
  for cand in python3 python; do
    if command -v "$cand" >/dev/null 2>&1 \
      && "$cand" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)' 2>/dev/null; then
      printf '%s\n' "$cand"
      return 0
    fi
  done
  err "需要 Python 3.11+（PATH 中的 python3 或 python）才能创建 $SERVER_DIR/.venv"
  return 1
}

ensure_server_venv() {
  if [ -f "$PY" ]; then
    return 0
  fi
  local host
  host="$(pick_host_python)" || return 1
  log "未找到虚拟环境，正在创建 $SERVER_DIR/.venv"
  if ! "$host" -m venv "$SERVER_DIR/.venv"; then
    err "创建虚拟环境失败"
    return 1
  fi
  if [ ! -f "$PY" ]; then
    err "venv 已创建但未找到 $PY"
    return 1
  fi
  log "安装后端依赖: pip install -e \".[dev]\""
  if ! (cd "$SERVER_DIR" && "$PY" -m pip install -e ".[dev]"); then
    err "安装后端依赖失败"
    return 1
  fi
}

start_server() {
  if port_up 8000; then
    log "后端已在运行 (:8000)"
    return 0
  fi
  if ! ensure_server_venv; then
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

ensure_web_deps() {
  if [ -d "$WEB_DIR/node_modules" ]; then
    return 0
  fi
  if ! command -v npm >/dev/null 2>&1; then
    err "需要 Node.js 18+（PATH 中能跑 npm）才能安装前端依赖"
    return 1
  fi
  log "未找到前端依赖，正在 npm install（$WEB_DIR）"
  if ! (cd "$WEB_DIR" && npm install); then
    err "npm install 失败"
    return 1
  fi
}

start_web() {
  if port_up 5173; then
    log "前端已在运行 (:5173)"
    return 0
  fi
  if ! ensure_web_deps; then
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
  ensure_code_server
  start_server || return 1
  start_web || { err "前端启动失败（后端保持运行，可用 ./dev.sh stop 全停）"; return 1; }
  log "全部就绪 → 浏览器打开 http://localhost:5173"
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
