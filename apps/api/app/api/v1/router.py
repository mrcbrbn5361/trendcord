from fastapi import APIRouter
from app.api.v1 import auth, products, guilds

router = APIRouter(prefix="/api/v1")

router.include_router(auth.router)
router.include_router(products.router)
router.include_router(guilds.router)
