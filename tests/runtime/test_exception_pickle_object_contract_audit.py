import json
from pathlib import Path

from runtime.exception_pickle_object_contract_audit import (
    run_exception_pickle_object_contract_audit,
)
from runtime.local_inference import LocalInferenceConfig


def test_object_contract_audit_extracts_source_backed_shapes(tmp_path: Path):
    project = tmp_path / "pkg"
    project.mkdir()
    (project / "errors.py").write_text(
        "class DomainError(RuntimeError):\n"
        "    def __init__(self, tenant, package_names):\n"
        "        self.tenant = tenant\n"
        "        self.package_names = package_names\n"
        "        super().__init__(f'{tenant}: ' + ','.join(package_names))\n"
        "\n"
        "class BodyError(RuntimeError):\n"
        "    def __init__(self, body):\n"
        "        self.status = body.get('status')\n"
        "        self.message = body['message']\n"
        "        super().__init__(self.message)\n"
        "\n"
        "class TarError(RuntimeError):\n"
        "    def __init__(self, tarinfo):\n"
        "        self.name = tarinfo.name\n"
        "        super().__init__(tarinfo.name)\n",
        encoding="utf-8",
    )
    audit = tmp_path / "audit.json"
    audit.write_text(
        json.dumps({
            "candidates": [
                {
                    "canonical_project": "pkg",
                    "project_root": "pkg",
                    "path": "errors.py",
                    "class_name": "DomainError",
                    "required_constructor_parameters": ["tenant", "package_names"],
                },
                {
                    "canonical_project": "pkg",
                    "project_root": "pkg",
                    "path": "errors.py",
                    "class_name": "BodyError",
                    "required_constructor_parameters": ["body"],
                },
                {
                    "canonical_project": "pkg",
                    "project_root": "pkg",
                    "path": "errors.py",
                    "class_name": "TarError",
                    "required_constructor_parameters": ["tarinfo"],
                },
            ],
        }),
        encoding="utf-8",
    )
    ledger = tmp_path / "ledger.json"
    ledger.write_text(
        json.dumps({
            "blocked_cases": [
                {
                    "project": "pkg",
                    "target": "errors.py:DomainError.__init__",
                    "blocker_kind": "semantic_sample_shape_unsupported",
                },
                {
                    "project": "pkg",
                    "target": "errors.py:BodyError.__init__",
                    "blocker_kind": "semantic_sample_shape_unsupported",
                },
                {
                    "project": "pkg",
                    "target": "errors.py:TarError.__init__",
                    "blocker_kind": "semantic_sample_shape_unsupported",
                },
            ],
        }),
        encoding="utf-8",
    )

    report = run_exception_pickle_object_contract_audit(
        root=tmp_path,
        audit_path=audit,
        application_ledger_path=ledger,
    )

    assert report["status"] == "ready"
    assert report["case_count"] == 3
    assert report["contract_summary"] == {
        "attribute_object": 1,
        "iterable_string_list": 1,
        "mapping_object": 1,
        "string_like": 1,
    }
    by_parameter = {
        contract["parameter"]: contract
        for case in report["cases"]
        for contract in case["contracts"]
    }
    assert by_parameter["tenant"]["contract_kind"] == "string_like"
    assert by_parameter["package_names"]["contract_kind"] == "iterable_string_list"
    assert by_parameter["body"]["evidence"]["mapping_keys"] == ["message", "status"]
    assert by_parameter["tarinfo"]["evidence"]["attributes"] == ["name"]
    assert report["source_apply"] is False
    assert report["kb_promotion"] is False
    assert report["llm_authority"] == "advisory_only"


def test_object_contract_audit_keeps_llm_advisory_non_authoritative(tmp_path: Path, monkeypatch):
    project = tmp_path / "pkg"
    project.mkdir()
    (project / "errors.py").write_text(
        "class BodyError(RuntimeError):\n"
        "    def __init__(self, body):\n"
        "        self.status = body.get('status')\n"
        "        super().__init__(str(self.status))\n",
        encoding="utf-8",
    )
    audit = tmp_path / "audit.json"
    audit.write_text(
        json.dumps({
            "candidates": [{
                "canonical_project": "pkg",
                "project_root": "pkg",
                "path": "errors.py",
                "class_name": "BodyError",
                "required_constructor_parameters": ["body"],
            }],
        }),
        encoding="utf-8",
    )
    ledger = tmp_path / "ledger.json"
    ledger.write_text(
        json.dumps({
            "blocked_cases": [{
                "project": "pkg",
                "target": "errors.py:BodyError.__init__",
                "blocker_kind": "semantic_sample_shape_unsupported",
            }],
        }),
        encoding="utf-8",
    )

    def fake_chat(messages, *, config):
        return {
            "contracts": [{
                "parameter": "body",
                "contract_kind": "attribute_object",
                "reason": "bad conflicting suggestion",
            }]
        }

    monkeypatch.setattr("runtime.exception_pickle_object_contract_audit.call_json_chat", fake_chat)
    report = run_exception_pickle_object_contract_audit(
        root=tmp_path,
        audit_path=audit,
        application_ledger_path=ledger,
        advisory_config=LocalInferenceConfig(
            base_url="http://example.test/v1",
            model="test",
            provider_label="test_llm",
        ),
    )

    advisory = report["cases"][0]["advisory"]
    assert advisory["llm_invoked"] is True
    assert advisory["authority"] == "advisory_only"
    assert advisory["suggestions"][0]["accepted"] is False
    assert report["cases"][0]["contracts"][0]["contract_kind"] == "mapping_object"


def test_object_contract_audit_excludes_later_applied_targets(tmp_path: Path):
    project = tmp_path / "pkg"
    project.mkdir()
    (project / "errors.py").write_text(
        "class BodyError(RuntimeError):\n"
        "    def __init__(self, body):\n"
        "        self.body = body\n"
        "        super().__init__(body)\n",
        encoding="utf-8",
    )
    audit = tmp_path / "audit.json"
    audit.write_text(
        json.dumps({
            "candidates": [{
                "canonical_project": "pkg",
                "project_root": "pkg",
                "path": "errors.py",
                "class_name": "BodyError",
                "required_constructor_parameters": ["body"],
            }],
        }),
        encoding="utf-8",
    )
    ledger = tmp_path / "ledger.json"
    ledger.write_text(
        json.dumps({
            "cases": [{
                "project": "pkg",
                "target": "errors.py:BodyError.__init__",
                "status": "applied_active_kb",
            }],
            "blocked_cases": [{
                "project": "pkg",
                "target": "errors.py:BodyError.__init__",
                "blocker_kind": "semantic_sample_shape_unsupported",
            }],
        }),
        encoding="utf-8",
    )

    report = run_exception_pickle_object_contract_audit(
        root=tmp_path,
        audit_path=audit,
        application_ledger_path=ledger,
    )

    assert report["case_count"] == 0
    assert report["contract_summary"] == {}


def test_object_contract_audit_follows_simple_aliases_and_profiles_safe_methods(tmp_path: Path):
    project = tmp_path / "pkg"
    project.mkdir()
    (project / "errors.py").write_text(
        "class AliasBodyError(RuntimeError):\n"
        "    def __init__(self, body):\n"
        "        payload = body\n"
        "        self.message = payload['message']\n"
        "        super().__init__(self.message)\n"
        "\n"
        "class JsonBodyError(RuntimeError):\n"
        "    def __init__(self, http_result):\n"
        "        body = http_result.json()\n"
        "        super().__init__(body['message'])\n"
        "\n"
        "class UnsafeMethodError(RuntimeError):\n"
        "    def __init__(self, http_result):\n"
        "        super().__init__(http_result.json('forced'))\n",
        encoding="utf-8",
    )
    audit = tmp_path / "audit.json"
    audit.write_text(
        json.dumps({
            "candidates": [
                {
                    "canonical_project": "pkg",
                    "project_root": "pkg",
                    "path": "errors.py",
                    "class_name": "AliasBodyError",
                    "required_constructor_parameters": ["body"],
                },
                {
                    "canonical_project": "pkg",
                    "project_root": "pkg",
                    "path": "errors.py",
                    "class_name": "JsonBodyError",
                    "required_constructor_parameters": ["http_result"],
                },
                {
                    "canonical_project": "pkg",
                    "project_root": "pkg",
                    "path": "errors.py",
                    "class_name": "UnsafeMethodError",
                    "required_constructor_parameters": ["http_result"],
                },
            ],
        }),
        encoding="utf-8",
    )
    ledger = tmp_path / "ledger.json"
    ledger.write_text(
        json.dumps({
            "blocked_cases": [
                {
                    "project": "pkg",
                    "target": "errors.py:AliasBodyError.__init__",
                    "blocker_kind": "semantic_sample_shape_unsupported",
                },
                {
                    "project": "pkg",
                    "target": "errors.py:JsonBodyError.__init__",
                    "blocker_kind": "semantic_sample_shape_unsupported",
                },
                {
                    "project": "pkg",
                    "target": "errors.py:UnsafeMethodError.__init__",
                    "blocker_kind": "semantic_sample_shape_unsupported",
                },
            ],
        }),
        encoding="utf-8",
    )

    report = run_exception_pickle_object_contract_audit(
        root=tmp_path,
        audit_path=audit,
        application_ledger_path=ledger,
    )

    contracts = {
        case["target"]: case["contracts"][0]
        for case in report["cases"]
    }
    assert contracts["errors.py:AliasBodyError.__init__"]["contract_kind"] == "mapping_object"
    assert contracts["errors.py:AliasBodyError.__init__"]["evidence"]["aliases"] == ["payload"]
    assert contracts["errors.py:JsonBodyError.__init__"]["contract_kind"] == "method_object"
    assert contracts["errors.py:JsonBodyError.__init__"]["evidence"]["method_return_profiles"] == {"json": "mapping"}
    assert contracts["errors.py:UnsafeMethodError.__init__"]["contract_kind"] == "opaque_hold"
    assert contracts["errors.py:UnsafeMethodError.__init__"]["evidence"]["opaque_reasons"] == [
        "parameter_method_call"
    ]
