import json
import logging
import os
import secrets
from datetime import datetime
from typing import Optional

import dotenv
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
    password = os.getenv('WEB_ADMIN_PASSWORD')
    discord_id = os.getenv('WEB_ADMIN_DISCORD_ID')

    if not password:
        logger.warning("WEB_ADMIN_PASSWORD tanımlanmadı. Varsayılan 'admin123' kullanılacak.")
        password = 'admin123'

    admin = db.get_user_by_username(username)
    if not admin:
        logger.info("Varsayılan admin kullanıcısı oluşturuluyor...")
        db.create_user(
            username=username,
            email=email,
            password_hash=pwd_context.hash(password),
            role='admin',
            discord_id=discord_id,
        )
        logger.info("Admin kullanıcısı hazır.")


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
    return templates.TemplateResponse('login.html', {"request": request, "error": None})


@app.post('/login', response_class=HTMLResponse)
async def login_action(request: Request, username: str = Form(...), password: str = Form(...), db: Database = Depends(get_db)):
    user = db.get_user_by_username(username)
    error = None
    if not user or not pwd_context.verify(password, user['password_hash']):
        error = "Kullanıcı adı veya şifre hatalı."
        return templates.TemplateResponse('login.html', {"request": request, "error": error}, status_code=status.HTTP_401_UNAUTHORIZED)

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
    return response


@app.get('/logout')
async def logout_action():
    response = RedirectResponse('/login', status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie(COOKIE_NAME)
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
async def create_user(request: Request, username: str = Form(...), email: str = Form(...), password: str = Form(...), role: str = Form('user'), discord_id: Optional[str] = Form(None), db: Database = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse('/login', status_code=status.HTTP_303_SEE_OTHER)
    if user['role'] != 'admin':
        raise HTTPException(status_code=403, detail="Bu işlem için yetkiniz yok")

    success, message = db.create_user(
        username=username.strip(),
        email=email.strip(),
        password_hash=pwd_context.hash(password),
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
