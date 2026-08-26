#!/data/data/com.termux/files/usr/bin/bash

# ============================================
# Trendcord - Hızlı Başlatıcı (Minimal)
# ============================================

TRENDCORD_DIR="/data/data/com.termux/files/home/trendcord"
LOG_DIR="$TRENDCORD_DIR/logs"
mkdir -p "$LOG_DIR"

echo "Trendcord başlatılıyor..."

# Eski süreçleri durdur
pkill -f "python3 main.py" 2>/dev/null
pkill -f "cloudflared tunnel" 2>/dev/null
sleep 2

# Bot'u başlat
cd "$TRENDCORD_DIR"
nohup "$TRENDCORD_DIR/venv/bin/python" main.py > "$LOG_DIR/bot.log" 2>&1 &
BOT_PID=$!
echo "Bot PID: $BOT_PID"
disown $BOT_PID

sleep 8

# Tunnel başlat (isteğe bağlı)
if command -v cloudflared &> /dev/null && [ -f "$HOME/.cloudflared/config.yml" ]; then
    nohup cloudflared tunnel --config "$HOME/.cloudflared/config.yml" run > "$LOG_DIR/tunnel.log" 2>&1 &
    TUNNEL_PID=$!
    echo "Tunnel PID: $TUNNEL_PID"
    disown $TUNNEL_PID
    sleep 5
fi

# Kontrol
echo ""
echo "Durum kontrolü:"
curl -s -o /dev/null -w "  Web: %{http_code}\n" http://localhost:8000/ 2>/dev/null || echo "  Web: HATA"
curl -s -o /dev/null -w "  Tunnel: %{http_code}\n" https://trendcord.miracdeveloper.com.tr/ 2>/dev/null || echo "  Tunnel: HATA"

echo ""
echo "Tamamlandı! Log: tail -f $LOG_DIR/bot.log"
