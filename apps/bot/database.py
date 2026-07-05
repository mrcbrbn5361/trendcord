import asyncpg
import json
from datetime import datetime
from typing import Optional, List


class Database:
    def __init__(self, database_url: str):
        self.database_url = database_url
        self.pool: Optional[asyncpg.Pool] = None

    async def connect(self):
        self.pool = await asyncpg.create_pool(self.database_url)
        await self._create_tables()

    async def _create_tables(self):
        async with self.pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS products (
                    product_id VARCHAR(64) PRIMARY KEY,
                    name VARCHAR(512) NOT NULL,
                    url VARCHAR(1024) NOT NULL,
                    image_url VARCHAR(1024) DEFAULT '',
                    current_price REAL DEFAULT 0,
                    original_price REAL DEFAULT 0,
                    last_checked TIMESTAMP DEFAULT NOW(),
                    guild_id VARCHAR(64) NOT NULL,
                    user_id VARCHAR(64) NOT NULL,
                    channel_id VARCHAR(64) DEFAULT '0',
                    username VARCHAR(255) DEFAULT '',
                    avatar_url VARCHAR(512) DEFAULT ''
                )
            """)
            
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS price_history (
                    id SERIAL PRIMARY KEY,
                    product_id VARCHAR(64) REFERENCES products(product_id),
                    price REAL NOT NULL,
                    timestamp TIMESTAMP DEFAULT NOW()
                )
            """)

    async def add_product(self, data: dict, guild_id: str, user_id: str, channel_id: str, username: str = "", avatar_url: str = ""):
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO products (product_id, name, url, image_url, current_price, original_price, last_checked, guild_id, user_id, channel_id, username, avatar_url)
                VALUES ($1, $2, $3, $4, $5, $6, NOW(), $7, $8, $9, $10, $11)
                ON CONFLICT (product_id) DO UPDATE SET
                    name = EXCLUDED.name,
                    url = EXCLUDED.url,
                    image_url = EXCLUDED.image_url,
                    current_price = EXCLUDED.current_price,
                    last_checked = NOW()
            """, data["product_id"], data["name"], data["url"], data.get("image_url", ""),
                data.get("current_price", 0), data.get("current_price", 0),
                guild_id, user_id, channel_id, username, avatar_url)

    async def get_all_products(self, guild_id: Optional[str] = None, user_id: Optional[str] = None) -> List[dict]:
        async with self.pool.acquire() as conn:
            if guild_id:
                rows = await conn.fetch("SELECT * FROM products WHERE guild_id = $1", guild_id)
            elif user_id:
                rows = await conn.fetch("SELECT * FROM products WHERE user_id = $1", user_id)
            else:
                rows = await conn.fetch("SELECT * FROM products")
            return [dict(row) for row in rows]

    async def get_product(self, product_id: str) -> Optional[dict]:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM products WHERE product_id = $1", product_id)
            return dict(row) if row else None

    async def update_product_price(self, product_id: str, price: float):
        async with self.pool.acquire() as conn:
            await conn.execute("""
                UPDATE products SET current_price = $1, last_checked = NOW() WHERE product_id = $2
            """, price, product_id)
            await conn.execute("""
                INSERT INTO price_history (product_id, price) VALUES ($1, $2)
            """, product_id, price)

    async def delete_product(self, product_id: str) -> bool:
        async with self.pool.acquire() as conn:
            result = await conn.execute("DELETE FROM products WHERE product_id = $1", product_id)
            return result.endswith("1")

    async def close(self):
        if self.pool:
            await self.pool.close()
