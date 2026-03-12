#!/usr/bin/env bash
# AI Office SaaS 交互式部署脚本
# 用途：引导完成开发/生产模式配置，自动生成后端 config.yaml、前端 .env、生产环境变量文件和 systemd 模板。
# 用法：
#   bash deploy.sh
#
# 或赋权后运行：
#   chmod +x deploy.sh
#   ./deploy.sh

set -euo pipefail

BLUE_BOLD='\033[1;34m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
NC='\033[0m'

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$ROOT_DIR/ai_office_saas/backend"
FRONTEND_DIR="$ROOT_DIR/ai_office_saas/frontend"

print_title() { echo -e "\n${BLUE_BOLD}$1${NC}"; }
info() { echo -e "${GREEN}[INFO]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; }

ask_default() {
  local prompt="$1"
  local default="$2"
  local value
  read -r -p "$prompt [$default]: " value
  if [[ -z "${value}" ]]; then
    echo "$default"
  else
    echo "$value"
  fi
}

version_ge() {
  # 用 sort -V 比较版本：$1 >= $2 返回 0
  [[ "$(printf '%s\n' "$2" "$1" | sort -V | head -n1)" == "$2" ]]
}

check_env() {
  print_title "=== 步骤 1：环境检测 ==="

  if ! command -v python3 >/dev/null 2>&1; then
    error "未检测到 python3，请先安装 Python 3.10+。"
    echo "Ubuntu 可执行：sudo apt update && sudo apt install -y python3 python3-venv python3-pip"
    exit 1
  fi

  local py_ver
  py_ver="$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")')"
  if ! version_ge "$py_ver" "3.10.0"; then
    error "Python 版本过低：$py_ver（需要 >= 3.10）"
    exit 1
  fi
  info "Python 版本：$py_ver"

  if ! command -v node >/dev/null 2>&1; then
    error "未检测到 Node.js，请先安装 Node.js 18 LTS+。"
    echo "可参考：https://nodejs.org/"
    exit 1
  fi

  local node_ver_raw node_ver
  node_ver_raw="$(node --version)"
  node_ver="${node_ver_raw#v}"
  if ! version_ge "$node_ver" "18.0.0"; then
    error "Node.js 版本过低：$node_ver_raw（需要 >= v18）"
    exit 1
  fi
  info "Node.js 版本：$node_ver_raw"

  if ! command -v npm >/dev/null 2>&1; then
    error "未检测到 npm，请先安装 npm 9+。"
    exit 1
  fi
  info "npm 版本：$(npm --version)"
}

select_mode() {
  print_title "=== 步骤 2：选择部署模式 ==="
  echo "1) 开发模式（本地开发，SQLite，不开 HTTPS）"
  echo "2) 生产模式（生产环境变量、构建前端、生成 systemd 文件）"
  while true; do
    read -r -p "请输入模式编号 [1]: " MODE
    MODE="${MODE:-1}"
    case "$MODE" in
      1|2) break ;;
      *) warn "请输入 1 或 2" ;;
    esac
  done
  if [[ "$MODE" == "1" ]]; then
    info "已选择：开发模式"
  else
    info "已选择：生产模式"
  fi
}

generate_jwt_secret() {
  python3 - <<'PY'
import secrets
print(secrets.token_hex(32))
PY
}

generate_token_encrypt_key() {
  python3 - <<'PY'
import base64, os
print(base64.urlsafe_b64encode(os.urandom(32)).decode())
PY
}

collect_config() {
  print_title "=== 步骤 3：交互式收集配置 ==="

  APP_HOST="$(ask_default '后端监听地址（示例：0.0.0.0）' '0.0.0.0')"
  APP_PORT="$(ask_default '后端端口（示例：8000）' '8000')"

  if [[ "$MODE" == "1" ]]; then
    FRONTEND_ORIGIN="$(ask_default '前端地址（示例：http://localhost:5173）' 'http://localhost:5173')"
  else
    FRONTEND_ORIGIN="$(ask_default '前端域名（示例：https://office.example.com）' 'https://office.example.com')"
  fi

  echo "LLM Provider：1) 智谱GLM  2) OpenAI兼容  3) 本地Ollama"
  while true; do
    read -r -p "请选择 LLM Provider [1]: " llm_choice
    llm_choice="${llm_choice:-1}"
    case "$llm_choice" in
      1)
        LLM_PROVIDER="zhipu"
        LLM_BASE_URL="https://open.bigmodel.cn/api/paas/v4"
        LLM_MODEL_DEFAULT="glm-4-flash"
        ;;
      2)
        LLM_PROVIDER="openai_compat"
        LLM_BASE_URL="https://api.openai.com/v1"
        LLM_MODEL_DEFAULT="gpt-4o-mini"
        ;;
      3)
        LLM_PROVIDER="openai_compat"
        LLM_BASE_URL="http://localhost:11434/v1"
        LLM_MODEL_DEFAULT="qwen2.5:7b"
        ;;
      *) warn "请输入 1/2/3"; continue ;;
    esac
    break
  done

  if [[ "$llm_choice" == "3" ]]; then
    LLM_API_KEY="ollama"
    info "Ollama 模式默认 LLM_API_KEY=ollama"
  else
    echo "LLM API Key（输入时不回显，示例：sk-xxxx）"
    while true; do
      read -rs -p "LLM API Key: " LLM_API_KEY
      echo
      if [[ -n "$LLM_API_KEY" ]]; then
        break
      fi
      warn "API Key 不能为空"
    done
  fi

  if [[ "$llm_choice" == "1" ]]; then
    info "智谱模式 base_url 默认使用：$LLM_BASE_URL"
  else
    LLM_BASE_URL="$(ask_default 'LLM base_url（示例：https://api.openai.com/v1）' "$LLM_BASE_URL")"
  fi
  LLM_MODEL="$(ask_default 'LLM 模型名（示例：glm-4-flash / gpt-4o-mini / qwen2.5:7b）' "$LLM_MODEL_DEFAULT")"

  if [[ "$MODE" == "1" ]]; then
    DB_TYPE="sqlite"
    DB_URL="sqlite:///./ai_office.db"
    info "开发模式固定使用 SQLite"
  else
    echo "数据库类型：1) SQLite  2) PostgreSQL"
    while true; do
      read -r -p "请选择数据库类型 [2]: " db_choice
      db_choice="${db_choice:-2}"
      case "$db_choice" in
        1) DB_TYPE="sqlite"; DB_URL="sqlite:///./ai_office.db"; break ;;
        2)
          DB_TYPE="postgresql"
          while true; do
            read -r -p "PostgreSQL 连接串（示例：postgresql+psycopg2://user:pass@host:5432/dbname）: " DB_URL
            [[ -n "$DB_URL" ]] && break
            warn "连接串不能为空"
          done
          break
          ;;
        *) warn "请输入 1 或 2" ;;
      esac
    done
  fi

  echo "存储类型：1) 本地存储  2) OneDrive"
  while true; do
    read -r -p "请选择存储类型 [1]: " storage_choice
    storage_choice="${storage_choice:-1}"
    case "$storage_choice" in
      1)
        STORAGE_TYPE="local"
        STORAGE_BASE_PATH="$(ask_default '本地存储路径（示例：./data/users）' './data/users')"
        STORAGE_ONEDRIVE_ROOT="ai-office-saas"
        OFFICE_PROVIDER="e5_mock"
        MS_GRAPH_CLIENT_ID=""
        MS_GRAPH_CLIENT_SECRET=""
        MS_GRAPH_TENANT_ID="common"
        MS_GRAPH_REDIRECT_URI="http://localhost:${APP_PORT}/api/oauth/callback"
        ;;
      2)
        STORAGE_TYPE="onedrive"
        STORAGE_BASE_PATH="./data/users"
        STORAGE_ONEDRIVE_ROOT="$(ask_default 'OneDrive 根目录（示例：ai-office-saas）' 'ai-office-saas')"
        OFFICE_PROVIDER="graph"
        MS_GRAPH_TENANT_ID="$(ask_default 'Azure tenant_id（示例：common）' 'common')"
        read -r -p "OneDrive client_id（示例：Azure 应用程序(客户端) ID）: " MS_GRAPH_CLIENT_ID
        while [[ -z "$MS_GRAPH_CLIENT_ID" ]]; do
          warn "client_id 不能为空"
          read -r -p "OneDrive client_id: " MS_GRAPH_CLIENT_ID
        done
        echo "OneDrive client_secret（输入时不回显）"
        read -rs -p "OneDrive client_secret: " MS_GRAPH_CLIENT_SECRET
        echo
        while [[ -z "$MS_GRAPH_CLIENT_SECRET" ]]; do
          warn "client_secret 不能为空"
          read -rs -p "OneDrive client_secret: " MS_GRAPH_CLIENT_SECRET
          echo
        done
        MS_GRAPH_REDIRECT_URI="$(ask_default 'OAuth 回调地址（示例：http://localhost:8000/api/oauth/callback）' "http://localhost:${APP_PORT}/api/oauth/callback")"
        ;;
      *) warn "请输入 1 或 2"; continue ;;
    esac
    break
  done

  local jwt_generated token_generated
  jwt_generated="$(generate_jwt_secret)"
  token_generated="$(generate_token_encrypt_key)"

  echo "已自动生成 JWT_SECRET：${jwt_generated:0:8}...（共 ${#jwt_generated} 字符）"
  read -r -p "是否使用自动生成的 JWT_SECRET？[Y/n]: " use_auto_jwt
  if [[ "${use_auto_jwt:-Y}" =~ ^[Nn]$ ]]; then
    read -rs -p "请输入自定义 JWT_SECRET（不回显，至少 32 字节）: " JWT_SECRET
    echo
  else
    JWT_SECRET="$jwt_generated"
  fi

  echo "已自动生成 TOKEN_ENCRYPT_KEY：${token_generated:0:8}...（共 ${#token_generated} 字符）"
  read -r -p "是否使用自动生成的 TOKEN_ENCRYPT_KEY？[Y/n]: " use_auto_token
  if [[ "${use_auto_token:-Y}" =~ ^[Nn]$ ]]; then
    read -rs -p "请输入自定义 TOKEN_ENCRYPT_KEY（不回显）: " TOKEN_ENCRYPT_KEY
    echo
  else
    TOKEN_ENCRYPT_KEY="$token_generated"
  fi

  APP_ENV="development"
  if [[ "$MODE" == "2" ]]; then
    APP_ENV="production"
  fi
}

write_backend_config() {
  print_title "=== 步骤 4：生成后端配置文件 ==="
  mkdir -p "$BACKEND_DIR"
  cat > "$BACKEND_DIR/config.yaml" <<EOT
app:
  name: "AI Office SaaS"
  host: "${APP_HOST}"
  port: ${APP_PORT}
  cors_origins:
    - "${FRONTEND_ORIGIN}"
  agent_max_steps: 5

security:
  jwt_secret: "INSECURE_DEV_ONLY_SET_JWT_SECRET_ENV"
  jwt_algorithm: "HS256"
  access_token_expire_minutes: 120

storage:
  type: "${STORAGE_TYPE}"
  base_path: "${STORAGE_BASE_PATH}"
  onedrive_root: "${STORAGE_ONEDRIVE_ROOT}"

llm:
  provider: "${LLM_PROVIDER}"
  api_key: "REPLACE_ME"
  base_url: "${LLM_BASE_URL}"
  model: "${LLM_MODEL}"

office:
  provider: "${OFFICE_PROVIDER}"

database:
  url: "${DB_URL}"

ms_graph:
  tenant_id: "${MS_GRAPH_TENANT_ID}"
  client_id: "${MS_GRAPH_CLIENT_ID}"
  client_secret: "${MS_GRAPH_CLIENT_SECRET}"
  redirect_uri: "${MS_GRAPH_REDIRECT_URI}"
  scopes:
    - "Files.ReadWrite"
    - "offline_access"
EOT
  info "已写入：$BACKEND_DIR/config.yaml"
}

write_frontend_env() {
  print_title "=== 步骤 5：生成前端 .env ==="
  local ws_base
  if [[ "$FRONTEND_ORIGIN" == https://* ]]; then
    ws_base="wss://${FRONTEND_ORIGIN#https://}"
  elif [[ "$FRONTEND_ORIGIN" == http://* ]]; then
    ws_base="ws://${FRONTEND_ORIGIN#http://}"
  else
    ws_base="ws://localhost:8000"
  fi

  cat > "$FRONTEND_DIR/.env" <<EOT
VITE_API_BASE_URL=http://localhost:${APP_PORT}/api
VITE_WS_BASE_URL=ws://localhost:${APP_PORT}
EOT

  if [[ "$MODE" == "2" ]]; then
    cat > "$FRONTEND_DIR/.env" <<EOT
VITE_API_BASE_URL=${FRONTEND_ORIGIN}/api
VITE_WS_BASE_URL=${ws_base}
EOT
  fi

  info "已写入：$FRONTEND_DIR/.env"
}

write_prod_env_file() {
  if [[ "$MODE" != "2" ]]; then
    return
  fi
  print_title "=== 步骤 6：生成生产环境变量文件 ==="
  cat > /tmp/ai-office-saas.env <<EOT
APP_ENV=production
JWT_SECRET=${JWT_SECRET}
TOKEN_ENCRYPT_KEY=${TOKEN_ENCRYPT_KEY}
LLM_API_KEY=${LLM_API_KEY}
DB_URL=${DB_URL}
FRONTEND_ORIGIN=${FRONTEND_ORIGIN}
MS_GRAPH_CLIENT_ID=${MS_GRAPH_CLIENT_ID}
MS_GRAPH_CLIENT_SECRET=${MS_GRAPH_CLIENT_SECRET}
EOT
  info "已生成：/tmp/ai-office-saas.env"
  warn "请执行：sudo mkdir -p /etc/ai-office-saas && sudo mv /tmp/ai-office-saas.env /etc/ai-office-saas/env && sudo chmod 600 /etc/ai-office-saas/env"
}

install_deps() {
  print_title "=== 步骤 7：安装依赖 ==="
  read -r -p "是否使用国内镜像源安装依赖？[y/N]: " use_cn_mirror

  info "准备 Python 虚拟环境"
  cd "$BACKEND_DIR"
  python3 -m venv .venv
  # shellcheck disable=SC1091
  source .venv/bin/activate
  python -m pip install --upgrade pip
  if [[ "${use_cn_mirror:-N}" =~ ^[Yy]$ ]]; then
    pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
  else
    pip install -r requirements.txt
  fi
  deactivate

  info "安装前端依赖"
  cd "$FRONTEND_DIR"
  if [[ "${use_cn_mirror:-N}" =~ ^[Yy]$ ]]; then
    npm install --registry https://registry.npmmirror.com
  else
    npm install
  fi
}

write_systemd_and_nginx() {
  if [[ "$MODE" != "2" ]]; then
    return
  fi
  print_title "=== 步骤 8：生产模式附加步骤（构建 + systemd + Nginx） ==="

  cd "$FRONTEND_DIR"
  npm run build
  info "前端构建完成：$FRONTEND_DIR/dist"

  cat > /tmp/ai-office-saas.service <<EOT
[Unit]
Description=AI Office SaaS Backend
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=${BACKEND_DIR}
Environment=APP_ENV=production
EnvironmentFile=/etc/ai-office-saas/env
ExecStart=${BACKEND_DIR}/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port ${APP_PORT} --workers 1
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOT

  info "已生成：/tmp/ai-office-saas.service"
  warn "请执行：sudo mv /tmp/ai-office-saas.service /etc/systemd/system/ai-office-saas.service && sudo systemctl daemon-reload && sudo systemctl enable --now ai-office-saas"

  cat <<'NGINX'

================ Nginx 配置示例（请替换 your-domain.com） ================
server {
    listen 80;
    server_name your-domain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name your-domain.com;

    ssl_certificate     /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;

    root /opt/ai-office-saas/ai_office_saas/frontend/dist;
    index index.html;
    location / {
        try_files $uri $uri/ /index.html;
    }

    location /api/ {
        proxy_pass http://127.0.0.1:8000/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /api/chat/ws {
        proxy_pass http://127.0.0.1:8000/api/chat/ws;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_read_timeout 300s;
        proxy_send_timeout 300s;
    }
}
==========================================================================
NGINX
}

start_dev_services() {
  if [[ "$MODE" != "1" ]]; then
    return
  fi

  print_title "=== 步骤 8：开发模式启动服务（可选） ==="
  read -r -p "是否立即启动后端？[y/N]: " start_backend
  if [[ "${start_backend:-N}" =~ ^[Yy]$ ]]; then
    read -r -p "后端启动方式：1) 前台运行 2) nohup 后台运行 [1]: " backend_run_mode
    backend_run_mode="${backend_run_mode:-1}"
    if [[ "$backend_run_mode" == "2" ]]; then
      (
        cd "$BACKEND_DIR"
        # shellcheck disable=SC1091
        source .venv/bin/activate
        nohup uvicorn app.main:app --host "$APP_HOST" --port "$APP_PORT" --reload >/tmp/ai-office-backend.log 2>&1 &
      )
      info "后端已后台启动，日志：/tmp/ai-office-backend.log"
    else
      warn "将以前台模式启动后端（按 Ctrl+C 结束）"
      (
        cd "$BACKEND_DIR"
        # shellcheck disable=SC1091
        source .venv/bin/activate
        uvicorn app.main:app --host "$APP_HOST" --port "$APP_PORT" --reload
      )
    fi
  fi

  read -r -p "是否立即启动前端？[y/N]: " start_frontend
  if [[ "${start_frontend:-N}" =~ ^[Yy]$ ]]; then
    read -r -p "前端启动方式：1) 前台运行 2) nohup 后台运行 [1]: " frontend_run_mode
    frontend_run_mode="${frontend_run_mode:-1}"
    if [[ "$frontend_run_mode" == "2" ]]; then
      (
        cd "$FRONTEND_DIR"
        nohup npm run dev >/tmp/ai-office-frontend.log 2>&1 &
      )
      info "前端已后台启动，日志：/tmp/ai-office-frontend.log"
    else
      warn "将以前台模式启动前端（按 Ctrl+C 结束）"
      (
        cd "$FRONTEND_DIR"
        npm run dev
      )
    fi
  fi
}

print_summary() {
  print_title "=== 步骤 9：完成摘要 ==="
  echo -e "${BLUE_BOLD}========================================================${NC}"
  echo -e "${GREEN}后端地址:${NC} http://${APP_HOST}:${APP_PORT}"
  echo -e "${GREEN}前端地址:${NC} ${FRONTEND_ORIGIN}"
  if [[ "$MODE" == "1" ]]; then
    echo -e "${GREEN}API 文档:${NC} http://${APP_HOST}:${APP_PORT}/docs"
  fi
  echo -e "${GREEN}后端配置:${NC} ${BACKEND_DIR}/config.yaml"
  echo -e "${GREEN}前端配置:${NC} ${FRONTEND_DIR}/.env"
  if [[ "$MODE" == "2" ]]; then
    echo -e "${GREEN}生产 env 文件:${NC} /tmp/ai-office-saas.env"
    echo -e "${GREEN}systemd 文件:${NC} /tmp/ai-office-saas.service"
    echo -e "${YELLOW}下一步:${NC} 安装 systemd 与 Nginx，申请 HTTPS 证书并重载服务。"
  else
    echo -e "${YELLOW}下一步:${NC} 使用浏览器访问前端并执行 Smoke Test。"
  fi
  echo -e "${BLUE_BOLD}========================================================${NC}"
}

main() {
  check_env
  select_mode
  collect_config
  write_backend_config
  write_frontend_env
  write_prod_env_file

  export APP_ENV="$APP_ENV"
  export JWT_SECRET="$JWT_SECRET"
  export TOKEN_ENCRYPT_KEY="$TOKEN_ENCRYPT_KEY"
  export LLM_API_KEY="$LLM_API_KEY"
  export DB_URL="$DB_URL"
  export FRONTEND_ORIGIN="$FRONTEND_ORIGIN"
  export MS_GRAPH_CLIENT_ID="$MS_GRAPH_CLIENT_ID"
  export MS_GRAPH_CLIENT_SECRET="$MS_GRAPH_CLIENT_SECRET"

  install_deps
  write_systemd_and_nginx
  start_dev_services
  print_summary
}

main "$@"
