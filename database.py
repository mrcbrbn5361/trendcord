import sqlite3
import os
import logging
from datetime import datetime
import threading

logger = logging.getLogger(__name__)


class Database:
    """SQLite veritabanı işlemlerini yöneten yardımcı sınıf."""

    def __init__(self, db_name="data/trendyol_tracker.sqlite"):
        self.db_name = db_name
        os.makedirs(os.path.dirname(db_name), exist_ok=True)
        abs_path = os.path.abspath(db_name)
        logger.info(f"Veritabanı dosyası yolu: {abs_path}")
        self.lock = threading.RLock()

        try:
            self.conn = sqlite3.connect(db_name, check_same_thread=False)
            self.conn.row_factory = sqlite3.Row
            self.cursor = self.conn.cursor()
            self.create_tables()
            logger.info(f"Veritabanı bağlantısı başarıyla kuruldu: {db_name}")
        except Exception as exc:
            logger.error(f"Veritabanı bağlantısı oluşturulurken hata: {exc}")
            raise

    def create_tables(self):
        """Gerekli tüm tabloları oluşturur."""
        with self.lock:
            self.cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS products (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    product_id TEXT UNIQUE,
                    name TEXT,
                    url TEXT,
                    image_url TEXT,
                    current_price REAL,
                    original_price REAL,
                    added_at TIMESTAMP,
                    last_checked TIMESTAMP,
                    guild_id TEXT,
                    user_id TEXT,
                    channel_id TEXT
                )
                """
            )

            self.cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS price_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    product_id TEXT,
                    price REAL,
                    date TIMESTAMP,
                    FOREIGN KEY(product_id) REFERENCES products(product_id)
                )
                """
            )

            self.cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    email TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL DEFAULT 'user',
                    discord_id TEXT,
                    created_at TIMESTAMP,
                    last_login TIMESTAMP
                )
                """
            )

            self.conn.commit()

    # ------------------------------------------------------------------
    # Ürün işlemleri
    # ------------------------------------------------------------------
    def add_product(self, product_data, guild_id, user_id, channel_id):
        """Ürün ekler ve ilk fiyat kaydını oluşturur."""
        try:
            with self.lock:
                now = datetime.now().isoformat()
                self.cursor.execute(
                    """
                    INSERT INTO products
                    (product_id, name, url, image_url, current_price, original_price, added_at, last_checked, guild_id, user_id, channel_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        product_data['product_id'],
                        product_data['name'],
                        product_data['url'],
                        product_data.get('image_url'),
                        product_data.get('current_price'),
                        product_data.get('original_price'),
                        now,
                        now,
                        guild_id,
                        user_id,
                        channel_id
                    ),
                )

                self.cursor.execute(
                    """
                    INSERT INTO price_history (product_id, price, date)
                    VALUES (?, ?, ?)
                    """,
                    (
                        product_data['product_id'],
                        product_data.get('current_price'),
                        now,
                    ),
                )
                self.conn.commit()
                return True
        except sqlite3.IntegrityError:
            return False
        except Exception as exc:
            logger.error(f"Ürün eklenirken hata: {exc}")
            return False

    def get_product(self, product_id):
        with self.lock:
            self.cursor.execute(
                "SELECT * FROM products WHERE product_id = ?",
                (product_id,),
            )
            row = self.cursor.fetchone()
            return dict(row) if row else None

    def get_all_products(self, guild_id=None, user_id=None):
        query = "SELECT * FROM products"
        params = []
        conditions = []

        if guild_id:
            conditions.append("guild_id = ?")
            params.append(str(guild_id))
        if user_id:
            conditions.append("user_id = ?")
            params.append(str(user_id))
        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        with self.lock:
            self.cursor.execute(query, params)
            rows = self.cursor.fetchall()
            return [dict(row) for row in rows]

    def update_product_price(self, product_id, new_price):
        try:
            with self.lock:
                now = datetime.now().isoformat()
                self.cursor.execute(
                    """
                    UPDATE products
                    SET current_price = ?, last_checked = ?
                    WHERE product_id = ?
                    """,
                    (new_price, now, product_id),
                )

                self.cursor.execute(
                    """
                    INSERT INTO price_history (product_id, price, date)
                    VALUES (?, ?, ?)
                    """,
                    (product_id, new_price, now),
                )
                self.conn.commit()
                return True
        except Exception as exc:
            logger.error(f"Ürün fiyatı güncellenirken hata: {exc}")
            with self.lock:
                self.conn.rollback()
            return False

    def get_price_history(self, product_id, limit=10, order="DESC"):
        order_keyword = "ASC" if order and order.upper() == "ASC" else "DESC"
        with self.lock:
            self.cursor.execute(
                f"""
                SELECT price, date FROM price_history
                WHERE product_id = ?
                ORDER BY date {order_keyword} LIMIT ?
                """,
                (product_id, limit),
            )
            rows = self.cursor.fetchall()
            return [{"price": row["price"], "date": row["date"]} for row in rows]

    def delete_product(self, product_id, guild_id=None, user_id=None):
        try:
            with self.lock:
                if guild_id and user_id:
                    self.cursor.execute(
                        """
                        DELETE FROM products
                        WHERE product_id = ? AND guild_id = ? AND user_id = ?
                        """,
                        (product_id, guild_id, user_id),
                    )
                elif guild_id:
                    self.cursor.execute(
                        "DELETE FROM products WHERE product_id = ? AND guild_id = ?",
                        (product_id, guild_id),
                    )
                elif user_id:
                    self.cursor.execute(
                        "DELETE FROM products WHERE product_id = ? AND user_id = ?",
                        (product_id, user_id),
                    )
                else:
                    self.cursor.execute(
                        "DELETE FROM products WHERE product_id = ?",
                        (product_id,),
                    )

                deleted_products = self.cursor.rowcount

                self.cursor.execute(
                    "DELETE FROM price_history WHERE product_id = ?",
                    (product_id,),
                )
                self.conn.commit()
                return deleted_products > 0
        except Exception as exc:
            logger.error(f"Ürün silinirken hata: {exc}")
            return False

    def check_price_changes(self):
        with self.lock:
            self.cursor.execute(
                """
                SELECT p.*,
                    (
                        SELECT price FROM price_history
                        WHERE product_id = p.product_id
                        ORDER BY date DESC LIMIT 1 OFFSET 1
                    ) as previous_price
                FROM products p
                """
            )
            rows = self.cursor.fetchall()

        changed_products = []
        for row in rows:
            product = dict(row)
            previous_price = product.get('previous_price')
            if previous_price and product['current_price'] != previous_price:
                change = product['current_price'] - previous_price
                product['price_change'] = change
                product['price_change_percentage'] = (
                    (change / previous_price) * 100 if previous_price else 0
                )
                changed_products.append(product)
        return changed_products

    def get_total_product_count(self):
        with self.lock:
            self.cursor.execute("SELECT COUNT(*) FROM products")
            return self.cursor.fetchone()[0]

    def get_distinct_guild_count(self):
        with self.lock:
            self.cursor.execute("SELECT COUNT(DISTINCT guild_id) FROM products WHERE guild_id IS NOT NULL")
            return self.cursor.fetchone()[0]

    def get_product_counts_by_guild(self):
        with self.lock:
            self.cursor.execute(
                """
                SELECT guild_id, COUNT(*) as product_count
                FROM products
                WHERE guild_id IS NOT NULL
                GROUP BY guild_id
                ORDER BY product_count DESC
                """
            )
            rows = self.cursor.fetchall()
            return [dict(row) for row in rows]

    def get_recent_price_events(self, limit=5):
        with self.lock:
            self.cursor.execute(
                """
                SELECT ph.product_id, ph.price, ph.date, p.name
                FROM price_history ph
                JOIN products p ON p.product_id = ph.product_id
                ORDER BY ph.date DESC
                LIMIT ?
                """,
                (limit,),
            )
            rows = self.cursor.fetchall()
            return [dict(row) for row in rows]

    # ------------------------------------------------------------------
    # Kullanıcı işlemleri
    # ------------------------------------------------------------------
    def create_user(self, username, email, password_hash, role="user", discord_id=None):
        try:
            with self.lock:
                now = datetime.now().isoformat()
                self.cursor.execute(
                    """
                    INSERT INTO users (username, email, password_hash, role, discord_id, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (username, email, password_hash, role, discord_id, now),
                )
                self.conn.commit()
                return True, None
        except sqlite3.IntegrityError as exc:
            logger.warning(f"Kullanıcı oluşturma başarısız: {exc}")
            message = "Kullanıcı adı veya e-posta zaten kullanılıyor."
            return False, message
        except Exception as exc:
            logger.error(f"Kullanıcı oluşturulurken hata: {exc}")
            return False, "Beklenmeyen bir hata oluştu."

    def get_user_by_username(self, username):
        with self.lock:
            self.cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
            row = self.cursor.fetchone()
            return dict(row) if row else None

    def get_user_by_discord_id(self, discord_id):
        if not discord_id:
            return None
        with self.lock:
            self.cursor.execute("SELECT * FROM users WHERE discord_id = ?", (str(discord_id),))
            row = self.cursor.fetchone()
            return dict(row) if row else None

    def get_user_by_id(self, user_id):
        with self.lock:
            self.cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
            row = self.cursor.fetchone()
            return dict(row) if row else None

    def list_users(self):
        with self.lock:
            self.cursor.execute(
                "SELECT id, username, email, role, discord_id, created_at, last_login FROM users ORDER BY created_at DESC"
            )
            rows = self.cursor.fetchall()
            return [dict(row) for row in rows]

    def update_user_password(self, user_id, password_hash):
        with self.lock:
            self.cursor.execute(
                "UPDATE users SET password_hash = ? WHERE id = ?",
                (password_hash, user_id),
            )
            self.conn.commit()

    def update_user_discord_id(self, user_id, discord_id):
        with self.lock:
            self.cursor.execute(
                "UPDATE users SET discord_id = ? WHERE id = ?",
                (discord_id, user_id),
            )
            self.conn.commit()

    def record_user_login(self, user_id):
        with self.lock:
            self.cursor.execute(
                "UPDATE users SET last_login = ? WHERE id = ?",
                (datetime.now().isoformat(), user_id),
            )
            self.conn.commit()

    # ------------------------------------------------------------------
    def close(self):
        with self.lock:
            if self.conn:
                self.conn.close()

    def test_database(self):
        test_data = {
            'product_id': 'test123',
            'name': 'Test Ürün',
            'url': 'https://www.trendyol.com/test-urun-p-123456',
            'image_url': 'https://test.com/image.jpg',
            'current_price': 99.99,
            'original_price': 129.99,
        }

        result = self.add_product(test_data, 'test_guild', 'test_user', 'test_channel')
        if not result:
            logger.error("Test verisi eklenemedi!")
            return False

        product = self.get_product('test123')
        if not product:
            logger.error("Test verisi okuma başarısız!")
            return False

        self.delete_product('test123')
        logger.info("Veritabanı testi başarıyla tamamlandı.")
        return True
