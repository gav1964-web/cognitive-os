from __future__ import annotations

from tests.runtime.exception_pickle_active_application_helpers import *

def test_self_reference_readmission_delta_rejects_imported_attribute_base(tmp_path: Path):
    project = tmp_path / "attribute-base"
    project.mkdir()
    (project / "pkg.py").write_text(
        "from external import error\n\n"
        "class ReaderError(error.Error):\n"
        "    def __init__(self, message):\n"
        "        self.message = message\n"
        "        super().__init__(self, message)\n",
        encoding="utf-8",
    )
    row = {
        "project_root": "attribute-base",
        "path": "pkg.py",
        "class_name": "ReaderError",
    }

    assert not _candidate_has_self_reference_args_readmission_delta(tmp_path, row)


def test_direct_file_effective_risk_ignores_stubbable_target_imports(tmp_path: Path):
    project = tmp_path / "risk-project"
    (project / "pkg").mkdir(parents=True)
    (project / "pkg" / "__init__.py").write_text(
        "import heavy_a\nimport heavy_b\n",
        encoding="utf-8",
    )
    (project / "pkg" / "errors.py").write_text(
        "import dep_a\nfrom dep_b import Thing\nfrom .base import BaseError\n\n"
        "class RiskError(BaseError):\n"
        "    def __init__(self, message):\n"
        "        self.message = message\n"
        "        super().__init__(message)\n",
        encoding="utf-8",
    )
    row = {
        "project_root": "risk-project",
        "path": "pkg/errors.py",
    }

    assert _candidate_effective_replay_risk(tmp_path, row) == 0


def test_direct_file_effective_risk_prefers_flat_file_with_stdlib_and_attr_imports(
    tmp_path: Path,
):
    project = tmp_path / "risk-project"
    project.mkdir()
    (project / "errors.py").write_text(
        "from __future__ import annotations\n"
        "from collections.abc import Sequence\n"
        "from typing import TYPE_CHECKING\n"
        "import attr\n\n"
        "@attr.s\n"
        "class AttrError(Exception):\n"
        "    value: str = attr.ib()\n\n"
        "class MaxLengthExceeded(Exception):\n"
        "    def __init__(self, value, property_name, max_length):\n"
        "        super().__init__(self, f'{value} {property_name} {max_length}')\n"
        "        self.value = value\n"
        "        self.property_name = property_name\n"
        "        self.max_length = max_length\n",
        encoding="utf-8",
    )
    row = {
        "project_root": "risk-project",
        "path": "errors.py",
    }

    assert _candidate_effective_replay_risk(tmp_path, row) == 0


def test_direct_file_effective_risk_prefers_bounded_target_declared_import_stubs(
    tmp_path: Path,
):
    project = tmp_path / "risk-project"
    project.mkdir()
    (project / "errors.py").write_text(
        "from enum import Enum\n"
        "from urllib.parse import urlparse\n"
        "import local_runtime\n"
        "from local_runtime.context import GlobalContext\n\n"
        "class ErrorName(Enum):\n"
        "    UnknownError = 'UnknownError'\n\n"
        "class MessageOnlyError(Exception):\n"
        "    def __init__(self, message):\n"
        "        super().__init__()\n"
        "        self.message = message\n",
        encoding="utf-8",
    )
    row = {
        "project_root": "risk-project",
        "path": "errors.py",
    }

    assert _candidate_effective_replay_risk(tmp_path, row) == 0


def test_direct_file_effective_risk_allows_stdlib_and_same_package_absolute_imports(
    tmp_path: Path,
):
    project = tmp_path / "risk-project"
    package = project / "pkg"
    package.mkdir(parents=True)
    (package / "errors.py").write_text(
        "from __future__ import annotations\n"
        "import os\n"
        "import secrets\n"
        "import time\n"
        "from abc import ABC\n"
        "from typing import Any\n"
        "from pkg.shared.store import Store\n\n"
        "class PackageLocalError(Exception):\n"
        "    def __init__(self, message):\n"
        "        self.message = message\n"
        "        super().__init__(message)\n",
        encoding="utf-8",
    )
    row = {
        "project_root": "risk-project",
        "path": "pkg/errors.py",
    }

    assert _candidate_effective_replay_risk(tmp_path, row) == 0


def test_static_patch_risk_allows_keyword_only_direct_state_constructor(tmp_path: Path):
    project = tmp_path / "keyword-project"
    package = project / "pkg"
    package.mkdir(parents=True)
    (package / "errors.py").write_text(
        "class ParserSyntaxError(Exception):\n"
        "    def __init__(self, message, *, source, span):\n"
        "        self.span = span\n"
        "        self.message = message\n"
        "        self.source = source\n"
        "        super().__init__()\n",
        encoding="utf-8",
    )
    row = {
        "project_root": str(project),
        "path": "pkg/errors.py",
        "class_name": "ParserSyntaxError",
        "required_constructor_parameters": ["message", "source", "span"],
    }

    assert _candidate_static_patch_risk(tmp_path, _active_catalog(), row) == 0


def test_direct_file_effective_risk_ignores_nested_raises(tmp_path: Path):
    project = tmp_path / "risk-project"
    (project / "pkg").mkdir(parents=True)
    (project / "pkg" / "__init__.py").write_text(
        "import heavy_package_init\n",
        encoding="utf-8",
    )
    (project / "pkg" / "errors.py").write_text(
        "class RiskError(Exception):\n"
        "    def __init__(self, message):\n"
        "        self.message = message\n"
        "        super().__init__(message)\n"
        "    def helper(self):\n"
        "        raise RuntimeError('not import time')\n",
        encoding="utf-8",
    )
    row = {
        "project_root": "risk-project",
        "path": "pkg/errors.py",
    }

    assert _candidate_effective_replay_risk(tmp_path, row) == 0


def test_active_application_direct_file_replay_preserves_relative_import_context(
    tmp_path: Path,
):
    _write_active_catalog(tmp_path)
    ledger = _write_transfer_ledger(tmp_path)
    project = tmp_path / "relative-project"
    (project / "pkg").mkdir(parents=True)
    (project / "pkg" / "__init__.py").write_text(
        "raise RuntimeError('package init must not execute')\n",
        encoding="utf-8",
    )
    (project / "pkg" / "errors.py").write_text(
        "from .base import ExternalBaseError\n\n"
        "class RelativeError(ExternalBaseError):\n"
        "    def __init__(self, message):\n"
        "        self.message = message\n"
        "        super().__init__(message)\n",
        encoding="utf-8",
    )
    audit = tmp_path / "audit.json"
    audit.write_text(
        json.dumps({
            "artifact_type": "ExceptionPickleCandidateAudit",
            "candidates": [{
                "canonical_project": "relative-project",
                "project_root": "relative-project",
                "path": "pkg/errors.py",
                "class_name": "RelativeError",
                "score": 7,
                "required_constructor_parameters": ["message"],
                "stored_constructor_parameters": ["message"],
            }],
        }),
        encoding="utf-8",
    )

    report = run_exception_pickle_active_application_trial(
        root=tmp_path,
        execution_dir=tmp_path / "execution",
        audit_path=audit,
        transfer_ledger_path=ledger,
        application_ledger_path=tmp_path / "application-ledger.json",
    )

    replay = report["selected_application"]["project_native_semantic_replay"]
    assert report["status"] == "applied_active_kb"
    assert '"import_strategy": "direct_file_import"' in replay["stdout"]
    assert "package init must not execute" not in replay["stderr"]


def test_active_application_replays_target_file_with_bounded_missing_import_stub(tmp_path: Path):
    _write_active_catalog(tmp_path)
    ledger = _write_transfer_ledger(tmp_path)
    project = tmp_path / "stub-project"
    project.mkdir()
    (project / "pkg.py").write_text(
        "from missing_base_package.errors import ExternalBaseError\n\n"
        "class MissingBaseError(ExternalBaseError):\n"
        "    def __init__(self, value):\n"
        "        self.value = value\n"
        "        super().__init__(value)\n",
        encoding="utf-8",
    )
    audit = tmp_path / "audit.json"
    audit.write_text(
        json.dumps({
            "artifact_type": "ExceptionPickleCandidateAudit",
            "candidates": [{
                "canonical_project": "stub-project",
                "project_root": "stub-project",
                "path": "pkg.py",
                "class_name": "MissingBaseError",
                "score": 7,
                "required_constructor_parameters": ["value"],
                "stored_constructor_parameters": ["value"],
            }],
        }),
        encoding="utf-8",
    )

    report = run_exception_pickle_active_application_trial(
        root=tmp_path,
        execution_dir=tmp_path / "execution",
        audit_path=audit,
        transfer_ledger_path=ledger,
        application_ledger_path=tmp_path / "application-ledger.json",
    )

    replay = report["selected_application"]["project_native_semantic_replay"]
    assert report["status"] == "applied_active_kb"
    assert '"import_strategy": "direct_file_import"' in replay["stdout"]


def test_active_application_replay_supports_py311_typing_and_enum_symbols(tmp_path: Path):
    _write_active_catalog(tmp_path)
    ledger = _write_transfer_ledger(tmp_path)
    project = tmp_path / "compat-project"
    project.mkdir()
    (project / "pkg.py").write_text(
        "from enum import StrEnum\n"
        "from types import GenericAlias\n"
        "from typing import Self, override\n\n"
        "class ErrorKind(StrEnum):\n"
        "    VALUE = 'value'\n\n"
        "class CompatError(Exception):\n"
        "    def __init__(self, value):\n"
        "        self.value = value\n"
        "        self.kind = ErrorKind.VALUE\n"
        "        self.alias_type = GenericAlias\n"
        "        super().__init__(value)\n\n"
        "    @override\n"
        "    def with_value(self, value) -> Self:\n"
        "        return type(self)(value)\n",
        encoding="utf-8",
    )
    audit = tmp_path / "audit.json"
    audit.write_text(
        json.dumps({
            "artifact_type": "ExceptionPickleCandidateAudit",
            "candidates": [{
                "canonical_project": "compat-project",
                "project_root": "compat-project",
                "path": "pkg.py",
                "class_name": "CompatError",
                "score": 7,
                "required_constructor_parameters": ["value"],
                "stored_constructor_parameters": ["value"],
            }],
        }),
        encoding="utf-8",
    )

    report = run_exception_pickle_active_application_trial(
        root=tmp_path,
        execution_dir=tmp_path / "execution",
        audit_path=audit,
        transfer_ledger_path=ledger,
        application_ledger_path=tmp_path / "application-ledger.json",
    )

    assert report["status"] == "applied_active_kb"
    assert report["selected_application"]["candidate"]["target"] == "pkg.py:CompatError.__init__"


def test_active_application_replay_avoids_local_stdlib_shadowing(tmp_path: Path):
    _write_active_catalog(tmp_path)
    ledger = _write_transfer_ledger(tmp_path)
    project = tmp_path / "shadow-project"
    package = project / "src" / "envium"
    package.mkdir(parents=True)
    (project / "src" / "types.py").write_text("class LocalType: pass\n", encoding="utf-8")
    (package / "exceptions.py").write_text(
        "from types import GenericAlias\n\n"
        "class ShadowCompatError(Exception):\n"
        "    def __init__(self, value):\n"
        "        self.value = value\n"
        "        self.alias_type = GenericAlias\n"
        "        super().__init__(value)\n",
        encoding="utf-8",
    )
    audit = tmp_path / "audit.json"
    audit.write_text(
        json.dumps({
            "artifact_type": "ExceptionPickleCandidateAudit",
            "candidates": [{
                "canonical_project": "shadow-project",
                "project_root": "shadow-project",
                "path": "src/envium/exceptions.py",
                "class_name": "ShadowCompatError",
                "score": 7,
                "required_constructor_parameters": ["value"],
                "stored_constructor_parameters": ["value"],
            }],
        }),
        encoding="utf-8",
    )

    report = run_exception_pickle_active_application_trial(
        root=tmp_path,
        execution_dir=tmp_path / "execution",
        audit_path=audit,
        transfer_ledger_path=ledger,
        application_ledger_path=tmp_path / "application-ledger.json",
    )

    assert report["status"] == "applied_active_kb"
    assert report["selected_application"]["candidate"]["target"] == (
        "src/envium/exceptions.py:ShadowCompatError.__init__"
    )


