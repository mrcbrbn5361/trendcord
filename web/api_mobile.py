"""
Trendcord Mobil API - /api/v1
Mobil uygulama icin token tabanli guvenli REST API.

Guvenlik onlemleri:
- Opak bearer token (DB'de SHA-256 hash saklanir, raw token hicbir zaman tutulmaz)
- Redis destekli rate limiting (IP + token bazli)
- Cikti sanitizasyonu (beyaz liste alanlar, hassas veri sizmaz)
- Girdi validasyonu (Pydantic + Discord ID regex)
- Body boyut limiti
- CORS yok (native mobil uygulama gerektirmez, tarayici erisimi engellenir)
- Genel hata mesajlari (ic detaylar log'a gider, response'a sizmaz)
"""
import os
import re
import time
import asyncio
import functools
import hashlib
import secrets
import sqlite3
import logging
from typing import Optional

from fastapi import APIRouter, Request, HTTPException, Depends, Header
from fastapi.responses import JSONResponse, PlainTextResponse
try:
    from pydantic import BaseModel, Field, field_validator
    PYDANTIC_V2 = True
except ImportError:
    from pydantic import BaseModel, Field, validator as _validator

    def field_validator(*fields, **kwargs):
        dec = _validator(*fields, allow_reuse=True, **kwargs)
        return dec
    PYDANTIC_V2 = False

logger = logging.getLogger("trendcord.api")

router = APIRouter(prefix="/api/v1", tags=["mobile"])

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "data", "trendyol_tracker.sqlite")

TOKEN_TTL = 60 * 60 * 24 * 30          # 30 gun
BODY_LIMIT = 64 * 1024                  # 64KB
DISCORD_ID_RE = re.compile(r"^\d{5,25}$")
CODE_RE = re.compile(r"^[A-Za-z0-9_-]{10,200}$")
URL_RE = re.compile(r"^https?://[^\s]{1,500}$")

# ---------------------------------------------------------------------------
# Rate limiter (Redis, fail-open)
# ---------------------------------------------------------------------------
_rl = None


def _redis():
    global _rl
    if _rl is None:
        import redis
        _rl = redis.Redis(host="127.0.0.1", port=6379, socket_timeout=1,
                          socket_connect_timeout=1, decode_responses=True)
    return _rl


def rate_limit(key: str, limit: int, window: int) -> bool:
    """Sliding window sayac. True=izin var, False=limit asildi."""
    try:
        r = _redis()
        full_key = f"rl:{key}:{int(time.time() // window)}"
        n = r.incr(full_key)
        if n == 1:
            r.expire(full_key, window + 1)
        return n <= limit
    except Exception:
        logger.warning("[API-RATE] Redis erisilemedi, fail-open")
        return True


def client_ip(request: Request) -> str:
    xf = request.headers.get("x-forwarded-for", "")
    return xf.split(",")[0].strip() if xf else (request.client.host if request.client else "?")


def too_many() -> JSONResponse:
    return JSONResponse(
        status_code=429,
        content={"detail": "rate_limited"},
        headers={"Retry-After": "60"},
    )


class RateLimitMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        path = scope.get("path", "")
        if not path.startswith("/api/"):
            await self.app(scope, receive, send)
            return

        # Header'lardan IP cikar (Cloudflare arkasinda)
        ip = "?"
        for name, value in scope.get("headers", []):
            if name == b"x-forwarded-for":
                ip = value.decode("latin-1").split(",")[0].strip()
                break
        if ip == "?":
            client = scope.get("client")
            ip = client[0] if client else "?"

        # Genel limit: 120 istek/dk/IP; auth/login ayrica 10/saat/IP (asagida ekstra)
        if not rate_limit(f"api:{ip}", 120, 60):
            resp = too_many()
            await resp(scope, receive, send)
            return
        await self.app(scope, receive, send)


# ---------------------------------------------------------------------------
# Token store (SQLite, hash'lenmis)
# ---------------------------------------------------------------------------
def _token_db():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.execute("""CREATE TABLE IF NOT EXISTS api_tokens (
        token_hash TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        created_at REAL NOT NULL,
        expires_at REAL NOT NULL,
        revoked INTEGER DEFAULT 0,
        last_used REAL DEFAULT 0
    )""")
    conn.commit()
    return conn


def issue_token(user_id: str):
    raw = secrets.token_urlsafe(40)
    th = hashlib.sha256(raw.encode()).hexdigest()
    now = time.time()
    with _token_db() as c:
        c.execute(
            "INSERT INTO api_tokens (token_hash, user_id, created_at, expires_at) VALUES (?,?,?,?)",
            (th, str(user_id), now, now + TOKEN_TTL),
        )
    return raw, TOKEN_TTL


def revoke_token(raw: str) -> bool:
    th = hashlib.sha256(raw.encode()).hexdigest()
    with _token_db() as c:
        cur = c.execute("UPDATE api_tokens SET revoked=1 WHERE token_hash=?", (th,))
        return cur.rowcount > 0


async def get_current_user(
    request: Request,
    authorization: Optional[str] = Header(None),
) -> dict:
    # Dogrudan cagirida Header() nesnesi gelebilir - header'i kendimiz okuruz
    auth_value = request.headers.get("authorization") or ""
    if not isinstance(auth_value, str):
        auth_value = ""
    raw = auth_value[7:].strip() if auth_value.lower().startswith("bearer ") else ""
    if not raw:
        raise HTTPException(401, "missing_token")
    if len(raw) < 20 or len(raw) > 128 or not re.match(r"^[A-Za-z0-9_-]+$", raw):
        raise HTTPException(401, "invalid_token")
    if not rate_limit(f"tok:{hashlib.sha256(raw.encode()).hexdigest()[:16]}", 240, 60):
        raise HTTPException(429, "rate_limited")
    th = hashlib.sha256(raw.encode()).hexdigest()
    with _token_db() as c:
        row = c.execute(
            "SELECT user_id, expires_at, revoked FROM api_tokens WHERE token_hash=?",
            (th,),
        ).fetchone()
        if not row:
            raise HTTPException(401, "invalid_token")
        user_id, expires_at, revoked = row
        if revoked or time.time() > expires_at:
            raise HTTPException(401, "expired_token")
        # last_used'u en fazla 60 sn bir guncelle (yazma yuku azalt)
        c.execute(
            "UPDATE api_tokens SET last_used=? WHERE token_hash=? AND last_used < ?",
            (time.time(), th, time.time() - 60),
        )
    return {"user_id": str(user_id)}


# ---------------------------------------------------------------------------
# DB yardimcilari (beyaz liste - sadece guvenli alanlar doner)
# ---------------------------------------------------------------------------
PRODUCT_FIELDS = (
    "product_id", "name", "url", "image_url", "current_price", "original_price",
    "basket_price", "discount_pct", "campaign_name", "campaign_type",
    "campaign_end", "last_checked", "guild_id", "username",
)


def q(sql, params=()):
    from web.app import db_instance
    if db_instance is None:
        raise HTTPException(503, "unavailable")
    try:
        cur = db_instance.conn.execute(sql, params)
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]
    except sqlite3.Error:
        logger.exception("[API-SQL]")
        raise HTTPException(503, "db_error")


def public_product(p: dict) -> dict:
    out = {}
    for k in PRODUCT_FIELDS:
        v = p.get(k)
        if v is not None:
            out[k] = v
    return out


def require_guild_id(v: str) -> str:
    if not DISCORD_ID_RE.match(v):
        raise HTTPException(400, "invalid_id")
    return v


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------
class LoginIn(BaseModel):
    code: str = Field(..., min_length=10, max_length=200)
    redirect_uri: Optional[str] = None

    @field_validator("code")
    @classmethod
    def code_fmt(cls, v):
        if not CODE_RE.match(v):
            raise ValueError("invalid code format")
        return v

    @field_validator("redirect_uri")
    @classmethod
    def uri_fmt(cls, v):
        if v is not None:
            from web.auth import REDIRECT_URI
            allowed = {
                REDIRECT_URI,
                "trendcord://callback",
                "https://trendcord.miracdeveloper.com.tr/mobile/oauth/discord/callback",
            }
            if v not in allowed:
                raise ValueError("redirect_uri not allowed")
        return v


class AlertIn(BaseModel):
    product_id: str = Field(..., min_length=5, max_length=64)
    guild_id: str = Field(..., min_length=5, max_length=25)
    channel_id: str = Field(..., min_length=5, max_length=25)
    target_price: float = Field(..., gt=0, le=10_000_000)
    direction: str = Field("below")

    if not PYDANTIC_V2:
        direction = Field("below", regex="^(below|above)$")

    @field_validator("product_id", "guild_id", "channel_id")
    @classmethod
    def ids(cls, v):
        if not DISCORD_ID_RE.match(v) and not re.match(r"^\d{5,64}$", v):
            raise ValueError("invalid id")
        return v


class ProductAddIn(BaseModel):
    url: str = Field(..., min_length=10, max_length=500)
    guild_id: str = Field(..., min_length=5, max_length=25)
    channel_id: Optional[str] = Field(None, min_length=5, max_length=25)
    discord_id: Optional[str] = Field(None, min_length=5, max_length=25)
    username: Optional[str] = Field(None, max_length=64)
    avatar_url: Optional[str] = Field(None, max_length=500)

    @field_validator("url")
    @classmethod
    def url_fmt(cls, v):
        if not URL_RE.match(v):
            raise ValueError("invalid url")
        return v

    if not PYDANTIC_V2:
        url = Field(..., regex=URL_RE.pattern)

    @field_validator("guild_id", "channel_id", "discord_id")
    @classmethod
    def ids(cls, v):
        if v is not None and not DISCORD_ID_RE.match(v):
            raise ValueError("invalid id")
        return v


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@router.post("/auth/login")
async def login(request: Request, body: LoginIn):
    ip = client_ip(request)
    if not rate_limit(f"login:{ip}", 10, 3600):
        return too_many()

    from web.auth import get_access_token, get_user_info
    from web.app import db_instance
    try:
        token_data = await get_access_token(body.code, body.redirect_uri)
        user_info = await get_user_info(token_data["access_token"])
    except Exception:
        logger.warning("[API-AUTH] login basarisiz ip=%s", ip)
        raise HTTPException(401, "oauth_failed")

    uid = user_info["id"]
    avatar_ext = "gif" if user_info.get("avatar", "").startswith("a_") else "png"
    avatar_url = (
        f"https://cdn.discordapp.com/avatars/{uid}/{user_info['avatar']}.{avatar_ext}"
        if user_info.get("avatar")
        else f"https://cdn.discordapp.com/embed/avatars/{(int(uid) >> 22) % 6}.png"
    )
    if db_instance:
        db_instance.add_user(uid, user_info.get("username", ""), avatar_url)

    raw, ttl = issue_token(uid)
    return {
        "access_token": raw,
        "token_type": "Bearer",
        "expires_in": ttl,
        "user": {
            "id": uid,
            "username": user_info.get("username"),
            "avatar_url": avatar_url,
        },
    }


@router.post("/auth/logout")
async def logout(request: Request, authorization: Optional[str] = Header(None)):
    if authorization and authorization.lower().startswith("bearer "):
        revoke_token(authorization[7:].strip())
    return {"ok": True}


@router.get("/me")
async def me(user: dict = Depends(get_current_user)):
    rows = q("SELECT COUNT(*) c FROM products WHERE user_id=?", (user["user_id"],))
    u = q("SELECT username, avatar_url FROM users WHERE user_id=? LIMIT 1", (user["user_id"],))
    profile = u[0] if u else {"username": None, "avatar_url": None}
    return {**user, **profile, "product_count": rows[0]["c"] if rows else 0}


@router.get("/products")
async def products(
    request: Request,
    guild_id: Optional[str] = None,
    mine: bool = False,
    limit: int = 50,
    offset: int = 0,
):
    limit = max(1, min(limit, 100))
    offset = max(0, min(offset, 10000))
    if guild_id:
        require_guild_id(guild_id)
        rows = q(
            "SELECT * FROM products WHERE guild_id=? LIMIT ? OFFSET ?",
            (guild_id, limit, offset),
        )
    elif mine:
        user = await get_current_user(request)
        rows = q(
            "SELECT * FROM products WHERE user_id=? LIMIT ? OFFSET ?",
            (user["user_id"], limit, offset),
        )
    else:
        rows = q("SELECT * FROM products LIMIT ? OFFSET ?", (limit, offset))
    return {"items": [public_product(p) for p in rows], "count": len(rows),
            "limit": limit, "offset": offset}


@router.get("/products/{product_id}")
async def product_detail(product_id: str):
    pid = re.sub(r"[^A-Za-z0-9_-]", "", product_id)[:64]
    if not pid:
        raise HTTPException(400, "invalid_id")
    rows = q("SELECT * FROM products WHERE product_id=? LIMIT 1", (pid,))
    if not rows:
        raise HTTPException(404, "not_found")
    history = q(
        "SELECT price, basket_price, timestamp FROM price_history "
        "WHERE product_id=? ORDER BY timestamp DESC LIMIT 100",
        (pid,),
    )
    return {"product": public_product(rows[0]), "price_history": history}


@router.post("/products")
async def add_product(request: Request, body: ProductAddIn):
    """Yeni urun takibe alir.

    Bearer token sahibi OWNER_ID ise ve discord_id verilmisse urun o
    Discord kullanicisina atanir (selfbot kanal komutlari icin). Aksi halde
    urun token sahibine atanir.
    """
    user = await get_current_user(request)
    owner_id = str(os.getenv("OWNER_ID", "") or "")
    target_uid = user["user_id"]
    is_owner = bool(owner_id) and user["user_id"] == owner_id

    if body.discord_id:
        if not is_owner:
            raise HTTPException(403, "not_authorized")
        target_uid = body.discord_id

    from web.app import bot_instance
    if bot_instance is None or not hasattr(bot_instance, "scraper"):
        raise HTTPException(503, "unavailable")

    loop = asyncio.get_event_loop()
    data = await loop.run_in_executor(
        None, functools.partial(bot_instance.scraper.scrape_product, body.url)
    )
    if not data or not data.get("success"):
        raise HTTPException(422, "scrape_failed")

    cid = body.channel_id or "0"
    uname = (body.username or "")[:64]
    avatar = (body.avatar_url or "")[:500]

    from web.app import db_instance
    if db_instance is None:
        raise HTTPException(503, "unavailable")
    if not db_instance.add_product(data, body.guild_id, target_uid, cid,
                                   username=uname, avatar_url=avatar):
        raise HTTPException(500, "db_error")

    return {"product": public_product({**data, "guild_id": body.guild_id,
                                       "user_id": target_uid})}


@router.delete("/products/{product_id}")
async def delete_product(product_id: str, request: Request):
    user = await get_current_user(request)
    from web.app import db_instance
    owner_id = str(os.getenv("OWNER_ID", "") or "")
    is_owner = bool(owner_id) and user["user_id"] == owner_id

    rows = q("SELECT user_id FROM products WHERE product_id=? LIMIT 1", (product_id,))
    if not rows:
        raise HTTPException(404, "not_found")
    if not is_owner and rows[0]["user_id"] != user["user_id"]:
        raise HTTPException(403, "not_your_product")

    if db_instance is None or not db_instance.delete_product(product_id):
        raise HTTPException(500, "db_error")
    return {"ok": True}


@router.get("/guilds")
async def guilds():
    from web.app import bot_instance
    items = []
    if bot_instance:
        counts = {r["guild_id"]: r["c"] for r in q(
            "SELECT guild_id, COUNT(*) c FROM products GROUP BY guild_id"
        ) if r.get("guild_id")}
        for g in bot_instance.guilds:
            items.append({
                "id": str(g.id), "name": g.name,
                "member_count": g.member_count,
                "product_count": counts.get(str(g.id), 0),
            })
    return {"items": items}


@router.get("/guilds/{guild_id}")
async def guild_detail(guild_id: str):
    require_guild_id(guild_id)
    from web.app import bot_instance
    g = bot_instance.get_guild(int(guild_id)) if bot_instance else None
    prows = q(
        "SELECT * FROM products WHERE guild_id=? ORDER BY last_checked DESC LIMIT 100",
        (guild_id,),
    )
    members = q("SELECT DISTINCT user_id, username FROM products WHERE guild_id=?", (guild_id,))
    return {
        "id": guild_id,
        "name": g.name if g else None,
        "member_count": g.member_count if g else None,
        "product_count": len(prows),
        "tracking_members": [{"id": m["user_id"], "username": m["username"]} for m in members],
        "recent_products": [public_product(p) for p in prows[:20]],
    }


@router.get("/users/{user_id}")
async def user_profile(user_id: str):
    require_guild_id(user_id)
    u = q("SELECT user_id, username, avatar_url FROM users WHERE user_id=? LIMIT 1", (user_id,))
    prows = q(
        "SELECT * FROM products WHERE user_id=? ORDER BY last_checked DESC LIMIT 50",
        (user_id,),
    )
    savings = sum(
        (p["original_price"] or 0) - (p["current_price"] or 0)
        for p in prows
        if p.get("original_price") and p.get("current_price")
        and p["original_price"] > p["current_price"]
    )
    base = u[0] if u else {"user_id": user_id, "username": None, "avatar_url": None}
    return {**base, "product_count": len(prows),
            "total_savings": round(savings, 2),
            "products": [public_product(p) for p in prows]}


@router.get("/stats")
async def stats():
    from web.app import db_instance
    s = db_instance.get_stats() if db_instance else {}
    return {k: v for k, v in s.items() if isinstance(v, (int, float, str))}


@router.get("/alerts")
async def list_alerts(request: Request):
    user = await get_current_user(request)
    rows = q("SELECT * FROM alerts WHERE user_id=?", (user["user_id"],))
    fields = ("id", "product_id", "guild_id", "target_price", "direction",
              "triggered", "created_at")
    return {"items": [{k: a.get(k) for k in fields} for a in rows]}


@router.post("/alerts")
async def create_alert(request: Request, body: AlertIn):
    user = await get_current_user(request)
    from web.app import db_instance
    owned = q("SELECT 1 x FROM products WHERE product_id=? AND user_id=? LIMIT 1",
              (body.product_id, user["user_id"]))
    if not owned:
        raise HTTPException(403, "not_your_product")
    db_instance.add_alert(body.product_id, user["user_id"], body.guild_id,
                          body.channel_id, body.target_price, body.direction)
    return {"ok": True}


@router.delete("/alerts/{alert_id}")
async def delete_alert(alert_id: int, request: Request):
    user = await get_current_user(request)
    from web.app import db_instance
    db_instance.delete_alert(alert_id, user["user_id"])  # sahiplik SQL icinde kontrol
    return {"ok": True}


# ---------------------------------------------------------------------------
# Genel hata yakalayici - ic detay sizmaz
# ---------------------------------------------------------------------------
def register_api_error_handler(app):
    @app.exception_handler(Exception)
    async def api_error_handler(request: Request, exc: Exception):
        if request.url.path.startswith("/api/"):
            logger.exception("[API-500] %s %s", request.method, request.url.path)
            return JSONResponse(status_code=500, content={"detail": "internal_error"})
        return PlainTextResponse("Internal Server Error", status_code=500)
