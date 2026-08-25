#!/data/data/com.termux/files/usr/bin/bash

# ============================================
# Trendcord - Basit Çalıştırıcı
# ============================================

TRENDCORD_DIR="/data/data/com.termux/files/home/trendcord"

cd "$TRENDCORD_DIR"

# .env kontrol
if [ ! -f ".env" ]; then
    echo "HATA: .env dosyası bulunamadı!"
    echo "Örnek: cp .env.example .env"
    exit 1
fi

# Wake lock
if command -v termux-wake-lock &> /dev/null; then
    termux-wake-lock 2>/dev/null
fi

echo "Trendcord başlatılıyor..."
venv/bin/python main.py
