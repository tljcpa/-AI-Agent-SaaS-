# AI Office SaaS

支持 Human-in-the-Loop 的办公 AI Agent SaaS 示例工程。

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688)
![React](https://img.shields.io/badge/React-18-61DAFB)
![TypeScript](https://img.shields.io/badge/TypeScript-5-3178C6)
![Vite](https://img.shields.io/badge/Vite-5-646CFF)
![Tailwind](https://img.shields.io/badge/TailwindCSS-3-38B2AC)

## 三步快速开始

1. 克隆仓库
   ```bash
   git clone <your-repo-url>
   cd -AI-Agent-SaaS-
   ```
2. 运行交互式部署脚本
   ```bash
   bash deploy.sh
   ```
3. 打开浏览器
   - 开发模式：`http://localhost:5173`
   - 后端开发文档：`http://localhost:8000/docs`

## 功能亮点

- 文件上传与管理：支持用户隔离的文件上传、列表与存储抽象（本地/OneDrive）。
- AI Agent 多步骤任务：内置状态机、工具注册与多轮执行流程。
- WebSocket 实时对话：`/api/chat/ws` 支持实时事件流与会话恢复。
- JWT 认证：提供注册/登录接口并返回 Bearer Token。
- 存储后端可切换：支持本地存储与 OneDrive Graph 存储。
- LLM 接入可扩展：支持智谱 GLM 与 OpenAI 兼容协议。

## 文档入口

- 完整部署文档：[`DEPLOYMENT.md`](./DEPLOYMENT.md)
- 离线/受限网络部署文档：[`ai_office_saas/docs/`](./ai_office_saas/docs/)

