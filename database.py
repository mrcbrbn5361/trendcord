import sqlite3
import json
import os
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class Database:
    def __init__(self, db_name="data/trendyol_tracker.sqlite"):
        """Veritabanı bağlantısını başlatır ve tabloları oluşturur."""
        self.db_name = db_name
        
        try:
            # Eğer data klasörü yoksa oluştur
            os.makedirs(os.path.dirname(db_name), exist_ok=True)
            
            # Tam dosya yolunu al
            abs_path = os.path.abspath(db_name)
            logger.info(f"Veritabanı dosyası yolu: {abs_path}")
            
            # Veritabanı bağlantısı oluştur
            self.conn = sqlite3.connect(db_name)
            self.conn.row_factory = sqlite3.Row
            self.cursor = self.conn.cursor()
            self.create_tables()
            logger.info(f"Veritabanı bağlantısı başarıyla kuruldu: {db_name}")
        except Exception as e:
            logger.error(f"Veritabanı bağlantısı oluşturulurken hata: {e}")
            raise

    def create_tables(self):
        """Gerekli tabloları oluşturur."""
        # Users table for OAuth2
        self.cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            discord_id TEXT PRIMARY KEY,
            username TEXT,
            avatar TEXT,
            access_token TEXT,
            refresh_token TEXT,
            expires_at TIMESTAMP
        )
        ''')

        # Refactored products table
        self.cursor.execute('''
        CREATE TABLE IF NOT EXISTS products (
            product_id TEXT PRIMARY KEY,
            name TEXT,
            url TEXT,
            image_url TEXT,
            current_price REAL,
            original_price REAL,
            last_checked TIMESTAMP
        )
        ''')

        # Subscriptions table
        self.cursor.execute('''
        CREATE TABLE IF NOT EXISTS subscriptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            product_id TEXT,
            guild_id TEXT,
            channel_id TEXT,
            added_at TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(discord_id),
            FOREIGN KEY(product_id) REFERENCES products(product_id),
            UNIQUE(user_id, product_id, guild_id)
        )
        ''')

        self.cursor.execute('''
        CREATE TABLE IF NOT EXISTS price_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id TEXT,
            price REAL,
            date TIMESTAMP,
            FOREIGN KEY(product_id) REFERENCES products(product_id)
        )
        ''')
        
        self.conn.commit()

    def add_user(self, user_data):
        """Kullanıcı ekler veya günceller."""
        try:
            self.cursor.execute('''
            INSERT INTO users (discord_id, username, avatar, access_token, refresh_token, expires_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(discord_id) DO UPDATE SET
                username = excluded.username,
                avatar = excluded.avatar,
                access_token = excluded.access_token,
                refresh_token = excluded.refresh_token,
                expires_at = excluded.expires_at
            ''', (
                user_data['id'],
                user_data['username'],
                user_data['avatar'],
                user_data['access_token'],
                user_data['refresh_token'],
                user_data['expires_at']
            ))
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"Kullanıcı eklenirken hata: {e}")
            return False

    def get_user(self, discord_id):
        """Kullanıcı bilgilerini getirir."""
        self.cursor.execute('SELECT * FROM users WHERE discord_id = ?', (discord_id,))
        row = self.cursor.fetchone()
        return dict(row) if row else None

    def add_product(self, product_data, guild_id, user_id, channel_id):
        """Ürün ve abonelik ekler."""
        try:
            now = datetime.now().isoformat()
            
            # Ürünü ekle veya güncelle (fiyatlar değişmiş olabilir)
            self.cursor.execute('''
            INSERT INTO products (product_id, name, url, image_url, current_price, original_price, last_checked)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(product_id) DO UPDATE SET
                current_price = excluded.current_price,
                original_price = excluded.original_price,
                last_checked = excluded.last_checked
            ''', (
                product_data['product_id'],
                product_data['name'],
                product_data['url'],
                product_data['image_url'],
                product_data['current_price'],
                product_data['original_price'],
                now
            ))
            
            # Abonelik ekle
            self.cursor.execute('''
            INSERT OR IGNORE INTO subscriptions (user_id, product_id, guild_id, channel_id, added_at)
            VALUES (?, ?, ?, ?, ?)
            ''', (user_id, product_data['product_id'], guild_id, channel_id, now))

            # Fiyat geçmişi (eğer yeni fiyat ise veya ilk kayıt ise eklemek mantıklı olabilir)
            # Ama genellikle update_product_price içinde yapılıyor. Burada ilk kaydı ekleyelim.
            self.cursor.execute('''
            INSERT INTO price_history (product_id, price, date)
            VALUES (?, ?, ?)
            ''', (product_data['product_id'], product_data['current_price'], now))
            
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"Ürün/Abonelik eklenirken hata: {e}")
            self.conn.rollback()
            return False

    def get_product(self, product_id):
        """Belirli bir ürünün bilgilerini getirir."""
        self.cursor.execute('SELECT * FROM products WHERE product_id = ?', (product_id,))
        row = self.cursor.fetchone()
        return dict(row) if row else None

    def get_user_products(self, user_id):
        """Bir kullanıcının takip ettiği tüm ürünleri getirir."""
        self.cursor.execute('''
        SELECT p.*, s.guild_id, s.channel_id, s.added_at
        FROM products p
        JOIN subscriptions s ON p.product_id = s.product_id
        WHERE s.user_id = ?
        ''', (user_id,))
        return [dict(row) for row in self.cursor.fetchall()]

    def get_all_products(self):
        """Takip edilen tüm benzersiz ürünleri getirir (fiyat kontrolü için)."""
        self.cursor.execute('SELECT * FROM products')
        return [dict(row) for row in self.cursor.fetchall()]

    def get_subscriptions_for_product(self, product_id):
        """Bir ürün için tüm abonelikleri getirir (bildirim için)."""
        self.cursor.execute('SELECT * FROM subscriptions WHERE product_id = ?', (product_id,))
        return [dict(row) for row in self.cursor.fetchall()]

    def update_product_price(self, product_id, new_price):
        """Ürün fiyatını günceller ve fiyat geçmişine ekler."""
        try:
            now = datetime.now().isoformat()
            self.cursor.execute('''
            UPDATE products SET current_price = ?, last_checked = ? WHERE product_id = ?
            ''', (new_price, now, product_id))
            
            self.cursor.execute('''
            INSERT INTO price_history (product_id, price, date)
            VALUES (?, ?, ?)
            ''', (product_id, new_price, now))
            
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"Fiyat güncellenirken hata: {e}")
            self.conn.rollback()
            return False

    def delete_subscription(self, user_id, product_id, guild_id=None):
        """Kullanıcının bir ürün aboneliğini siler."""
        try:
            if guild_id:
                self.cursor.execute('''
                DELETE FROM subscriptions WHERE user_id = ? AND product_id = ? AND guild_id = ?
                ''', (user_id, product_id, guild_id))
            else:
                self.cursor.execute('''
                DELETE FROM subscriptions WHERE user_id = ? AND product_id = ?
                ''', (user_id, product_id))

            # Eğer ürüne başka abonelik kalmadıysa ürünü de silebiliriz (isteğe bağlı)
            self.cursor.execute('SELECT COUNT(*) FROM subscriptions WHERE product_id = ?', (product_id,))
            if self.cursor.fetchone()[0] == 0:
                self.cursor.execute('DELETE FROM products WHERE product_id = ?', (product_id,))
                self.cursor.execute('DELETE FROM price_history WHERE product_id = ?', (product_id,))
            
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"Abonelik silinirken hata: {e}")
            return False

    def get_price_history(self, product_id, limit=10):
        self.cursor.execute('''
        SELECT price, date FROM price_history WHERE product_id = ? ORDER BY date DESC LIMIT ?
        ''', (product_id, limit))
        return [{"price": row['price'], "date": row['date']} for row in self.cursor.fetchall()]

    def close(self):
        if self.conn:
            self.conn.close()
