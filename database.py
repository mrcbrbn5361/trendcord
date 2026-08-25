import sqlite3
import json
import os
from datetime import datetime
import re

class Database:
    def __init__(self, db_name=None):
        if db_name is None:
            db_name = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "trendyol_tracker.sqlite")
        os.makedirs(os.path.dirname(db_name), exist_ok=True)
        
        self.conn = sqlite3.connect(db_name, check_same_thread=False)
        # WAL modu: Eşzamanlı okuma/yazma (Web + Bot) için kritik
        self.conn.execute("PRAGMA journal_mode=WAL;")
        self.cursor = self.conn.cursor()
        self._create_tables()

    def _create_tables(self):
        # Ürünler tablosu
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS products (
            product_id TEXT PRIMARY KEY, 
            name TEXT, 
            url TEXT, 
            image_url TEXT,
            current_price REAL, 
            original_price REAL, 
            basket_price REAL,
            discount_pct REAL,
            campaign_name TEXT,
            campaign_type TEXT,
            campaign_end TEXT,
            last_checked TIMESTAMP,
            guild_id TEXT, 
            user_id TEXT, 
            channel_id TEXT,
            username TEXT DEFAULT '',
            avatar_url TEXT DEFAULT '')''')
        
        # Fiyat geçmişi tablosu (İstatistikler için)
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS price_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id TEXT,
            price REAL,
            basket_price REAL,
            timestamp DATETIME,
            FOREIGN KEY(product_id) REFERENCES products(product_id))''')
        
        # Migration: yeni sütunlar
        migrations = [
            ("price_history", "timestamp", "DATETIME"),
            ("products", "username", "TEXT DEFAULT ''"),
            ("products", "avatar_url", "TEXT DEFAULT ''"),
            ("products", "basket_price", "REAL"),
            ("products", "discount_pct", "REAL"),
            ("products", "campaign_name", "TEXT"),
            ("products", "campaign_type", "TEXT"),
            ("products", "campaign_end", "TEXT"),
            ("price_history", "basket_price", "REAL"),
        ]
        for table, col, typ in migrations:
            try:
                self.cursor.execute(f"SELECT {col} FROM {table} LIMIT 1")
            except:
                try:
                    self.cursor.execute(f"ALTER TABLE {table} ADD COLUMN {col} {typ}")
                except:
                    pass

        # Guild kurulum tablolari (provisioner)
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS guild_settings (
            guild_id TEXT PRIMARY KEY,
            auto_setup INTEGER DEFAULT 1,
            modules TEXT DEFAULT '{}',
            left_at TEXT
        )''')
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS guild_setup_state (
            guild_id TEXT PRIMARY KEY,
            mode TEXT DEFAULT 'CLIENT',
            status TEXT DEFAULT 'PENDING',
            analyzed_roles TEXT,
            last_run_at TEXT,
            last_error TEXT
        )''')
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS managed_entities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id TEXT NOT NULL,
            entity_type TEXT NOT NULL,
            discord_id TEXT NOT NULL,
            key TEXT NOT NULL,
            spec TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            deleted_at TEXT,
            UNIQUE (guild_id, key)
        )''')
        self.conn.commit()

        # Kullanıcılar tablosu
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY,
            username TEXT DEFAULT '',
            avatar_url TEXT DEFAULT '',
            last_login TIMESTAMP
        )''')

        # Performans index'leri (sık kullanılan sorgular için)
        try:
            self.cursor.execute('CREATE INDEX IF NOT EXISTS idx_products_guild ON products(guild_id)')
            self.cursor.execute('CREATE INDEX IF NOT EXISTS idx_products_user ON products(user_id)')
            self.cursor.execute('CREATE INDEX IF NOT EXISTS idx_price_history_product ON price_history(product_id)')
        except: pass
        
        # Alerts tablosu (lazy creation ile tutarlı olması için burada da oluştur)
        self._create_alerts_table()
        self._create_prefs_table()
        
        # Alert/Preference index'leri
        try:
            self.cursor.execute('CREATE INDEX IF NOT EXISTS idx_alerts_user ON alerts(user_id)')
            self.cursor.execute('CREATE INDEX IF NOT EXISTS idx_alerts_product ON alerts(product_id)')
            self.cursor.execute('CREATE INDEX IF NOT EXISTS idx_alerts_active ON alerts(triggered, user_id)')
        except: pass

        self.conn.commit()

    def _safe_float(self, val):
        """Fiyat stringini güvenli bir şekilde sayıya çevirir."""
        if not val: return 0.0
        if isinstance(val, (int, float)): return float(val)
        if isinstance(val, dict): val = val.get('value', 0.0)
        
        val_str = str(val).upper().replace('TL', '').replace('₺', '').strip()
        val_str = re.sub(r'[^\d.,]', '', val_str)
        
        if not val_str: return 0.0
        if '.' in val_str and ',' in val_str:
            val_str = val_str.replace('.', '').replace(',', '.')
        elif ',' in val_str:
            val_str = val_str.replace(',', '.')
            
        try:
            return float(val_str)
        except ValueError:
            return 0.0

    def add_product(self, data, gid, uid, cid, username='', avatar_url=''):
        try:
            now = datetime.now().isoformat()
            price = self._safe_float(data.get('current_price'))
            original_price = self._safe_float(data.get('original_price')) or price
            basket_price = self._safe_float(data.get('basket_price')) or price
            discount_pct = self._safe_float(data.get('discount_pct')) or 0
            campaign_name = str(data.get('campaign_name', '') or '')
            campaign_type = str(data.get('campaign_type', '') or '')
            campaign_end = str(data.get('campaign_end', '') or '')
            img = data.get('image_url', '')
            if not isinstance(img, str) or img.startswith('{'): img = "" 

            self.cursor.execute('''INSERT OR REPLACE INTO products 
                (product_id, name, url, image_url, current_price, original_price, basket_price,
                 discount_pct, campaign_name, campaign_type, campaign_end,
                 last_checked, guild_id, user_id, channel_id, username, avatar_url)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''', 
                (str(data['product_id']), str(data['name']), str(data['url']), str(img), 
                 price, original_price, basket_price,
                 discount_pct, campaign_name, campaign_type, campaign_end,
                 now, str(gid), str(uid), str(cid), str(username), str(avatar_url)))
            self.conn.commit()
            return True
        except Exception as e:
            print(f"[DB ERROR] add_product: {e}")
            return False

    def get_all_products(self, guild_id=None, user_id=None):
        try:
            q = "SELECT * FROM products"
            params = []
            if guild_id: 
                q += " WHERE guild_id = ?"
                params.append(str(guild_id))
            elif user_id: 
                q += " WHERE user_id = ?"
                params.append(str(user_id))
            
            self.cursor.execute(q, params)
            colnames = [d[0] for d in self.cursor.description]
            return [dict(zip(colnames, r)) for r in self.cursor.fetchall()]
        except Exception as e:
            print(f"[DB ERROR] get_all_products: {e}")
            return []

    def update_product_price(self, pid, price, original_price=None, basket_price=None, discount_pct=None, campaign_name=None, campaign_type=None, campaign_end=None):
        try:
            now = datetime.now().isoformat()
            updates = ["current_price = ?", "last_checked = ?"]
            params = [price, now]
            
            if original_price and original_price > 0:
                updates.append("original_price = ?")
                params.append(original_price)
            if basket_price and basket_price > 0:
                updates.append("basket_price = ?")
                params.append(basket_price)
            if discount_pct is not None:
                updates.append("discount_pct = ?")
                params.append(discount_pct)
            if campaign_name is not None:
                updates.append("campaign_name = ?")
                params.append(campaign_name)
            if campaign_type is not None:
                updates.append("campaign_type = ?")
                params.append(campaign_type)
            if campaign_end is not None:
                updates.append("campaign_end = ?")
                params.append(campaign_end)
            
            params.append(str(pid))
            self.cursor.execute(f'UPDATE products SET {", ".join(updates)} WHERE product_id = ?', params)
            self.cursor.execute('INSERT INTO price_history (product_id, price, basket_price, timestamp) VALUES (?, ?, ?, ?)', 
                (str(pid), price, basket_price, now))
            self.conn.commit()
            return True
        except Exception as e:
            print(f"[DB ERROR] update_price: {e}")
            return False

    def delete_product(self, pid):
        self.cursor.execute('DELETE FROM products WHERE product_id = ?', (str(pid),))
        self.conn.commit()
        return self.cursor.rowcount > 0

    def add_user(self, user_id, username, avatar_url=''):
        """Kullanıcıyı kaydet veya güncelle."""
        try:
            now = datetime.now().isoformat()
            self.cursor.execute('''INSERT OR REPLACE INTO users 
                (user_id, username, avatar_url, last_login)
                VALUES (?, ?, ?, ?)''', 
                (str(user_id), str(username), str(avatar_url), now))
            self.conn.commit()
            return True
        except Exception as e:
            print(f"[DB ERROR] add_user: {e}")
            return False

    def get_all_users(self):
        """Tüm kayıtlı kullanıcıları döndür."""
        try:
            self.cursor.execute("SELECT * FROM users ORDER BY last_login DESC")
            colnames = [d[0] for d in self.cursor.description]
            return [dict(zip(colnames, r)) for r in self.cursor.fetchall()]
        except Exception as e:
            print(f"[DB ERROR] get_all_users: {e}")
            return []

    def get_user(self, user_id):
        """Belirli bir kullanıcıyı döndür."""
        try:
            self.cursor.execute("SELECT * FROM users WHERE user_id = ?", (str(user_id),))
            colnames = [d[0] for d in self.cursor.description]
            row = self.cursor.fetchone()
            return dict(zip(colnames, row)) if row else None
        except Exception as e:
            print(f"[DB ERROR] get_user: {e}")
            return None

    def get_stats(self):
        """Web tarafı için gerçek sayıları hesaplar."""
        try:
            self.cursor.execute("SELECT COUNT(*) FROM products")
            p_count = self.cursor.fetchone()[0]
            self.cursor.execute("SELECT COUNT(*) FROM price_history")
            h_count = self.cursor.fetchone()[0]
            return {"product_count": p_count, "price_checks": h_count}
        except:
            return {"product_count": 0, "price_checks": 0}

    def get_system_stats(self):
        """Admin panel için sistem istatistikleri."""
        try:
            stats = {"total_users": 0, "total_products": 0, "total_checks": 0, "db_size": 0}
            self.cursor.execute("SELECT COUNT(*) FROM users")
            stats["total_users"] = self.cursor.fetchone()[0]
            self.cursor.execute("SELECT COUNT(*) FROM products")
            stats["total_products"] = self.cursor.fetchone()[0]
            self.cursor.execute("SELECT COUNT(*) FROM price_history")
            stats["total_checks"] = self.cursor.fetchone()[0]
            # DB boyutu
            db_path = self.conn.execute("PRAGMA database_list").fetchone()[2]
            if db_path and os.path.exists(db_path):
                stats["db_size"] = os.path.getsize(db_path)
            return stats
        except Exception as e:
            print(f"[DB ERROR] get_system_stats: {e}")
            return {"total_users": 0, "total_products": 0, "total_checks": 0, "db_size": 0}

    def get_all_products_admin(self):
        """Admin için tüm ürünleri kullanıcı ve sunucu bilgileriyle döndür."""
        try:
            self.cursor.execute("""
                SELECT p.*, u.username as user_name, u.last_login as user_last_login
                FROM products p
                LEFT JOIN users u ON p.user_id = u.user_id
                ORDER BY p.last_checked DESC
            """)
            colnames = [d[0] for d in self.cursor.description]
            return [dict(zip(colnames, r)) for r in self.cursor.fetchall()]
        except Exception as e:
            print(f"[DB ERROR] get_all_products_admin: {e}")
            return []

    # ---------- Guild kurulum (provisioner) ----------
    def ensure_guild_settings(self, guild_id):
        try:
            self.cursor.execute("INSERT OR IGNORE INTO guild_settings (guild_id) VALUES (?)", (str(guild_id),))
            self.conn.commit()
        except Exception as e:
            print(f"[DB ERROR] ensure_guild_settings: {e}")

    def get_guild_settings(self, guild_id):
        self.ensure_guild_settings(guild_id)
        try:
            self.cursor.execute("SELECT guild_id, auto_setup, modules, left_at FROM guild_settings WHERE guild_id = ?", (str(guild_id),))
            row = self.cursor.fetchone()
            if not row:
                return {"guild_id": str(guild_id), "auto_setup": 1, "modules": "{}", "left_at": None}
            return {"guild_id": row[0], "auto_setup": row[1], "modules": row[2] or "{}", "left_at": row[3]}
        except Exception as e:
            print(f"[DB ERROR] get_guild_settings: {e}")
            return {"guild_id": str(guild_id), "auto_setup": 0, "modules": "{}", "left_at": None}

    def set_guild_settings(self, guild_id, auto_setup=None, modules=None, left_at=None):
        self.ensure_guild_settings(guild_id)
        try:
            if auto_setup is not None:
                self.cursor.execute("UPDATE guild_settings SET auto_setup = ? WHERE guild_id = ?", (1 if auto_setup else 0, str(guild_id)))
            if modules is not None:
                self.cursor.execute("UPDATE guild_settings SET modules = ? WHERE guild_id = ?", (json.dumps(modules), str(guild_id)))
            if left_at is not None:
                self.cursor.execute("UPDATE guild_settings SET left_at = ? WHERE guild_id = ?", (left_at, str(guild_id)))
            self.conn.commit()
        except Exception as e:
            print(f"[DB ERROR] set_guild_settings: {e}")

    def upsert_setup_state(self, guild_id, mode='CLIENT', status='PENDING', analyzed_roles=None, last_error=None):
        from datetime import datetime
        try:
            self.cursor.execute('''INSERT INTO guild_setup_state (guild_id, mode, status, analyzed_roles, last_run_at, last_error)
                VALUES (?,?,?,?,?,?)
                ON CONFLICT(guild_id) DO UPDATE SET mode=excluded.mode, status=excluded.status,
                analyzed_roles=excluded.analyzed_roles, last_run_at=excluded.last_run_at, last_error=excluded.last_error''',
                (str(guild_id), mode, status, json.dumps(analyzed_roles, ensure_ascii=False) if analyzed_roles else None,
                 datetime.utcnow().isoformat(), last_error))
            self.conn.commit()
        except Exception as e:
            print(f"[DB ERROR] upsert_setup_state: {e}")

    def get_setup_state(self, guild_id):
        try:
            self.cursor.execute("SELECT guild_id, mode, status, analyzed_roles, last_run_at, last_error FROM guild_setup_state WHERE guild_id = ?", (str(guild_id),))
            row = self.cursor.fetchone()
            if not row:
                return None
            return {"guild_id": row[0], "mode": row[1], "status": row[2], "analyzed_roles": row[3],
                    "last_run_at": row[4], "last_error": row[5]}
        except Exception as e:
            print(f"[DB ERROR] get_setup_state: {e}")
            return None

    def mark_entity(self, guild_id, key, entity_type, discord_id, spec=None):
        from datetime import datetime
        try:
            self.cursor.execute('''INSERT INTO managed_entities (guild_id, entity_type, discord_id, key, spec, created_at)
                VALUES (?,?,?,?,?,?)
                ON CONFLICT(guild_id, key) DO UPDATE SET discord_id=excluded.discord_id,
                entity_type=excluded.entity_type, spec=excluded.spec, deleted_at=NULL''',
                (str(guild_id), entity_type, str(discord_id), key, json.dumps(spec, ensure_ascii=False) if spec else None,
                 datetime.utcnow().isoformat()))
            self.conn.commit()
        except Exception as e:
            print(f"[DB ERROR] mark_entity: {e}")

    def get_entities(self, guild_id, active_only=True):
        try:
            q = "SELECT key, entity_type, discord_id, spec, deleted_at FROM managed_entities WHERE guild_id = ?"
            if active_only:
                q += " AND deleted_at IS NULL"
            self.cursor.execute(q, (str(guild_id),))
            return [{"key": r[0], "entity_type": r[1], "discord_id": r[2], "spec": r[3], "deleted_at": r[4]}
                    for r in self.cursor.fetchall()]
        except Exception as e:
            print(f"[DB ERROR] get_entities: {e}")
            return []

    def get_entity(self, guild_id, key):
        try:
            self.cursor.execute("SELECT key, entity_type, discord_id, spec, deleted_at FROM managed_entities WHERE guild_id = ? AND key = ?", (str(guild_id), key))
            row = self.cursor.fetchone()
            return {"key": row[0], "entity_type": row[1], "discord_id": row[2], "spec": row[3], "deleted_at": row[4]} if row else None
        except Exception as e:
            print(f"[DB ERROR] get_entity: {e}")
            return None

    def mark_entity_deleted(self, guild_id, key):
        from datetime import datetime
        try:
            self.cursor.execute("UPDATE managed_entities SET deleted_at = ? WHERE guild_id = ? AND key = ?",
                                (datetime.utcnow().isoformat(), str(guild_id), key))
            self.conn.commit()
        except Exception as e:
            print(f"[DB ERROR] mark_entity_deleted: {e}")

    def get_entity_by_discord_id(self, discord_id):
        try:
            self.cursor.execute("SELECT key, guild_id, entity_type FROM managed_entities WHERE discord_id = ? AND deleted_at IS NULL", (str(discord_id),))
            row = self.cursor.fetchone()
            return {"key": row[0], "guild_id": row[1], "entity_type": row[2]} if row else None
        except Exception as e:
            print(f"[DB ERROR] get_entity_by_discord_id: {e}")
            return None

    def get_product(self, product_id):
        """Tek bir urunu dondur."""
        try:
            self.cursor.execute(
                "SELECT * FROM products WHERE product_id = ?",
                (str(product_id),)
            )
            colnames = [d[0] for d in self.cursor.description]
            row = self.cursor.fetchone()
            return dict(zip(colnames, row)) if row else None
        except Exception as e:
            print(f"[DB ERROR] get_product: {e}")
            return None

    def get_product_price_history(self, product_id, limit=20):
        """Bir ürünün fiyat geçmişini döndür."""
        try:
            self.cursor.execute(
                "SELECT price, timestamp FROM price_history WHERE product_id = ? ORDER BY timestamp DESC LIMIT ?",
                (str(product_id), limit)
            )
            colnames = [d[0] for d in self.cursor.description]
            return [dict(zip(colnames, r)) for r in self.cursor.fetchall()]
        except Exception as e:
            print(f"[DB ERROR] get_product_price_history: {e}")
            return []

    def get_recent_activity(self, limit=20):
        """Son aktiviteleri döndür (ürün ekleme/fiyat değişimi)."""
        try:
            self.cursor.execute("""
                SELECT p.product_id, p.name, p.url, p.current_price, p.original_price,
                       p.guild_id, p.user_id, p.username, p.last_checked,
                       ph.price as old_price, ph.timestamp as change_time
                FROM price_history ph
                JOIN products p ON ph.product_id = p.product_id
                ORDER BY ph.timestamp DESC LIMIT ?
            """, (limit,))
            colnames = [d[0] for d in self.cursor.description]
            return [dict(zip(colnames, r)) for r in self.cursor.fetchall()]
        except Exception as e:
            print(f"[DB ERROR] get_recent_activity: {e}")
            return []

    def get_all_guilds_from_db(self):
        """DB'de kaydı olan tüm sunucuları ürün sayılarıyla döndür."""
        try:
            self.cursor.execute("""
                SELECT guild_id, COUNT(*) as product_count, 
                       COUNT(DISTINCT user_id) as user_count,
                       MAX(last_checked) as last_activity
                FROM products 
                WHERE guild_id IS NOT NULL AND guild_id != ''
                GROUP BY guild_id
                ORDER BY product_count DESC
            """)
            colnames = [d[0] for d in self.cursor.description]
            return [dict(zip(colnames, r)) for r in self.cursor.fetchall()]
        except Exception as e:
            print(f"[DB ERROR] get_all_guilds_from_db: {e}")
            return []

    def get_guild_products_detail(self, guild_id):
        """Bir sunucudaki tüm ürünleri kullanıcı detaylarıyla döndür."""
        try:
            self.cursor.execute("""
                SELECT p.*, u.username as user_name, u.last_login as user_last_login
                FROM products p
                LEFT JOIN users u ON p.user_id = u.user_id
                WHERE p.guild_id = ?
                ORDER BY p.last_checked DESC
            """, (str(guild_id),))
            colnames = [d[0] for d in self.cursor.description]
            return [dict(zip(colnames, r)) for r in self.cursor.fetchall()]
        except Exception as e:
            print(f"[DB ERROR] get_guild_products_detail: {e}")
            return []

    # ===== FİYAT ALARMLARI =====
    def _create_alerts_table(self):
        try:
            self.cursor.execute('''CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id TEXT,
                user_id TEXT,
                guild_id TEXT,
                channel_id TEXT,
                target_price REAL,
                direction TEXT DEFAULT 'below',
                triggered INTEGER DEFAULT 0,
                created_at DATETIME,
                FOREIGN KEY(product_id) REFERENCES products(product_id))''')
            self.conn.commit()
        except Exception as e:
            print(f"[DB ERROR] _create_alerts_table: {e}")

    def add_alert(self, product_id, user_id, guild_id, channel_id, target_price, direction='below'):
        try:
            self._create_alerts_table()
            now = datetime.now().isoformat()
            self.cursor.execute('''INSERT INTO alerts 
                (product_id, user_id, guild_id, channel_id, target_price, direction, triggered, created_at)
                VALUES (?,?,?,?,?,?,0,?)''',
                (str(product_id), str(user_id), str(guild_id), str(channel_id),
                 float(target_price), str(direction), now))
            self.conn.commit()
            return self.cursor.lastrowid
        except Exception as e:
            print(f"[DB ERROR] add_alert: {e}")
            return None

    def get_user_alerts(self, user_id):
        try:
            self._create_alerts_table()
            self.cursor.execute(
                "SELECT a.*, p.name as product_name, p.current_price FROM alerts a LEFT JOIN products p ON a.product_id = p.product_id WHERE a.user_id = ? AND a.triggered = 0 ORDER BY a.created_at DESC",
                (str(user_id),))
            colnames = [d[0] for d in self.cursor.description]
            return [dict(zip(colnames, r)) for r in self.cursor.fetchall()]
        except Exception as e:
            print(f"[DB ERROR] get_user_alerts: {e}")
            return []

    def delete_alert(self, alert_id, user_id):
        try:
            self._create_alerts_table()
            self.cursor.execute("DELETE FROM alerts WHERE id = ? AND user_id = ?", (int(alert_id), str(user_id)))
            self.conn.commit()
            return self.cursor.rowcount > 0
        except Exception as e:
            print(f"[DB ERROR] delete_alert: {e}")
            return False

    def get_active_alerts(self):
        try:
            self._create_alerts_table()
            self.cursor.execute(
                "SELECT a.*, p.name as product_name, p.current_price, p.guild_id as prod_guild_id FROM alerts a LEFT JOIN products p ON a.product_id = p.product_id WHERE a.triggered = 0")
            colnames = [d[0] for d in self.cursor.description]
            return [dict(zip(colnames, r)) for r in self.cursor.fetchall()]
        except Exception as e:
            print(f"[DB ERROR] get_active_alerts: {e}")
            return []

    def trigger_alert(self, alert_id):
        try:
            self._create_alerts_table()
            self.cursor.execute("UPDATE alerts SET triggered = 1 WHERE id = ?", (int(alert_id),))
            self.conn.commit()
            return True
        except Exception as e:
            print(f"[DB ERROR] trigger_alert: {e}")
            return False

    # ===== BİLDİRİM TERCİHLERİ =====
    def _create_prefs_table(self):
        try:
            self.cursor.execute('''CREATE TABLE IF NOT EXISTS user_preferences (
                user_id TEXT,
                guild_id TEXT,
                notify_channel_id TEXT DEFAULT '',
                notify_on_drop INTEGER DEFAULT 1,
                notify_on_rise INTEGER DEFAULT 1,
                notify_threshold REAL DEFAULT 5.0,
                PRIMARY KEY(user_id, guild_id))''')
            self.conn.commit()
        except Exception as e:
            print(f"[DB ERROR] _create_prefs_table: {e}")

    def get_user_preferences(self, user_id, guild_id):
        try:
            self._create_prefs_table()
            self.cursor.execute(
                "SELECT * FROM user_preferences WHERE user_id = ? AND guild_id = ?",
                (str(user_id), str(guild_id)))
            colnames = [d[0] for d in self.cursor.description]
            row = self.cursor.fetchone()
            return dict(zip(colnames, row)) if row else {
                'user_id': user_id, 'guild_id': guild_id,
                'notify_channel_id': '', 'notify_on_drop': 1,
                'notify_on_rise': 1, 'notify_threshold': 5.0
            }
        except Exception as e:
            print(f"[DB ERROR] get_user_preferences: {e}")
            return None

    def set_user_preferences(self, user_id, guild_id, channel_id=None, on_drop=None, on_rise=None, threshold=None):
        try:
            self._create_prefs_table()
            current = self.get_user_preferences(user_id, guild_id)
            if not current:
                self.cursor.execute(
                    "INSERT INTO user_preferences (user_id, guild_id, notify_channel_id, notify_on_drop, notify_on_rise, notify_threshold) VALUES (?,?,?,?,?,?)",
                    (str(user_id), str(guild_id),
                     str(channel_id) if channel_id is not None else '',
                     int(on_drop) if on_drop is not None else 1,
                     int(on_rise) if on_rise is not None else 1,
                     float(threshold) if threshold is not None else 5.0))
            else:
                updates = []
                params = []
                if channel_id is not None:
                    updates.append("notify_channel_id = ?")
                    params.append(str(channel_id))
                if on_drop is not None:
                    updates.append("notify_on_drop = ?")
                    params.append(int(on_drop))
                if on_rise is not None:
                    updates.append("notify_on_rise = ?")
                    params.append(int(on_rise))
                if threshold is not None:
                    updates.append("notify_threshold = ?")
                    params.append(float(threshold))
                if updates:
                    params.extend([str(user_id), str(guild_id)])
                    self.cursor.execute(
                        f"UPDATE user_preferences SET {', '.join(updates)} WHERE user_id = ? AND guild_id = ?",
                        params)
            self.conn.commit()
            return True
        except Exception as e:
            print(f"[DB ERROR] set_user_preferences: {e}")
            return False

    # ===== SUNUCU İSTATİSTİKLERİ =====
    def get_guild_stats(self, guild_id):
        try:
            stats = {"total_products": 0, "unique_users": 0, "total_savings": 0,
                     "top_products": [], "recent_products": [], "price_drops": 0}
            self.cursor.execute(
                "SELECT COUNT(*) FROM products WHERE guild_id = ?", (str(guild_id),))
            stats["total_products"] = self.cursor.fetchone()[0]

            self.cursor.execute(
                "SELECT COUNT(DISTINCT user_id) FROM products WHERE guild_id = ?", (str(guild_id),))
            stats["unique_users"] = self.cursor.fetchone()[0]

            self.cursor.execute(
                """SELECT SUM(original_price - current_price) FROM products 
                   WHERE guild_id = ? AND original_price > current_price AND original_price > 0""",
                (str(guild_id),))
            row = self.cursor.fetchone()
            stats["total_savings"] = row[0] if row and row[0] else 0

            self.cursor.execute(
                """SELECT name, current_price, original_price, image_url, product_id, user_id, username
                   FROM products WHERE guild_id = ? ORDER BY current_price DESC LIMIT 5""",
                (str(guild_id),))
            colnames = [d[0] for d in self.cursor.description]
            stats["top_products"] = [dict(zip(colnames, r)) for r in self.cursor.fetchall()]

            self.cursor.execute(
                """SELECT name, current_price, original_price, image_url, product_id, last_checked
                   FROM products WHERE guild_id = ? ORDER BY last_checked DESC LIMIT 5""",
                (str(guild_id),))
            colnames = [d[0] for d in self.cursor.description]
            stats["recent_products"] = [dict(zip(colnames, r)) for r in self.cursor.fetchall()]

            self.cursor.execute(
                "SELECT COUNT(*) FROM products WHERE guild_id = ? AND current_price < original_price AND original_price > 0",
                (str(guild_id),))
            stats["price_drops"] = self.cursor.fetchone()[0]

            return stats
        except Exception as e:
            print(f"[DB ERROR] get_guild_stats: {e}")
            return {}

    def get_guild_compare(self, guild_id):
        try:
            self.cursor.execute(
                """SELECT product_id, name, current_price, original_price, image_url, username, user_id,
                   CASE WHEN original_price > 0 THEN ROUND((original_price - current_price) * 100.0 / original_price, 1) ELSE 0 END as discount_pct
                   FROM products WHERE guild_id = ? ORDER BY discount_pct DESC""",
                (str(guild_id),))
            colnames = [d[0] for d in self.cursor.description]
            return [dict(zip(colnames, r)) for r in self.cursor.fetchall()]
        except Exception as e:
            print(f"[DB ERROR] get_guild_compare: {e}")
            return []

    def close(self):
        self.conn.close()
