# AI Office SaaS 部署文档

## 目录
- [第 0 章：部署前必须提前准备的账号与资源](#第-0-章部署前必须提前准备的账号与资源)
  - [0.1 智谱 AI API Key（必需，用于 LLM 功能）](#01-智谱-ai-api-key必需用于-llm-功能)
  - [0.2 Microsoft Azure 应用注册（可选，仅使用 OneDrive 功能时需要）](#02-microsoft-azure-应用注册可选仅使用-onedrive-功能时需要)
  - [0.3 服务器环境（生产部署）](#03-服务器环境生产部署)
- [第 1 章：项目结构](#第-1-章项目结构)
- [第 2 章：环境要求](#第-2-章环境要求)
- [第 3 章：后端配置详解](#第-3-章后端配置详解)
- [第 4 章：安装步骤（开发环境）](#第-4-章安装步骤开发环境)
- [第 5 章：启动验证（Smoke Test）](#第-5-章启动验证smoke-test)
- [第 6 章：生产部署](#第-6-章生产部署)
- [第 7 章：LLM Provider 配置](#第-7-章llm-provider-配置)
- [第 8 章：OneDrive / Microsoft Graph 集成（可选）](#第-8-章onedrive--microsoft-graph-集成可选)
- [第 9 章：故障排查](#第-9-章故障排查)
- [第 10 章：版本回滚](#第-10-章版本回滚)

---

## 第 0 章：部署前必须提前准备的账号与资源

### 0.1 智谱 AI API Key（必需，用于 LLM 功能）

- 注册地址：https://open.bigmodel.cn
- 推荐步骤：
  1. 打开官网并注册账号。
  2. 按页面提示完成实名认证。
  3. 登录后进入控制台。
  4. 在 API Key 管理页面创建新的 Key。
  5. 复制并安全保存该 Key（建议放入密码管理器）。
- 免费额度说明：新用户通常可获得免费 token 额度，`glm-4-flash` 提供长期免费版本（以平台最新活动为准）。
- 部署注意：API Key 是一段长字符串，不是用户名密码；部署时填入 `LLM_API_KEY` 环境变量。

> ⚠️ 请勿把 API Key 直接写入公开仓库、截图或聊天记录。

### 0.2 Microsoft Azure 应用注册（可选，仅使用 OneDrive 功能时需要）

如果你只使用本地存储（`office.provider = e5_mock`），可以完全跳过本节。

- 注册地址：https://portal.azure.com
- 详细步骤：
  1. 登录 Azure Portal，搜索 **“应用注册”**，点击 **“新注册”**。
  2. 应用名称可自定义；账户类型选择 **“任何组织目录中的账户和个人 Microsoft 账户”**。
  3. 重定向 URI 选择 **Web**，开发环境填写 `http://localhost:8000/api/oauth/callback`，生产环境改为你的真实域名回调地址。
  4. 注册完成后，记录 **应用程序(客户端) ID**，它就是 `client_id`。
  5. 进入 **“证书和密码”** → **“新建客户端密码”**，创建后立即复制 **值**，它就是 `client_secret`（只显示一次）。
  6. 进入 **“API 权限”** → **“添加权限”** → **Microsoft Graph** → **委托权限**，添加 `Files.ReadWrite` 和 `offline_access`。

> ⚠️ `client_secret` 只在创建当下可见，丢失后只能重新生成。

### 0.3 服务器环境（生产部署）

- 推荐规格：1 核 2G 及以上 Linux 服务器（Ubuntu 20.04/22.04 LTS）。
- 域名要求：
  - 中国大陆服务器通常需备案域名；
  - 境外服务器按服务商要求即可。
- 端口开放：确认 80/443/8000 已在防火墙/安全组开放（或仅开放 80/443，通过 Nginx 转发到 8000）。
- HTTPS：建议使用 Let’s Encrypt + certbot 申请免费证书。

---

## 第 1 章：项目结构

```text
ai-agent-saas/                    ← 仓库根目录
├── README.md                     ← 项目简介
├── DEPLOYMENT.md                 ← 本文档
├── deploy.sh                     ← 一键部署脚本
├── requirements.txt              ← 后端依赖（根目录副本）
└── ai_office_saas/
    ├── backend/
    │   ├── app/
    │   │   ├── api/              ← 路由：auth、chat、files、oauth
    │   │   ├── agent/            ← Agent 状态机与工具注册
    │   │   ├── adapters/         ← LLM/存储/Office Provider 适配器
    │   │   ├── core/             ← 配置加载、JWT、依赖注入容器
    │   │   ├── models/           ← SQLAlchemy 数据模型
    │   │   └── main.py           ← FastAPI 应用入口
    │   ├── config.yaml           ← 主配置文件（从 example 复制后修改）
    │   ├── config.yaml.example   ← 配置模板
    │   ├── requirements.txt      ← Python 依赖
    │   └── scripts/
    │       └── install_backend_deps.sh
    ├── frontend/
    │   ├── src/
    │   │   ├── api/client.ts     ← Axios 实例配置
    │   │   ├── components/       ← ChatBox、FileUpload 等组件
    │   │   ├── pages/            ← Login、Dashboard 页面
    │   │   └── App.tsx
    │   ├── .env                  ← 前端环境变量（从 example 复制后修改）
    │   ├── .env.example
    │   ├── package.json
    │   └── scripts/
    │       └── install_frontend_deps.sh
    └── docs/
        ├── DEPLOYMENT_QUICKSTART_CN.md
        └── OFFLINE_SETUP_CN.md
```

---

## 第 2 章：环境要求

| 软件 | 最低版本 | 检查命令 | 说明 |
|------|---------|---------|------|
| Python | 3.10 | `python3 --version` | 推荐 3.11/3.12 |
| pip | 22+ | `pip --version` | Python 包管理 |
| Node.js | 18 LTS | `node --version` | 推荐 20 LTS |
| npm | 9+ | `npm --version` | 前端依赖与构建 |
| Git | 2.x | `git --version` | 代码拉取与回滚 |
| （生产可选）Nginx | 1.18+ | `nginx -v` | 反向代理 |
| （生产可选）PostgreSQL | 13+ | `psql --version` | 替换 SQLite |

---

## 第 3 章：后端配置详解

### 3.1 配置文件字段说明

| 字段路径 | 默认值 | 是否必须修改 | 说明 |
|---------|-------|-----------|------|
| `app.host` | `0.0.0.0` | 否 | 后端监听地址 |
| `app.port` | `8000` | 否 | 后端端口 |
| `app.cors_origins` | `['http://localhost:5173']` | ✅ 生产建议修改 | 前端允许来源 |
| `app.agent_max_steps` | `5` | 否 | Agent 最大步骤数 |
| `security.jwt_secret` | `INSECURE_DEV_ONLY_SET_JWT_SECRET_ENV` | ✅ 必须 | JWT 签名密钥 |
| `security.jwt_algorithm` | `HS256` | 否 | JWT 算法 |
| `security.access_token_expire_minutes` | `120` | 视业务 | Token 过期时间 |
| `storage.type` | `local` | 视场景 | `local` / `onedrive` |
| `storage.base_path` | `./data/users` | 本地存储建议改 | 本地上传根目录 |
| `storage.onedrive_root` | `ai-office-saas` | OneDrive 建议确认 | OneDrive 根目录 |
| `llm.provider` | `zhipu` | 视场景 | `zhipu` / `openai_compat` |
| `llm.api_key` | `REPLACE_ME` | ✅ 必须 | 建议仅用环境变量注入 |
| `llm.base_url` | `https://open.bigmodel.cn/api/paas/v4` | 视 provider | OpenAI 兼容接口基地址 |
| `llm.model` | `glm-4-flash` | 建议确认 | 模型名称 |
| `office.provider` | `e5_mock` | 视场景 | `e5_mock` / `graph` |
| `database.url` | `sqlite:///./ai_office.db` | ✅ 生产建议修改 | 数据库连接串 |
| `ms_graph.tenant_id` | `common` | OneDrive 视场景 | Azure 租户 |
| `ms_graph.client_id` | `在此填入 Azure 应用 client_id` | OneDrive 必须 | Azure 应用 ID |
| `ms_graph.client_secret` | `在此填入 Azure 应用 client_secret` | OneDrive 必须 | Azure 应用密钥 |
| `ms_graph.redirect_uri` | `http://localhost:8000/api/oauth/callback` | OneDrive 必须确认 | OAuth 回调地址 |
| `ms_graph.scopes` | `['Files.ReadWrite','offline_access']` | 通常否 | Graph 权限范围 |

### 3.2 环境变量覆盖表

| 环境变量名 | 覆盖的配置字段 | 是否生产必须 | 生成/获取方式 |
|-----------|-------------|-----------|-------------|
| `APP_ENV` | — | ✅ 必须设为 production | 直接填写 |
| `JWT_SECRET` | `security.jwt_secret` | ✅ 必须 | `openssl rand -hex 32` |
| `TOKEN_ENCRYPT_KEY` | OAuth token 加密 | 使用 OneDrive 时必须 | `python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |
| `LLM_API_KEY` | `llm.api_key` | ✅ 必须 | 智谱控制台 |
| `DB_URL` | `database.url` | 生产推荐 | `postgresql+psycopg2://user:pass@host:5432/dbname` |
| `FRONTEND_ORIGIN` | `app.cors_origins` | ✅ 生产必须 | 前端域名，如 `https://office.example.com` |
| `MS_GRAPH_CLIENT_ID` | `ms_graph.client_id` | OneDrive 时必须 | Azure Portal |
| `MS_GRAPH_CLIENT_SECRET` | `ms_graph.client_secret` | OneDrive 时必须 | Azure Portal |

> ⚠️ 生产环境下请优先使用环境变量注入密钥，不要把密钥写入 `config.yaml`。

---

## 第 4 章：安装步骤（开发环境）

### 4.1 克隆仓库

```bash
git clone <your-repo-url>
cd -AI-Agent-SaaS-
```

### 4.2 后端：创建虚拟环境并安装依赖

```bash
cd ai_office_saas/backend
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
# 国内镜像（网络受限时）：
# pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### 4.3 后端：配置文件初始化

```bash
cp config.yaml.example config.yaml
# 然后编辑 config.yaml，至少填写：
# - security.jwt_secret（或通过 JWT_SECRET 环境变量）
# - llm.api_key（或通过 LLM_API_KEY 环境变量）
# - app.cors_origins（填写前端地址）
```

### 4.4 启动后端（开发）

```bash
cd ai_office_saas/backend
source .venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 4.5 前端：安装依赖

```bash
cd ai_office_saas/frontend
npm install
# 国内镜像（网络受限时）：
# npm install --registry https://registry.npmmirror.com
```

### 4.6 前端：配置环境变量

```bash
cp .env.example .env
# 编辑 .env，填写：
# VITE_API_BASE_URL=http://localhost:8000/api
# VITE_WS_BASE_URL=ws://localhost:8000
```

### 4.7 启动前端（开发）

```bash
npm run dev
# 访问 http://localhost:5173
```

---

## 第 5 章：启动验证（Smoke Test）

- [ ] 后端 `/docs` 页面可访问（仅开发模式）
- [ ] 前端首页正常加载
- [ ] 注册新用户成功
- [ ] 登录并获取 JWT Token
- [ ] 上传一个 `.docx` 或 `.xlsx` 文件成功
- [ ] 进入聊天，WebSocket 连接建立（浏览器 DevTools Network 可见 101 Switching Protocols）
- [ ] 发送消息，Agent 返回响应

---

## 第 6 章：生产部署

### 6.1 安全加固清单（逐条说明）

- 生成强 JWT_SECRET：`openssl rand -hex 32`（至少 32 字节）
- 设置 `APP_ENV=production`（自动关闭 `/docs`、`/redoc`、`/openapi.json`）
- 所有密钥通过环境变量注入，`config.yaml` 中不得明文填写
- 数据库改用 PostgreSQL/MySQL，不使用 SQLite
- 强制 HTTPS

### 6.2 多 Worker 注意事项

> ⚠️ 当前 WebSocket 会话状态存储在进程内存中。多 worker 模式下，不同请求可能路由到不同 worker，导致会话丢失。

生产命令（单 worker）：

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1
```

如需多 worker（高并发），需配置 Nginx `ip_hash` sticky session，并将来考虑迁移至 Redis 存储会话。

### 6.3 完整 systemd 服务文件

```ini
[Unit]
Description=AI Office SaaS Backend
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/ai-office-saas/ai_office_saas/backend
Environment=APP_ENV=production
EnvironmentFile=/etc/ai-office-saas/env
ExecStart=/opt/ai-office-saas/ai_office_saas/backend/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

`/etc/ai-office-saas/env` 内容示例：

```bash
JWT_SECRET=your-strong-secret-here
LLM_API_KEY=your-zhipu-api-key
APP_ENV=production
FRONTEND_ORIGIN=https://office.example.com
```

### 6.4 前端生产构建

```bash
cd ai_office_saas/frontend
# 确保 .env 中的 URL 已改为生产域名
npm run build
# 产物在 dist/ 目录
```

### 6.5 完整 Nginx 配置（含 HTTPS + WebSocket + 静态文件）

```nginx
server {
    listen 80;
    server_name office.example.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name office.example.com;

    ssl_certificate     /etc/letsencrypt/live/office.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/office.example.com/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;

    # 前端静态文件
    root /opt/ai-office-saas/ai_office_saas/frontend/dist;
    index index.html;
    location / {
        try_files $uri $uri/ /index.html;
    }

    # 后端 API（普通 HTTP）
    location /api/ {
        proxy_pass http://127.0.0.1:8000/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # WebSocket（必须单独配置 Upgrade 头）
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
```

---

## 第 7 章：LLM Provider 配置

### 7.1 智谱 AI（默认）

- `llm.provider = "zhipu"`
- 可用模型：`glm-4-flash`（免费）、`glm-4`（高质量）、`glm-3-turbo`（快速）
- 控制台地址：https://open.bigmodel.cn/usercenter/proj-mgmt/apikeys

### 7.2 OpenAI 官方 API

- `llm.provider = "openai_compat"`
- `llm.base_url = "https://api.openai.com/v1"`
- `llm.model = "gpt-4o-mini"` 或其他模型

### 7.3 本地 Ollama（完全离线）

- 安装 Ollama：https://ollama.com
- 拉取模型：`ollama pull qwen2.5:7b`
- `llm.provider = "openai_compat"`
- `llm.base_url = "http://localhost:11434/v1"`
- `llm.api_key = "ollama"`（任意字符串）
- `llm.model = "qwen2.5:7b"`

### 7.4 其他 OpenAI 兼容接口（如 DeepSeek、月之暗面 Kimi 等）

常见 `base_url` 参考（以各平台官方文档为准）：

- DeepSeek：`https://api.deepseek.com/v1`
- 月之暗面 Kimi：`https://api.moonshot.cn/v1`
- 智谱 OpenAI 兼容入口：`https://open.bigmodel.cn/api/paas/v4`
- 阿里云百炼兼容入口（示例）：`https://dashscope.aliyuncs.com/compatible-mode/v1`

---

## 第 8 章：OneDrive / Microsoft Graph 集成（可选）

仅当 `office.provider = "graph"` 时需要。若使用 `e5_mock`，可跳过。

1. 打开 Azure Portal（https://portal.azure.com）并登录。
2. 顶部搜索栏输入“应用注册”，点击进入。
3. 点击“新注册”：
   - 名称：任意（如 `AI Office SaaS`）
   - 账户类型：任何组织目录中的账户和个人 Microsoft 账户
   - 重定向 URI（Web）：`http://localhost:8000/api/oauth/callback`（生产改为 HTTPS 域名）
4. 注册成功后，在“概述”页复制“应用程序(客户端) ID”到 `ms_graph.client_id`。
5. 打开“证书和密码”→“新建客户端密码”，复制生成值到 `ms_graph.client_secret`。
6. 打开“API 权限”→“添加权限”→“Microsoft Graph”→“委托权限”，添加：
   - `Files.ReadWrite`
   - `offline_access`
7. 在后端 `config.yaml` 中设置：
   - `office.provider: graph`
   - `storage.type: onedrive`
   - `ms_graph.*` 各字段
8. 启动后访问前端，按业务流程触发 OAuth 登录并完成授权。

截图描述建议（便于企业内文档归档）：
- 截图 1：应用注册页面，显示重定向 URI 配置。
- 截图 2：证书和密码页面，显示“客户端密码值”生成结果（打码保存）。
- 截图 3：API 权限页，显示 `Files.ReadWrite` 与 `offline_access` 已授予。

> ⚠️ 如果重定向 URI 与实际访问域名不一致，会导致 OAuth 回调失败。

---

## 第 9 章：故障排查

| 症状 | 可能原因 | 解决方法 |
|------|---------|---------|
| 启动时报 `FileNotFoundError: config.yaml` | 未从 `config.yaml.example` 复制配置 | 执行 `cp ai_office_saas/backend/config.yaml.example ai_office_saas/backend/config.yaml` 并补全配置 |
| 启动时报 `RuntimeError: jwt_secret 强度不足` | `JWT_SECRET` 未设置或短于 32 字节 | 执行 `openssl rand -hex 32` 生成并导出 `JWT_SECRET` |
| 启动时报 `RuntimeError: 生产环境必须通过 JWT_SECRET 环境变量` | 设置了 `APP_ENV=production` 但未设置 `JWT_SECRET` | 在 systemd `EnvironmentFile` 或 shell 中补充 `JWT_SECRET` |
| 浏览器 CORS 报错 | `cors_origins` 未包含前端域名或 `FRONTEND_ORIGIN` 未设置 | 在配置中加入前端域名，生产优先设置 `FRONTEND_ORIGIN` |
| `POST /api/auth/register` 返回 429 | 注册频率超限（5 次/分钟） | 等待 1 分钟后重试，避免脚本高频请求 |
| WebSocket 连接失败（101 未出现） | Nginx 未配置 Upgrade 头 | 按第 6.5 章添加 `Upgrade/Connection` 配置 |
| 文件上传 500 | `storage.base_path` 目录不存在或无写权限 | 创建目录并赋予运行用户写权限 |
| LLM 返回 401/403 | `LLM_API_KEY` 错误或未设置 | 检查 Key 是否有效并正确注入环境变量 |
| 多 worker 模式下聊天会话丢失 | 会话状态在进程内存，负载后会话漂移 | 先使用单 worker，或配置 sticky session 并评估 Redis |

---

## 第 10 章：版本回滚

```bash
git log --oneline -n 10
git checkout <commit-hash>
# 重启服务
```

