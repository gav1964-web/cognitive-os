def render(name, amount):
    return name.encode("ascii", errors="ignore").decode() + ": " + str(amount)
