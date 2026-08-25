import os
import secrets
import httpx
from urllib.parse import quote
from fastapi import HTTPException
from dotenv import load_dotenv

load_dotenv()

CLIENT_ID = os.getenv('CLIENT_ID')
CLIENT_SECRET = os.getenv('CLIENT_SECRET')
REDIRECT_URI = os.getenv('REDIRECT_URI')
DISCORD_API_URL = "https://discord.com/api/v10"

async def get_access_token(code: str, redirect_uri: str = None):
    data = {
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET,
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': redirect_uri or REDIRECT_URI
    }
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded'
    }
    async with httpx.AsyncClient() as client:
        response = await client.post(f"{DISCORD_API_URL}/oauth2/token", data=data, headers=headers)
        if response.status_code != 200:
            raise Exception(f"Discord token error ({response.status_code}): {response.text}")
        return response.json()

async def get_user_info(token: str):
    headers = {
        'Authorization': f'Bearer {token}'
    }
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{DISCORD_API_URL}/users/@me", headers=headers)
        if response.status_code != 200:
            raise HTTPException(status_code=400, detail=f"Failed to get user info: {response.text}")
        return response.json()

async def get_user_guilds(token: str):
    headers = {
        'Authorization': f'Bearer {token}'
    }
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{DISCORD_API_URL}/users/@me/guilds", headers=headers)
        if response.status_code != 200:
            raise HTTPException(status_code=400, detail=f"Failed to get user guilds: {response.text}")
        return response.json()

def generate_state():
    """CSRF koruması için rastgele state parametresi üret."""
    return secrets.token_urlsafe(32)

def get_login_url(state: str = None):
    """Discord OAuth2 login URL'i üret. CSRF state parametresi dahil."""
    if not state:
        state = generate_state()
    return f"https://discord.com/api/oauth2/authorize?client_id={CLIENT_ID}&redirect_uri={REDIRECT_URI}&response_type=code&scope=identify%20guilds&state={state}"
