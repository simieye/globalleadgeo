#!/bin/zsh
# 本地服务启动脚本（前台运行，供原生 App 拉起 / 命令行调用）
# 首次运行在 ~/Library/Application Support/GlobalEagleGEO 创建虚拟环境并离线安装依赖，
# 随后以 exec 方式前台运行 uvicorn（父进程退出时服务随之结束）。
set -u

HERE=${0:A:h}
APP_DIR="$HERE/app"
WHEELS="$HERE/wheels"
SUP="$HOME/Library/Application Support/GlobalEagleGEO"
VENV="$SUP/venv"
DATA="$SUP/data"
LOG="$SUP/server.log"
PORT="${GEO_PORT:-8787}"

mkdir -p "$SUP" "$DATA"

PY=""
for c in python3.14 python3.13 python3.12 python3.11 python3.10 python3; do
  if command -v "$c" >/dev/null 2>&1; then PY="$c"; break; fi
done
if [ -z "$PY" ]; then
  echo "[server.sh] 未找到 Python 3.10+，请先安装：https://www.python.org/downloads/" >>"$LOG"
  exit 1
fi

install_deps() {
  if [ -d "$WHEELS" ] && [ -n "$(ls -A "$WHEELS" 2>/dev/null)" ]; then
    "$VENV/bin/python" -m pip install --no-index --find-links "$WHEELS" \
      -r "$APP_DIR/requirements.txt" >>"$LOG" 2>&1
    if "$VENV/bin/python" -c "import fastapi, uvicorn, pydantic" >/dev/null 2>&1; then
      return 0
    fi
  fi
  # 离线 wheel 与本机型 / Python 版本不匹配时，退化为联网安装
  "$VENV/bin/python" -m pip install -r "$APP_DIR/requirements.txt" >>"$LOG" 2>&1
}

if [ ! -x "$VENV/bin/python" ]; then
  echo "[server.sh] 创建虚拟环境：$VENV" >>"$LOG"
  "$PY" -m venv "$VENV" >>"$LOG" 2>&1
  install_deps
fi

if [ ! -x "$VENV/bin/python" ]; then
  echo "[server.sh] 依赖安装失败，详见日志：$LOG" >>"$LOG"
  exit 1
fi

export GEO_DATA_DIR="$DATA"
export PYTHONPATH="$APP_DIR"
cd "$APP_DIR" || exit 1
exec "$VENV/bin/python" -m uvicorn backend.main:app --host 127.0.0.1 --port "$PORT"
