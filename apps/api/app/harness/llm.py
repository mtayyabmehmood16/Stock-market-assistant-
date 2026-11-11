from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

import httpx

from apps.api.app.config import Settings


@dataclass
class PlannedToolCall:
    name: str
    args: dict[str, Any]


class AnalystPlannerLLM:
    """Plans tool calls and synthesizes grounded narratives (deterministic offline driver + optional Gemini/OpenAI)."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def plan_tools(self, query: str, active_tickers: list[str]) -> list[PlannedToolCall]:
        q = query.lower()
        tickers = active_tickers or ["AAPL"]
        primary = tickers[0]

        period = "6mo"
        if "1 year" in q or "1y" in q or "12 month" in q:
            period = "1y"
        elif "3 month" in q or "3m" in q:
            period = "3mo"
        elif "1 month" in q or "1m" in q:
            period = "1mo"

        is_deep = any(k in q for k in ("deep", "monte carlo", "background", "celery", "comprehensive", "full report"))
        is_compare = len(tickers) >= 2 or any(k in q for k in ("compare", "comparison", "vs", "versus", "peer"))
        is_what_if = any(k in q for k in ("what-if", "what if", "dcf", "projection", "scenario", "sensitivity", "intrinsic"))
        is_fund = any(k in q for k in ("fundamental", "financial", "statement", "income", "balance", "cash flow", "earnings", "valuation", "pe", "p/e", "margin", "10-k"))
        is_tech = any(k in q for k in ("technical", "chart", "candlestick", "rsi", "macd", "sma", "ema", "bollinger", "trend", "volume"))

        calls: list[PlannedToolCall] = []

        if is_deep:
            calls.append(PlannedToolCall("enqueue_deep_analysis", {"tickers": tickers if len(tickers) >= 2 else [primary, "MSFT"], "period": period}))
            calls.append(PlannedToolCall("get_technical_analysis", {"ticker": primary, "period": period}))
            return calls

        if is_compare:
            comp_tickers = tickers if len(tickers) >= 2 else [primary, "MSFT"]
            calls.append(PlannedToolCall("compare_stocks_python", {"tickers": comp_tickers, "period": period}))
            calls.append(PlannedToolCall("get_technical_analysis", {"ticker": comp_tickers[0], "period": period}))
            return calls

        if is_what_if:
            fcf_g = self._extract_pct(q, r"(?:growth|cagr)\s*(?:of|at|=)?\s*(\d+(?:\.\d+)?)\s*%", default=0.12)
            wacc = self._extract_pct(q, r"wacc\s*(?:of|at|=)?\s*(\d+(?:\.\d+)?)\s*%", default=0.09)
            calls.append(
                PlannedToolCall(
                    "run_what_if_dcf",
                    {"ticker": primary, "fcf_growth_rate": fcf_g, "wacc": wacc, "terminal_growth": 0.03},
                )
            )
            calls.append(PlannedToolCall("get_fundamental_research", {"ticker": primary}))
            return calls

        if is_tech and not is_fund:
            calls.append(PlannedToolCall("get_technical_analysis", {"ticker": primary, "period": period}))
            return calls

        if is_fund and not is_tech:
            calls.append(PlannedToolCall("get_fundamental_research", {"ticker": primary}))
            calls.append(PlannedToolCall("get_technical_analysis", {"ticker": primary, "period": period}))
            return calls

        # Default holistic stock overview: technicals + fundamentals
        calls.append(PlannedToolCall("get_technical_analysis", {"ticker": primary, "period": period}))
        calls.append(PlannedToolCall("get_fundamental_research", {"ticker": primary}))
        return calls

    @staticmethod
    def _extract_pct(text: str, pattern: str, default: float) -> float:
        m = re.search(pattern, text)
        if not m:
            return default
        val = float(m.group(1))
        return round(val / 100.0, 4)

    def synthesize_narrative(
        self,
        query: str,
        tool_results: dict[str, Any],
        fallback_narrative: str,
    ) -> str:
        provider = self.settings.llm_provider.lower()
        if provider == "gemini" and self.settings.gemini_api_key:
            try:
                return self._call_gemini(query, tool_results) or fallback_narrative
            except Exception:
                return fallback_narrative
        if provider == "openai" and self.settings.openai_api_key:
            try:
                return self._call_openai(query, tool_results) or fallback_narrative
            except Exception:
                return fallback_narrative
        return fallback_narrative

    def _call_gemini(self, query: str, tool_results: dict[str, Any]) -> str | None:
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.settings.gemini_model}:generateContent?key={self.settings.gemini_api_key}"
        )
        prompt = (
            "You are a disciplined financial research assistant. Summarize the verified tool outputs below "
            "concisely in markdown, citing the exact numbers, sources, and assumptions. Do not invent numbers.\n\n"
            f"User query: {query}\n\nTool outputs:\n{str(tool_results)[:10000]}"
        )
        with httpx.Client(timeout=15.0) as client:
            resp = client.post(url, json={"contents": [{"parts": [{"text": prompt}]}]})
            resp.raise_for_status()
            data = resp.json()
            return data["candidates"][0]["content"]["parts"][0]["text"]

    def _call_openai(self, query: str, tool_results: dict[str, Any]) -> str | None:
        with httpx.Client(timeout=15.0) as client:
            resp = client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {self.settings.openai_api_key}"},
                json={
                    "model": self.settings.openai_model,
                    "messages": [
                        {
                            "role": "system",
                            "content": "You are a disciplined financial research assistant. Cite exact verified tool outputs and assumptions.",
                        },
                        {"role": "user", "content": f"Query: {query}\n\nTool outputs: {str(tool_results)[:10000]}"},
                    ],
                },
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]
