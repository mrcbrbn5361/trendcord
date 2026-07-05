import httpx
from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from app.config import settings


DISCORD_API_URL = "https://discord.com/api/v10"


async def get_discord_token(code: str) -> dict:
    """Exchange authorization code for access token."""
    data = {
        "client_id": settings.CLIENT_ID,
        "client_secret": settings.CLIENT_SECRET,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": settings.REDIRECT_URI
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    
    async with httpx.AsyncClient() as client:
        response = await client.post(f"{DISCORD_API_URL}/oauth2/token", data=data, headers=headers)
        if response.status_code != 200:
            raise Exception(f"Discord token error: {response.text}")
        return response.json()


async def refresh_discord_token(refresh_token: str) -> dict:
    """Refresh Discord access token."""
    data = {
        "client_id": settings.CLIENT_ID,
        "client_secret": settings.CLIENT_SECRET,
        "grant_type": "refresh_token",
        "refresh_token": refresh_token
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    
    async with httpx.AsyncClient() as client:
        response = await client.post(f"{DISCORD_API_URL}/oauth2/token", data=data, headers=headers)
        if response.status_code != 200:
            raise Exception(f"Discord refresh error: {response.text}")
        return response.json()


async def get_discord_user(access_token: str) -> dict:
    """Get user info from Discord API."""
    headers = {"Authorization": f"Bearer {access_token}"}
    
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{DISCORD_API_URL}/users/@me", headers=headers)
        if response.status_code != 200:
            raise Exception(f"Discord user error: {response.text}")
        return response.json()


async def get_discord_user_guilds(access_token: str) -> list:
    """Get user's guilds from Discord API."""
    headers = {"Authorization": f"Bearer {access_token}"}
    
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{DISCORD_API_URL}/users/@me/guilds", headers=headers)
        if response.status_code != 200:
            raise Exception(f"Discord guilds error: {response.text}")
        return response.json()


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create JWT access token."""
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_refresh_token(data: dict) -> str:
    """Create JWT refresh token."""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def verify_token(token: str) -> Optional[dict]:
    """Verify and decode JWT token."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except JWTError:
        return None
