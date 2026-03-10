#!/usr/bin/env bash
set -euo pipefail

# 中文说明：
# 1) 默认走官方源安装。
# 2) 若环境受限可传入镜像源 PIP_INDEX_URL。
# 3) 若已准备离线 wheelhouse，可传入 WHEELHOUSE_DIR 走完全离线安装。

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REQ_FILE="$ROOT_DIR/requirements.txt"

if [[ ! -f "$REQ_FILE" ]]; then
  echo "[ERROR] requirements.txt 不存在: $REQ_FILE"
  exit 1
fi

if [[ -n "${WHEELHOUSE_DIR:-}" ]]; then
  if [[ ! -d "$WHEELHOUSE_DIR" ]]; then
    echo "[ERROR] 指定的 WHEELHOUSE_DIR 不存在: $WHEELHOUSE_DIR"
    exit 1
  fi
  echo "[INFO] 使用离线 wheelhouse 安装依赖: $WHEELHOUSE_DIR"
  pip install --no-index --find-links "$WHEELHOUSE_DIR" -r "$REQ_FILE"
  exit 0
fi

if [[ -n "${PIP_INDEX_URL:-}" ]]; then
  echo "[INFO] 使用镜像源安装依赖: $PIP_INDEX_URL"
  pip install -i "$PIP_INDEX_URL" -r "$REQ_FILE"
  exit 0
fi

echo "[INFO] 使用默认源安装依赖"
pip install -r "$REQ_FILE"
