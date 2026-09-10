from pathlib import Path

from runtime.hypothesis_structural_screen import screen_projects


def test_structural_screen_requires_configured_semantic_context(tmp_path):
    logging_project = tmp_path / "logging_project"
    unrelated_project = tmp_path / "unrelated_project"
    logging_project.mkdir(); unrelated_project.mkdir()
    (logging_project / "formatter.py").write_text(
        "import logging\nclass JsonFormatter(logging.Formatter):\n"
        "    def format(self, record):\n        return record.msg\n",
        encoding="utf-8",
    )
    (unrelated_project / "state.py").write_text(
        "def format(value):\n    return value\n", encoding="utf-8",
    )
    policy = {
        "semantic_context": ["logging_record_projection"],
        "semantic_context_tokens": {
            "logging_record_projection": [
                "logging.formatter", "logrecord", "def format(self, record",
            ],
        },
        "semantic_context_callable_tokens": {
            "logging_record_projection": ["format"],
        },
        "maximum_shortlist_projects": 2,
    }

    report = screen_projects(
        [unrelated_project, logging_project], "meta_only|pure|return_expression", policy,
    )

    assert report["selected_projects"] == ["logging_project"]
    row = next(row for row in report["projects"] if row["project"] == "logging_project")
    assert row["contextual_evidence_samples"][0]["source"].endswith(":JsonFormatter.format")


def test_semantic_context_disables_unrelated_minimum_shortlist_fallback(tmp_path):
    project = tmp_path / "unrelated"
    project.mkdir()
    (project / "module.py").write_text(
        "def format_value(value):\n    return value\n", encoding="utf-8",
    )

    report = screen_projects([project], "meta_only|pure|return_expression", {
        "semantic_context": ["logging_record_projection"],
        "semantic_context_tokens": {"logging_record_projection": ["logrecord"]},
        "semantic_context_callable_tokens": {"logging_record_projection": ["format"]},
        "minimum_shortlist_projects": 1,
    })

    assert report["selected_projects"] == []


def test_runtime_failure_context_is_deferred_to_full_probe(tmp_path):
    project = tmp_path / "sample"
    project.mkdir()
    (project / "app.py").write_text(
        "def normalize(value: str) -> str:\n    return value.strip()\n",
        encoding="utf-8",
    )
    policy = {
        "maximum_shortlist_projects": 2,
        "semantic_context": [
            "executable_failure:argument_materialization_mismatch",
        ],
    }

    report = screen_projects(
        [project], "meta_only|pure|explicit_return_annotation", policy,
    )

    assert report["selected_projects"] == ["sample"]
    assert report["static_semantic_context"] == []
    assert report["runtime_only_semantic_context"] == [
        "executable_failure:argument_materialization_mismatch",
    ]


def _policy(**overrides):
    return {
        "maximum_shortlist_projects": 3,
        "minimum_shortlist_projects": 2,
        "maximum_python_files": 20,
        "maximum_functions": 100,
        "maximum_file_bytes": 100_000,
        "maximum_evidence_samples": 4,
        "excluded_directories": ["tests"],
        "weights": {"exact_effects": 60, "compatible_effects": 40, "output_basis": 40},
        **overrides,
    }


def _project(root: Path, name: str, source: str) -> Path:
    project = root / name
    project.mkdir()
    (project / "module.py").write_text(source, encoding="utf-8")
    return project


def test_screen_prioritizes_matching_effect_and_output_signature(tmp_path: Path):
    matching = _project(tmp_path, "matching", """
class Store:
    def update(self, value):
        self.values.append(value)
""")
    fallback = _project(tmp_path, "fallback", "def normalize(value):\n    return value.strip()\n")

    report = screen_projects(
        [fallback, matching],
        "side_effectful_target|memory_state|no_value_return",
        _policy(),
    )

    assert report["structural_match_project_count"] == 1
    assert report["selected_projects"] == ["matching", "fallback"]
    row = next(item for item in report["projects"] if item["project"] == "matching")
    assert row["structural_score"] == 100
    assert row["evidence_samples"][0]["source"] == "module.py:Store.update"
    assert row["evidence_samples"][0]["observed_side_effects"] == ["memory_state"]


def test_screen_supports_pure_return_signatures(tmp_path: Path):
    project = _project(tmp_path, "pure", "def normalize(value):\n    return value.strip()\n")

    report = screen_projects(
        [project], "executable_callable|pure|return_expression",
        _policy(minimum_shortlist_projects=1),
    )

    assert report["structural_match_project_count"] == 1
    assert report["selected_projects"] == ["pure"]


def test_screen_excludes_configured_non_product_directories(tmp_path: Path):
    project = _project(tmp_path, "product", "def normalize(value):\n    return value.strip()\n")
    tests = project / "tests"
    tests.mkdir()
    (tests / "test_state.py").write_text(
        "class Fake:\n    def update(self, value):\n        self.values.append(value)\n",
        encoding="utf-8",
    )

    report = screen_projects(
        [project], "side_effectful_target|memory_state|no_value_return",
        _policy(minimum_shortlist_projects=1),
    )

    assert report["structural_match_project_count"] == 0
    assert report["projects"][0]["files_scanned"] == 1


def test_screen_normalizes_void_output_and_uses_name_token_boundaries(tmp_path: Path):
    project = _project(tmp_path, "state", """
class Store:
    def detail(self, value) -> None:
        self.values.append(value)
""")
    policy = _policy(
        minimum_shortlist_projects=1,
        output_basis_families={
            "void_side_effect": ["no_value_return", "explicit_none_annotation"],
        },
        callable_name_tokens={"void_side_effect": ["emit"]},
        weights={
            "exact_effects": 60, "compatible_effects": 40,
            "output_basis": 40, "callable_name_signal": 20,
        },
    )

    report = screen_projects(
        [project], "side_effectful_target|memory_state|void_side_effect", policy,
    )

    assert report["structural_match_project_count"] == 1
    assert report["projects"][0]["structural_score"] == 100


def test_screen_does_not_rescan_full_source_per_function(monkeypatch, tmp_path: Path):
    source = "\n".join(
        f"def operation_{index}(value):\n    return value + {index}\n"
        for index in range(100)
    )
    project = _project(tmp_path, "generated", source)
    monkeypatch.setattr(
        "runtime.hypothesis_structural_screen.ast.get_source_segment",
        lambda *_args: (_ for _ in ()).throw(AssertionError("full-source rescan")),
    )

    report = screen_projects(
        [project], "executable_callable|pure|return_expression",
        _policy(maximum_functions=100, minimum_shortlist_projects=1),
    )

    assert report["projects"][0]["functions_scanned"] == 100


def test_screen_requires_recovery_candidate_when_contrast_provides_one(tmp_path: Path):
    recoverable = _project(tmp_path, "recoverable", """
def emit(value):
    print(value)

def normalize(value):
    return value.strip()

def typed(value: str) -> str:
    return value.strip()
""")
    failure_only = _project(tmp_path, "failure_only", """
def emit(value):
    print(value)

def verify(driver: Driver, timeout: int, locator: str) -> bool:
    ExternalWait(driver, timeout).until(locator)
    return True

def outer():
    def hidden() -> str:
        return "not an addressable module target"
    hidden
""")
    policy = _policy(
        minimum_shortlist_projects=2,
        recovery_contract={
            "min_return_paths": 1,
            "forbidden_output_inference_basis": ["no_value_return"],
            "no_observed_side_effects": True,
            "state_mutation": False,
        },
    )

    report = screen_projects(
        [failure_only, recoverable],
        "first_slice_reselection_required|observability|no_value_return",
        policy,
    )

    assert report["selected_projects"] == ["recoverable"]
    row = next(item for item in report["projects"] if item["project"] == "recoverable")
    assert row["structural_match_count"] == 1
    assert row["recovery_match_count"] == 2
    assert row["recovery_evidence_samples"][0]["source"] == "module.py:typed"
    rejected = next(item for item in report["projects"] if item["project"] == "failure_only")
    assert rejected["recovery_match_count"] == 0
