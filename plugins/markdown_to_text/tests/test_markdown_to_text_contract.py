from plugins.markdown_to_text.src.main import run


def test_markdown_to_text_contract():
    assert run({"markdown": "# Hello **world** [x](https://e.test)"}) == {"text": "Hello world x"}
