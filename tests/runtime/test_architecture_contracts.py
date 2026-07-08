from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_baseline_contracts_have_code_gates():
    baseline = (ROOT / "COGNITIVE_OS_TECHNICAL_BASELINE.md").read_text(encoding="utf-8")
    assert "Правило 400 строк" in baseline
    assert (ROOT / "runtime" / "plugin_lint.py").exists()
    assert "Plugin Isolation" in baseline
    assert "plugin-to-plugin import is forbidden" in (ROOT / "runtime" / "plugin_lint.py").read_text(encoding="utf-8")


def test_capability_foundry_is_explicit_in_docs_and_tools():
    manifesto = (ROOT / "COGNITIVE_OS_MANIFESTO.md").read_text(encoding="utf-8")
    spec = (ROOT / "MVP_RUNTIME_SPEC.md").read_text(encoding="utf-8")
    assert "Кузница возможностей" in manifesto
    assert "Уровню 3.2" in spec
    assert (ROOT / "tools" / "generate_plugin_candidate.py").exists()
    assert (ROOT / "tools" / "promote_candidate.py").exists()
    assert (ROOT / "tools" / "rebuild_capability.py").exists()


def test_level_35_backend_boundary_exists():
    baseline = (ROOT / "COGNITIVE_OS_TECHNICAL_BASELINE.md").read_text(encoding="utf-8")
    assert "vLLM" in baseline and "Ollama" in baseline and "llama.cpp" in baseline
    assert (ROOT / "runtime" / "local_inference.py").exists()


def test_contract_registry_is_documented_and_enforced():
    baseline = (ROOT / "COGNITIVE_OS_TECHNICAL_BASELINE.md").read_text(encoding="utf-8")
    spec = (ROOT / "MVP_RUNTIME_SPEC.md").read_text(encoding="utf-8")
    assert "Contract Registry" in baseline
    assert "runtime/contract_registry.py" in spec
    assert (ROOT / "runtime" / "contract_registry.py").exists()
