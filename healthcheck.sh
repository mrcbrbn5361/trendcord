#!/data/data/com.termux/files/usr/bin/bash

# ============================================
# Trendcord Health Check & Auto-Recovery
# Tunnel ve bot'u izler, gerekirse yeniden başlatır
# ============================================

TRENDCORD_DIR="/data/data/com.termux/files/home/trendcord"
LOG_DIR="$TRENDCORD_DIR/logs"
HEALTH_LOG="$LOG_DIR/health.log"

mkdir -p "$LOG_DIR"

check_tunnel() {
    pgrep -f "cloudflared tunnel" > /dev/null 2>&1
}

check_bot() {
    pgrep -f "venv/bin/python main.py" > /dev/null 2>&1
}

check_web() {
    curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/ 2>/dev/null | grep -q "200"
}

restart_tunnel() {
    echo "[$(date)] Tunnel yeniden başlatılıyor..." >> "$HEALTH_LOG"
    pkill -f "cloudflared" 2>/dev/null
    sleep 2
    cd "$TRENDCORD_DIR"
    if [ -f "$HOME/.cloudflared/config.yml" ]; then
        setsid cloudflared tunnel --config "$HOME/.cloudflared/config.yml" run > "$LOG_DIR/tunnel.log" 2>&1 &
        sleep 5
        if check_tunnel; then
            echo "[$(date)] Tunnel başlatıldı ✓" >> "$HEALTH_LOG"
        else
            echo "[$(date)] Tunnel başlatılamadı ✗" >> "$HEALTH_LOG"
        fi
    fi
}

restart_bot() {
    echo "[$(date)] Bot yeniden başlatılıyor..." >> "$HEALTH_LOG"
    pkill -9 -f "venv/bin/python main.py" 2>/dev/null
    sleep 2
    cd "$TRENDCORD_DIR"
    setsid venv/bin/python main.py > "$LOG_DIR/bot.log" 2>&1 &
    sleep 8
    if check_bot; then
        echo "[$(date)] Bot başlatıldı ✓" >> "$HEALTH_LOG"
        # Termux bildirimi
        if command -v termux-notification &> /dev/null; then
            termux-notification --title "Trendcord" --content "Bot yeniden başlatıldı" --id trendcord 2>/dev/null
        fi
    else
        echo "[$(date)] Bot başlatılamadı ✗" >> "$HEALTH_LOG"
    fi
}

# Ana kontrol döngüsü
while true; do
    # Tunnel kontrol
    if ! check_tunnel; then
        restart_tunnel
    fi

    # Bot kontrol
    if ! check_bot; then
        restart_bot
    fi

    # Web kontrol
    if ! check_web; then
        echo "[$(date)] Web sunucusu yanıt vermiyor, bot yeniden başlatılıyor..." >> "$HEALTH_LOG"
        restart_bot
    fi

    sleep 60  # 60 saniyede bir kontrol
done
