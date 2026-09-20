#!/usr/bin/env bash
# 启动全球鹰 GEO 全球AI推荐系统
set -e
cd "$(dirname "$0")"
export PYTHONPATH="$(pwd)"
python3 -m uvicorn backend.main:app --host 127.0.0.1 --port 8787
