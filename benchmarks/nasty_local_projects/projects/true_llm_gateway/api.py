from fastapi import FastAPI

from providers.factory import build_providers_from_config


app = FastAPI()


@app.post("/v1/chat/completions")
def chat_completions(request: dict):
    providers = build_providers_from_config({"default": "demo"})
    return providers["demo"].chat(request)
