#!/usr/bin/env bash
# 部署验证脚本：检查 /health 和 /api/stocks 是否正常
# 用法: ./scripts/verify_deploy.sh [BASE_URL]
# 默认 BASE_URL=http://localhost:8000

set -e
BASE_URL="${1:-http://localhost:8000}"

echo ">>> 检查 $BASE_URL/health"
resp=$(curl -s -o /tmp/health.json -w "%{http_code}" "$BASE_URL/health")
if [ "$resp" != "200" ]; then
  echo "FAIL: /health 返回 $resp"
  cat /tmp/health.json
  exit 1
fi
echo "OK: $(cat /tmp/health.json)"

echo ""
echo ">>> 检查 $BASE_URL/api/stocks?page=1&page_size=5"
resp=$(curl -s -o /tmp/stocks.json -w "%{http_code}" "$BASE_URL/api/stocks?page=1&page_size=5")
if [ "$resp" != "200" ]; then
  echo "FAIL: /api/stocks 返回 $resp"
  cat /tmp/stocks.json
  exit 1
fi
echo "OK: 返回 200"
echo ">>> 部署验证通过"
