from __future__ import annotations

import json
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.app.config import get_settings
from apps.api.app.db.models import Conversation
from apps.api.app.db.session import get_db
from apps.api.app.harness.workflow import AIHarness, serialize_sse
from packages.shared_schemas.schemas import AnalysisResponse

router = APIRouter(prefix="/api", tags=["chat"])


class ChatRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    conversation_id: str | None = None


@router.post("/chat", response_model=AnalysisResponse)
def chat_turn(req: ChatRequest, db: Session = Depends(get_db)) -> AnalysisResponse:
    conv_id = req.conversation_id or str(uuid.uuid4())
    harness = AIHarness(get_settings())
    return harness.run_turn(db=db, conversation_id=conv_id, user_query=req.query)


@router.post("/chat/stream")
def chat_turn_stream(req: ChatRequest, db: Session = Depends(get_db)) -> StreamingResponse:
    conv_id = req.conversation_id or str(uuid.uuid4())
    harness = AIHarness(get_settings())

    def event_gen():
        yield serialize_sse("status", {"stage": "planning", "message": "Analyzing query & planning MCP/sandbox tools..."})
        response = harness.run_turn(db=db, conversation_id=conv_id, user_query=req.query)
        yield serialize_sse("tools", {"tools_used": response.tools_used, "tickers": response.tickers})
        yield serialize_sse("complete", response.model_dump())

    return StreamingResponse(event_gen(), media_type="text/event-stream")


@router.get("/conversations")
def list_conversations(db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    rows = db.scalars(select(Conversation).order_by(Conversation.updated_at.desc()).limit(25)).all()
    return [
        {
            "id": c.id,
            "title": c.title,
            "active_tickers": json.loads(c.active_tickers_json or "[]"),
            "updated_at": c.updated_at.isoformat() if c.updated_at else None,
        }
        for c in rows
    ]


@router.get("/conversations/{conversation_id}")
def get_conversation(conversation_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    conv = db.get(Conversation, conversation_id)
    if conv is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {
        "id": conv.id,
        "title": conv.title,
        "active_tickers": json.loads(conv.active_tickers_json or "[]"),
        "messages": [
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "payload": json.loads(m.response_payload_json) if m.response_payload_json else None,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in conv.messages
        ],
    }
