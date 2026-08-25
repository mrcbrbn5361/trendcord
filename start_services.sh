#!/data/data/com.termux/files/usr/bin/bash
# Trendcord - Bot + Tunnel başlatıcı

DIR="/data/data/com.termux/files/home/trendcord"
LOGS="$DIR/logs"
mkdir -p "$LOGS"

# Eski process'leri öldür
kill -9 $(pgrep -f "main.py") 2>/dev/null
kill -9 $(pgrep -f "cloudflared tunnel") 2>/dev/null
sleep 2

# Bot başlat
cd "$DIR"
nohup python3 main.py </dev/null >> "$LOGS/bot.log" 2>&1 &
BOT_PID=$!

# Tunnel başlat
nohup cloudflared tunnel run eadb15bf-ab59-498f-b262-470529614b56 </dev/null >> "$LOGS/tunnel.log" 2>&1 &
TUNNEL_PID=$!

disown -a
sleep 5

# Kontrol
if kill -0 $BOT_PID 2>/dev/null && kill -0 $TUNNEL_PID 2>/dev/null; then
    echo "✅ Her ikisi de çalışıyor (Bot=$BOT_PID Tunnel=$TUNNEL_PID)"
else
    echo "❌ Bir service başlatılamadı"
    kill -0 $BOT_PID 2>/dev/null && echo "  Bot: ✅" || echo "  Bot: ❌"
    kill -0 $TUNNEL_PID 2>/dev/null && echo "  Tunnel: ✅" || echo "  Tunnel: ❌"
fi
