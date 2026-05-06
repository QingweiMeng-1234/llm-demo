# LLM API Demo

一个面向个人项目的云原生容器化 LLM API 服务 Demo，使用 `FastAPI + OpenAI SDK + Docker` 构建，并以 AWS 上的容器部署实践为背景，展示从本地开发、容器封装到云上运行的一条最小可用链路。

> 这是一个 **demo 项目**，重点在于演示接口封装、容器化、基础鉴权、测试覆盖，以及面向云部署的工程化思路；并非生产级完整平台。

## 项目概述

这个仓库实现了一个轻量的 LLM API 服务，提供：

- `POST /chat`：封装上游 LLM 调用
- `GET /health`：健康检查
- `GET /api`：服务探活信息
- `GET /`：静态前端页面，用于手动测试接口

服务端使用 `Pydantic` 定义请求/响应结构，使用 `response_model` 固化 API 边界；同时通过自定义 `Middleware` 输出 `X-Latency-Ms` 响应头，便于性能观测与分层排障。

## 技术栈

- Python 3.11
- FastAPI
- Pydantic
- Uvicorn
- OpenAI Python SDK
- Docker
- pytest + FastAPI TestClient

## 工程亮点

### 1. 容器化与无状态服务设计

- 使用 `Dockerfile` 固化 Python 版本、依赖安装与启动方式
- 支持 `Build once, run consistently across local / test / cloud`
- 服务通过环境变量注入配置，不在镜像中写入密钥
- 应用本身保持无状态，便于水平扩展与副本替换

### 2. API 边界标准化

- 使用 `Pydantic` 定义 `ChatReq` / `ChatResp`
- `POST /chat` 使用 `response_model` 保证响应结构稳定
- 对空消息、缺失服务端密钥、鉴权失败、上游异常分别做了明确处理

### 3. 基础安全与鉴权

- 使用 `X-API-Key` 作为服务层 API Key 鉴权
- 服务端要求配置 `APP_API_KEY`
- 上游 LLM 凭证通过 `OPENAI_API_KEY` 注入

### 4. 可观测性

- 自定义中间件记录请求耗时
- 响应头返回 `X-Latency-Ms`
- 服务日志输出请求方法、路径、状态码和耗时

### 5. 测试覆盖

项目使用 `pytest + FastAPI TestClient` 编写测试，覆盖核心路由与关键行为：

- `/`
- `/api`
- `/health`
- `/chat` 鉴权失败
- `/chat` 空消息校验
- `/chat` 成功调用
- 上游异常封装
- 环境变量缺失场景

`pytest.ini` 中配置了覆盖率门槛：

- `--cov=app`
- `--cov-branch`
- `--cov-fail-under=90`

## 目录结构

```text
.
├── app/
│   └── main.py
├── tests/
│   └── test_main.py
├── web/
│   └── index.html
├── Dockerfile
├── requirements.txt
└── pytest.ini
```

## 本地运行

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境变量

示例：

```env
OPENAI_API_KEY=your-openai-api-key
APP_API_KEY=your-service-api-key
MODEL_NAME=gpt-4o-mini
```

说明：

- `OPENAI_API_KEY`：上游 LLM 提供商密钥
- `APP_API_KEY`：调用当前服务时需要携带的 API Key
- `MODEL_NAME`：可选，默认值为 `gpt-4o-mini`

### 3. 启动服务

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

启动后可访问：

- `http://localhost:8000/`
- `http://localhost:8000/docs`
- `http://localhost:8000/health`
- 线上 Demo：`https://weber.weber-llmdemo.xyz/`

## Docker 运行

### 构建镜像

```bash
docker build -t llm-api-demo:latest .
```

### 启动容器

```bash
docker run --env-file .env -p 8000:8000 llm-api-demo:latest
```

`Dockerfile` 基于 `python:3.11-slim`，容器启动命令为：

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## 测试

运行测试：

```bash
pytest
```

这个测试集的目标之一，是验证本地运行与容器运行下的接口行为保持一致。

## API 示例

### 健康检查

```bash
curl http://localhost:8000/health
```

### 调用聊天接口

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-service-api-key" \
  -d "{\"message\":\"hello\"}"
```

示例响应：

```json
{
  "reply": "Hello! How can I help you today?",
  "model": "gpt-4o-mini",
  "latency_ms": 523
}
```

## 云上部署实践

这个仓库对应的云上实践重点是“把一个轻量 LLM API 服务按平台工程思路运行起来”，当前部署思路如下：

- 使用 Docker 固化运行环境，实现本地、测试、云上尽量一致的执行方式
- 构建镜像并推送至 AWS ECR
- 运行在 AWS ECS Fargate 上，通过 ECS Service 管理副本数量与 Rolling Update
- 使用 ALB 暴露服务，并配置健康检查
- 使用 Cloudflare 管理 DNS，自定义域名接入 ALB，并通过 AWS ACM 证书为 HTTPS 提供支持
- 使用 AWS Secrets Manager 管理密钥，在运行时注入环境变量
- 镜像保持无密钥，结合自定义 IAM Task Role 实现最小权限原则
- 使用 CloudWatch Logs 做集中日志管理与基础运行时监控
- 通过自定义域名对外提供线上访问：`https://weber.weber-llmdemo.xyz/`

这一套部署方式本质上遵循容器编排思想，因此天然可迁移到 Kubernetes 语义下的：

- `Deployment`
- `Service`
- `Ingress`

也就是说，当前虽然运行在 ECS Fargate，但整体设计并没有和某一种单一运行时强绑定。

## 适合写在简历 / 项目介绍里的表述

可参考下面这版项目描述：

> 云原生容器化 LLM API 服务 Demo。使用 FastAPI + Pydantic 封装聊天接口与健康检查接口，通过 Docker 固化 Python 运行环境与启动方式，遵循无状态服务设计，支持本地、测试与云上环境一致运行。镜像构建后推送至 AWS ECR，并部署到 ECS Fargate，通过 ECS Service 管理副本与 Rolling Update；结合 ALB 健康检查、Secrets Manager 密钥注入、IAM Task Role 最小权限控制及 CloudWatch Logs 日志采集，实现面向云部署的基础工程化闭环。使用 pytest + FastAPI TestClient 覆盖核心路由与鉴权逻辑，并通过自定义 Middleware 输出请求耗时，支持基础可观测性。

## Demo 边界说明

这是一个演示项目，因此当前更关注“最小可运行闭环”而不是“大而全平台能力”。例如：

- 当前仓库未包含完整 IaC（如 Terraform / CDK）代码
- 鉴权方式为轻量 API Key，不是完整用户体系
- 主要演示单服务 API 封装，而非复杂多 Agent / 多服务架构
- 可观测性以请求日志与基础延迟暴露为主，未扩展到完整 tracing 体系

如果后续继续扩展，可以往以下方向演进：

- Terraform / CDK 基础设施即代码
- GitHub Actions / CI-CD 自动发布
- 更细粒度的监控、告警与 tracing
- 多环境配置管理
- 限流、配额、审计日志
- 更完整的认证授权体系
