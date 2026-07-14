from tools.l4_defaults import DEFAULT_L4_BASE_URL, DEFAULT_L4_MODEL, l4_base_url, l4_model


def test_l4_defaults_use_explicit_gigachat_pro_gateway_profile(monkeypatch):
    monkeypatch.delenv("COGNITIVE_OS_L4_BASE_URL", raising=False)
    monkeypatch.delenv("COGNITIVE_OS_L4_MODEL", raising=False)

    assert l4_base_url() == DEFAULT_L4_BASE_URL == "http://127.0.0.1:8000/v1"
    assert l4_model() == DEFAULT_L4_MODEL == "GigaChat-Pro"


def test_l4_profile_can_be_overridden(monkeypatch):
    monkeypatch.setenv("COGNITIVE_OS_L4_BASE_URL", "http://gateway.example/v1")
    monkeypatch.setenv("COGNITIVE_OS_L4_MODEL", "another-cortex-model")

    assert l4_base_url() == "http://gateway.example/v1"
    assert l4_model() == "another-cortex-model"
