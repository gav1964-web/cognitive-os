def project_groups(groups):
    projected = []
    for group in groups:
        for item in group:
            projected.append({"value": item})
    return projected
