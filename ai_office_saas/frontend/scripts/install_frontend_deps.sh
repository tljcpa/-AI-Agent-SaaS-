#!/usr/bin/env bash
set -euo pipefail

# 中文说明：
# 1) 默认使用 npm 官方源。
# 2) 如网络受限可传入 NPM_REGISTRY 指定镜像。
# 3) 如已有离线缓存可传入 NPM_CACHE_DIR 并启用 --prefer-offline。

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ -n "${NPM_REGISTRY:-}" ]]; then
  echo "[INFO] 使用指定 npm registry 安装: $NPM_REGISTRY"
  npm install --registry "$NPM_REGISTRY"
  exit 0
fi

if [[ -n "${NPM_CACHE_DIR:-}" ]]; then
  mkdir -p "$NPM_CACHE_DIR"
  echo "[INFO] 使用 npm 缓存目录: $NPM_CACHE_DIR"
  npm install --cache "$NPM_CACHE_DIR" --prefer-offline
  exit 0
fi

echo "[INFO] 使用默认模式安装 npm 依赖"
npm install
