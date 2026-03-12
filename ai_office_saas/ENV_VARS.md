# 生产环境必须配置的环境变量

| 变量名 | 说明 | 生成示例 |
|---|---|---|
| APP_ENV | 运行环境，生产必须设为 production | `production` |
| JWT_SECRET | JWT 签名密钥，至少 32 字节 | `openssl rand -hex 32` |
| TOKEN_ENCRYPT_KEY | OAuth token Fernet 加密密钥 | `python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |
| LLM_API_KEY | 智谱 GLM API Key | 从 https://open.bigmodel.cn 获取 |
| DB_URL | 数据库连接串 | `postgresql+psycopg2://user:pass@host:5432/dbname` |
| FRONTEND_ORIGIN | 前端访问域名（CORS 白名单） | `https://office.example.com` |
