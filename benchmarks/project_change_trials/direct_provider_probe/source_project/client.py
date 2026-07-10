PROVIDER = "direct-provider"
MODEL = "GigaChat-2-Pro"
TOKEN_ENV = "GIGACHAT_CLIENT_SECRET"


def call_provider(payload):
    return {"provider": PROVIDER, "model": MODEL, "payload": payload}
