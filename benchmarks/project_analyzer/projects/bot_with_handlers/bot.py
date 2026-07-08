SESSIONS: dict[str, list[str]] = {}


def parse_command(text: str) -> tuple[str, str]:
    parts = text.strip().split(maxsplit=1)
    return parts[0], parts[1] if len(parts) > 1 else ""


def remember(user_id: str, text: str) -> None:
    SESSIONS.setdefault(user_id, []).append(text)


def handle_start(user_id: str) -> str:
    remember(user_id, "start")
    return "started"


def handle_echo(user_id: str, value: str) -> str:
    remember(user_id, value)
    return value


def dispatch(user_id: str, text: str) -> str:
    command, value = parse_command(text)
    if command == "/start":
        return handle_start(user_id)
    if command == "/echo":
        return handle_echo(user_id, value)
    remember(user_id, "unknown")
    return "unknown command"
