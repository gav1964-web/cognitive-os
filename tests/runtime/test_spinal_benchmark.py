from pathlib import Path

from runtime.registry import CapabilityRegistry
from runtime.spinal_benchmark import run_spinal_benchmark


def test_spinal_benchmark_passes_contract_and_route_gates():
    root = Path(__file__).resolve().parents[2]
    CapabilityRegistry(root).reset_from_plugins()

    result = run_spinal_benchmark(root)

    assert result["status"] == "ok"
    assert result["summary"]["case_count"] == 8
    assert result["summary"]["route_accuracy"] == 1.0
    assert result["summary"]["quality_gate_rate"] == 1.0
    assert result["summary"]["packet_contract_rate"] == 1.0
    assert result["summary"]["recovery_accuracy"] == 1.0
    assert result["summary"]["llm_invocations"] == 0
