import hashlib
import secrets
import time
from dataclasses import dataclass, field


@dataclass
class Session:
    session_id: str
    connection_code: str
    created_at: float
    last_active: float
    chat_history: list[dict] = field(default_factory=list)
    settings: dict = field(default_factory=dict)
    is_authenticated: bool = False
    username: str = ""

    def add_message(self, role: str, content: str) -> None:
        self.chat_history.append({
            "role": role,
            "content": content,
            "timestamp": time.time(),
        })
        if len(self.chat_history) > 200:
            self.chat_history = self.chat_history[-200:]

    def touch(self) -> None:
        self.last_active = time.time()


class SessionManager:
    def __init__(self):
        self._sessions: dict[str, Session] = {}
        self._codes: dict[str, str] = {}
        self._session_timeout = 3600 * 24

    def create_session(self, username: str = "") -> Session:
        session_id = secrets.token_urlsafe(32)
        code = self._generate_code()
        now = time.time()
        session = Session(
            session_id=session_id,
            connection_code=code,
            created_at=now,
            last_active=now,
            username=username,
        )
        self._sessions[session_id] = session
        self._codes[code] = session_id
        return session

    def get_session(self, session_id: str) -> Session | None:
        session = self._sessions.get(session_id)
        if session:
            if time.time() - session.last_active > self._session_timeout:
                self.remove_session(session_id)
                return None
            session.touch()
        return session

    def get_by_code(self, code: str) -> Session | None:
        session_id = self._codes.get(code.upper())
        if session_id:
            return self.get_session(session_id)
        return None

    def remove_session(self, session_id: str) -> None:
        session = self._sessions.pop(session_id, None)
        if session:
            self._codes.pop(session.connection_code, None)

    def cleanup_expired(self) -> int:
        now = time.time()
        expired = [
            sid for sid, s in self._sessions.items()
            if now - s.last_active > self._session_timeout
        ]
        for sid in expired:
            self.remove_session(sid)
        return len(expired)

    def _generate_code(self) -> str:
        while True:
            code = secrets.token_hex(3).upper()[:6]
            if code not in self._codes:
                return code

    @property
    def active_count(self) -> int:
        return len(self._sessions)
