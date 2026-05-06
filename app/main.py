import os
import time
from typing import Optional
import logging


from fastapi import FastAPI, HTTPException, Header, Request, Depends
from fastapi.security import APIKeyHeader
from pydantic import BaseModel
from openai import OpenAI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

logger = logging.getLogger("app")
logging.basicConfig(level=logging.INFO)

app = FastAPI(title="LLM API Demo", version="0.2.1")

app.mount("/web", StaticFiles(directory="web"), name="web")

MODEL = os.getenv("MODEL_NAME", "gpt-4o-mini")

# 你的服务鉴权 key（给调用方/客户用）
APP_API_KEY = os.getenv("APP_API_KEY")

# Swagger / OpenAPI 会识别它，并生成右上角 Authorize
api_key_scheme = APIKeyHeader(name="X-API-Key", auto_error=False)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # demo 用 *；生产环境换成你的前端域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)



class ChatReq(BaseModel):
    message: str


class ChatResp(BaseModel):
    reply: str
    model: str
    latency_ms: int

# Serve index.html at root
@app.get("/")
def frontend():
    return FileResponse("web/index.html")

@app.get("/api")
def root():
    return {"message": "LLM API Demo is running. Visit /docs"}


@app.get("/health")
def health():
    return {"status": "ok"}


def require_api_key_dep(api_key: Optional[str] = Depends(api_key_scheme)) -> None:
    """
    强制鉴权：
    - 服务必须配置 APP_API_KEY
    - 调用方必须传 X-API-Key 且匹配
    """
    if not APP_API_KEY:
        raise HTTPException(status_code=500, detail="Server misconfigured: APP_API_KEY missing")
    if api_key != APP_API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")


def get_openai_client() -> OpenAI:
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("OPENAI_API_KEY is missing")
    return OpenAI(api_key=key)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    t0 = time.time()
    resp = await call_next(request)
    latency_ms = int((time.time() - t0) * 1000)

    resp.headers["X-Latency-Ms"] = str(latency_ms)

    logger.info(
        "%s %s -> %s (%dms)",
        request.method,
        request.url.path,
        resp.status_code,
        latency_ms,
    )
    return resp

@app.post("/chat", response_model=ChatResp)
def chat(
    req: ChatReq,
    _: None = Depends(require_api_key_dep),
):
    msg = (req.message or "").strip()
    if not msg:
        raise HTTPException(status_code=400, detail="message is empty")

    t0 = time.time()
    try:
        client = get_openai_client()
        resp = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": msg},
            ],
            temperature=0.2,
        )
        reply = (resp.choices[0].message.content or "").strip()
        latency_ms = int((time.time() - t0) * 1000)

        return ChatResp(
            reply=reply,
            model=MODEL,
            latency_ms=latency_ms,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM call failed: {e}")

