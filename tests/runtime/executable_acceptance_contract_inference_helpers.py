from pathlib import Path

from runtime.executable_acceptance import run_executable_acceptance
from runtime.executable_acceptance_contract_inference import infer_argument_samples
from tests.runtime.test_executable_acceptance import _plan


def _source(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "module.py"
    path.write_text(text, encoding="utf-8")
    return path

























































__all__ = [name for name in globals() if not name.startswith("__")]
