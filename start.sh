#!/data/data/com.termux/files/usr/bin/bash

# ============================================
# Trendcord - Termux Başlatıcı
# ============================================

TRENDCORD_DIR="/data/data/com.termux/files/home/trendcord"
LOG_DIR="$TRENDCORD_DIR/logs"
mkdir -p "$LOG_DIR"

echo "========================================="
echo "  Trendcord Başlatılıyor..."
echo "========================================="

# Eski süreçleri durdur
echo "[1/6] Eski süreçler durduruluyor..."
pkill -f "$TRENDCORD_DIR/venv/bin/python main.py" 2>/dev/null
pkill -f "cloudflared tunnel" 2>/dev/null
sleep 2

# PostgreSQL başlat (Termux paketi gerekli)
echo "[2/6] PostgreSQL başlatılıyor..."
if command -v pg_ctl &> /dev/null; then
    pg_ctl -D "$PREFIX/var/lib/postgresql" -l "$LOG_DIR/postgresql.log" start 2>/dev/null
    if [ $? -eq 0 ]; then
        echo "  ✓ PostgreSQL başlatıldı"
    else
        echo "  ✗ PostgreSQL başlatılamadı (zaten çalışyor olabilir)"
    fi
else
    echo "  ⚠ PostgreSQL yüklü değil (pkg install postgresql)"
fi

# Redis başlat (isteğe bağlı)
echo "[3/6] Redis başlatılıyor..."
if command -v redis-server &> /dev/null; then
    pgrep -f "redis-server" > /dev/null 2>&1
    if [ $? -ne 0 ]; then
        redis-server --ignore-warnings ARM64-COW-BUG > /dev/null 2>&1 &
        echo "  ✓ Redis başlatıldı"
    else
        echo "  ✓ Redis zaten çalışıyor"
    fi
else
    echo "  ⚠ Redis yüklü değil (pkg install redis)"
fi

sleep 2

# Bot'u başlat
echo "[4/6] Discord bot başlatılıyor..."
cd "$TRENDCORD_DIR"
nohup "$TRENDCORD_DIR/venv/bin/python" main.py > "$LOG_DIR/bot.log" 2>&1 &
sleep 8

# Bot çalışıyor mu kontrol et
if pgrep -f "$TRENDCORD_DIR/venv/bin/python main.py" > /dev/null 2>&1; then
    BOT_PID=$(pgrep -f "$TRENDCORD_DIR/venv/bin/python main.py" | head -1)
    echo "  ✓ Bot PID: $BOT_PID"
else
    echo "  ✗ Bot başlatılamadı! Log: $LOG_DIR/bot.log"
    exit 1
fi

# Cloudflare Tunnel başlat (isteğe bağlı)
echo "[5/6] Cloudflare Tunnel başlatılıyor..."
if command -v cloudflared &> /dev/null; then
    if [ -f "$HOME/.cloudflared/config.yml" ]; then
        nohup cloudflared tunnel --config "$HOME/.cloudflared/config.yml" run > "$LOG_DIR/tunnel.log" 2>&1 &
        echo "  ✓ Tunnel PID: $!"
    else
        echo "  ⚠ config.yml bulunamadı, tunnel başlatılmadı"
    fi
else
    echo "  ⚠ cloudflared yüklü değil"
fi
sleep 3

# Healthcheck başlat
echo "[6/6] Healthcheck başlatılıyor..."
nohup bash "$TRENDCORD_DIR/healthcheck.sh" > /dev/null 2>&1 &
echo "  ✓ Healthcheck PID: $!"

# Termux bildirimi
if command -v termux-notification &> /dev/null; then
    termux-notification --title "Trendcord" --content "Tüm servisler başlatıldı" --id trendcord 2>/dev/null
fi

# Wake lock (Termux)
if command -v termux-wake-lock &> /dev/null; then
    termux-wake-lock 2>/dev/null
fi

echo ""
echo "========================================="
echo "  Trendcord başarıyla başlatıldı!"
echo "  Web: http://localhost:8000"
echo "  Log: $LOG_DIR/bot.log"
echo "========================================="
echo ""
echo "Durdurmak için: bash $TRENDCORD_DIR/stop.sh"
echo "Logları izlemek için: tail -f $LOG_DIR/bot.log"
