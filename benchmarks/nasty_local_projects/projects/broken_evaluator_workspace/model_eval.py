def evaluate(query, answer):
    response = pipe(query, answer)
    return float(output[0]["score"])


def generate_response(prompt):
    return prompt.strip().upper()
