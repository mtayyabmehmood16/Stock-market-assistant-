from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from apps.api.app.db.models import Conversation, Message

COMMON_STOPWORDS = frozenset(
    {
        "AI", "AND", "ARE", "BUY", "CAN", "DCF", "EPS", "ETF", "FOR", "FCF",
        "GET", "HOW", "INC", "MAX", "MCP", "MIN", "NOT", "NOW", "OFF", "ONE",
        "OUT", "PE", "ROE", "RSI", "RUN", "SEC", "SET", "SMA", "EMA", "THE",
        "TOP", "USD", "VS", "WHY", "YOU", "WITH", "WHAT", "WHEN", "SHOW", "RUN",
        "MACD", "WACC", "CAGR", "EV", "PB", "EBITDA", "JSON", "API",
    }
)

KNOWN_COMPANY_ALIASES = {
    "apple": "AAPL",
    "microsoft": "MSFT",
    "nvidia": "NVDA",
    "google": "GOOGL",
    "alphabet": "GOOGL",
    "amazon": "AMZN",
    "tesla": "TSLA",
    "spy": "SPY",
}


@dataclass
class ConversationContext:
    conversation_id: str
    active_tickers: list[str] = field(default_factory=list)
    history: list[dict[str, str]] = field(default_factory=list)


class ContextManager:
    """Loads/persists conversation state and resolves ticker entities from user queries."""

    def load_or_create(self, db: Session, conversation_id: str, user_query: str) -> ConversationContext:
        conv = db.get(Conversation, conversation_id)
        if conv is None:
            conv = Conversation(
                id=conversation_id,
                title=user_query[:80].strip() or "New Market Analysis",
                active_tickers_json="[]",
            )
            db.add(conv)
            db.commit()
            db.refresh(conv)

        prior_tickers: list[str] = json.loads(conv.active_tickers_json or "[]")
        detected = self.extract_tickers(user_query)
        active = detected if detected else (prior_tickers or ["AAPL"])

        history = [
            {"role": m.role, "content": m.content}
            for m in conv.messages[-8:]
        ]
        return ConversationContext(
            conversation_id=conversation_id,
            active_tickers=active,
            history=history,
        )

    def save_turn(
        self,
        db: Session,
        conversation_id: str,
        user_msg_id: str,
        user_query: str,
        assistant_msg_id: str,
        assistant_narrative: str,
        response_payload_json: str,
        active_tickers: list[str],
    ) -> None:
        conv = db.get(Conversation, conversation_id)
        if conv is not None:
            conv.active_tickers_json = json.dumps(active_tickers)
        db.add(
            Message(
                id=user_msg_id,
                conversation_id=conversation_id,
                role="user",
                content=user_query,
            )
        )
        db.add(
            Message(
                id=assistant_msg_id,
                conversation_id=conversation_id,
                role="assistant",
                content=assistant_narrative,
                response_payload_json=response_payload_json,
            )
        )
        db.commit()

    @staticmethod
    def extract_tickers(text: str) -> list[str]:
        found: list[str] = []
        lower = text.lower()
        for name, sym in KNOWN_COMPANY_ALIASES.items():
            if re.search(rf"\b{re.escape(name)}\b", lower) and sym not in found:
                found.append(sym)

        # Match $AAPL or uppercase 2-5 letter ticker tokens
        for match in re.finditer(r"(?:\$([A-Za-z]{1,5})|\b([A-Z]{2,5})\b)", text):
            sym = (match.group(1) or match.group(2)).upper()
            if sym not in COMMON_STOPWORDS and sym not in found:
                found.append(sym)
        return found[:5]
