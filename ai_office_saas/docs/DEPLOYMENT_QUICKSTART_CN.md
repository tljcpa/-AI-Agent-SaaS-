# AI Office SaaS 部署与启动指南（中文 / GitHub 风格）

> 面向第一次接手项目的开发者与运维同学。
> 本文覆盖：本地开发、受限网络安装、生产上线前检查、反向代理要点、常见故障排查。

---

## 目录

- [1. 项目结构](#1-项目结构)
- [2. 环境要求](#2-环境要求)
- [3. 部署前必改配置](#3-部署前必改配置)
- [4. 安装依赖](#4-安装依赖)
- [5. 启动服务（开发模式）](#5-启动服务开发模式)
- [6. 启动后验证（Smoke Test）](#6-启动后验证smoke-test)
- [7. 生产部署建议](#7-生产部署建议)
- [8. Nginx 反向代理示例（含 WebSocket）](#8-nginx-反向代理示例含-websocket)
- [9. 常见问题排查](#9-常见问题排查)
- [10. 快速回滚与恢复](#10-快速回滚与恢复)

---

## 1. 项目结构

```text
ai_office_saas/
├── backend/
│   ├── app/
│   ├── config.yaml
│   ├── requirements.txt
│   └── scripts/
├── frontend/
│   ├── src/
│   ├── package.json
│   └── scripts/
└── docs/
```

---

## 2. 环境要求

### 后端

- Python 3.10+
- Linux / macOS / Windows（生产推荐 Linux）

### 前端

- Node.js 18+
- npm 9+

### 网络

- 可访问 PyPI 与 npm 仓库（若受限，见离线/镜像方案）
- 如有企业防火墙，确保 WebSocket 连接允许 Upgrade

---

## 3. 部署前必改配置

配置文件：`backend/config.yaml`

> ⚠️ 安全重点：`jwt_secret` 默认是开发占位值。生产必须使用高强度密钥，并建议通过环境变量 `JWT_SECRET` 注入。

### 推荐修改项

1. `security.jwt_secret`
   - 开发可在 `config.yaml` 中设置。
   - 生产推荐：仅通过环境变量 `JWT_SECRET` 注入。
2. `app.cors_origins`
   - 填写前端实际访问域名。
3. `database.url`
   - 开发可用 SQLite；生产建议 PostgreSQL / MySQL。
4. `storage.base_path`
   - 建议使用绝对路径，如 `/data/ai-office/users`。

### 示例（仅示意）

```yaml
app:
  name: "AI Office SaaS"
  host: "0.0.0.0"
  port: 8000
  cors_origins:
    - "https://office.example.com"

security:
  # 不要在此填写明文密钥，请通过环境变量注入：
  # export JWT_SECRET=$(openssl rand -hex 32)
  jwt_secret: "通过 JWT_SECRET 环境变量注入"
  jwt_algorithm: "HS256"
  access_token_expire_minutes: 120

storage:
  type: "local"
  base_path: "/data/ai-office/users"

llm:
  provider: "zhipu_mock"
  api_key: "mock-key"

office:
  provider: "e5_mock"

database:
  url: "sqlite:///./ai_office.db"
```

### 生产环境变量示例

```bash
export JWT_SECRET='replace-with-a-strong-random-secret'
```

---

## 4. 安装依赖

> 假设当前目录为 `ai_office_saas/`

### 4.1 后端依赖安装

```bash
cd backend
./scripts/install_backend_deps.sh
```

#### 受限网络（镜像源）

```bash
PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple ./scripts/install_backend_deps.sh
```

#### 完全离线（wheelhouse）

```bash
WHEELHOUSE_DIR=./wheelhouse ./scripts/install_backend_deps.sh
```

---

### 4.2 前端依赖安装

```bash
cd ../frontend
./scripts/install_frontend_deps.sh
```

#### 受限网络（镜像源）

```bash
NPM_REGISTRY=https://registry.npmmirror.com ./scripts/install_frontend_deps.sh
```

---

## 5. 启动服务（开发模式）

### 5.1 启动后端

```bash
cd ../backend
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 5.2 启动前端

```bash
cd ../frontend
npm run dev
```

### 5.3 配置前端 API 地址

编辑 `frontend/src/api/client.ts`，将 `baseURL` 配置为后端地址（包含 `/api` 前缀）：

```ts
baseURL: 'https://api.example.com/api'
```

---

## 6. 启动后验证（Smoke Test）

按顺序验证：

1. 打开后端文档：`http://<backend-host>:8000/docs`
2. 打开前端：`http://<frontend-host>:5173`
3. 完成注册/登录
4. 上传文件（符合类型与大小限制）
5. 打开聊天，触发 Agent 流程：
   - `start`
   - 文件缺失时 `action_ask_user`

---

## 7. 生产部署建议

### 后端

- 禁止使用 `--reload`。
- 使用 `systemd` / Supervisor / 容器编排托管进程。
- 使用环境变量注入敏感信息（如 `JWT_SECRET`）。

### 数据库

- 生产优先 PostgreSQL / MySQL。
- 为用户表、文件表做好备份策略。

### 存储

- `storage.base_path` 使用独立数据盘。
- 增加磁盘配额与监控告警。

### 安全

- 强制 HTTPS。
- 对外仅暴露反向代理端口。
- 定期轮换 JWT 密钥（需配合业务会话策略）。

### 可用性

- 会话状态当前为内存态，生产建议迁移到 Redis。
- 关键接口增加日志、指标和告警（错误率、延迟、磁盘使用）。

---

## 8. Nginx 反向代理示例（含 WebSocket）

> 以下为最小示例，请按实际域名、证书路径调整。

```nginx
server {
    listen 80;
    server_name office.example.com;

    # 前端静态资源
    location / {
        proxy_pass http://127.0.0.1:5173;
        proxy_set_header Host $host;
    }

    # 后端 API
    location /api/ {
        proxy_pass http://127.0.0.1:8000/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # WebSocket
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

## 9. 常见问题排查

### 9.1 前端打开正常，但接口 401 / 403

检查项：

- Token 是否正确携带（`Authorization: Bearer <token>`）
- `cors_origins` 是否包含前端域名
- 反向代理是否正确透传请求头

### 9.2 WebSocket 连不上

检查项：

- URL 是否使用正确路径：`/api/chat/ws`
- Nginx 是否配置 Upgrade / Connection 头
- 网关或企业代理是否阻断 WS

### 9.3 上传失败

检查项：

- 文件 MIME 类型是否受支持
- 文件是否超过后端大小上限
- `storage.base_path` 是否有写权限

### 9.4 启动时报配置错误

检查项：

- `backend/config.yaml` 是否存在且格式正确
- 生产是否正确设置 `JWT_SECRET`

---

## 10. 快速回滚与恢复

### 回滚版本

```bash
git log --oneline -n 5
git checkout <stable_commit>
```

### 恢复服务

1. 重装依赖（必要时）
2. 检查配置与环境变量
3. 依次重启后端与前端
4. 重新执行 Smoke Test

---

## 附录

- 受限网络/离线安装：[`OFFLINE_SETUP_CN.md`](./OFFLINE_SETUP_CN.md)
