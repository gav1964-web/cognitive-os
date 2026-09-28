from pathlib import Path

from runtime.exception_pickle_candidate_audit import audit_exception_pickle_candidates


def test_audit_finds_incompatible_exception_and_skips_untouched(tmp_path: Path):
    exposed = tmp_path / "exposed"
    exposed.mkdir()
    (exposed / "errors.py").write_text(
        "class PayloadError(RuntimeError):\n"
        "    def __init__(self, payload, code):\n"
        "        self.payload = payload\n"
        "        message = f'{code}: {payload}'\n"
        "        super().__init__(message)\n",
        encoding="utf-8",
    )
    tests = exposed / "tests"
    tests.mkdir()
    (tests / "test_errors.py").write_text(
        "import pickle\n"
        "def test_payload_error():\n"
        "    pickle.loads(pickle.dumps(PayloadError('x', 2)))\n",
        encoding="utf-8",
    )
    untouched = tmp_path / "untouched"
    untouched.mkdir()
    (untouched / "errors.py").write_text(
        "class HiddenError(RuntimeError):\n"
        "    def __init__(self, value):\n"
        "        super().__init__(str(value))\n",
        encoding="utf-8",
    )

    report = audit_exception_pickle_candidates(
        projects=[
            {
                "project": "owner__exposed",
                "canonical_project": "owner__exposed",
                "owner": "owner",
                "project_root": "exposed",
                "exposure": "historically_exposed",
            },
            {
                "project": "owner__untouched",
                "canonical_project": "owner__untouched",
                "owner": "owner",
                "project_root": "untouched",
                "exposure": "untouched",
            },
        ],
        workspace_root=tmp_path,
    )

    assert report["status"] == "candidates_found"
    assert report["candidate_count"] == 1
    candidate = report["candidates"][0]
    assert candidate["class_name"] == "PayloadError"
    assert candidate["required_constructor_parameters"] == ["payload", "code"]
    assert candidate["pickle_test_signals"] == ["tests/test_errors.py"]
    assert report["scan"]["untouched_holdout_scanned"] is False


def test_audit_skips_exception_with_local_inherited_reduce(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "errors.py").write_text(
        "class ProjectError(Exception):\n"
        "    def __reduce__(self):\n"
        "        return (type(self), (), self.__dict__)\n"
        "\n"
        "class FormattedError(ProjectError):\n"
        "    def __init__(self, value):\n"
        "        self.value = value\n"
        "        super().__init__(f'value={value}')\n",
        encoding="utf-8",
    )

    report = audit_exception_pickle_candidates(
        projects=[{
            "project": "owner__project",
            "canonical_project": "owner__project",
            "owner": "owner",
            "project_root": "project",
            "exposure": "historically_exposed",
        }],
        workspace_root=tmp_path,
    )

    assert report["status"] == "no_candidates"
    assert report["candidate_count"] == 0


def test_audit_counts_required_keyword_only_constructor_inputs(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "errors.py").write_text(
        "class ParserSyntaxError(Exception):\n"
        "    def __init__(self, message, *, source, span):\n"
        "        self.message = message\n"
        "        self.source = source\n"
        "        self.span = span\n"
        "        super().__init__()\n",
        encoding="utf-8",
    )

    report = audit_exception_pickle_candidates(
        projects=[{
            "project": "pypa__packaging",
            "canonical_project": "pypa__packaging",
            "owner": "pypa",
            "project_root": "project",
            "exposure": "historically_exposed",
        }],
        workspace_root=tmp_path,
    )

    assert report["status"] == "candidates_found"
    candidate = report["candidates"][0]
    assert candidate["constructor_parameters"] == ["message", "source", "span"]
    assert candidate["required_constructor_parameters"] == [
        "message",
        "source",
        "span",
    ]
