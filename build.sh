#!/usr/bin/env bash
set -e
echo ""
echo "  ╔══════════════════════════════════════╗"
echo "  ║   CortexNodus  Build  (Go/Unix)      ║"
echo "  ╚══════════════════════════════════════╝"
echo ""

command -v go &>/dev/null || { echo "  [错误] 未找到 Go，请从 https://go.dev 安装"; exit 1; }

echo "  [1/3] 下载依赖..."
cd launcher && go mod tidy && cd ..

echo "  [2/3] 编译..."
cd launcher && go build -ldflags "-s -w" -o ../CortexNodus . && cd ..

echo "  [3/3] 打包分发目录..."
rm -rf dist && mkdir -p dist
cp CortexNodus app.py marketplace_server.py requirements.txt dist/
cp -r ml templates static dist/
[ -d subgraphs ] && cp -r subgraphs dist/

echo ""
echo "  ✓ 完成！运行：./dist/CortexNodus"
echo ""
