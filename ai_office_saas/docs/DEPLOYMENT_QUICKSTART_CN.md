# AI Office SaaS 部署与启动指南（GitHub 风格）

> 适用场景：你已经 `git clone` 了仓库，并进入了 `ai_office_saas/` 目录。

---

## 1. 目录说明

```text
ai_office_saas/
├── backend/   # FastAPI + Agent 引擎
├── frontend/  # React + Vite
└── docs/      # 部署/离线文档
```

---

## 2. 先改配置（必须）

编辑文件：`backend/config.yaml`

最少要修改以下内容：

1. `security.jwt_secret`
   - 默认是占位值，必须替换为强随机密钥。
2. `app.cors_origins`
   - 改成你前端的实际访问地址。
3. `database.url`
   - 小规模可继续用 SQLite；生产建议 MySQL / PostgreSQL。
4. `storage.base_path`
   - 建议改成服务器绝对路径（如 `/data/ai-office/users`）。

示例（仅示意）：

```yaml
app:
  name: "AI Office SaaS"
  host: "0.0.0.0"
  port: 8000
  cors_origins:
    - "https://office.example.com"

security:
  jwt_secret: "your-very-strong-random-secret"
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

---

## 3. 安装依赖

### 3.1 后端依赖

```bash
cd backend
./scripts/install_backend_deps.sh
```

受限网络（推荐镜像）：

```bash
PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple ./scripts/install_backend_deps.sh
```

完全离线：

```bash
WHEELHOUSE_DIR=./wheelhouse ./scripts/install_backend_deps.sh
```

### 3.2 前端依赖

```bash
cd ../frontend
./scripts/install_frontend_deps.sh
```

受限网络（镜像）：

```bash
NPM_REGISTRY=https://registry.npmmirror.com ./scripts/install_frontend_deps.sh
```

---

## 4. 改前端 API 地址（按部署环境）

编辑文件：`frontend/src/api/client.ts`

把 `baseURL` 从默认值改成后端实际地址：

```ts
baseURL: 'https://api.example.com/api'
```

---

## 5. 启动服务

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

---

## 6. 启动后验证（Smoke Test）

1. 打开后端文档：`http://<server-ip>:8000/docs`
2. 打开前端页面：`http://<server-ip>:5173`
3. 注册/登录后：
   - 上传文件
   - 进入聊天
   - 触发 Agent 事件按钮（确认/取消/继续）

---

## 7. 常见问题

### Q1: `pip install` 或 `npm install` 报 403

使用项目自带脚本 + 镜像参数，详见：`docs/OFFLINE_SETUP_CN.md`。

### Q2: 前端能打开但接口报错

检查：
1. `frontend/src/api/client.ts` 的 `baseURL` 是否正确。
2. `backend/config.yaml` 的 `app.cors_origins` 是否包含前端地址。

### Q3: WebSocket 连不上

检查：
1. 前端是否使用了正确的后端域名/端口。
2. 反向代理（如 Nginx）是否开启了 WebSocket Upgrade 头转发。

---

## 8. 生产建议

- 使用 `systemd` 托管后端进程（不要长期用 `--reload`）。
- 使用 Nginx 反代前后端，并启用 HTTPS。
- 将 SQLite 升级为 PostgreSQL/MySQL。
- 将会话状态从内存迁移到 Redis。
