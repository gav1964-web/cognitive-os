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


def test_hypothesis_driven_self_improvement_docs_match_runtime():
    self_improvement = (ROOT / "SELF_IMPROVEMENT.md").read_text(encoding="utf-8")
    readme = (ROOT / "docs/architecture/research.md").read_text(encoding="utf-8")
    baseline = (ROOT / "COGNITIVE_OS_TECHNICAL_BASELINE.md").read_text(encoding="utf-8")

    for text in (self_improvement, readme, baseline):
        normalized = " ".join(text.lower().split())
        assert "HypothesisValidationPlan" in text
        assert "post-training admission" in normalized
        assert "newly discovered match" in normalized or "минимум новых matches" in normalized
    assert "external_discovery_failed" in self_improvement
    assert "insufficient_matching_holdouts" in self_improvement
    assert "insufficient_new_matching_holdouts" in self_improvement
    assert "hypothesis_validation_*.json" in self_improvement
    assert "maximum_discovery_rounds" in self_improvement
    assert "probe_failed" in self_improvement
    assert "GitLab -> GitHub" in self_improvement
    assert "large blind corpora remain release/calibration" in readme
    assert (ROOT / "runtime" / "self_improvement_hypothesis_validation.py").exists()
    assert (ROOT / "runtime" / "self_improvement_hypothesis_compiler.py").exists()
    assert (ROOT / "config" / "hypothesis_compiler.json").exists()
    assert "Hypothesis Compiler" in self_improvement
    assert "HypothesisCandidate" in baseline
    assert (ROOT / "tools" / "self_improvement_project_discovery.py").exists()
