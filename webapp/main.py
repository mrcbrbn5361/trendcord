import json
import logging
import os
import secrets
from datetime import datetime
from typing import Optional
from urllib.parse import urlencode

import dotenv
import httpx
from fastapi import Depends, FastAPI, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from itsdangerous import BadSignature, URLSafeSerializer
from passlib.context import CryptContext

from database import Database

dotenv.load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

DATABASE_PATH = os.getenv('DATABASE_PATH', 'data/trendyol_tracker.sqlite')
COOKIE_NAME = os.getenv('WEB_SESSION_COOKIE', 'trendcord_session')
COOKIE_SECURE = os.getenv('WEB_COOKIE_SECURE', 'false').lower() == 'true'
COOKIE_MAX_AGE = int(os.getenv('WEB_SESSION_MAX_AGE', 60 * 60 * 24 * 7))
SECRET_KEY = os.getenv('WEB_SECRET_KEY', secrets.token_hex(16))
DISCORD_CLIENT_ID = os.getenv('DISCORD_CLIENT_ID')
DISCORD_CLIENT_SECRET = os.getenv('DISCORD_CLIENT_SECRET')
DISCORD_REDIRECT_URI = os.getenv('DISCORD_REDIRECT_URI')
DISCORD_SCOPE = os.getenv('DISCORD_SCOPE', 'identify email')
DISCORD_API_BASE = 'https://discord.com/api'
OAUTH_STATE_COOKIE = f"{COOKIE_NAME}_oauth_state"

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
serializer = URLSafeSerializer(SECRET_KEY, salt='trendcord-web')

app = FastAPI(title="Trendcord Yönetim Paneli", version="1.0.0")
app.mount('/web/static', StaticFiles(directory='webapp/static'), name='web_static')
templates = Jinja2Templates(directory='webapp/templates')


def format_datetime(value: Optional[str], fmt: str = "%d.%m.%Y %H:%M") -> str:
    if not value:
        return "-"
    try:
        return datetime.fromisoformat(value).strftime(fmt)
    except ValueError:
        return value


templates.env.filters['datetime'] = format_datetime


def get_db() -> Database:
    return app.state.db


def get_current_user(request: Request, db: Database) -> Optional[dict]:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return None
    try:
        payload = serializer.loads(token)
    except BadSignature:
        return None

    user = db.get_user_by_id(payload.get('user_id'))
    return user


def ensure_admin_user(db: Database):
    username = os.getenv('WEB_ADMIN_USERNAME', 'admin')
    email = os.getenv('WEB_ADMIN_EMAIL', 'admin@example.com')
    discord_id = os.getenv('WEB_ADMIN_DISCORD_ID')

    if not discord_id:
        logger.warning("WEB_ADMIN_DISCORD_ID tanımlanmadı. Admin hesabı Discord ile oturum açamayacak.")

    admin = db.get_user_by_username(username)
    if not admin:
        logger.info("Varsayılan admin kullanıcısı oluşturuluyor...")
        db.create_user(
            username=username,
            email=email,
            password_hash=pwd_context.hash(secrets.token_urlsafe(32)),
            role='admin',
            discord_id=discord_id,
        )
        logger.info("Admin kullanıcısı hazır.")
    elif discord_id and str(admin.get('discord_id')) != str(discord_id):
        logger.info("Admin kullanıcısının Discord ID'si güncelleniyor...")
        db.update_user_discord_id(admin['id'], discord_id)


def _discord_oauth_ready() -> bool:
    return all([DISCORD_CLIENT_ID, DISCORD_CLIENT_SECRET, DISCORD_REDIRECT_URI])


def _build_discord_authorize_url(state: str) -> str:
    params = {
        'response_type': 'code',
        'client_id': DISCORD_CLIENT_ID,
        'scope': DISCORD_SCOPE,
        'redirect_uri': DISCORD_REDIRECT_URI,
        'state': state,
        'prompt': 'consent',
    }
    return f"{DISCORD_API_BASE}/oauth2/authorize?{urlencode(params)}"


async def _fetch_discord_profile(code: str) -> dict:
    data = {
        'client_id': DISCORD_CLIENT_ID,
        'client_secret': DISCORD_CLIENT_SECRET,
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': DISCORD_REDIRECT_URI,
    }
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}

    async with httpx.AsyncClient(timeout=10) as client:
        token_resp = await client.post(f"{DISCORD_API_BASE}/oauth2/token", data=data, headers=headers)
        token_resp.raise_for_status()
        token_data = token_resp.json()
        access_token = token_data.get('access_token')
        if not access_token:
            raise RuntimeError('Discord access token alınamadı')

        user_resp = await client.get(
            f"{DISCORD_API_BASE}/users/@me",
            headers={'Authorization': f"Bearer {access_token}"},
        )
        user_resp.raise_for_status()
        return user_resp.json()


@app.on_event('startup')
async def startup_event():
    app.state.db = Database(db_name=DATABASE_PATH)
    ensure_admin_user(app.state.db)
    logger.info("Web uygulaması başlatıldı.")


@app.on_event('shutdown')
async def shutdown_event():
    db: Database = app.state.db
    db.close()
    logger.info("Veritabanı bağlantısı kapatıldı.")


@app.get('/', response_class=HTMLResponse)
async def root(request: Request, db: Database = Depends(get_db)):
    user = get_current_user(request, db)
    if user:
        return RedirectResponse('/dashboard', status_code=status.HTTP_303_SEE_OTHER)
    return RedirectResponse('/login', status_code=status.HTTP_303_SEE_OTHER)


@app.get('/login', response_class=HTMLResponse)
async def login_page(request: Request, db: Database = Depends(get_db)):
    user = get_current_user(request, db)
    if user:
        return RedirectResponse('/dashboard', status_code=status.HTTP_303_SEE_OTHER)
    error = request.query_params.get('error')
    context = {
        "request": request,
        "error": error,
        "oauth_ready": _discord_oauth_ready(),
    }
    return templates.TemplateResponse('login.html', context)


@app.get('/auth/discord')
async def start_discord_oauth():
    if not _discord_oauth_ready():
        raise HTTPException(status_code=500, detail="Discord OAuth ayarları eksik. Lütfen .env dosyanızı kontrol edin.")

    state = secrets.token_urlsafe(16)
    authorize_url = _build_discord_authorize_url(state)
    signed_state = serializer.dumps({"state": state})

    response = RedirectResponse(authorize_url, status_code=status.HTTP_307_TEMPORARY_REDIRECT)
    response.set_cookie(
        OAUTH_STATE_COOKIE,
        signed_state,
        httponly=True,
        secure=COOKIE_SECURE,
        max_age=300,
        samesite='lax'
    )
    return response


@app.get('/auth/callback', response_class=HTMLResponse)
async def discord_callback(request: Request, code: Optional[str] = None, state: Optional[str] = None, db: Database = Depends(get_db)):
    if not _discord_oauth_ready():
        raise HTTPException(status_code=500, detail="Discord OAuth ayarları eksik.")

    if not code or not state:
        return templates.TemplateResponse(
            'login.html',
            {"request": request, "error": "Discord doğrulaması başarısız oldu.", "oauth_ready": True},
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    stored_state = request.cookies.get(OAUTH_STATE_COOKIE)
    if not stored_state:
        return templates.TemplateResponse(
            'login.html',
            {"request": request, "error": "Oturum doğrulama bilgisi bulunamadı.", "oauth_ready": True},
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    try:
        payload = serializer.loads(stored_state)
    except BadSignature:
        return templates.TemplateResponse(
            'login.html',
            {"request": request, "error": "Geçersiz oturum doğrulama bilgisi.", "oauth_ready": True},
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    if payload.get('state') != state:
        return templates.TemplateResponse(
            'login.html',
            {"request": request, "error": "Oturum doğrulaması uyuşmuyor.", "oauth_ready": True},
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    try:
        profile = await _fetch_discord_profile(code)
    except httpx.HTTPError as exc:
        logger.error("Discord OAuth isteği başarısız oldu: %s", exc)
        return templates.TemplateResponse(
            'login.html',
            {"request": request, "error": "Discord doğrulaması sırasında hata oluştu.", "oauth_ready": True},
            status_code=status.HTTP_502_BAD_GATEWAY,
        )
    except Exception as exc:
        logger.error("Discord OAuth beklenmedik hata: %s", exc)
        return templates.TemplateResponse(
            'login.html',
            {"request": request, "error": "Discord hesabı doğrulanamadı.", "oauth_ready": True},
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    discord_id = profile.get('id')
    if not discord_id:
        return templates.TemplateResponse(
            'login.html',
            {"request": request, "error": "Discord hesabı doğrulanamadı.", "oauth_ready": True},
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    user = db.get_user_by_discord_id(discord_id)
    if not user:
        context = {
            "request": request,
            "error": "Bu Discord hesabı için yetkilendirilmiş kullanıcı bulunamadı.",
            "oauth_ready": True,
        }
        response = templates.TemplateResponse('login.html', context, status_code=status.HTTP_403_FORBIDDEN)
        response.delete_cookie(OAUTH_STATE_COOKIE)
        return response

    db.record_user_login(user['id'])

    response = RedirectResponse('/dashboard', status_code=status.HTTP_303_SEE_OTHER)
    token = serializer.dumps({"user_id": user['id'], "role": user['role']})
    response.set_cookie(
        COOKIE_NAME,
        token,
        httponly=True,
        secure=COOKIE_SECURE,
        max_age=COOKIE_MAX_AGE,
        samesite='lax'
    )
    response.delete_cookie(OAUTH_STATE_COOKIE)
    return response


@app.get('/logout')
async def logout_action():
    response = RedirectResponse('/login', status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie(COOKIE_NAME)
    response.delete_cookie(OAUTH_STATE_COOKIE)
    return response


def _products_for_user(db: Database, user: dict):
    if user['role'] == 'admin':
        return db.get_all_products()
    discord_id = user.get('discord_id')
    if discord_id:
        return db.get_all_products(user_id=str(discord_id))
    return []


@app.get('/dashboard', response_class=HTMLResponse)
async def dashboard(request: Request, db: Database = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse('/login', status_code=status.HTTP_303_SEE_OTHER)

    products = _products_for_user(db, user)
    total_products = db.get_total_product_count()
    guild_count = db.get_distinct_guild_count()
    guild_breakdown = db.get_product_counts_by_guild()
    recent_events = db.get_recent_price_events(limit=6)

    context = {
        "request": request,
        "user": user,
        "products": products,
        "total_products": total_products,
        "guild_count": guild_count,
        "guild_breakdown": guild_breakdown,
        "recent_events": recent_events,
        "owns_products": len(products) > 0,
    }
    return templates.TemplateResponse('dashboard.html', context)


@app.get('/products/{product_id}', response_class=HTMLResponse)
async def product_detail(product_id: str, request: Request, db: Database = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse('/login', status_code=status.HTTP_303_SEE_OTHER)

    product = db.get_product(product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Ürün bulunamadı")

    if user['role'] != 'admin':
        discord_id = user.get('discord_id')
        if not discord_id or str(product.get('user_id')) != str(discord_id):
            raise HTTPException(status_code=403, detail="Bu ürüne erişim izniniz yok")

    history = db.get_price_history(product_id, limit=30, order='ASC')
    labels = [format_datetime(item['date']) for item in history]
    values = [item['price'] for item in history]

    context = {
        "request": request,
        "user": user,
        "product": product,
        "labels": json.dumps(labels, ensure_ascii=False),
        "values": json.dumps(values),
        "history": history,
    }
    return templates.TemplateResponse('product_detail.html', context)


@app.get('/admin/users', response_class=HTMLResponse)
async def manage_users(request: Request, db: Database = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse('/login', status_code=status.HTTP_303_SEE_OTHER)
    if user['role'] != 'admin':
        raise HTTPException(status_code=403, detail="Bu sayfaya erişim izniniz yok")

    users = db.list_users()
    return templates.TemplateResponse('admin_users.html', {"request": request, "user": user, "users": users, "message": None, "error": None})


@app.post('/admin/users', response_class=HTMLResponse)
async def create_user(
    request: Request,
    username: str = Form(...),
    email: str = Form(...),
    role: str = Form('user'),
    discord_id: Optional[str] = Form(None),
    db: Database = Depends(get_db),
):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse('/login', status_code=status.HTTP_303_SEE_OTHER)
    if user['role'] != 'admin':
        raise HTTPException(status_code=403, detail="Bu işlem için yetkiniz yok")

    if not discord_id:
        users = db.list_users()
        context = {"request": request, "user": user, "users": users, "error": "Discord ID zorunludur.", "message": None}
        return templates.TemplateResponse('admin_users.html', context, status_code=status.HTTP_400_BAD_REQUEST)

    success, message = db.create_user(
        username=username.strip(),
        email=email.strip(),
        password_hash=pwd_context.hash(secrets.token_urlsafe(32)),
        role=role,
        discord_id=discord_id.strip() if discord_id else None,
    )

    users = db.list_users()
    context = {"request": request, "user": user, "users": users}
    if success:
        context['message'] = f"{username} adlı kullanıcı oluşturuldu."
        context['error'] = None
    else:
        context['message'] = None
        context['error'] = message or "Kullanıcı oluşturulamadı."
    return templates.TemplateResponse('admin_users.html', context)


@app.get('/api/products/summary', response_class=JSONResponse)
async def products_summary(db: Database = Depends(get_db)):
    return {
        "total_products": db.get_total_product_count(),
        "guild_count": db.get_distinct_guild_count(),
        "guild_breakdown": db.get_product_counts_by_guild(),
        "recent_events": db.get_recent_price_events(limit=5),
    }
