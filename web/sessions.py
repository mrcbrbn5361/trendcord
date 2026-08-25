"""
Server-side session middleware - stores session data in SQLite instead of cookies.
The cookie only contains a session ID (< 100 bytes), solving the 4KB browser cookie limit.
"""
import os
import json
import time
import secrets
import sqlite3
import threading
import logging
from starlette.types import ASGIApp, Receive, Scope, Send

logger = logging.getLogger("trendcord.sessions")

_db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "sessions.db")
_local = threading.local()


def _get_db():
    if not hasattr(_local, "conn") or _local.conn is None:
        _local.conn = sqlite3.connect(_db_path, check_same_thread=False)
        _local.conn.row_factory = sqlite3.Row
        _local.conn.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                data TEXT NOT NULL,
                expires_at REAL NOT NULL
            )
        """)
        _local.conn.commit()
    return _local.conn


def _cleanup_expired():
    try:
        db = _get_db()
        db.execute("DELETE FROM sessions WHERE expires_at < ?", (time.time(),))
        db.commit()
    except Exception as e:
        logger.warning(f"Session cleanup error: {e}")


class ServerSession:
    """Dict-like session object that syncs with SQLite."""

    def __init__(self, session_id: str, data: dict, max_age: int):
        self._session_id = session_id
        self._data = data
        self._max_age = max_age
        self._modified = False

    def __getitem__(self, key):
        return self._data[key]

    def __setitem__(self, key, value):
        self._data[key] = value
        self._modified = True

    def __delitem__(self, key):
        del self._data[key]
        self._modified = True

    def __contains__(self, key):
        return key in self._data

    def __len__(self):
        return len(self._data)

    def __iter__(self):
        return iter(self._data)

    def __repr__(self):
        return f"ServerSession({self._data})"

    def get(self, key, default=None):
        return self._data.get(key, default)

    def pop(self, key, *args):
        self._modified = True
        return self._data.pop(key, *args)

    def keys(self):
        return self._data.keys()

    def values(self):
        return self._data.values()

    def items(self):
        return self._data.items()

    def clear(self):
        self._data.clear()
        self._modified = True

    def update(self, *args, **kwargs):
        self._data.update(*args, **kwargs)
        self._modified = True

    def setdefault(self, key, default=None):
        if key not in self._data:
            self._data[key] = default
            self._modified = True
        return self._data[key]

    @property
    def session_id(self):
        return self._session_id

    @property
    def is_new(self):
        return len(self._data) == 0

    def save(self):
        if not self._modified:
            return
        try:
            db = _get_db()
            expires_at = time.time() + self._max_age
            db.execute(
                "INSERT OR REPLACE INTO sessions (session_id, data, expires_at) VALUES (?, ?, ?)",
                (self._session_id, json.dumps(self._data), expires_at)
            )
            db.commit()
        except Exception as e:
            logger.error(f"Session save error: {e}")


class ServerSessionMiddleware:
    """ASGI middleware for server-side sessions stored in SQLite."""

    def __init__(
        self,
        app: ASGIApp,
        max_age: int = 604800,
        cookie_name: str = "session",
        cookie_path: str = "/",
        cookie_httponly: bool = True,
        cookie_secure: bool = True,
        cookie_samesite: str = "lax",
    ):
        self.app = app
        self.max_age = max_age
        self.cookie_name = cookie_name
        self.cookie_path = cookie_path
        self.cookie_httponly = cookie_httponly
        self.cookie_secure = cookie_secure
        self.cookie_samesite = cookie_samesite

    def _get_session_id_from_cookies(self, cookies: dict) -> str | None:
        return cookies.get(self.cookie_name)

    def _load_session(self, session_id: str) -> dict:
        try:
            db = _get_db()
            row = db.execute(
                "SELECT data, expires_at FROM sessions WHERE session_id = ?",
                (session_id,)
            ).fetchone()
            if row and row["expires_at"] > time.time():
                return json.loads(row["data"])
            elif row:
                db.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
                db.commit()
        except Exception as e:
            logger.error(f"Session load error: {e}")
        return {}

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return

        # Periodic cleanup
        if int(time.time()) % 3600 == 0:
            _cleanup_expired()

        # Extract session ID from cookies
        cookie_header = ""
        for header_name, header_value in scope.get("headers", []):
            if header_name == b"cookie":
                cookie_header = header_value.decode("latin-1")
                break

        cookies = {}
        if cookie_header:
            for item in cookie_header.split(";"):
                item = item.strip()
                if "=" in item:
                    k, v = item.split("=", 1)
                    cookies[k.strip()] = v.strip()

        session_id = self._get_session_id_from_cookies(cookies)

        if session_id:
            data = self._load_session(session_id)
        else:
            session_id = secrets.token_urlsafe(32)
            data = {}

        session = ServerSession(session_id, data, self.max_age)
        scope["session"] = session

        # Track if we need to set the cookie
        initial_empty = len(data) == 0

        async def send_wrapper(message: dict) -> None:
            if message["type"] == "http.response.start":
                response_headers = list(message.get("headers", []))

                # Always set cookie if new session, or if session was modified
                if session._modified or initial_empty:
                    cookie_value = f"{self.cookie_name}={session.session_id}; Path={self.cookie_path}"
                    if self.cookie_httponly:
                        cookie_value += "; HttpOnly"
                    if self.cookie_secure:
                        cookie_value += "; Secure"
                    cookie_value += f"; SameSite={self.cookie_samesite}"
                    cookie_value += f"; Max-Age={self.max_age}"
                    response_headers.append((b"set-cookie", cookie_value.encode("latin-1")))

                message["headers"] = response_headers
                await send(message)
            else:
                await send(message)

        await self.app(scope, receive, send_wrapper)

        # Save session after request processing
        if session._modified:
            session.save()
