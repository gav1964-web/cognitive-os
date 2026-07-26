API_KEY = "sk-demo-secret"


def load_config():
    return {"api_key": API_KEY}


def build_client(config):
    return {"headers": {"Authorization": "Bearer " + config["api_key"]}}
