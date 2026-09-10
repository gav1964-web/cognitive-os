from runtime.programmer_fstring_brace_offset_patch import fstring_brace_offset_patch


RECIPE = {
    "required_symbol": "FileProcessor.build_logical_line_tokens",
    "offset_name": "brace_offset",
}

SOURCE = '''\
class FileProcessor:
    def build_logical_line_tokens(self):
        for token_type, text, start, end, line in self.tokens:
            if token_type == STRING:
                text = mutate_string(text)
            elif token_type == FSTRING_MIDDLE:
                text = "x" * len(text)
        return text, end
'''


def test_adds_brace_offset_and_end_correction():
    result = fstring_brace_offset_patch(
        SOURCE,
        symbol="FileProcessor.build_logical_line_tokens",
        recipe=RECIPE,
    )

    assert result is not None
    assert 'brace_offset = text.count("{") + text.count("}")' in result["source"]
    assert 'text = "x" * (len(text) + brace_offset)' in result["source"]
    assert "end = (end[0], end[1] + brace_offset)" in result["source"]


def test_rejects_already_fixed_source():
    first = fstring_brace_offset_patch(
        SOURCE,
        symbol="FileProcessor.build_logical_line_tokens",
        recipe=RECIPE,
    )

    assert first is not None
    assert fstring_brace_offset_patch(
        first["source"],
        symbol="FileProcessor.build_logical_line_tokens",
        recipe=RECIPE,
    ) is None


def test_rejects_branch_with_additional_behavior():
    source = SOURCE.replace(
        '                text = "x" * len(text)\n',
        '                text = "x" * len(text)\n                audit(text)\n',
    )

    assert fstring_brace_offset_patch(
        source,
        symbol="FileProcessor.build_logical_line_tokens",
        recipe=RECIPE,
    ) is None


def test_rejects_wrong_symbol():
    assert fstring_brace_offset_patch(
        SOURCE,
        symbol="FileProcessor.other",
        recipe=RECIPE,
    ) is None
