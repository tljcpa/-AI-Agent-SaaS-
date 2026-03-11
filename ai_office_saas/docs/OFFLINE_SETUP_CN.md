# AI Office SaaS 受限网络/离线部署指南（中文）

本指南用于解决以下常见问题：
- `pip install -r requirements.txt` 因代理策略返回 403。
- `npm install` 因仓库访问策略返回 403。

## 1. 后端依赖安装

### 1.1 使用镜像源安装（推荐）
```bash
cd ai_office_saas/backend
PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple ./scripts/install_backend_deps.sh
```

### 1.2 使用离线 wheelhouse 安装
先在可联网机器下载依赖：
```bash
pip download -r requirements.txt -d ./wheelhouse
```
将 `wheelhouse` 目录拷贝到目标机后执行：
```bash
cd ai_office_saas/backend
WHEELHOUSE_DIR=./wheelhouse ./scripts/install_backend_deps.sh
```

## 2. 前端依赖安装

### 2.1 使用镜像源安装
```bash
cd ai_office_saas/frontend
NPM_REGISTRY=https://registry.npmmirror.com ./scripts/install_frontend_deps.sh
```

### 2.2 使用缓存优先安装（半离线）
```bash
cd ai_office_saas/frontend
NPM_CACHE_DIR=./.npm-cache ./scripts/install_frontend_deps.sh
```

## 3. 启动项目

### 3.1 启动后端
```bash
cd ai_office_saas/backend
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 3.2 启动前端
```bash
cd ai_office_saas/frontend
npm run dev
```

## 4. 最小验证

- 后端：打开 `http://localhost:8000/docs` 应看到 FastAPI 文档。
- 前端：打开 `http://localhost:5173` 登录后可进入 Dashboard。
- 聊天：通过 WebSocket 与 Agent 交互，触发 `action_ask_user`。

## 5. 额外建议

- 在企业网络中建议搭建私有 PyPI / npm proxy（如 Nexus、Artifactory、Verdaccio）。
- CI 中建议缓存 pip 与 npm 目录，降低对外网依赖。
