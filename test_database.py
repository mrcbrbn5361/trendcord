#!/usr/bin/env python3
"""database.py için birim testleri."""
import os
import sys
import tempfile
import pytest

# Proje dizinini path'e ekle
sys.path.insert(0, os.path.dirname(__file__))

from database import Database


@pytest.fixture
def db():
    """Geçici in-memory veritabanı oluştur."""
    # Database sınıfı :memory: için special处理 gerekir
    import sqlite3
    database = Database.__new__(Database)
    database.conn = sqlite3.connect(":memory:", check_same_thread=False)
    database.conn.execute("PRAGMA journal_mode=WAL;")
    database.cursor = database.conn.cursor()
    database._create_tables()
    yield database
    database.conn.close()


class TestSafeFloat:
    """_safe_float fonksiyonu testleri."""

    def test_none_returns_zero(self, db):
        assert db._safe_float(None) == 0.0

    def test_int_returns_float(self, db):
        assert db._safe_float(100) == 100.0

    def test_float_returns_float(self, db):
        assert db._safe_float(99.9) == 99.9

    def test_string_tl(self, db):
        assert db._safe_float("299.99 TL") == 299.99

    def test_string_lira_sign(self, db):
        assert db._safe_float("₺1.299") == 1.299  # ₺1.299 → 1.299

    def test_string_comma_separator(self, db):
        assert db._safe_float("1.299,99") == 1299.99

    def test_string_dot_only(self, db):
        assert db._safe_float("299.99") == 299.99

    def test_dict_with_value(self, db):
        assert db._safe_float({"value": 150.0}) == 150.0

    def test_empty_string(self, db):
        assert db._safe_float("") == 0.0


class TestProducts:
    """Products tablosu testleri."""

    def test_add_product(self, db):
        data = {
            'product_id': '12345',
            'name': 'Test Ürün',
            'url': 'https://trendyol.com/test',
            'image_url': 'https://img.jpg',
            'current_price': 100.0,
            'original_price': 150.0,
            'basket_price': 90.0,
            'discount_pct': 10.0,
            'campaign_name': 'Kampanya',
            'campaign_type': 'indirim',
            'campaign_end': '2026-12-31',
        }
        db.add_product(data, 'guild1', 'user1', 'channel1', 'testuser', 'https://avatar.jpg')
        
        products = db.get_all_products(guild_id='guild1')
        assert len(products) == 1
        assert products[0]['product_id'] == '12345'
        assert products[0]['name'] == 'Test Ürün'
        assert products[0]['current_price'] == 100.0
        assert products[0]['basket_price'] == 90.0
        assert products[0]['campaign_name'] == 'Kampanya'

    def test_update_product_price(self, db):
        data = {
            'product_id': '12345',
            'name': 'Test Ürün',
            'url': 'https://trendyol.com/test',
            'image_url': '',
            'current_price': 100.0,
        }
        db.add_product(data, 'guild1', 'user1', 'channel1')
        
        db.update_product_price('12345', 85.0, basket_price=75.0, discount_pct=15.0)
        
        products = db.get_all_products(guild_id='guild1')
        assert products[0]['current_price'] == 85.0
        assert products[0]['basket_price'] == 75.0
        assert products[0]['discount_pct'] == 15.0

    def test_delete_product(self, db):
        data = {
            'product_id': '12345',
            'name': 'Test Ürün',
            'url': 'https://trendyol.com/test',
            'image_url': '',
            'current_price': 100.0,
        }
        db.add_product(data, 'guild1', 'user1', 'channel1')
        
        result = db.delete_product('12345')
        assert result is True
        
        products = db.get_all_products(guild_id='guild1')
        assert len(products) == 0

    def test_get_all_products_by_guild(self, db):
        for i in range(3):
            data = {
                'product_id': str(i),
                'name': f'Ürün {i}',
                'url': f'https://trendyol.com/{i}',
                'image_url': '',
                'current_price': 100.0 + i,
            }
            db.add_product(data, 'guild1', 'user1', 'channel1')
        
        # Farklı guild'a ürün ekle
        data = {
            'product_id': '99',
            'name': 'Farklı Guild',
            'url': 'https://trendyol.com/99',
            'image_url': '',
            'current_price': 200.0,
        }
        db.add_product(data, 'guild2', 'user1', 'channel1')
        
        guild1_products = db.get_all_products(guild_id='guild1')
        guild2_products = db.get_all_products(guild_id='guild2')
        
        assert len(guild1_products) == 3
        assert len(guild2_products) == 1


class TestUsers:
    """Users tablosu testleri."""

    def test_add_user(self, db):
        db.add_user('user1', 'TestUser', 'https://avatar.jpg')
        
        user = db.get_user('user1')
        assert user is not None
        assert user['username'] == 'TestUser'

    def test_get_all_users(self, db):
        db.add_user('user1', 'User1', '')
        db.add_user('user2', 'User2', '')
        
        users = db.get_all_users()
        assert len(users) == 2


class TestAlerts:
    """Alerts tablosu testleri."""

    def test_add_alert(self, db):
        # Önce ürün ekle
        data = {
            'product_id': '12345',
            'name': 'Test Ürün',
            'url': 'https://trendyol.com/test',
            'image_url': '',
            'current_price': 100.0,
        }
        db.add_product(data, 'guild1', 'user1', 'channel1')
        
        alert_id = db.add_alert('12345', 'user1', 'guild1', 'channel1', 80.0, 'below')
        assert alert_id is not None

    def test_get_user_alerts(self, db):
        data = {
            'product_id': '12345',
            'name': 'Test Ürün',
            'url': 'https://trendyol.com/test',
            'image_url': '',
            'current_price': 100.0,
        }
        db.add_product(data, 'guild1', 'user1', 'channel1')
        
        db.add_alert('12345', 'user1', 'guild1', 'channel1', 80.0, 'below')
        db.add_alert('12345', 'user1', 'guild1', 'channel1', 90.0, 'above')
        
        alerts = db.get_user_alerts('user1')
        assert len(alerts) == 2

    def test_delete_alert(self, db):
        data = {
            'product_id': '12345',
            'name': 'Test Ürün',
            'url': 'https://trendyol.com/test',
            'image_url': '',
            'current_price': 100.0,
        }
        db.add_product(data, 'guild1', 'user1', 'channel1')
        
        alert_id = db.add_alert('12345', 'user1', 'guild1', 'channel1', 80.0, 'below')
        result = db.delete_alert(alert_id, 'user1')
        assert result is True


class TestStats:
    """İstatistik metodları testleri."""

    def test_get_stats(self, db):
        # Boş veritabanı
        stats = db.get_stats()
        assert 'product_count' in stats
        assert stats['product_count'] == 0

    def test_get_system_stats(self, db):
        stats = db.get_system_stats()
        assert 'total_products' in stats
        assert 'total_users' in stats


class TestIndexes:
    """Index'lerin doğru oluşturulduğunu doğrula."""

    def test_indexes_exist(self, db):
        db.cursor.execute("SELECT name FROM sqlite_master WHERE type='index'")
        indexes = [row[0] for row in db.cursor.fetchall()]
        
        assert 'idx_products_guild' in indexes
        assert 'idx_products_user' in indexes
        assert 'idx_price_history_product' in indexes
        assert 'idx_alerts_user' in indexes


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
