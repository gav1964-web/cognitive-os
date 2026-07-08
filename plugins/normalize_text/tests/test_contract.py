from plugins.normalize_text.src.main import run


def test_normalize_text_contract():
    assert run({"text": " a   b\nc "}) == {"text": "a b c"}

