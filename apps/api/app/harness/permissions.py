from __future__ import annotations

import re

from services.sandbox.ast_guard import SandboxSecurityError, validate_python_code

ALLOWED_TOOLS = frozenset(
    {
        "get_technical_analysis",
        "get_fundamental_research",
        "compare_stocks_python",
        "run_what_if_dcf",
        "run_python_sandbox",
        "enqueue_deep_analysis",
    }
)

TICKER_PATTERN = re.compile(r"^[A-Z]{1,5}(?:\.[A-Z]{1,2})?$")


class PermissionDeniedError(PermissionError):
    """Raised when a harness tool call or argument violates permission policy."""


class PermissionPolicy:
    """Enforces tool allowlists, ticker sanitization, and Python sandbox AST guardrails."""

    def __init__(self, allowed_tools: frozenset[str] = ALLOWED_TOOLS) -> None:
        self.allowed_tools = allowed_tools

    def authorize_tool_call(self, tool_name: str, args: dict) -> dict:
        if tool_name not in self.allowed_tools:
            raise PermissionDeniedError(f"Tool '{tool_name}' is not permitted by harness policy.")

        sanitized = dict(args)
        if "ticker" in sanitized:
            t = str(sanitized["ticker"]).strip().upper()
            if not TICKER_PATTERN.match(t):
                raise PermissionDeniedError(f"Invalid ticker symbol '{sanitized['ticker']}'.")
            sanitized["ticker"] = t

        if "tickers" in sanitized and isinstance(sanitized["tickers"], list):
            clean_list: list[str] = []
            for raw in sanitized["tickers"][:5]:
                t = str(raw).strip().upper()
                if not TICKER_PATTERN.match(t):
                    raise PermissionDeniedError(f"Invalid ticker symbol '{raw}'.")
                clean_list.append(t)
            sanitized["tickers"] = clean_list

        if tool_name == "run_python_sandbox":
            code = str(sanitized.get("code", ""))
            try:
                validate_python_code(code)
            except SandboxSecurityError as exc:
                raise PermissionDeniedError(f"Sandbox script rejected by AST policy: {exc}") from exc

        return sanitized
