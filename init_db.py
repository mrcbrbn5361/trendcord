#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Veritabanını başlatan script.
Bu dosyayı çalıştırarak veritabanı dosyasını oluşturabilirsiniz.
"""

from database import Database
import logging
import os
import dotenv

# .env dosyasını yükle
dotenv.load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

if __name__ == "__main__":
    logger.info("Veritabanı başlatılıyor...")
    
    # Veritabanı yollarını al
    DATABASE_PATH = os.getenv('DATABASE_PATH', 'data/trendyol_tracker.sqlite')
    BACKUP_DATABASE_PATH = os.getenv('BACKUP_DATABASE_PATH', 'data/database.sqlite')
    
    # Ana veritabanını oluştur
    db = Database(db_name=DATABASE_PATH)
    # kaldırıldı
    # kaldırıldı
    logger.info(f"Ana veritabanı başarıyla oluşturuldu: {DATABASE_PATH}")
    
    # Yedek veritabanını oluştur
    db_backup = Database(db_name=BACKUP_DATABASE_PATH)
    # kaldırıldı
    # kaldırıldı 
    logger.info(f"Yedek veritabanı başarıyla oluşturuldu: {BACKUP_DATABASE_PATH}")
    
    logger.info("Şimdi 'python main.py' ile botu başlatabilirsiniz.") 