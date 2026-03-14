import os
from fastapi import FastAPI, Request, Depends, HTTPException, Form
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
import httpx
from database import Database
from scraper import TrendyolScraper
from dotenv import load_dotenv
from datetime import datetime, timedelta
import logging

load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key=os.getenv("SECRET_KEY", "trendyol-secret-key-123"))

# Ensure static directory exists
os.makedirs("static", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

templates = Jinja2Templates(directory="templates")

db = Database()
scraper = TrendyolScraper(use_proxy=os.getenv("PROXY_ENABLED", "True").lower() == "true")

CLIENT_ID = os.getenv("DISCORD_CLIENT_ID")
CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET")
REDIRECT_URI = os.getenv("DISCORD_REDIRECT_URI")
BOT_TOKEN = os.getenv("DISCORD_TOKEN")
API_ENDPOINT = "https://discord.com/api/v10"

async def get_current_user(request: Request):
    return request.session.get("user")

@app.get("/", response_class=HTMLResponse)
async def index(request: Request, user=Depends(get_current_user)):
    if user:
        return RedirectResponse(url="/dashboard")
    return templates.TemplateResponse("index.html", {"request": request, "user": user})

@app.get("/login")
async def login():
    scope = "identify guilds"
    auth_url = f"https://discord.com/api/oauth2/authorize?client_id={CLIENT_ID}&redirect_uri={REDIRECT_URI}&response_type=code&scope={scope}"
    return RedirectResponse(url=auth_url)

@app.get("/auth/callback")
async def callback(request: Request, code: str):
    data = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}

    async with httpx.AsyncClient() as client:
        try:
            token_res = await client.post(f"{API_ENDPOINT}/oauth2/token", data=data, headers=headers)
            token_res.raise_for_status()
            token_data = token_res.json()

            user_res = await client.get(f"{API_ENDPOINT}/users/@me", headers={
                "Authorization": f"Bearer {token_data['access_token']}"
            })
            user_res.raise_for_status()
            user_info = user_res.json()

            user_db_data = {
                "id": user_info["id"],
                "username": user_info["username"],
                "avatar": user_info["avatar"],
                "access_token": token_data["access_token"],
                "refresh_token": token_data["refresh_token"],
                "expires_at": (datetime.now() + timedelta(seconds=token_data["expires_in"])).isoformat()
            }
            db.add_user(user_db_data)

            request.session["user"] = user_db_data
            return RedirectResponse(url="/dashboard")
        except Exception as e:
            logger.error(f"Auth error: {e}")
            return RedirectResponse(url="/?error=auth_failed")

@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/")

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, user=Depends(get_current_user)):
    if not user:
        return RedirectResponse(url="/")

    products = db.get_user_products(user["id"])
    return templates.TemplateResponse("dashboard.html", {"request": request, "user": user, "products": products})

@app.post("/add-product")
async def add_product(request: Request, url: str = Form(...), user=Depends(get_current_user)):
    if not user:
        return RedirectResponse(url="/", status_code=303)

    product_data = scraper.scrape_product(url)
    if product_data and product_data.get("success"):
        db.add_product(product_data, None, user["id"], None)
        return RedirectResponse(url="/dashboard", status_code=303)

    return RedirectResponse(url="/dashboard?error=product_not_found", status_code=303)

@app.get("/delete-product/{product_id}")
async def delete_product(product_id: str, user=Depends(get_current_user)):
    if not user:
        return RedirectResponse(url="/")

    db.delete_subscription(user["id"], product_id)
    return RedirectResponse(url="/dashboard")

@app.get("/guilds", response_class=HTMLResponse)
async def guilds(request: Request, user=Depends(get_current_user)):
    if not user:
        return RedirectResponse(url="/")

    async with httpx.AsyncClient() as client:
        # Get user guilds
        res = await client.get(f"{API_ENDPOINT}/users/@me/guilds", headers={
            "Authorization": f"Bearer {user['access_token']}"
        })
        if res.status_code != 200:
             return RedirectResponse(url="/login")
        user_guilds = res.json()

        # Get bot guilds
        bot_res = await client.get(f"{API_ENDPOINT}/users/@me/guilds", headers={
            "Authorization": f"Bot {BOT_TOKEN}"
        })
        bot_guild_ids = []
        if bot_res.status_code == 200:
            bot_guild_ids = [g['id'] for g in bot_res.json()]

    # Filter manageable guilds and check bot presence
    processed_guilds = []
    for g in user_guilds:
        if (int(g['permissions']) & 0x20) == 0x20 or (int(g['permissions']) & 0x8) == 0x8: # Manage Guild or Admin
            g['has_bot'] = g['id'] in bot_guild_ids
            processed_guilds.append(g)

    return templates.TemplateResponse("guilds.html", {
        "request": request,
        "user": user,
        "guilds": processed_guilds,
        "bot_id": CLIENT_ID
    })

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
