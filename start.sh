#!/bin/bash
# Agora — 一键启动脚本
# 同时启动后端 (FastAPI, port 8001) 和前端 (Vite dev, port 5173)

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
FRONTEND_DIR="$ROOT_DIR/frontend"
BACKEND_SCRIPT="$ROOT_DIR/run_web.py"
BACKEND_PID=""
FRONTEND_PID=""
CLEANUP_EXIT_CODE=0
BACKEND_PYTHON=""

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

cleanup() {
  echo ""
  echo -e "${YELLOW}正在关闭服务…${NC}"
  if [ -n "${BACKEND_PID}" ]; then
    kill "$BACKEND_PID" 2>/dev/null || true
    wait "$BACKEND_PID" 2>/dev/null || true
  fi
  if [ -n "${FRONTEND_PID}" ]; then
    kill "$FRONTEND_PID" 2>/dev/null || true
    wait "$FRONTEND_PID" 2>/dev/null || true
  fi
  echo -e "${GREEN}已关闭。${NC}"
  exit "$CLEANUP_EXIT_CODE"
}

fail() {
  echo ""
  echo -e "${RED}$1${NC}"
  CLEANUP_EXIT_CODE=1
  cleanup
}

trap 'CLEANUP_EXIT_CODE=0; cleanup' SIGINT SIGTERM

if [ -f "$ROOT_DIR/.env" ]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT_DIR/.env"
  set +a
fi

python_has_backend_deps() {
  "$1" - <<'PY' >/dev/null 2>&1
import fastapi
import semantic_kernel
import uvicorn
PY
}

select_backend_python() {
  if [ -n "${AGORA_PYTHON:-}" ]; then
    if python_has_backend_deps "$AGORA_PYTHON"; then
      BACKEND_PYTHON="$AGORA_PYTHON"
      return
    fi
    fail "指定的 AGORA_PYTHON 缺少后端依赖，请确认已安装 fastapi / semantic-kernel / uvicorn。"
  fi

  for candidate in \
    "$ROOT_DIR/.venv/bin/python3" \
    "$ROOT_DIR/.venv/bin/python" \
    "python3.11" \
    "python3"; do
    if command -v "$candidate" >/dev/null 2>&1 && python_has_backend_deps "$candidate"; then
      BACKEND_PYTHON="$candidate"
      return
    fi
  done

  fail "未找到可运行后端的 Python。请先安装依赖，或用 AGORA_PYTHON=/path/to/python ./start.sh 指定解释器。"
}

# --- 检查前端依赖 ---
if [ ! -d "$FRONTEND_DIR/node_modules" ]; then
  echo -e "${CYAN}首次运行，安装前端依赖…${NC}"
  cd "$FRONTEND_DIR" && npm install
  cd "$ROOT_DIR"
fi

# --- 启动后端 ---
echo -e "${CYAN}启动后端 (http://localhost:8001)…${NC}"
cd "$ROOT_DIR"
export PYTHONUNBUFFERED=1
export AGORA_LOG_LEVEL="${AGORA_LOG_LEVEL:-INFO}"
select_backend_python
echo -e "  后端日志级别: ${AGORA_LOG_LEVEL}"
echo -e "  Python: $("${BACKEND_PYTHON}" -c 'import sys; print(sys.executable)')"
"$BACKEND_PYTHON" -u "$BACKEND_SCRIPT" &
BACKEND_PID=$!

# 等后端真正就绪（最多 15 秒）
echo -n "  等待后端就绪"
for i in $(seq 1 30); do
  if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
    fail "后端进程已退出，请查看上方 Python / uvicorn 错误。"
  fi
  if curl -s http://localhost:8001/api/reports > /dev/null 2>&1; then
    echo -e " ${GREEN}✓${NC}"
    break
  fi
  echo -n "."
  sleep 0.5
  if [ "$i" -eq 30 ]; then
    fail "后端 15 秒内未就绪：http://localhost:8001/api/reports 无响应。"
  fi
done

# --- 启动前端 ---
echo -e "${CYAN}启动前端 (http://localhost:5173)…${NC}"
cd "$FRONTEND_DIR"
npx vite --host 0.0.0.0 --port 5173 --strictPort &
FRONTEND_PID=$!

# 等前端真正就绪（最多 15 秒）。使用 --strictPort，避免 Vite 自动切到 5174 但脚本仍打印 5173。
echo -n "  等待前端就绪"
for i in $(seq 1 30); do
  if ! kill -0 "$FRONTEND_PID" 2>/dev/null; then
    fail "前端进程已退出，可能是 5173 端口被占用或 Vite 启动失败。"
  fi
if curl -s http://localhost:5173/ > /dev/null 2>&1; then
    echo -e " ${GREEN}✓${NC}"
    break
  fi
  echo -n "."
  sleep 0.5
  if [ "$i" -eq 30 ]; then
    fail "前端 15 秒内未就绪：http://localhost:5173 无响应。"
  fi
done

echo -n "  预热前端模块"
curl -s http://localhost:5173/src/main.tsx > /dev/null 2>&1 || true
curl -s http://localhost:5173/src/App.tsx > /dev/null 2>&1 || true
echo -e " ${GREEN}✓${NC}"

echo ""
echo -e "${GREEN}======================================${NC}"
echo -e "${GREEN}  Agora 已启动！${NC}"
echo -e "${GREEN}======================================${NC}"
echo -e "  前端:  ${CYAN}http://localhost:5173${NC}"
echo -e "  后端:  ${CYAN}http://localhost:8001${NC}"
echo -e "  ${YELLOW}按 Ctrl+C 停止所有服务${NC}"
echo ""

while true; do
  if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
    fail "后端进程已退出。"
  fi
  if ! kill -0 "$FRONTEND_PID" 2>/dev/null; then
    fail "前端进程已退出。"
  fi
  sleep 1
done
