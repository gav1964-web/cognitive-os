from plugins.extract_links.src.main import run


def test_extract_links_contract():
    html = '<a href="https://example.test">x</a><a href="/local">y</a>'
    assert run({"html": html}) == {"links": ["https://example.test", "/local"]}
