from plugins.json_transform.src.main import run


def test_json_transform_contract():
    assert run({"data": {"b": 2, "a": 1}, "mode": "keys"}) == {"data": ["a", "b"]}
