from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from app.models.base import get_db
from app.schemas.product import ProductCreate, ProductUpdate, ProductResponse, PriceHistoryResponse
from app.services.product import (
    get_products,
    get_product,
    create_product,
    update_product,
    delete_product,
    get_price_history
)
from app.services.auth import verify_token

router = APIRouter(prefix="/products", tags=["products"])


async def get_current_user_id(request: Request) -> int:
    """Extract user ID from JWT token."""
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    payload = verify_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    return int(payload["sub"])


@router.get("/", response_model=List[ProductResponse])
async def list_products(
    guild_id: Optional[int] = None,
    user_id: Optional[int] = None,
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id)
):
    """List products with optional filtering."""
    products = await get_products(db, guild_id=guild_id, user_id=user_id, skip=skip, limit=limit)
    return products


@router.get("/{product_id}", response_model=ProductResponse)
async def get_single_product(
    product_id: str,
    db: AsyncSession = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id)
):
    """Get single product."""
    product = await get_product(db, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


@router.post("/", response_model=ProductResponse)
async def create_new_product(
    product_data: ProductCreate,
    db: AsyncSession = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id)
):
    """Create new product."""
    product = await create_product(db, product_data, current_user_id)
    return product


@router.put("/{product_id}", response_model=ProductResponse)
async def update_existing_product(
    product_id: str,
    product_data: ProductUpdate,
    db: AsyncSession = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id)
):
    """Update product."""
    product = await update_product(db, product_id, product_data)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


@router.delete("/{product_id}")
async def delete_existing_product(
    product_id: str,
    db: AsyncSession = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id)
):
    """Delete product."""
    success = await delete_product(db, product_id)
    if not success:
        raise HTTPException(status_code=404, detail="Product not found")
    return {"message": "Product deleted"}


@router.get("/{product_id}/history", response_model=List[PriceHistoryResponse])
async def get_product_history(
    product_id: str,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id)
):
    """Get price history for product."""
    history = await get_price_history(db, product_id, limit)
    return history
