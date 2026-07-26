from __future__ import annotations

from runtime.human_document_quality import evaluate_human_role_documents


def test_human_document_quality_accepts_readable_foundation_documents(tmp_path):
    architecture = tmp_path / "architecture.md"
    spec = tmp_path / "spec.md"
    architecture.write_text(
        "\n".join(
            [
                "# Анализ архитектуры",
                "Документ для человека с ProjectMapReport evidence.",
                "## Краткое резюме",
                "Проект имеет понятный первый срез и проверяемые границы. " * 10,
                "## Рекомендации по улучшению",
                "Уточнить входы, выходы и границы ответственности.",
                "## Открытые вопросы",
                "Нет блокирующих вопросов.",
                "## Evidence и трассируемость",
                "ProjectMapReport -> ArchitectureDecisionRecord -> TechnicalSpec.",
            ]
        ),
        encoding="utf-8",
    )
    spec.write_text(
        "\n".join(
            [
                "# Техническое задание",
                "Документ для человека с TechnicalSpec API.",
                "## Главный контракт работ",
                "Кандидат source.py:run получает InputModel и возвращает OutputModel. " * 8,
                "## Контракт входа и выхода",
                "Вход и выход типизированы.",
                "## Validation gates и failure modes",
                "Ошибки входа и внешних зависимостей описаны.",
                "## Критерии приемки",
                "Критерии связаны с source.py:run.",
                "## Передача в реализацию",
                "Implementer получает bounded handoff.",
            ]
        ),
        encoding="utf-8",
    )

    report = evaluate_human_role_documents(architecture_document=architecture, technical_spec_document=spec)

    assert report["status"] == "pass"
    assert report["score"] == 1.0


def test_human_document_quality_blocks_empty_markdown(tmp_path):
    architecture = tmp_path / "architecture.md"
    spec = tmp_path / "spec.md"
    architecture.write_text("# Анализ архитектуры\n", encoding="utf-8")
    spec.write_text("# TechnicalSpec\n", encoding="utf-8")

    report = evaluate_human_role_documents(architecture_document=architecture, technical_spec_document=spec)

    assert report["status"] == "fail"
    assert "documents_do_not_look_empty" in report["warnings"]
