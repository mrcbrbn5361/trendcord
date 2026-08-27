"""
Trendcord - API token uretme araci.

Sunucuda DB'nin yaninda calistirilir. Selfbot gibi harici istemcilerin
/api/v1 endpoint'lerini kullanabilmesi icin bearer token olusturur.

Kullanim:
    python issue_token.py <discord_user_id> [gun]
    python issue_token.py 123456789012345678 30

Cikti (tek satir): olusturulan raw token. Bir kez gosterilir, DB'de SHA-256
hash saklanir.
"""
import sys
import time
import hashlib
import secrets
import sqlite3
import os

TOKEN_TTL_DAY = 60 * 60 * 24


def main():
    if len(sys.argv) < 2:
        print("Kullanim: python issue_token.py <discord_user_id> [gun]", file=sys.stderr)
        sys.exit(2)

    user_id = sys.argv[1].strip()
    if not user_id.isdigit():
        print("Gecersiz discord ID.", file=sys.stderr)
        sys.exit(2)

    days = int(sys.argv[2]) if len(sys.argv) > 2 else 30
    ttl = days * TOKEN_TTL_DAY

    base = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(base, "data", "trendyol_tracker.sqlite")
    if not os.path.exists(db_path):
        print(f"DB bulunamadi: {db_path}", file=sys.stderr)
        sys.exit(1)

    raw = secrets.token_urlsafe(40)
    th = hashlib.sha256(raw.encode()).hexdigest()
    now = time.time()

    conn = sqlite3.connect(db_path, timeout=10)
    conn.execute("""CREATE TABLE IF NOT EXISTS api_tokens (
        token_hash TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        created_at REAL NOT NULL,
        expires_at REAL NOT NULL,
        revoked INTEGER DEFAULT 0,
        last_used REAL DEFAULT 0
    )""")
    conn.execute(
        "INSERT INTO api_tokens (token_hash, user_id, created_at, expires_at) VALUES (?,?,?,?)",
        (th, user_id, now, now + ttl),
    )
    conn.commit()
    conn.close()

    print(raw)


if __name__ == "__main__":
    main()