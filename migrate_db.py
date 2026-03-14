from database import Database
import os

db_path = "data/trendyol_tracker.sqlite"
if os.path.exists(db_path):
    os.remove(db_path)

db = Database(db_path)
print("Veritabanı başarıyla yeniden oluşturuldu.")
