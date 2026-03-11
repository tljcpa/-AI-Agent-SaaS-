# AI Office SaaS

一个支持 Human-in-the-Loop 的办公 AI Agent SaaS 示例工程。

## 目录
- `backend/`: FastAPI + Agent 状态机 + Protocol 驱动 Provider
- `frontend/`: React 18 + TypeScript + Tailwind
- `docs/OFFLINE_SETUP_CN.md`: 受限网络/离线部署指南

## 快速开始

建议按以下顺序阅读：

1. 部署与启动主指南（开发/生产通用）
   - [DEPLOYMENT_QUICKSTART_CN.md](./docs/DEPLOYMENT_QUICKSTART_CN.md)
2. 受限网络 / 离线安装补充
   - [OFFLINE_SETUP_CN.md](./docs/OFFLINE_SETUP_CN.md)

## 部署注意事项
- 当前后端 `build_container` 构建出的 Agent 会话状态保存在进程内存中（`/api/chat/ws`）。
- 生产环境若启用多 worker，必须配置 sticky session（如 nginx `ip_hash`）或使用单 worker（`--workers=1`），否则会话状态可能丢失。
