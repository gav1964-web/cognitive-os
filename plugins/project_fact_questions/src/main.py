"""Answer simple factual questions from Project Analyzer evidence."""

from __future__ import annotations

from typing import Any


OPENCV_IMPORT_ROOTS = {"cv2", "opencv", "opencv_python", "opencv-python"}
FILESYSTEM_IMPORT_ROOTS = {"os", "pathlib", "shutil", "tempfile", "glob", "zipfile", "tarfile", "io"}
FILESYSTEM_EFFECTS = {"filesystem", "filesystem_read"}


def run(payload: dict[str, object]) -> dict[str, object]:
    tree = dict(payload["tree"])  # type: ignore[index]
    python_structure = dict(payload["python_structure"])  # type: ignore[index]
    project_map_report = dict(payload.get("project_map_report") or {})
    scope = str(payload.get("scope") or "all")
    allowed_paths = _allowed_paths(project_map_report, scope)
    py_files = _filter_rows(_python_files(tree, python_structure), allowed_paths)
    over_300 = [
        {"path": row["path"], "line_count": row["line_count"]}
        for row in py_files
        if int(row.get("line_count") or 0) > 300
    ]
    opencv_files = _opencv_files(python_structure, allowed_paths)
    disk_files = _disk_files(python_structure, allowed_paths)
    return {
        "artifact_type": "ProjectFactQuestionAnswers",
        "scope": scope if allowed_paths is not None else "all",
        "answers": {
            "py_files_over_300_lines": {
                "count": len(over_300),
                "files": sorted(over_300, key=lambda row: (-int(row["line_count"]), str(row["path"]))),
            },
            "opencv_usage": {
                "count": len(opencv_files),
                "files": opencv_files,
            },
            "disk_work": {
                "count": len(disk_files),
                "files": disk_files,
            },
        },
        "evidence_policy": "static Project Analyzer evidence only; no LLM inference",
    }


def _python_files(tree: dict[str, Any], python_structure: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for item in tree.get("files", []):
        if not isinstance(item, dict):
            continue
        path = str(item.get("path") or "")
        if path.endswith(".py"):
            rows.append({"path": path, "line_count": int(item.get("line_count") or 0)})
    if rows:
        return rows
    # Fallback for older scan_project_tree payloads: exact line counts may be unavailable.
    return [
        {"path": str(item.get("path") or ""), "line_count": 0}
        for item in python_structure.get("files", [])
        if str(item.get("path") or "").endswith(".py")
    ]


def _opencv_files(python_structure: dict[str, Any], allowed_paths: set[str] | None) -> list[dict[str, Any]]:
    rows = []
    for file_row in python_structure.get("files", []):
        if not isinstance(file_row, dict):
            continue
        path = str(file_row.get("path") or "")
        if allowed_paths is not None and path not in allowed_paths:
            continue
        imports = {str(item).split(".", 1)[0].lower() for item in file_row.get("imports", [])}
        evidence = sorted(imports & OPENCV_IMPORT_ROOTS)
        if evidence:
            rows.append({"path": path, "evidence": [f"import:{item}" for item in evidence]})
    return sorted(rows, key=lambda row: str(row["path"]))


def _disk_files(python_structure: dict[str, Any], allowed_paths: set[str] | None) -> list[dict[str, Any]]:
    rows = []
    for file_row in python_structure.get("files", []):
        if not isinstance(file_row, dict):
            continue
        path = str(file_row.get("path") or "")
        if allowed_paths is not None and path not in allowed_paths:
            continue
        evidence = _disk_import_evidence(file_row)
        for function in file_row.get("functions", []):
            effects = set(function.get("side_effects", []) or [])
            if effects & FILESYSTEM_EFFECTS:
                evidence.append(
                    f"function:{function.get('name')}:{','.join(sorted(effects & FILESYSTEM_EFFECTS))}"
                )
        if evidence:
            rows.append({"path": path, "evidence": sorted(set(evidence))})
    return sorted(rows, key=lambda row: str(row["path"]))


def _disk_import_evidence(file_row: dict[str, Any]) -> list[str]:
    imports = {str(item).split(".", 1)[0].lower() for item in file_row.get("imports", [])}
    return [f"import:{item}" for item in sorted(imports & FILESYSTEM_IMPORT_ROOTS)]


def _allowed_paths(project_map_report: dict[str, Any], scope: str) -> set[str] | None:
    if scope != "active_core":
        return None
    answers = dict(project_map_report.get("answers") or {})
    readiness = dict(answers.get("6_runtime_extraction_readiness") or {})
    strata = dict(readiness.get("source_strata") or {})
    rows = strata.get("active_core") or []
    paths = {str(row.get("path") or "") for row in rows if isinstance(row, dict) and row.get("path")}
    return paths or None


def _filter_rows(rows: list[dict[str, Any]], allowed_paths: set[str] | None) -> list[dict[str, Any]]:
    if allowed_paths is None:
        return rows
    return [row for row in rows if str(row.get("path") or "") in allowed_paths]
