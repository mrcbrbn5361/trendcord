from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from typing import Optional
from app.models.product import Product, PriceHistory
from app.models.user import User
from app.models.guild import Guild
from app.schemas.product import ProductCreate, ProductUpdate


async def get_products(
    db: AsyncSession,
    guild_id: Optional[int] = None,
    user_id: Optional[int] = None,
    skip: int = 0,
    limit: int = 100
):
    """Get products with optional filtering."""
    query = select(Product).options(selectinload(Product.user))
    
    if guild_id:
        query = query.where(Product.guild_id == guild_id)
    if user_id:
        query = query.where(Product.user_id == user_id)
    
    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


async def get_product(db: AsyncSession, product_id: str):
    """Get single product by product_id."""
    query = select(Product).options(
        selectinload(Product.user),
        selectinload(Product.price_history)
    ).where(Product.product_id == product_id)
    result = await db.execute(query)
    return result.scalar_one_or_none()


async def create_product(db: AsyncSession, product_data: ProductCreate, user_id: int):
    """Create a new product."""
    product = Product(
        **product_data.model_dump(),
        user_id=user_id
    )
    db.add(product)
    await db.flush()
    await db.refresh(product)
    return product


async def update_product(db: AsyncSession, product_id: str, product_data: ProductUpdate):
    """Update product details."""
    query = select(Product).where(Product.product_id == product_id)
    result = await db.execute(query)
    product = result.scalar_one_or_none()
    
    if product:
        update_data = product_data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(product, key, value)
        await db.flush()
        await db.refresh(product)
    
    return product


async def delete_product(db: AsyncSession, product_id: str):
    """Delete product."""
    query = select(Product).where(Product.product_id == product_id)
    result = await db.execute(query)
    product = result.scalar_one_or_none()
    
    if product:
        await db.delete(product)
        return True
    return False


async def update_product_price(db: AsyncSession, product_id: str, new_price: float):
    """Update product price and add to history."""
    query = select(Product).where(Product.product_id == product_id)
    result = await db.execute(query)
    product = result.scalar_one_or_none()
    
    if product:
        product.current_price = new_price
        
        # Add to history
        history = PriceHistory(
            price=new_price,
            product_id=product.id
        )
        db.add(history)
        await db.flush()
        return True
    return False


async def get_price_history(db: AsyncSession, product_id: str, limit: int = 100):
    """Get price history for a product."""
    query = select(Product).where(Product.product_id == product_id)
    result = await db.execute(query)
    product = result.scalar_one_or_none()
    
    if product:
        query = select(PriceHistory).where(
            PriceHistory.product_id == product.id
        ).order_by(PriceHistory.timestamp.desc()).limit(limit)
        result = await db.execute(query)
        return result.scalars().all()
    return []


async def get_product_stats(db: AsyncSession):
    """Get product statistics."""
    total_products = await db.scalar(select(func.count(Product.id)))
    total_price_checks = await db.scalar(select(func.count(PriceHistory.id)))
    
    return {
        "product_count": total_products or 0,
        "price_checks": total_price_checks or 0
    }
