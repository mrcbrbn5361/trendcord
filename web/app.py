from fastapi import FastAPI, Request, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
import os
import sys

# Ana dizini path'e ekle ki database ve scraper'a erişebilelim
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from web.auth import get_access_token, get_user_info, get_user_guilds, get_login_url

app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key=os.getenv("SECRET_KEY", "very-secret-key"))

templates = Jinja2Templates(directory="web/templates")

# Bot ve DB instance'larını buraya main.py'den set edeceğiz
bot_instance = None
db_instance = None

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    user = request.session.get("user")
    return templates.TemplateResponse("index.html", {"request": request, "user": user})

@app.get("/login")
async def login():
    return RedirectResponse(get_login_url())

@app.get("/callback")
async def callback(request: Request, code: str):
    token_data = await get_access_token(code)
    access_token = token_data['access_token']
    user_info = await get_user_info(access_token)

    request.session["user"] = user_info
    request.session["access_token"] = access_token
    return RedirectResponse("/dashboard")

@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/")

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    user = request.session.get("user")
    if not user:
        return RedirectResponse("/login")

    user_id = user['id']
    owner_id = os.getenv('OWNER_ID')

    products = []

    if user_id == owner_id:
        # Bot sahibi her şeyi görür
        products = db_instance.get_all_products()
        view_type = "Full Access (Bot Owner)"
    else:
        # Normal kullanıcı veya sunucu sahibi
        token = request.session.get("access_token")
        guilds = await get_user_guilds(token)

        # Kullanıcının kendi ürünleri
        user_products = db_instance.get_all_products(user_id=user_id)
        products_dict = {p['product_id']: p for p in user_products}

        # Sunucu sahibi olduğu sunuculardaki tüm ürünler
        for guild in guilds:
            # owner: True if the user is the owner of the guild
            # permissions: bitmask of permissions (ADMINISTRATOR is 0x8)
            is_admin = (guild.get('permissions', 0) & 0x8) == 0x8
            if guild.get('owner') or is_admin:
                guild_products = db_instance.get_all_products(guild_id=guild['id'])
                for p in guild_products:
                    products_dict[p['product_id']] = p

        products = list(products_dict.values())
        view_type = "Personal + Owned Servers"

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "user": user,
        "products": products,
        "view_type": view_type
    })

def set_instances(bot, db):
    global bot_instance, db_instance
    bot_instance = bot
    db_instance = db
