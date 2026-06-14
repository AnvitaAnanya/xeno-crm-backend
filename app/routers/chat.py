from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import Optional
from app.database import get_db
from app.services.ai_service import chat_with_ai

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatMessage(BaseModel):
    role: str      # "user" or "assistant"
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]


class ChatResponse(BaseModel):
    response: str
    tool_calls: list[dict] = []


@router.post("/", response_model=ChatResponse)
async def chat(
    payload: ChatRequest,
    db: AsyncSession = Depends(get_db)
):
    messages = [
        {"role": m.role, "content": m.content}
        for m in payload.messages
    ]
    result = await chat_with_ai(messages, db)
    return ChatResponse(
        response=result["response"],
        tool_calls=result["tool_calls"]
    )