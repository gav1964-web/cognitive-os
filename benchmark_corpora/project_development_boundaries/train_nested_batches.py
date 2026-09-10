def normalize_batches(batches):
    output = []
    for batch in batches:
        for row in batch:
            output.append({"name": row.strip()})
    return output
