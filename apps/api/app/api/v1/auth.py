from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import settings
from app.models.base import get_db
from app.models.user import User
from app.schemas.user import UserResponse
from app.services.auth import (
    get_discord_token,
    get_discord_user,
    create_access_token,
    create_refresh_token,
    verify_token
)
from app.services.user import get_user_by_discord_id, create_user

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/login")
async def login():
    """Redirect to Discord OAuth2."""
    discord_url = (
        f"https://discord.com/api/oauth2/authorize"
        f"?client_id={settings.CLIENT_ID}"
        f"&redirect_uri={settings.REDIRECT_URI}"
        f"&response_type=code"
        f"&scope=identify%20guilds"
    )
    return RedirectResponse(discord_url)


@router.get("/callback")
async def callback(code: str, db: AsyncSession = Depends(get_db)):
    """Handle Discord OAuth2 callback."""
    try:
        # Get Discord token
        token_data = await get_discord_token(code)
        access_token = token_data["access_token"]
        
        # Get user info
        user_info = await get_discord_user(access_token)
        
        # Get or create user
        user = await get_user_by_discord_id(db, user_info["id"])
        if not user:
            user = await create_user(db, {
                "discord_id": user_info["id"],
                "username": user_info["username"],
                "avatar_url": user_info.get("avatar", ""),
                "access_token": access_token,
                "refresh_token": token_data.get("refresh_token", "")
            })
        
        # Create JWT tokens
        jwt_access = create_access_token({"sub": str(user.id), "discord_id": user.discord_id})
        jwt_refresh = create_refresh_token({"sub": str(user.id), "discord_id": user.discord_id})
        
        # Set cookies and redirect
        response = RedirectResponse("/dashboard", status_code=303)
        response.set_cookie("access_token", jwt_access, httponly=True, secure=True, samesite="lax")
        response.set_cookie("refresh_token", jwt_refresh, httponly=True, secure=True, samesite="lax")
        
        return response
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Auth error: {str(e)}")


@router.get("/me", response_model=UserResponse)
async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Get current authenticated user."""
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    payload = verify_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    user = await get_user_by_discord_id(db, payload["discord_id"])
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return user


@router.post("/logout")
async def logout():
    """Clear session cookies."""
    response = RedirectResponse("/", status_code=303)
    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token")
    return response
