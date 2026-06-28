#!/bin/bash
# AI Quant 构建发布脚本
# 自动递增版本号、构建、部署

set -e

echo "🚀 开始构建发布流程..."

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 进入项目目录
cd "$(dirname "$0")"

# 读取当前版本号
PACKAGE_JSON="frontend/package.json"
CURRENT_VERSION=$(grep '"version"' "$PACKAGE_JSON" | head -1 | sed 's/.*"version": "\(.*\)".*/\1/')
echo "📦 当前版本: $CURRENT_VERSION"

# 解析版本号并自增
IFS='.' read -r -a VERSION_PARTS <<< "$CURRENT_VERSION"
MAJOR=${VERSION_PARTS[0]}
MINOR=${VERSION_PARTS[1]}
PATCH=${VERSION_PARTS[2]}

# 自增 patch 版本
PATCH=$((PATCH + 1))
NEW_VERSION="$MAJOR.$MINOR.$PATCH"
echo "📦 新版本: $NEW_VERSION"

# 更新 package.json
sed -i "s/\"version\": \"$CURRENT_VERSION\"/\"version\": \"$NEW_VERSION\"/" "$PACKAGE_JSON"
echo "✅ 版本号已更新"

# 构建前端
echo "🔨 开始构建前端..."
cd frontend
pnpm build 2>&1
cd ..

# 检查构建是否成功
if [ ! -f "frontend/dist/index.html" ]; then
    echo -e "${RED}❌ 构建失败，dist/index.html 不存在${NC}"
    exit 1
fi

echo -e "${GREEN}✅ 前端构建成功${NC}"

# 重载 nginx
echo "🔄 重载 nginx..."
if /usr/sbin/nginx -t > /dev/null 2>&1; then
    /usr/sbin/nginx -s reload
    echo -e "${GREEN}✅ nginx 重载成功${NC}"
else
    echo -e "${RED}❌ nginx 配置检查失败${NC}"
    exit 1
fi

# 显示版本信息
echo ""
echo -e "${GREEN}🎉 发布成功！${NC}"
echo -e "版本: ${YELLOW}$NEW_VERSION${NC}"
echo -e "访问: https://innee.cn"
echo ""
echo "更新内容:"
echo "  - 修复添加自选报错"
echo "  - 修复登录页面闪烁"
echo "  - 修复 Dashboard 闪烁"
