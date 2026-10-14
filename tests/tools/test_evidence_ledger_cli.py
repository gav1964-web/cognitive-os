from tools.evidence_ledger import _parser


def test_promote_replay_preserves_nested_command_options() -> None:
    args = _parser().parse_args([
        "promote", "--source", "report.json", "--producer", "producer:v1",
        "--evaluator", "evaluator:v1", "--replay", "python", "tool.py",
        "--manifest", "manifest.json", "--summary",
    ])

    assert args.replay == [
        "python", "tool.py", "--manifest", "manifest.json", "--summary",
    ]
