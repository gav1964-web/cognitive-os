from plugins.parse_title_fallback.src.main import run


def test_parse_title_fallback_contract():
    assert run({"html": "<title>Hello</title>"}) == {"title": "Hello"}

