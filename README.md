# 📚 PaperPilot — 面向电化学储能材料领域的智能文献问答平台

## 项目简介

PaperPilot 是一个面向电化学储能材料领域科研人员的智能文献问答平台。支持 PDF 文献上传、自动解析与分块、向量化存储、语义检索以及基于 RAG（检索增强生成）的智能问答服务。

## 功能特性

- 🔐 **用户认证** — 注册/登录/JWT Token 认证
- 📄 **文献管理** — PDF 上传、自动解析元数据、文本分块、状态追踪
- 🧠 **向量化存储** — 基于 ChromaDB 的本地持久化向量库
- 🤖 **智能问答** — RAG 检索 + 豆包大模型生成，支持引用原文来源
- 🌐 **翻译工具** — 中英互译及多语言翻译
- 📝 **摘要解读** — 单篇文献结构化解读（背景/方法/发现/创新点/局限性）
- 💬 **会话管理** — 多轮对话、历史记录管理

## 技术架构

```
┌─────────────────────────────────────────────────────┐
│                    Frontend                          │
│           Vue 3 + Vite + Element Plus               │
│         Pinia (状态管理) + Vue Router               │
└──────────────────────┬──────────────────────────────┘
                       │ HTTP / REST API
┌──────────────────────┴──────────────────────────────┐
│                    Backend                           │
│              Flask + Flask-JWT-Extended              │
│                                                      │
│  ┌──────────┐  ┌──────────────┐  ┌───────────────┐  │
│  │ PDF解析  │  │  RAG 服务    │  │  工具插件系统 │  │
│  │ PyMuPDF  │  │  LangChain   │  │  翻译/摘要    │  │
│  └────┬─────┘  └──────┬───────┘  └───────────────┘  │
│       │               │                              │
│  ┌────┴───────────────┴───────────────────────────┐  │
│  │          豆包大模型（火山方舟）                   │  │
│  │   Embedding: Doubao-embedding                  │  │
│  │   Generation: Doubao-pro-32k                    │  │
│  └─────────────────────────────────────────────────┘  │
│                                                      │
│  ┌──────────────┐        ┌──────────────────────┐    │
│  │   SQLite     │        │      ChromaDB        │    │
│  │  (SQLAlchemy)│        │   (向量持久化)       │    │
│  └──────────────┘        └──────────────────────┘    │
└──────────────────────────────────────────────────────┘
```

## 快速开始

### 环境要求

- Python 3.10+
- Node.js 18+
- 火山方舟 API Key（豆包大模型）

### 后端启动

```bash
cd backend

# 创建虚拟环境（推荐）
python -m venv venv
source venv/bin/activate  # macOS/Linux
# venv\Scripts\activate   # Windows

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
# 然后编辑 .env 文件，填入以下必要配置：
#
# 1. ARK_API_KEY（必填）：
#    前往 https://console.volcengine.com/ark 创建 API Key
#    然后在「开通管理」页面开通模型服务
#
# 2. JWT_SECRET_KEY（建议修改）：
#    用于 JWT Token 签名，生产环境务必改为随机长字符串
#    可用命令生成：python -c "import secrets; print(secrets.token_hex(32))"
#
# 其余配置项保持默认即可（模型名称已内置默认值）

# 启动后端服务
python run.py
```

后端将在 http://localhost:5001 启动。

### 前端启动

```bash
cd frontend

# 安装依赖
npm install

# 启动开发服务器
npm run dev
```

前端将在 http://localhost:5173 启动，并自动代理 `/api` 请求到后端。

## 环境变量说明

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| `ARK_API_KEY` | 火山方舟 API 密钥 | 必填 |
| `ARK_CHAT_MODEL` | 豆包对话模型名称 | doubao-seed-2-0-lite-260215 |
| `ARK_EMBED_MODEL` | 豆包 Embedding 模型名称 | doubao-embedding-large-text-250515 |
| `JWT_SECRET_KEY` | JWT 签名密钥 | dev-secret-key |
| `DATABASE_URL` | SQLite 数据库路径 | sqlite:///./app.db |
| `UPLOAD_FOLDER` | PDF 文件存储目录 | ./uploads |
| `CHROMA_DB_PATH` | ChromaDB 持久化目录 | ./chroma_db |
| `MAX_CONTENT_LENGTH` | 最大上传文件大小（字节） | 52428800 (50MB) |
| `FLASK_DEBUG` | 调试模式 | True |

## API 文档简表

### 认证 `/api/auth`

| 方法 | 路径 | 说明 | 认证 |
|------|------|------|------|
| POST | `/register` | 用户注册 | 否 |
| POST | `/login` | 用户登录 | 否 |
| GET | `/me` | 获取当前用户 | 是 |
| POST | `/logout` | 登出 | 是 |

### 文献 `/api/documents`

| 方法 | 路径 | 说明 | 认证 |
|------|------|------|------|
| POST | `/upload` | 上传 PDF 文献 | 是 |
| GET | `/` | 获取文献列表 | 是 |
| GET | `/<id>` | 获取文献详情 | 是 |
| DELETE | `/<id>` | 删除文献 | 是 |
| GET | `/<id>/status` | 查询处理状态 | 是 |

### 对话 `/api/chat`

| 方法 | 路径 | 说明 | 认证 |
|------|------|------|------|
| POST | `/conversations` | 创建会话 | 是 |
| GET | `/conversations` | 获取会话列表 | 是 |
| GET | `/conversations/<id>/messages` | 获取消息列表 | 是 |
| POST | `/ask` | 智能问答 | 是 |
| DELETE | `/conversations/<id>` | 删除会话 | 是 |

### 工具 `/api/tools`

| 方法 | 路径 | 说明 | 认证 |
|------|------|------|------|
| POST | `/translate` | 翻译 | 是 |
| POST | `/summarize` | 摘要解读 | 是 |
| GET | `/list` | 获取工具列表 | 是 |

## 统一响应格式

```json
// 成功
{"code": 0, "data": {...}, "message": "success"}

// 失败
{"code": 1, "message": "错误信息"}
```

## 许可证

MIT License
