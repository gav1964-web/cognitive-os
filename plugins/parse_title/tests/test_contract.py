from plugins.parse_title.src.main import run


def test_parse_title_contract():
    assert run({"html": "<title>Hello</title>"}) == {"title": "Hello"}

