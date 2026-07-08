from plugins.markdown_to_rtf.src.main import run


def test_markdown_to_rtf_contract():
    result = run({"markdown": "# Hello **world**\n\n- [link](https://e.test)\n\n`x`"})

    assert result["rtf"].startswith("{\\rtf1\\ansi\\deff0")
    assert "\\b\\fs40 Hello \\b world\\b0\\b0\\par" in result["rtf"]
    assert "\\u8226? link\\par" in result["rtf"]
    assert "\\fmodern x\\f0\\par" in result["rtf"]


def test_markdown_to_rtf_escapes_unicode_and_rtf_chars():
    result = run({"markdown": "Привет {x}\\y"})

    assert "\\u1055?" in result["rtf"]
    assert "\\{x\\}\\\\y" in result["rtf"]
