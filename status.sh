#!/data/data/com.termux/files/usr/bin/bash

# ============================================
# Trendcord - Durum Kontrol
# ============================================

echo "========================================="
echo "  Trendcord Durum"
echo "========================================="
echo ""

# Bot durumu
if pgrep -f "venv/bin/python main.py" > /dev/null 2>&1; then
    BOT_PID=$(pgrep -f "venv/bin/python main.py")
    echo "Bot:       ✓ Çalışıyor (PID: $BOT_PID)"
else
    echo "Bot:       ✗ Çalışmıyor"
fi

# Tunnel durumu
if pgrep -f "cloudflared tunnel" > /dev/null 2>&1; then
    TUNNEL_PID=$(pgrep -f "cloudflared tunnel")
    echo "Tunnel:    ✓ Çalışıyor (PID: $TUNNEL_PID)"
else
    echo "Tunnel:    ✗ Çalışmıyor"
fi

# Web durumu
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/ 2>/dev/null)
if [ "$HTTP_CODE" = "200" ]; then
    echo "Web:       ✓ Çalışıyor (HTTP $HTTP_CODE)"
else
    echo "Web:       ✗ Yanıt yok (HTTP $HTTP_CODE)"
fi

# PostgreSQL durumu
if pgrep -f "postgres" > /dev/null 2>&1; then
    echo "PostgreSQL: ✓ Çalışıyor"
else
    echo "PostgreSQL: ✗ Çalışmıyor"
fi

# Redis durumu
if pgrep -f "redis-server" > /dev/null 2>&1; then
    echo "Redis:     ✓ Çalışıyor"
else
    echo "Redis:     ✗ Çalışmıyor"
fi

# Disk kullanımı
echo ""
echo "-----------------------------------------"
DB_SIZE=$(du -h /data/data/com.termux/files/home/trendcord/data/trendyol_tracker.sqlite 2>/dev/null | cut -f1)
LOG_SIZE=$(du -sh /data/data/com.termux/files/home/trendcord/logs/ 2>/dev/null | cut -f1)
echo "DB Boyutu: $DB_SIZE"
echo "Log Boyutu: $LOG_SIZE"

# Son log
echo ""
echo "-----------------------------------------"
echo "Son 5 log satırı:"
tail -5 /data/data/com.termux/files/home/trendcord/logs/bot.log 2>/dev/null || echo "Log bulunamadı"
