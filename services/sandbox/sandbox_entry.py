from __future__ import annotations

import contextlib
import io
import json
import math
import statistics
import sys
import traceback


def main() -> None:
    raw = sys.stdin.read()
    try:
        payload = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError as exc:
        print(json.dumps({"success": False, "error": f"Invalid JSON payload: {exc}", "outputs": {}, "stdout": ""}))
        return

    code = payload.get("code", "")
    inputs = payload.get("inputs", {})

    stdout_buf = io.StringIO()
    env: dict[str, object] = {
        "__builtins__": {
            "abs": abs,
            "all": all,
            "any": any,
            "bool": bool,
            "dict": dict,
            "enumerate": enumerate,
            "float": float,
            "int": int,
            "isinstance": isinstance,
            "len": len,
            "list": list,
            "max": max,
            "min": min,
            "pow": pow,
            "print": print,
            "range": range,
            "round": round,
            "set": set,
            "sorted": sorted,
            "str": str,
            "sum": sum,
            "tuple": tuple,
            "zip": zip,
            "__import__": __import__,
        },
        "inputs": inputs,
        "result": {},
        "math": math,
        "statistics": statistics,
    }

    try:
        with contextlib.redirect_stdout(stdout_buf):
            exec(compile(code, "<sandbox>", "exec"), env, env)  # noqa: S102
        out = env.get("result", {})
        if not isinstance(out, dict):
            out = {"value": out}
        print(
            json.dumps(
                {
                    "success": True,
                    "outputs": out,
                    "stdout": stdout_buf.getvalue(),
                    "error": None,
                },
                default=str,
            )
        )
    except Exception:
        print(
            json.dumps(
                {
                    "success": False,
                    "outputs": {},
                    "stdout": stdout_buf.getvalue(),
                    "error": traceback.format_exc(limit=4),
                }
            )
        )


if __name__ == "__main__":
    main()
