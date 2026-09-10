from pathlib import Path

from runtime.executable_acceptance_isolation import load_source_isolated_callable


def test_isolated_method_substitutes_called_relative_import_factory(tmp_path: Path):
    package = tmp_path / "pkg"
    package.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "models.py").write_text("raise RuntimeError('database unavailable')\n", encoding="utf-8")
    source = package / "service.py"
    source.write_text(
        "from .models import Record, UnusedModel\n\n"
        "class Service:\n"
        "    def save(self, value):\n"
        "        record = Record(owner=self.owner)\n"
        "        record.payload.write(value)\n",
        encoding="utf-8",
    )

    loaded = load_source_isolated_callable(source, "Service.save")
    loaded["callable"].__self__.owner = "sample"

    assert loaded["reason"] == ""
    assert loaded["callable"]("value") is None
    assert "local_factory:Record" in loaded["effect_module_stubs"]
