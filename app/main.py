import time
from collections import defaultdict, deque
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.chatbot import Chatbot
from app.config import APP_NAME, APP_VERSION, settings

app = FastAPI(title=APP_NAME, version=APP_VERSION,
              description="AI-powered real estate information assistant.")
bot = Chatbot()
STATIC = Path(__file__).parent / "static"
hits: dict[str, deque] = defaultdict(deque)


class Turn(BaseModel):
    role: str = Field(pattern="^(user|assistant)$")
    content: str = Field(max_length=4000)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=1000)
    history: list[Turn] = []


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


@app.get("/health")
def health():
    return {"status": "healthy", "app": APP_NAME, "version": APP_VERSION, "chunks": len(bot.retriever.store.chunks),
            "dense_retrieval": bot.retriever.has_dense, "models": settings.models}


@app.post("/chat")
async def chat(req: ChatRequest, request: Request):
    ip = request.headers.get("x-forwarded-for", request.client.host if request.client else "?").split(",")[0]
    q, now = hits[ip], time.time()
    while q and now - q[0] > 60:
        q.popleft()
    if len(q) >= settings.rate_limit_per_min:
        raise HTTPException(429, "Too many requests, please wait a moment.")
    q.append(now)
    return await bot.answer(req.message, [t.model_dump() for t in req.history])
