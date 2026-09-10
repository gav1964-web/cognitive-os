def index_tokens(tokens):
    index = []
    for position, token in enumerate(tokens):
        index.append({"position": position, "token": token})
    return index
