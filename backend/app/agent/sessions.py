SessionHistory = list[dict]

_sessions: dict[str, SessionHistory] = {}


def get_history(session_id: str) -> SessionHistory:
    return _sessions.setdefault(session_id, [])


def reset_session(session_id: str) -> None:
    _sessions.pop(session_id, None)
