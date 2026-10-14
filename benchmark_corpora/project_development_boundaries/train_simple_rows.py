def normalize_rows(rows):
    output = []
    for row in rows:
        output.append({"name": row.strip()})
    return output
