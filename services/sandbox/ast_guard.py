from __future__ import annotations

import ast

ALLOWED_MODULES = frozenset(
    {
        "math",
        "statistics",
        "datetime",
        "decimal",
        "fractions",
        "itertools",
        "functools",
        "collections",
        "json",
        "numpy",
        "np",
        "pandas",
        "pd",
        "scipy",
    }
)

FORBIDDEN_CALLS = frozenset(
    {
        "open",
        "eval",
        "exec",
        "compile",
        "__import__",
        "globals",
        "locals",
        "vars",
        "dir",
        "getattr",
        "setattr",
        "delattr",
        "input",
        "breakpoint",
    }
)

FORBIDDEN_ATTRS = frozenset(
    {
        "__class__",
        "__bases__",
        "__subclasses__",
        "__mro__",
        "__globals__",
        "__builtins__",
        "__code__",
        "__closure__",
        "__dict__",
    }
)


class SandboxSecurityError(ValueError):
    """Raised when user/LLM-generated Python code violates sandbox AST rules."""


def validate_python_code(code: str) -> None:
    """Validate Python code against an allowlist of safe analytical imports and builtins."""
    if not code or not code.strip():
        raise SandboxSecurityError("Empty Python script cannot be executed.")

    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        raise SandboxSecurityError(f"Syntax error in sandbox script: {exc}") from exc

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                if root not in ALLOWED_MODULES:
                    raise SandboxSecurityError(f"Import '{alias.name}' is not allowed in the Python sandbox.")
        elif isinstance(node, ast.ImportFrom):
            if node.module is None:
                raise SandboxSecurityError("Relative imports are not allowed in the Python sandbox.")
            root = node.module.split(".")[0]
            if root not in ALLOWED_MODULES:
                raise SandboxSecurityError(f"Import from '{node.module}' is not allowed in the Python sandbox.")
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in FORBIDDEN_CALLS:
                raise SandboxSecurityError(f"Builtin call '{node.func.id}()' is forbidden in the Python sandbox.")
        elif isinstance(node, ast.Attribute):
            if node.attr in FORBIDDEN_ATTRS:
                raise SandboxSecurityError(f"Attribute access '{node.attr}' is forbidden in the Python sandbox.")
