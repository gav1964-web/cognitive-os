from plugins.hash_payload.src.main import run


def test_hash_payload_contract():
    assert run({"value": {"b": 2, "a": 1}})["hash"].startswith("sha256:")

