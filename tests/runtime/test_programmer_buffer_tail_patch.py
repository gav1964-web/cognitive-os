from pathlib import Path

import pytest

from runtime.programmer_buffer_tail_patch import preserve_split_buffer_tail
from runtime.programmer_patch_synthesizer_core import synthesize_patch_package


SOURCE = '''class Writer:
    def flush(self):
        head, self.buffer = self.buffer[:self.size], self.buffer[self.size:]
        self.output.extend(head)
        self.buffer.clear()
'''


@pytest.mark.parametrize("size", [1, 4, 8, 20])
def test_training_patch_preserves_every_byte_across_flushes(size):
    result = preserve_split_buffer_tail(SOURCE, "Writer.flush")
    namespace = {}
    exec(result["source"], namespace)
    writer = namespace["Writer"]()
    writer.buffer = bytearray(b"abcdefghTAIL")
    writer.output = bytearray()
    writer.size = size
    while writer.buffer:
        writer.flush()
    assert writer.output == b"abcdefghTAIL"
    assert result["affected_symbols"] == ["Writer.flush"]
    assert result["source"] == SOURCE.replace("        self.buffer.clear()\n", "")


@pytest.mark.parametrize("source,symbol", [
    (SOURCE, "Other.flush"),
    (SOURCE, "flush"),
    (SOURCE.replace("[self.size:]", "[self.size + 1:]"), "Writer.flush"),
    (SOURCE.replace("[:self.size]", "[:self.size:2]"), "Writer.flush"),
    (SOURCE.replace("self.output.extend(head)", "self.buffer.extend(head)"), "Writer.flush"),
    (SOURCE.replace("self.output.extend(head)", "alias = self.buffer"), "Writer.flush"),
    (SOURCE.replace("self.output.extend(head)", "self.buffer = bytearray()"), "Writer.flush"),
    (SOURCE.replace(".clear()", ".clear(1)"), "Writer.flush"),
    (SOURCE.replace(".clear()", ".clear(); print('extra')"), "Writer.flush"),
    (SOURCE + "        return None\n", "Writer.flush"),
    ("invalid python!", "Writer.flush"),
])
def test_training_patch_rejects_unsupported_shapes(source, symbol):
    assert preserve_split_buffer_tail(source, symbol) is None


@pytest.mark.parametrize("authorized", [False, True])
def test_training_patch_requires_authority_and_preserves_source(tmp_path: Path, authorized):
    project = tmp_path / "project"
    project.mkdir()
    source = project / "writer.py"
    source.write_text(SOURCE, encoding="utf-8")
    operator = "preserve_split_buffer_tail"
    intent = {"operator_id": operator, "allowed_operator_ids": [operator]}
    if authorized:
        intent["authority"] = "explicit_training_replay"
    target = "writer.py:Writer.flush"
    result = synthesize_patch_package(
        execution_dir=tmp_path / "execution", project_dir=project,
        implementation_plan={
            "implementation_target": {"candidate": target},
            "patch_intent": {"target_symbol": target},
            "expected_files": ["writer.py"],
            "implementation_delta": {"status": "ready", "intent": intent},
        }, test_plan={},
    )
    assert source.read_text(encoding="utf-8") == SOURCE
    assert result["status"] == ("prepared" if authorized else "blocked")
    if authorized:
        patched = Path(result["sandbox_project"]) / "writer.py"
        assert patched.read_text(encoding="utf-8") == SOURCE.replace("        self.buffer.clear()\n", "")
    else:
        assert result["reason"] == "training_replay_authority_required"
