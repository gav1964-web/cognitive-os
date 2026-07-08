from plugins.json_select.src.main import run


def test_json_select_contract():
    assert run({"data": {"a": {"b": 3}}, "path": "a.b"}) == {"value": 3}

