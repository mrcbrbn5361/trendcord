import os
import json
import asyncio
import functools
import httpx
import logging
import mimetypes
from pathlib import Path
from fastapi import FastAPI, Request, Form, Query, HTTPException
from fastapi.responses import RedirectResponse, HTMLResponse, Response, FileResponse
from fastapi.templating import Jinja2Templates
from starlette.middleware.base import BaseHTTPMiddleware
from web.auth import get_access_token, get_user_info, get_login_url, get_user_guilds, generate_state
from web.sessions import ServerSessionMiddleware
from web.api_mobile import router as mobile_router, RateLimitMiddleware, register_api_error_handler
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

logger = logging.getLogger("trendcord.web")

# Register MIME types that Python's mimetypes may not know
mimetypes.add_type("font/woff2", ".woff2")
mimetypes.add_type("font/woff", ".woff")
mimetypes.add_type("image/svg+xml", ".svg")
mimetypes.add_type("application/manifest+json", ".webmanifest")

app = FastAPI()

# Mobil API router + rate limit middleware (sadece /api/* yollari)
app.include_router(mobile_router)
app.add_middleware(RateLimitMiddleware)
register_api_error_handler(app)

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "web" / "static"

# --- Static Files (catch-all route, not ASGI mount, to avoid uvicorn/threading issues) ---
@app.get("/static/{filepath:path}")
async def static_files(filepath: str):
    file_path = STATIC_DIR / filepath
    if not file_path.is_file():
        from fastapi.responses import PlainTextResponse
        return PlainTextResponse("Not Found", status_code=404)
    media_type, _ = mimetypes.guess_type(str(file_path))
    return FileResponse(str(file_path), media_type=media_type)

# --- Security Headers Middleware ---
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        if request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response

app.add_middleware(SecurityHeadersMiddleware)

# --- SEO Middleware: Trailing slash redirect ---
class SEOFixMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        host = request.url.hostname
        # WWW → non-WWW redirect
        if host and host.startswith("www."):
            new_url = str(request.url).replace("www.", "", 1)
            return RedirectResponse(url=new_url, status_code=301)
        # Trailing slash redirect: /path/ → /path (except root)
        if len(path) > 1 and path.endswith("/"):
            new_path = path.rstrip("/")
            new_url = str(request.url).replace(path, new_path, 1)
            return RedirectResponse(url=new_url, status_code=301)
        response = await call_next(request)
        return response

app.add_middleware(SEOFixMiddleware)

app.add_middleware(ServerSessionMiddleware,
    max_age=604800,
    cookie_name="session",
    cookie_httponly=True,
    cookie_secure=False,  # Termux için False (localhost'ta HTTPS yok)
    cookie_samesite="lax",
)

app.add_middleware(ProxyHeadersMiddleware,
    trusted_hosts=["trendcord.miracdeveloper.com.tr", "*.miracdeveloper.com.tr"]
)

# --- Cache Headers for Static Files ---
class CacheHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        if request.url.path.startswith("/static/"):
            if ".min." in request.url.path or request.url.path.endswith((".woff2", ".woff", ".ttf")):
                response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
            else:
                response.headers["Cache-Control"] = "public, max-age=86400"
        return response

app.add_middleware(CacheHeadersMiddleware)
templates = Jinja2Templates(directory=str(BASE_DIR / "web" / "templates"))

bot_instance = None
db_instance = None

def set_instances(bot, db):
    global bot_instance, db_instance
    bot_instance = bot
    db_instance = db

def _ensure_db():
    global db_instance
    if not db_instance:
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
        from database import Database
        db_instance = Database()

_ensure_db()

OWNER_ID = os.getenv("OWNER_ID", "")
CLIENT_ID = os.getenv("CLIENT_ID", "")
BOT_INVITE_URL = f"https://discord.com/api/oauth2/authorize?client_id={CLIENT_ID}&permissions=8&scope=bot%20applications.commands"
SUPPORT_SERVER = os.getenv("SUPPORT_SERVER", "https://discord.gg/trendcord")

@app.exception_handler(404)
async def not_found(request: Request, exc):
    path = request.url.path
    if path.startswith("/static/") or path.startswith("/.well-known/"):
        from fastapi.responses import PlainTextResponse
        return PlainTextResponse("Not Found", status_code=404)
    return templates.TemplateResponse("index.html", template_context(request), status_code=404)

@app.get("/.well-known/maintenance")
async def maintenance_page(request: Request):
    return templates.TemplateResponse("maintenance.html", {"request": request})

def get_global_stats():
    """Tüm sayfalarda kullanılacak ortak sayısal verileri toplar."""
    stats = {"guild_count": 0, "product_count": 0, "price_checks": 0}
    if bot_instance:
        stats["guild_count"] = len(bot_instance.guilds)
    if db_instance:
        data = db_instance.get_stats()
        stats["product_count"] = data["product_count"]
        stats["price_checks"] = data["price_checks"]
    return stats

def template_context(request: Request, extra: dict = None):
    """Tüm sayfalar için ortak template context'i oluşturur."""
    user_data = request.session.get("user") or {}
    ctx = {
        "request": request,
        "user": user_data or None,
        "stats": get_global_stats(),
        "is_owner": str(user_data.get("id", "")) == OWNER_ID,
        "bot_invite_url": BOT_INVITE_URL,
        "support_server": SUPPORT_SERVER
    }
    if extra:
        ctx.update(extra)
    return ctx

def get_guild_name(gid):
    if not bot_instance: return str(gid)
    try:
        g = bot_instance.get_guild(int(gid))
        return g.name if g else str(gid)
    except (ValueError, TypeError):
        return str(gid)

def get_guild_icon_url(g):
    """Guild icon URL'sini güvenli bir şekilde oluşturur."""
    if not g or not g.icon:
        return None
    try:
        icon_key = g.icon.key if hasattr(g.icon, 'key') else str(g.icon)
        return f"https://cdn.discordapp.com/icons/{g.id}/{icon_key}.png"
    except Exception:
        return None

@app.get("/")
async def index(request: Request):
    return templates.TemplateResponse("index.html", template_context(request))

@app.get("/features")
async def features(request: Request):
    return templates.TemplateResponse("features.html", template_context(request))

@app.get("/how-it-works")
async def how_it_works(request: Request):
    return templates.TemplateResponse("how_it_works.html", template_context(request))

@app.get("/stats")
async def stats_page(request: Request):
    return templates.TemplateResponse("stats.html", template_context(request))

@app.get("/privacy")
async def privacy(request: Request):
    return templates.TemplateResponse("privacy.html", template_context(request))

@app.get("/terms")
async def terms(request: Request):
    return templates.TemplateResponse("terms.html", template_context(request))

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, guild_id: str = Query(None)):
    user = request.session.get("user")
    token = request.session.get("access_token")
    if not user or not token: return RedirectResponse("/login")
    
    uid = str(user['id'])
    is_owner = uid == OWNER_ID
    
    active_guilds = []
    current_guild = None
    try:
        user_guilds = await get_user_guilds(token)
        bot_guild_ids = {str(g.id) for g in bot_instance.guilds} if bot_instance else set()
        if is_owner:
            # Bot admin: tüm sunucuları göster
            for g in user_guilds:
                if str(g['id']) in bot_guild_ids:
                    g["icon_url"] = f"https://cdn.discordapp.com/icons/{g['id']}/{g['icon']}.png" if g.get("icon") else None
                    active_guilds.append(g)
                    if guild_id and str(g['id']) == str(guild_id): current_guild = g
        else:
            for g in user_guilds:
                if (int(g.get('permissions', 0)) & 0x8) == 0x8 or g.get('owner'):
                    if str(g['id']) in bot_guild_ids:
                        g["icon_url"] = f"https://cdn.discordapp.com/icons/{g['id']}/{g['icon']}.png" if g.get("icon") else None
                        active_guilds.append(g)
                        if guild_id and str(g['id']) == str(guild_id): current_guild = g
    except HTTPException as e:
        if e.status_code == 401:
            request.session.clear()
            return RedirectResponse("/login")
    except: pass

    if is_owner:
        products = db_instance.get_all_products(guild_id=guild_id) if db_instance else []
    else:
        products = db_instance.get_all_products(guild_id=guild_id) if guild_id and db_instance else db_instance.get_all_products(user_id=uid) if db_instance else []

    # Discord API'den kullanıcı avatarlarını çek
    user_avatars = {}
    if bot_instance:
        unique_ids = list(set(p['user_id'] for p in products if p.get('user_id')))
        bot_token = os.getenv('DISCORD_TOKEN', '')
        headers = {"Authorization": f"Bot {bot_token}"}
        async with httpx.AsyncClient(timeout=5.0) as client:
            for uid_key in unique_ids[:100]:
                try:
                    resp = await client.get(f"https://discord.com/api/v10/users/{uid_key}", headers=headers)
                    if resp.status_code == 200:
                        udata = resp.json()
                        av = udata.get("avatar")
                        uid_int = int(uid_key)
                        if av:
                            ext = "gif" if av.startswith("a_") else "png"
                            user_avatars[uid_key] = f"https://cdn.discordapp.com/avatars/{uid_int}/{av}.{ext}"
                        else:
                            user_avatars[uid_key] = f"https://cdn.discordapp.com/embed/avatars/{(uid_int >> 22) % 6}.png"
                    else:
                        user_avatars[uid_key] = ""
                except Exception as e:
                    print(f"[AVATAR] httpx error ({uid_key}): {e}")
                    user_avatars[uid_key] = ""

    invite_url = f"https://discord.com/api/oauth2/authorize?client_id={os.getenv('CLIENT_ID')}&permissions=8&scope=bot%20applications.commands"

    ctx = template_context(request, {
        "request": request, "user": user, "products": products, 
        "guilds": active_guilds, "current_guild": current_guild, "invite_url": invite_url,
        "is_owner": is_owner, "get_guild_name": get_guild_name,
        "user_avatars": user_avatars
    })
    return templates.TemplateResponse("dashboard.html", ctx)

@app.post("/product/add")
async def add_product(request: Request, url: str = Form(...), guild_id: str = Form(None)):
    user = request.session.get("user")
    if not user or not guild_id: return RedirectResponse("/dashboard", status_code=303)
    data = await asyncio.get_event_loop().run_in_executor(None, functools.partial(bot_instance.scraper.scrape_product, url))
    if data:
        target_channel = "0"
        try:
            g = bot_instance.get_guild(int(guild_id))
            target_channel = str(g.system_channel.id) if g.system_channel else str(next((c.id for c in g.text_channels if c.permissions_for(g.me).send_messages), "0"))
        except: pass
        db_instance.add_product(data, guild_id, user['id'], target_channel, username=user.get('username', ''), avatar_url=user.get('avatar_url', ''))
        return RedirectResponse(f"/dashboard?guild_id={guild_id}&added=1", status_code=303)
    return RedirectResponse(f"/dashboard?guild_id={guild_id}&error=1", status_code=303)

@app.post("/product/delete/{pid}")
async def delete_product(request: Request, pid: str, guild_id: str = Form(None)):
    if request.session.get("user") and db_instance: db_instance.delete_product(pid)
    redirect_path = f"/dashboard?guild_id={guild_id}" if guild_id else "/dashboard"
    return RedirectResponse(redirect_path, status_code=303)

@app.get("/product/{pid}", response_class=HTMLResponse)
async def product_detail(request: Request, pid: str):
    _ensure_db()
    product = db_instance.get_product(pid) if db_instance else None
    if not product:
        return templates.TemplateResponse("index.html", template_context(request), status_code=404)

    history_desc = db_instance.get_product_price_history(pid, limit=300) or []
    chrono = list(reversed(history_desc))
    prices = [float(h["price"]) for h in chrono if h.get("price") is not None]

    stats = {"count": len(prices), "min": None, "max": None, "avg": None,
             "change_pct": None, "first_ts": None}
    if prices:
        stats["min"] = min(prices)
        stats["max"] = max(prices)
        stats["avg"] = round(sum(prices) / len(prices))
        first_p = prices[0]
        cur = float(product["current_price"] or first_p)
        if first_p > 0:
            stats["change_pct"] = round((cur - first_p) / first_p * 100, 1)
        stats["first_ts"] = (chrono[0].get("timestamp") or "")[:16]

    chart = [{"t": (h.get("timestamp") or "")[:16], "p": float(h["price"])}
             for h in chrono if h.get("price") is not None]

    ctx = template_context(request, {
        "product": product,
        "history": history_desc[:40],
        "stats": stats,
        "chart_json": json.dumps(chart, ensure_ascii=False),
        "get_guild_name": get_guild_name,
    })
    return templates.TemplateResponse("product_detail.html", ctx)

@app.get("/login")
async def login(request: Request):
    if request.session.get("user"):
        return RedirectResponse("/dashboard")
    # CSRF koruması için state parametresi üret ve session'a kaydet
    from web.auth import generate_state
    state = generate_state()
    request.session["oauth_state"] = state
    # Ara sayfa olmadan doğrudan Discord OAuth'a yönlendir
    request.session.save()
    return RedirectResponse(get_login_url(state), status_code=307)

@app.get("/callback")
async def callback(request: Request, code: str = None, state: str = None):
    if not code:
        logger.error("[AUTH] Callback error: No code received")
        return RedirectResponse("/login")
    # CSRF state doğrulaması
    saved_state = request.session.pop("oauth_state", None)
    if saved_state and state != saved_state:
        logger.warning(f"[AUTH] CSRF state mismatch: expected={saved_state}, got={state}")
        return RedirectResponse("/login")
    elif not saved_state:
        logger.info(f"[AUTH] No saved state (direct OAuth URL), proceeding without CSRF check")
    try:
        logger.info(f"[AUTH] Callback received code: {code[:20]}...")
        token_data = await get_access_token(code)
        logger.info(f"[AUTH] Token received: {list(token_data.keys())}")
        user_info = await get_user_info(token_data['access_token'])
        logger.info(f"[AUTH] User: {user_info.get('username')} ({user_info.get('id')})")
        avatar_ext = "gif" if user_info.get("avatar", "").startswith("a_") else "png"
        user_info["avatar_url"] = f"https://cdn.discordapp.com/avatars/{user_info['id']}/{user_info['avatar']}.{avatar_ext}" if user_info.get("avatar") else "https://cdn.discordapp.com/embed/avatars/0.png"
        request.session.update({"user": user_info, "access_token": token_data['access_token']})
        # Kullanıcının sunucularını session'a kaydet (IDOR koruması için)
        try:
            user_guilds = await get_user_guilds(token_data['access_token'])
            request.session["user_guilds"] = user_guilds or []
        except:
            request.session["user_guilds"] = []
        # Kullanıcıyı veritabanına kaydet
        if db_instance:
            db_instance.add_user(user_info['id'], user_info.get('username', ''), user_info.get('avatar_url', ''))
        logger.info(f"[AUTH] Session set, redirecting to dashboard")
        request.session.save()
        resp = RedirectResponse("/dashboard", status_code=302)
        return resp
    except Exception as e:
        logger.error(f"[AUTH] Callback error: {e}")
        return RedirectResponse("/login?error=auth_failed")

@app.get("/mobile/oauth/discord/callback")
async def mobile_oauth_callback(request: Request, code: str = None, error: str = None):
    """Mobil uygulama OAuth kopru sayfasi.
    Discord'dan donen code'u yakalayip trendcord:// deep link ile uygulamaya aktarir."""
    if error or not code:
        html = """<!DOCTYPE html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Trendcord</title></head>
<body style="font-family:sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0;background:#141218;color:#e6e0e9;text-align:center">
<div><h2>Giriş iptal edildi</h2><p>Uygulamaya geri dönebilirsiniz.</p></div></body></html>"""
        return HTMLResponse(html)
    import json as _json
    safe_code = "".join(c for c in code if c.isalnum() or c in "-_")[:200]
    payload = _json.dumps({"code": safe_code})
    html = f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Trendcord - Giriş</title></head>
<body style="font-family:sans-serif;display:flex;flex-direction:column;align-items:center;justify-content:center;min-height:100vh;margin:0;background:#141218;color:#e6e0e9;text-align:center;padding:24px">
<div id="spinner" style="width:42px;height:42px;border:4px solid #ffb68a33;border-top-color:#ffb68a;border-radius:50%;animation:sp 1s linear infinite;margin-bottom:20px"></div>
<h2 style="margin:0 0 8px">Trendcord'a giriş yapılıyor...</h2>
<p style="color:#cac4d0">Uygulama açılmazsa aşağıdaki butona dokunun.</p>
<a id="appbtn" href="" style="display:none;background:#ffb68a;color:#442b00;font-weight:bold;padding:14px 32px;border-radius:999px;text-decoration:none;margin-top:16px">Uygulamaya Dön</a>
<script>
const payload = {payload};
const code = payload.code;
// Desteklenen deep link hedefleri: yeni scheme + mevcut Manus build schemi
const targets = [
  'trendcord://callback?code=' + code,
  'manusrendcordmobile://callback?code=' + code,
  // Android intent fallback: paketi hedefler, scheme dagilimi calismasa bile acar
  'intent://callback?code=' + code + '#Intent;scheme=manusrendcordmobile;package=com.app.trendcordmobile;end'
];
let i = 0;
function tryNext() {{
  if (i < targets.length) {{
    document.getElementById('appbtn').href = targets[i];
    location.href = targets[i++];
    setTimeout(tryNext, 1500);
  }} else {{
    document.getElementById('appbtn').style.display = 'inline-block';
    document.getElementById('spinner').style.display = 'none';
  }}
}}
setTimeout(tryNext, 300);
</script>
<style>@keyframes sp{{to{{transform:rotate(360deg)}}}}</style>
</body></html>"""
    return HTMLResponse(html)


@app.get("/servers")
async def servers_list(request: Request):
    """Botun bulunduğu tüm sunucuların listesi."""
    guilds_data = []
    total_members = 0
    total_products = 0
    active_users_set = set()

    if bot_instance:
        for g in bot_instance.guilds:
            product_count = 0
            if db_instance:
                prods = db_instance.get_all_products(guild_id=str(g.id))
                product_count = len(prods)
                for p in prods:
                    if p.get('user_id'):
                        active_users_set.add(p['user_id'])
            total_products += product_count
            total_members += g.member_count
            icon_url = get_guild_icon_url(g)
            guilds_data.append({
                "id": g.id,
                "name": g.name,
                "member_count": g.member_count,
                "icon_url": icon_url,
                "product_count": product_count
            })
    elif db_instance:
        db_guilds = db_instance.get_all_guilds_from_db()
        for g in db_guilds:
            gid = g['guild_id']
            product_count = g.get('product_count', 0)
            user_count = g.get('user_count', 0)
            total_products += product_count
            total_members += user_count
            active_users_set.update([str(user_count)])
            guilds_data.append({
                "id": gid,
                "name": f"Sunucu {gid}",
                "member_count": user_count,
                "icon_url": "",
                "product_count": product_count
            })

    ctx = template_context(request, {
        "servers": guilds_data,
        "total_members": total_members,
        "total_products": total_products,
        "active_users": len(active_users_set)
    })
    return templates.TemplateResponse("servers.html", ctx)


@app.get("/servers/{guild_id}")
async def server_detail(request: Request, guild_id: str):
    """Belirli bir sunucunun detay sayfası."""
    # Herkese açık istatistik sayfası - liste sayfası gibi giriş gerektirmez
    guild = None
    if bot_instance:
        guild = bot_instance.get_guild(int(guild_id))

    products = []
    user_avatars = {}
    if db_instance:
        products = db_instance.get_all_products(guild_id=guild_id)

    # Tüm sunucu üyelerini Discord API'den çek
    members_map = {}
    bot_token = os.getenv('DISCORD_TOKEN', '')
    if bot_token:
        headers = {"Authorization": f"Bot {bot_token}"}
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                resp = await client.get(
                    f"https://discord.com/api/v10/guilds/{guild_id}/members?limit=1000",
                    headers=headers
                )
                if resp.status_code == 200:
                    guild_members = resp.json()
                    for m in guild_members:
                        if m.get('user', {}).get('bot'):
                            continue
                        uid = m['user']['id']
                        av = m['user'].get('avatar')
                        if av:
                            ext = "gif" if av.startswith("a_") else "png"
                            avatar_url = f"https://cdn.discordapp.com/avatars/{uid}/{av}.{ext}"
                        else:
                            avatar_url = f"https://cdn.discordapp.com/embed/avatars/{(int(uid) >> 22) % 6}.png"
                        members_map[uid] = {
                            "user_id": uid,
                            "username": m['user'].get('username', 'Bilinmeyen'),
                            "avatar_url": avatar_url,
                            "product_count": 0
                        }
                        user_avatars[uid] = avatar_url
                else:
                    logger.warning(f"[GUILD] Members fetch failed for {guild_id}: {resp.status_code}")
            except Exception as e:
                logger.warning(f"[GUILD] Members fetch error for {guild_id}: {e}")

    # Ürün sayılarını üyelerin üzerine ekle
    for p in products:
        uid = p.get('user_id')
        if uid:
            if uid in members_map:
                members_map[uid]["product_count"] += 1
            else:
                # Üyeler arasında yoksa bile ürün sahibini göster
                avatar_url = user_avatars.get(uid, '') or p.get('avatar_url', '')
                if not avatar_url:
                    avatar_url = f"https://cdn.discordapp.com/embed/avatars/{(int(uid) >> 22) % 6}.png"
                members_map[uid] = {
                    "user_id": uid,
                    "username": p.get('username', 'Bilinmeyen'),
                    "avatar_url": avatar_url,
                    "product_count": 1
                }

    icon_url = get_guild_icon_url(guild)

    guild_info = None
    if guild:
        guild_info = {
            "id": guild.id,
            "name": guild.name,
            "member_count": guild.member_count,
            "icon_url": icon_url
        }
    else:
        guild_info = {
            "id": guild_id,
            "name": f"Sunucu {guild_id}",
            "member_count": len(members_map),
            "icon_url": ""
        }

    ctx = template_context(request, {
        "guild": guild_info,
        "products": products,
        "members": list(members_map.values()),
        "unique_users": len(members_map),
        "user_avatars": user_avatars
    })
    return templates.TemplateResponse("server_detail.html", ctx)


@app.get("/users")
async def users_list(request: Request):
    """Tüm kayıtlı kullanıcıların listesi."""
    users_data = []
    total_products = 0
    total_savings = 0

    if db_instance:
        # Veritabanındaki tüm kullanıcıları al
        db_users = db_instance.get_all_users()
        users_map = {}
        for u in db_users:
            uid = u.get('user_id')
            if not uid:
                continue
            users_map[uid] = {
                "user_id": uid,
                "username": u.get('username', 'Bilinmeyen'),
                "avatar_url": u.get('avatar_url', ''),
                "product_count": 0,
                "guilds": set(),
                "savings": 0
            }

        # Ürün sayısını ve tasarrufu hesapla
        all_products = db_instance.get_all_products()
        for p in all_products:
            uid = p.get('user_id')
            if uid:
                if uid not in users_map:
                    # Ürün tablosunda ama users tablosunda olmayan kullanıcılar
                    users_map[uid] = {
                        "user_id": uid,
                        "username": p.get('username', 'Bilinmeyen'),
                        "avatar_url": p.get('avatar_url', ''),
                        "product_count": 0,
                        "guilds": set(),
                        "savings": 0
                    }
                users_map[uid]["product_count"] += 1
                gid = p.get('guild_id')
                if gid:
                    users_map[uid]["guilds"].add(gid)
                if p.get('original_price') and p.get('current_price'):
                    if p['original_price'] > p['current_price']:
                        users_map[uid]["savings"] += p['original_price'] - p['current_price']
                        total_savings += p['original_price'] - p['current_price']
                total_products += 1

        # Discord API'den güncel avatarları çek
        unique_ids = list(users_map.keys())
        if bot_instance and unique_ids:
            bot_token = os.getenv('DISCORD_TOKEN', '')
            headers = {"Authorization": f"Bot {bot_token}"}
            async with httpx.AsyncClient(timeout=5.0) as client:
                for uid_key in unique_ids[:100]:
                    try:
                        resp = await client.get(f"https://discord.com/api/v10/users/{uid_key}", headers=headers)
                        if resp.status_code == 200:
                            udata = resp.json()
                            av = udata.get("avatar")
                            uid_int = int(uid_key)
                            if av:
                                ext = "gif" if av.startswith("a_") else "png"
                                users_map[uid_key]["avatar_url"] = f"https://cdn.discordapp.com/avatars/{uid_int}/{av}.{ext}"
                            else:
                                users_map[uid_key]["avatar_url"] = f"https://cdn.discordapp.com/embed/avatars/{(uid_int >> 22) % 6}.png"
                            users_map[uid_key]["username"] = udata.get("username", users_map[uid_key]["username"])
                    except Exception as e:
                        logger.warning(f"[AVATAR] Fetch failed for {uid_key}: {e}")

        # Set'leri listeye çevir
        for uid in users_map:
            users_map[uid]["guilds"] = list(users_map[uid]["guilds"])
            users_map[uid]["guild_count"] = len(users_map[uid]["guilds"])
        users_data = sorted(users_map.values(), key=lambda x: x["product_count"], reverse=True)

    ctx = template_context(request, {
        "users": users_data,
        "total_users": len(users_data),
        "total_products": total_products,
        "total_savings": total_savings
    })
    return templates.TemplateResponse("users.html", ctx)


@app.get("/users/{user_id}")
async def user_detail(request: Request, user_id: str):
    """Kullanıcı detay sayfası."""
    # Herkese açık istatistik sayfası - liste sayfası gibi giriş gerektirmez
    products = []
    if db_instance:
        products = db_instance.get_all_products(user_id=user_id)

    user_data = {"username": "Bilinmeyen Kullanıcı", "avatar_url": ""}
    if bot_instance:
        bot_token = os.getenv('DISCORD_TOKEN', '')
        headers = {"Authorization": f"Bot {bot_token}"}
        async with httpx.AsyncClient(timeout=5.0) as client:
            try:
                resp = await client.get(
                    f"https://discord.com/api/v10/users/{user_id}",
                    headers=headers
                )
                if resp.status_code == 200:
                    udata = resp.json()
                    av = udata.get("avatar")
                    uid_int = int(user_id)
                    if av:
                        ext = "gif" if av.startswith("a_") else "png"
                        avatar_url = f"https://cdn.discordapp.com/avatars/{uid_int}/{av}.{ext}"
                    else:
                        avatar_url = f"https://cdn.discordapp.com/embed/avatars/{(uid_int >> 22) % 6}.png"
                    user_data = {
                        "username": udata.get("username", "Bilinmeyen Kullanıcı"),
                        "avatar_url": avatar_url
                    }
                else:
                    logger.warning(f"[USER] HTTP fetch failed for {user_id}: {resp.status_code}")
            except Exception as e:
                logger.warning(f"[USER] HTTP fetch error for {user_id}: {e}")

    if user_data["username"] == "Bilinmeyen Kullanıcı" and db_instance:
        db_user = db_instance.get_user(user_id)
        if db_user:
            user_data["username"] = db_user.get('username', 'Bilinmeyen Kullanıcı')
            user_data["avatar_url"] = db_user.get('avatar_url', '')

    if user_data["username"] == "Bilinmeyen Kullanıcı" and products:
        if products[0].get('username'):
            user_data["username"] = products[0]['username']
        if products[0].get('avatar_url'):
            user_data["avatar_url"] = products[0]['avatar_url']

    guilds = []
    seen_guilds = set()
    for p in products:
        gid = p.get('guild_id')
        if gid and gid not in seen_guilds:
            seen_guilds.add(gid)
            g = None
            if bot_instance:
                g = bot_instance.get_guild(int(gid))
            if g:
                icon_url = get_guild_icon_url(g)
                guilds.append({"id": g.id, "name": g.name, "icon_url": icon_url})

    total_savings = 0
    for p in products:
        if p.get('original_price') and p.get('current_price'):
            if p['original_price'] > p['current_price']:
                total_savings += p['original_price'] - p['current_price']

    def get_guild_name_local(gid):
        if not bot_instance: return str(gid)
        try:
            g = bot_instance.get_guild(int(gid))
            return g.name if g else str(gid)
        except:
            return str(gid)

    ctx = template_context(request, {
        "user_data": user_data,
        "products": products,
        "guilds": guilds,
        "total_savings": total_savings,
        "get_guild_name": get_guild_name_local
    })
    return templates.TemplateResponse("user_detail.html", ctx)


# ============================================================
# ADMIN PANELI ROUTES (Sadece Bot Owner)
# ============================================================

def is_owner(request: Request):
    """Bot owner kontrolü."""
    user = request.session.get("user")
    if not user or str(user['id']) != OWNER_ID:
        return False
    return True

async def owner_redirect(request: Request):
    """Owner değilse dashboard'a yönlendir."""
    if not is_owner(request):
        return RedirectResponse("/dashboard")
    return None

def is_authenticated(request: Request):
    """Kullanıcı giriş yapmış mı kontrol et."""
    return request.session.get("user") is not None

def is_user_authorized(request: Request, user_id: str):
    """IDOR koruması: Kullanıcı kendi verisine mi erişiyor, yoksa owner mı?"""
    if is_owner(request):
        return True
    user = request.session.get("user")
    if user and str(user.get("id", "")) == str(user_id):
        return True
    return False

def is_guild_authorized(request: Request, guild_id: str):
    """IDOR koruması: Kullanıcı bu sunucunun üyesi mi, yoksa owner mı?"""
    if is_owner(request):
        return True
    user_guilds = request.session.get("user_guilds", [])
    for g in user_guilds:
        if str(g.get("id", "")) == str(guild_id):
            return True
    return False

@app.get("/admin")
async def admin_dashboard(request: Request):
    redirect = await owner_redirect(request)
    if redirect: return redirect
    
    user = request.session.get("user")
    sys_stats = db_instance.get_system_stats() if db_instance else {}
    guilds_data = []
    total_members = 0
    if bot_instance:
        for g in bot_instance.guilds:
            guilds_data.append({"id": g.id, "name": g.name, "member_count": g.member_count, "icon_url": get_guild_icon_url(g)})
            total_members += g.member_count
    
    recent_activity = db_instance.get_recent_activity(10) if db_instance else []
    
    ctx = template_context(request, {
        "is_owner": True, "active_page": "dashboard",
        "sys_stats": sys_stats, "guilds": guilds_data,
        "total_members": total_members, "recent_activity": recent_activity
    })
    return templates.TemplateResponse("admin.html", ctx)

@app.get("/admin/servers")
async def admin_servers(request: Request):
    redirect = await owner_redirect(request)
    if redirect: return redirect
    
    user = request.session.get("user")
    guilds_data = []
    db_guilds = db_instance.get_all_guilds_from_db() if db_instance else {}
    db_guild_map = {g['guild_id']: g for g in db_guilds}
    
    if bot_instance:
        for g in bot_instance.guilds:
            db_info = db_guild_map.get(str(g.id), {})
            guilds_data.append({
                "id": g.id, "name": g.name, "member_count": g.member_count,
                "icon_url": get_guild_icon_url(g),
                "product_count": db_info.get('product_count', 0),
                "user_count": db_info.get('user_count', 0),
                "last_activity": db_info.get('last_activity', ''),
                "role_count": len(g.roles),
                "channel_count": len(g.text_channels) + len(g.voice_channels)
            })
    
    ctx = template_context(request, {
        "is_owner": True, "active_page": "servers",
        "servers": guilds_data,
        "total_members": sum(s['member_count'] for s in guilds_data),
        "total_products": sum(s['product_count'] for s in guilds_data)
    })
    return templates.TemplateResponse("admin_servers.html", ctx)

@app.get("/admin/servers/{guild_id}")
async def admin_server_detail(request: Request, guild_id: str):
    redirect = await owner_redirect(request)
    if redirect: return redirect
    
    user = request.session.get("user")
    guild = bot_instance.get_guild(int(guild_id)) if bot_instance else None
    if not guild:
        return RedirectResponse("/admin/servers")
    
    members = []
    roles = [{"id": r.id, "name": r.name, "color_hex": f"{r.color.value:06x}" if r.color.value else "8b7264", "position": r.position, "member_count": len(r.members)} 
             for r in guild.roles if r.name != "@everyone"]
    channels = [{"id": c.id, "name": c.name, "type": str(c.type), "position": c.position}
                for c in guild.channels]
    
    invite_link = ""
    bot_token = os.getenv('DISCORD_TOKEN', '')
    headers_a = {"Authorization": f"Bot {bot_token}"}
    try:
        system_ch = guild.system_channel or next((c for c in guild.text_channels if c.permissions_for(guild.me).create_instant_invite), None)
        if system_ch:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.post(
                    f"https://discord.com/api/v10/channels/{system_ch.id}/invites",
                    headers=headers_a,
                    json={"max_age": 86400, "max_uses": 0, "reason": "Admin panel invite"}
                )
                if resp.status_code == 200:
                    code = resp.json().get('code', '')
                    if code:
                        invite_link = f"https://discord.gg/{code}"
    except:
        pass
    
    products = db_instance.get_guild_products_detail(guild_id) if db_instance else []
    
    ctx = template_context(request, {
        "is_owner": True, "active_page": "servers",
        "guild": {"id": guild.id, "name": guild.name, "member_count": guild.member_count,
                  "icon_url": get_guild_icon_url(guild), "owner_id": guild.owner_id},
        "members": members, "roles": roles, "channels": channels,
        "products": products, "invite_link": invite_link,
        "get_guild_name": get_guild_name
    })
    return templates.TemplateResponse("admin_server_detail.html", ctx)

@app.get("/admin/users")
async def admin_users(request: Request):
    redirect = await owner_redirect(request)
    if redirect: return redirect
    
    user = request.session.get("user")
    users_data = []
    if db_instance:
        db_users = db_instance.get_all_users()
        all_products = db_instance.get_all_products()
        user_product_map = {}
        for p in all_products:
            uid = p.get('user_id')
            if uid:
                if uid not in user_product_map:
                    user_product_map[uid] = {"count": 0, "guilds": set(), "savings": 0}
                user_product_map[uid]["count"] += 1
                if p.get('guild_id'):
                    user_product_map[uid]["guilds"].add(p['guild_id'])
                if p.get('original_price') and p.get('current_price') and p['original_price'] > p['current_price']:
                    user_product_map[uid]["savings"] += p['original_price'] - p['current_price']
        
        for u in db_users:
            uid = u.get('user_id', '')
            pdata = user_product_map.get(uid, {"count": 0, "guilds": set(), "savings": 0})
            users_data.append({
                "user_id": uid,
                "username": u.get('username', 'Bilinmeyen'),
                "avatar_url": u.get('avatar_url', ''),
                "last_login": u.get('last_login', ''),
                "product_count": pdata["count"],
                "guild_count": len(pdata["guilds"]),
                "savings": pdata["savings"]
            })
    
    ctx = template_context(request, {
        "is_owner": True, "active_page": "users",
        "admin_users": users_data
    })
    return templates.TemplateResponse("admin_users.html", ctx)

@app.get("/admin/products")
async def admin_products(request: Request):
    redirect = await owner_redirect(request)
    if redirect: return redirect
    
    user = request.session.get("user")
    products = db_instance.get_all_products_admin() if db_instance else []
    
    ctx = template_context(request, {
        "is_owner": True, "active_page": "products",
        "products": products, "get_guild_name": get_guild_name
    })
    return templates.TemplateResponse("admin_products.html", ctx)

@app.get("/admin/products/{product_id}")
async def admin_product_detail(request: Request, product_id: str):
    redirect = await owner_redirect(request)
    if redirect: return redirect
    
    user = request.session.get("user")
    products = db_instance.get_all_products() if db_instance else []
    product = None
    for p in products:
        if p.get('product_id') == product_id:
            product = p
            break
    
    if not product:
        return RedirectResponse("/admin/products")
    
    price_history = db_instance.get_product_price_history(product_id, 30) if db_instance else []
    
    ctx = template_context(request, {
        "is_owner": True, "active_page": "products",
        "product": product, "price_history": price_history,
        "get_guild_name": get_guild_name
    })
    return templates.TemplateResponse("admin_product_detail.html", ctx)

@app.get("/admin/logs")
async def admin_logs(request: Request):
    redirect = await owner_redirect(request)
    if redirect: return redirect
    
    user = request.session.get("user")
    recent_activity = db_instance.get_recent_activity(50) if db_instance else []
    
    ctx = template_context(request, {
        "is_owner": True, "active_page": "logs",
        "activities": recent_activity, "get_guild_name": get_guild_name
    })
    return templates.TemplateResponse("admin_logs.html", ctx)

@app.get("/admin/system")
async def admin_system(request: Request):
    redirect = await owner_redirect(request)
    if redirect: return redirect
    
    user = request.session.get("user")
    sys_stats = db_instance.get_system_stats() if db_instance else {}
    
    bot_status = "online"
    bot_latency = 0
    bot_uptime = 0
    if bot_instance:
        bot_latency = round(bot_instance.latency * 1000)
        if bot_instance.is_ready():
            import time
            bot_uptime = int(time.time() - bot_instance.start_time) if hasattr(bot_instance, 'start_time') else 0
    
    ctx = template_context(request, {
        "is_owner": True, "active_page": "system",
        "sys_stats": sys_stats, "bot_status": bot_status,
        "bot_latency": bot_latency, "bot_uptime": bot_uptime
    })
    return templates.TemplateResponse("admin_system.html", ctx)


# ===== FİYAT ALARMLARI =====
@app.get("/alerts")
async def alerts_page(request: Request):
    user = request.session.get("user")
    if not user:
        return RedirectResponse("/login")

    user_id = user.get("id", "")
    alerts_data = []
    if db_instance:
        alerts_data = db_instance.get_user_alerts(user_id)

    ctx = template_context(request, {"alerts": alerts_data})
    return templates.TemplateResponse("alerts.html", ctx)


@app.post("/alert/add")
async def add_alert(request: Request):
    user = request.session.get("user")
    if not user:
        return RedirectResponse("/login")

    form = await request.form()
    product_id = form.get("product_id", "")
    target_price = form.get("target_price", "0")
    direction = form.get("direction", "below")

    try:
        target_price = float(target_price)
    except:
        target_price = 0

    user_id = user.get("id", "")
    guild_id = form.get("guild_id", "0")
    channel_id = form.get("channel_id", "0")

    if db_instance:
        db_instance.add_alert(product_id, user_id, guild_id, channel_id, target_price, direction)

    return RedirectResponse("/alerts", status_code=303)


@app.post("/alert/delete/{alert_id}")
async def delete_alert(request: Request, alert_id: int):
    user = request.session.get("user")
    if not user:
        return RedirectResponse("/login")

    user_id = user.get("id", "")
    if db_instance:
        db_instance.delete_alert(alert_id, user_id)

    return RedirectResponse("/alerts", status_code=303)


# ===== ÜRÜN KARŞILAŞTIRMA =====
@app.get("/compare")
async def compare_page(request: Request):
    guild_id = request.query_params.get("guild_id", "")
    products = []
    guild_name = ""

    if guild_id and db_instance:
        products = db_instance.get_guild_compare(guild_id)
        if bot_instance:
            g = bot_instance.get_guild(int(guild_id))
            if g:
                guild_name = g.name

    guilds = []
    if bot_instance:
        for g in bot_instance.guilds:
            guilds.append({"id": g.id, "name": g.name})

    ctx = template_context(request, {
        "products": products,
        "guilds": guilds,
        "selected_guild": guild_id,
        "guild_name": guild_name
    })
    return templates.TemplateResponse("compare.html", ctx)


# ===== BİLDİRİM TERCİHLERİ =====
@app.get("/notifications")
async def notifications_page(request: Request):
    user = request.session.get("user")
    if not user:
        return RedirectResponse("/login")

    user_id = user.get("id", "")
    guilds = []
    preferences = {}

    if bot_instance:
        for g in bot_instance.guilds:
            guilds.append({"id": g.id, "name": g.name})
            if db_instance:
                prefs = db_instance.get_user_preferences(user_id, str(g.id))
                if prefs:
                    preferences[str(g.id)] = prefs

    ctx = template_context(request, {
        "guilds": guilds,
        "preferences": preferences
    })
    return templates.TemplateResponse("notifications.html", ctx)


@app.post("/notifications/save")
async def save_notifications(request: Request):
    user = request.session.get("user")
    if not user:
        return RedirectResponse("/login")

    form = await request.form()
    user_id = user.get("id", "")
    guild_id = form.get("guild_id", "")
    channel_id = form.get("channel_id", "")
    on_drop = 1 if form.get("notify_on_drop") else 0
    on_rise = 1 if form.get("notify_on_rise") else 0
    threshold = 5.0
    try:
        threshold = float(form.get("notify_threshold", "5.0"))
    except:
        pass

    if db_instance and guild_id:
        db_instance.set_user_preferences(user_id, guild_id,
            channel_id=channel_id, on_drop=on_drop, on_rise=on_rise, threshold=threshold)

    return RedirectResponse("/notifications", status_code=303)


# ===== SUNUCU İSTATİSTİKLERİ =====
@app.get("/servers/{guild_id}/stats")
async def guild_stats_page(request: Request, guild_id: str):
    if not is_authenticated(request):
        return RedirectResponse("/login")
    if not is_guild_authorized(request, guild_id):
        return RedirectResponse("/dashboard")
    
    guild = None
    if bot_instance:
        guild = bot_instance.get_guild(int(guild_id))

    if not guild:
        return RedirectResponse("/servers")

    stats = {}
    if db_instance:
        stats = db_instance.get_guild_stats(guild_id)

    products = stats.get('top_products', [])
    icon_url = get_guild_icon_url(guild)

    ctx = template_context(request, {
        "guild": {"id": guild.id, "name": guild.name, "member_count": guild.member_count, "icon_url": icon_url},
        "stats": stats,
        "products": products
    })
    return templates.TemplateResponse("guild_stats.html", ctx)


@app.get("/logout")
async def logout(request: Request):
    user = request.session.get("user")
    request.session.clear()
    ctx = template_context(request)
    return templates.TemplateResponse("logout.html", ctx)
