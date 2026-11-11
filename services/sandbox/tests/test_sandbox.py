from __future__ import annotations

import pytest

from packages.shared_schemas.schemas import SandboxRequest
from services.sandbox.ast_guard import SandboxSecurityError, validate_python_code
from services.sandbox.runner import SandboxService
from services.sandbox.templates import (
    DCF_WHAT_IF_SCRIPT,
    MONTE_CARLO_SCRIPT,
    STOCK_COMPARISON_SCRIPT,
)


def test_ast_guard_blocks_unsafe_imports_and_builtins():
    with pytest.raises(SandboxSecurityError):
        validate_python_code("import os\nresult = {'x': os.getcwd()}")

    with pytest.raises(SandboxSecurityError):
        validate_python_code("import subprocess\nsubprocess.run(['ls'])")

    with pytest.raises(SandboxSecurityError):
        validate_python_code("data = open('/etc/passwd').read()")

    with pytest.raises(SandboxSecurityError):
        validate_python_code("x = ().__class__.__bases__[0].__subclasses__()")


def test_sandbox_executes_dcf_and_comparison_templates():
    svc = SandboxService(mode="local_restricted")

    dcf = svc.run(
        SandboxRequest(
            code=DCF_WHAT_IF_SCRIPT,
            inputs={
                "base_fcf": 100e9,
                "shares_outstanding": 15e9,
                "fcf_growth_rate": 0.10,
                "wacc": 0.09,
                "terminal_growth": 0.03,
                "current_price": 200.0,
            },
        )
    )
    assert dcf.success is True, dcf.error
    assert dcf.outputs["intrinsic_value_per_share"] > 0
    assert len(dcf.outputs["sensitivity_matrix"]) == 5

    comp = svc.run(
        SandboxRequest(
            code=STOCK_COMPARISON_SCRIPT,
            inputs={
                "series": {
                    "AAPL": [
                        {"time": "2026-01-01", "close": 100.0},
                        {"time": "2026-01-02", "close": 102.0},
                        {"time": "2026-01-03", "close": 105.0},
                    ],
                    "MSFT": [
                        {"time": "2026-01-01", "close": 200.0},
                        {"time": "2026-01-02", "close": 198.0},
                        {"time": "2026-01-03", "close": 204.0},
                    ],
                }
            },
        )
    )
    assert comp.success is True, comp.error
    assert len(comp.outputs["metrics"]) == 2

    mc = svc.run(
        SandboxRequest(
            code=MONTE_CARLO_SCRIPT,
            inputs={"closes": [100.0, 101.2, 100.5, 102.4, 103.8], "horizon_days": 30, "n_paths": 300},
        )
    )
    assert mc.success is True, mc.error
    assert mc.outputs["terminal_p90"] >= mc.outputs["terminal_p10"]
