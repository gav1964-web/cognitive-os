from runtime.goal_intake import build_goal_spec


def test_goal_intake_recognizes_markdown_to_rtf_conversion():
    spec = build_goal_spec("Convert markdown file from $input.input_path to RTF file at $input.output_path")

    assert spec.status == "ready"
    assert spec.intent == "convert_markdown"
    assert "$input.input_path" in spec.inputs
    assert "$input.output_path" in spec.inputs
    assert "rtf" in spec.outputs
    assert spec.clarification is None


def test_goal_intake_recognizes_spreadsheet_conversion():
    spec = build_goal_spec("Convert XLSX file from $input.input_path to CSV file at $input.output_path")

    assert spec.status == "ready"
    assert spec.intent == "convert_spreadsheet"
    assert "$input.input_path" in spec.inputs
    assert "$input.output_path" in spec.inputs
    assert spec.clarification is None
