"""Human-readable document for mixed-root scope selection."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def write_scope_selection_document(*, root: Path, scope_report: dict[str, Any], output_group: str = "foundations") -> Path:
    out_dir = root / "artifacts" / "roles" / output_group
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    path = out_dir / f"scope_selection_{stamp}.md"
    path.write_text(render_scope_selection_document(scope_report), encoding="utf-8")
    return path


def render_scope_selection_document(scope_report: dict[str, Any]) -> str:
    candidates = list(scope_report.get("candidate_roots") or [])
    lines = [
        "# Выбор активного корня проекта",
        "",
        "## Итог",
        f"- Статус: `{scope_report.get('status')}`",
        f"- Корень: `{scope_report.get('root')}`",
        f"- Причина остановки: {scope_report.get('reason')}",
        f"- Уверенность выбора: `{scope_report.get('selection_confidence')}`",
        f"- Автовыбранный кандидат: `{scope_report.get('preferred_candidate') or 'нет'}`",
        f"- Следующее действие: `{scope_report.get('recommended_action')}`",
        "",
        "## Почему downstream остановлен",
        "Project Analyzer обнаружил смешанный root: под одним каталогом лежат несколько поколений, срезов или рабочих областей. "
        "До явного выбора active root нельзя строить ArchitectureDecisionRecord и TechnicalSpec, иначе Architect/SpecWriter будут смешивать старое, новое, тестовое и generated.",
        "",
        "## Кандидаты active root",
    ]
    if not candidates:
        lines.append("- Кандидаты не найдены.")
    for row in candidates:
        lines.extend(
            [
                f"### `{row.get('path')}`",
                f"- Тип: `{row.get('kind')}`",
                f"- Score: `{row.get('score')}`",
                f"- Файлы: `{row.get('file_count')}`, Python: `{row.get('python_files')}`, JS/TS: `{row.get('js_ts_files')}`",
                f"- Markdown: `{row.get('markdown_files')}`, max depth: `{row.get('max_depth')}`",
                f"- Последнее изменение: `{row.get('last_write') or 'unknown'}`",
                f"- Manifest samples: {_inline_list(row.get('manifest_samples'))}",
                f"- Noise samples: {_inline_list(row.get('noise_samples'))}",
                f"- Крупные Python-файлы: {_inline_python(row.get('largest_python_samples'))}",
                "",
            ]
        )
    evidence = dict(scope_report.get("evidence") or {})
    lines.extend(
        [
            "## Evidence",
            f"- Project shape: `{evidence.get('project_shape')}`",
            f"- Tree counts: `{evidence.get('tree_counts')}`",
            f"- Generated/run samples: {_inline_list(evidence.get('generated_run_samples'))}",
            f"- Artifact-noise samples: {_inline_list(evidence.get('artifact_noise_samples'))}",
            f"- Packaged-copy samples: {_inline_list(evidence.get('packaged_copy_samples'))}",
            "",
            "## Политика исключения шума",
            _inline_list(scope_report.get("excluded_noise_policy")),
            "",
            "## Разрешенные следующие шаги",
            "1. Выбрать один active root и передать его как `--active-root`.",
            "2. Повторить foundation pipeline уже на выбранном срезе.",
            "3. Сравнить ADR/TechnicalSpec по нескольким кандидатам, если active root не очевиден.",
            "",
        ]
    )
    return "\n".join(lines)


def _inline_list(values: object) -> str:
    items = [str(item) for item in list(values or [])]
    return ", ".join(f"`{item}`" for item in items[:8]) or "`нет`"


def _inline_python(values: object) -> str:
    rows = []
    for row in list(values or [])[:5]:
        item = dict(row)
        rows.append(f"{item.get('path')} ({item.get('size_bytes')} bytes)")
    return ", ".join(f"`{row}`" for row in rows) or "`нет`"
