from __future__ import annotations

import ast
import hashlib
from pathlib import Path

import pytest

from tools.programmer_l45_semantic_trial import _verify_provenance


def test_semantic_trial_verifies_frozen_ast_provenance(tmp_path: Path):
    project = tmp_path / "demo"
    project.mkdir()
    source = "def normalize(value):\n    return value.strip()\n"
    (project / "main.py").write_text(source, encoding="utf-8")
    node = ast.parse(source).body[0]
    digest = hashlib.sha256(ast.dump(node, include_attributes=False).encode()).hexdigest()
    case = {
        "id": "case",
        "project": "demo",
        "provenance": "main.py:normalize",
        "provenance_ast_sha256": digest,
    }

    assert _verify_provenance(tmp_path, case) == "verified_ast_fingerprint"

    case["provenance_ast_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="fingerprint mismatch"):
        _verify_provenance(tmp_path, case)
