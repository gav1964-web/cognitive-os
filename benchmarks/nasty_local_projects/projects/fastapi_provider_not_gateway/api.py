from fastapi import FastAPI


app = FastAPI()
PROVIDER_NAME = "demo-provider"


@app.get("/health")
def health():
    return {"status": "ok", "provider": PROVIDER_NAME}


def list_provider_capabilities():
    return ["health", "metadata"]
