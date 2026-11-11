from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Literal

from packages.shared_schemas.schemas import SandboxRequest, SandboxResult
from services.sandbox.ast_guard import SandboxSecurityError, validate_python_code


class SandboxService:
    """Executes quantitative Python scripts in an isolated Docker container (or restricted dev subprocess)."""

    def __init__(
        self,
        mode: Literal["docker", "local_restricted"] | None = None,
        docker_image: str | None = None,
    ) -> None:
        env_mode = mode or os.getenv("SANDBOX_MODE", "docker")
        self.mode: Literal["docker", "local_restricted"] = (
            "local_restricted" if env_mode == "local_restricted" else "docker"
        )
        self.docker_image = docker_image or os.getenv("SANDBOX_DOCKER_IMAGE", "stock-assistant-sandbox:latest")
        self._entry_script = Path(__file__).resolve().parent / "sandbox_entry.py"

    def run(self, request: SandboxRequest) -> SandboxResult:
        start = time.perf_counter()
        try:
            validate_python_code(request.code)
        except SandboxSecurityError as exc:
            return SandboxResult(
                success=False,
                mode=self.mode,
                error=str(exc),
                execution_ms=int((time.perf_counter() - start) * 1000),
            )

        payload = json.dumps({"code": request.code, "inputs": request.inputs})
        if self.mode == "docker":
            return self._run_docker(payload, request.timeout_seconds, start)
        return self._run_local_restricted(payload, request.timeout_seconds, start)

    def _run_docker(self, payload: str, timeout_seconds: int, start: float) -> SandboxResult:
        cmd = [
            "docker",
            "run",
            "--rm",
            "-i",
            "--network",
            "none",
            "--read-only",
            "--tmpfs",
            "/tmp:rw,noexec,nosuid,size=64m",
            "--cpus",
            "1.0",
            "--memory",
            "512m",
            "--pids-limit",
            "64",
            "--user",
            "65534:65534",
            self.docker_image,
        ]
        try:
            proc = subprocess.run(
                cmd,
                input=payload,
                text=True,
                capture_output=True,
                timeout=timeout_seconds,
                check=False,
            )
            return self._parse_subprocess_result(proc, "docker", start)
        except FileNotFoundError:
            return SandboxResult(
                success=False,
                mode="docker",
                error="Docker binary not found. Install Docker Desktop or set SANDBOX_MODE=local_restricted for local dev.",
                execution_ms=int((time.perf_counter() - start) * 1000),
            )
        except subprocess.TimeoutExpired:
            return SandboxResult(
                success=False,
                mode="docker",
                error=f"Sandbox execution timed out after {timeout_seconds}s.",
                execution_ms=int((time.perf_counter() - start) * 1000),
            )

    def _run_local_restricted(self, payload: str, timeout_seconds: int, start: float) -> SandboxResult:
        minimal_env = {
            "PATH": os.environ.get("PATH", ""),
            "SYSTEMROOT": os.environ.get("SYSTEMROOT", ""),
            "PYTHONNOUSERSITE": "1",
            "PYTHONDONTWRITEBYTECODE": "1",
        }
        try:
            with tempfile.TemporaryDirectory(prefix="stock_sandbox_") as tmpdir:
                proc = subprocess.run(
                    [sys.executable, "-I", str(self._entry_script)],
                    input=payload,
                    text=True,
                    capture_output=True,
                    timeout=timeout_seconds,
                    cwd=tmpdir,
                    env=minimal_env,
                    check=False,
                )
            return self._parse_subprocess_result(proc, "local_restricted", start)
        except subprocess.TimeoutExpired:
            return SandboxResult(
                success=False,
                mode="local_restricted",
                error=f"Sandbox execution timed out after {timeout_seconds}s.",
                execution_ms=int((time.perf_counter() - start) * 1000),
            )

    @staticmethod
    def _parse_subprocess_result(
        proc: subprocess.CompletedProcess[str],
        mode: Literal["docker", "local_restricted"],
        start: float,
    ) -> SandboxResult:
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        stdout = (proc.stdout or "").strip()
        if not stdout:
            return SandboxResult(
                success=False,
                mode=mode,
                error=proc.stderr.strip() or f"Sandbox exited with code {proc.returncode} and no output.",
                execution_ms=elapsed_ms,
            )
        try:
            parsed = json.loads(stdout.splitlines()[-1])
        except json.JSONDecodeError:
            return SandboxResult(
                success=False,
                mode=mode,
                stdout=stdout,
                error=f"Malformed sandbox JSON response: {proc.stderr.strip()}",
                execution_ms=elapsed_ms,
            )
        return SandboxResult(
            success=bool(parsed.get("success", False)),
            mode=mode,
            outputs=parsed.get("outputs", {}),
            stdout=parsed.get("stdout", ""),
            error=parsed.get("error"),
            execution_ms=elapsed_ms,
        )
