from runtime.feature_workspace import inventory, read_sources


def test_code_token_name_is_readable_but_data_and_secrets_stay_excluded(tmp_path):
    files = {
        'token_counts.py': 'def count_tokens(values):\n    return len(values)\n',
        'tokenizer.py': 'class Scanner:\n    pass\n',
        'tokens.json': '{"token": "synthetic"}',
        'token_data.py': 'TOKEN = "synthetic"\n',
        'token_store.py': 'TOKEN = "synthetic"\ndef load():\n    return TOKEN\n',
        'token_bad.py': 'def invalid(:\n',
        'access_token.py': 'def load():\n    return "synthetic"\n',
        'credentials.py': 'def load():\n    return "synthetic"\n',
        'secrets/helper.py': 'def helper():\n    return 1\n',
        'Config.json': '{}',
        '.env': 'TOKEN=synthetic',
    }
    for name, content in files.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding='utf-8')
    sources = inventory(tmp_path)
    assert set(sources) == {'token_counts.py', 'tokenizer.py'}
    assert read_sources(tmp_path, sources, [{'path': 'token_counts.py'}])[0]['content'] == files['token_counts.py']


def test_inline_literal_token_in_function_does_not_gain_code_exception(tmp_path):
    (tmp_path/'token_client.py').write_text(
        'def client():\n    access_token: str = "synthetic-only"\n    return access_token\n')
    assert inventory(tmp_path) == {}
