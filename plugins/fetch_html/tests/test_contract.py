from plugins.fetch_html.src.main import run


def test_fetch_html_contract():
    assert "html" in run({"url": "mock://ok"})

