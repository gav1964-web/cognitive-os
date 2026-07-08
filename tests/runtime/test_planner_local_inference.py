from __future__ import annotations

from unittest.mock import patch

from runtime.models import PolicyDecision
from runtime.planner_stub import plan_recovery


class _Registry:
    def find_fallback(self, capability_id):
        return None


def test_planner_uses_local_inference_when_enabled(monkeypatch):
    monkeypatch.setenv("COGNITIVE_OS_ENABLE_LOCAL_PLANNER", "1")
    with patch("runtime.planner_stub.call_json_chat", return_value={"action": "STOP", "reason_code": "MODEL_STOP"}):
        decision = plan_recovery(
            {"error_class": "runtime_error", "capability_id": "x", "suggested_actions": ["STOP"]},
            _Registry(),
        )

    assert isinstance(decision, PolicyDecision)
    assert decision.action == "STOP"
    assert decision.reason_code == "MODEL_STOP"
