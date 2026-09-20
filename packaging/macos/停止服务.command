#!/bin/zsh
# 双击停止本地 GEO 服务
pkill -f "uvicorn backend.main:app" >/dev/null 2>&1
if [ $? -eq 0 ]; then
  osascript -e 'display notification "全球鹰 GEO 服务已停止" with title "Global Eagle GEO"' >/dev/null 2>&1 || true
  echo "服务已停止。"
else
  echo "未发现运行中的服务。"
fi
