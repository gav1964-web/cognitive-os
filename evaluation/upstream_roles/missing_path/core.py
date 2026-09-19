def lookup(tree, path, default=None):
    current = tree
    for key in path:
        if key not in current:
            return default
        current = current[key]
        if not isinstance(current, dict):
            return current
    return current
