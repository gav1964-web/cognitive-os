class DemoProvider:
    def chat(self, request):
        return {"choices": [{"message": {"content": str(request)}}]}


def build_providers_from_config(config):
    return {"demo": DemoProvider()}
