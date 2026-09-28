from __future__ import annotations

from pathlib import Path

from plugins.apply_project_change_recipe.src.main import run


def test_apply_project_change_recipe_updates_configured_files(tmp_path, monkeypatch):
    project = tmp_path / "project"
    (project / "app" / "gigachat").mkdir(parents=True)
    (project / "app" / "api").mkdir(parents=True)
    (project / "tests").mkdir(parents=True)
    (project / "app" / "gigachat" / "orchestrator.py").write_text(
        '"""x"""\n'
        ":param model: Model name (if None, will classify)\n"
        "        # Step 3: Classify if model not specified\n"
        "        if selected_model is None:\n"
        "            selected_model, search_flag, search_queries = await self.classifier.classify(messages)\n",
        encoding="utf-8",
    )
    (project / "app" / "api" / "server.py").write_text(
        "    # Normalize model name: add provider prefix if missing\n"
        "    # For gigachat, pass None for auto model selection\n"
        "    final_model_name = model_name\n"
        "    if provider_id.lower() == \"gigachat\":\n"
        "        final_model_name = model_name or None\n",
        encoding="utf-8",
    )
    (project / "tests" / "test_gigachat_decomposition.py").write_text(
        "    async def test_orchestrator_model_none_triggers_classifier(self):\n"
        "        \"\"\"If model=None, classifier should be called.\"\"\"\n"
        "        # Classifier should have been called\n"
        "        classifier.classify.assert_called_once()\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    first = run({"root": "project", "recipe_id": "disable_gigachat_auto_model"})
    second = run({"root": "project", "recipe_id": "disable_gigachat_auto_model"})

    assert first["replacement_count"] == 5
    assert len(first["changed_files"]) == 3
    assert second["replacement_count"] == 0
    assert len(second["skipped"]) == 5
    assert "defaults to GigaChat" in (project / "app" / "gigachat" / "orchestrator.py").read_text(encoding="utf-8")
