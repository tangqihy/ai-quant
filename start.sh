#!/bin/bash
# 设置项目根目录为 PYTHONPATH，确保 app 模块可被导入
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PYTHONPATH="$SCRIPT_DIR"
export QUANT_AUTH_PASSWORD="tangqi2024"
cd "$SCRIPT_DIR"
exec python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
