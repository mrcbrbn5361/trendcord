#!/data/data/com.termux/files/usr/bin/bash

# ============================================
# Trendcord - Durdur
# ============================================

echo "Trendcord durduruluyor..."

# Bot'u durdur
pkill -f "venv/bin/python main.py" 2>/dev/null
if [ $? -eq 0 ]; then
    echo "  ✓ Bot durduruldu"
else
    echo "  ⚠ Bot zaten durmuş"
fi

# Tunnel'ı durdur
pkill -f "cloudflared tunnel" 2>/dev/null
if [ $? -eq 0 ]; then
    echo "  ✓ Tunnel durduruldu"
fi

# Healthcheck'i durdur
pkill -f "healthcheck.sh" 2>/dev/null

# Wake lock'ı serbest bırak
if command -v termux-wake-unlock &> /dev/null; then
    termux-wake-unlock 2>/dev/null
    echo "  ✓ Wake lock serbest bırakıldı"
fi

# Bildirim
if command -v termux-notification &> /dev/null; then
    termux-notification --title "Trendcord" --content "Durduruldu" --id trendcord-status 2>/dev/null
fi

echo ""
echo "Trendcord durduruldu."
