#!/data/data/com.termux/files/usr/bin/bash

# ============================================
# Trendcord - Kurulum Scripti (Termux)
# Tek komutla tüm bağımlılıkları yükler
# ============================================

set -e

echo ""
echo "========================================="
echo "  Trendcord Kurulum Başlatılıyor..."
echo "========================================="
echo ""

TRENDCORD_DIR="/data/data/com.termux/files/home/trendcord"

# Gerekli Termux paketleri
echo "[1/5] Termux paketleri güncelleniyor..."
pkg update -y && pkg upgrade -y

echo ""
echo "[2/5] Gerekli paketler yükleniyor..."
pkg install -y python git curl wget

# PostgreSQL (isteğe bağlı)
echo ""
read -p "PostgreSQL yüklensin mi? (y/n): " INSTALL_PG
if [[ "$INSTALL_PG" =~ ^[Yy]$ ]]; then
    pkg install -y postgresql
    echo "  ✓ PostgreSQL yüklendi"
fi

# Redis (isteğe bağlı)
read -p "Redis yüklensin mi? (y/n): " INSTALL_REDIS
if [[ "$INSTALL_REDIS" =~ ^[Yy]$ ]]; then
    pkg install -y redis
    echo "  ✓ Redis yüklendi"
fi

# Cloudflare Tunnel (isteğe bağlı)
read -p "cloudflared yüklensin mi? (y/n): " INSTALL_CF
if [[ "$INSTALL_CF" =~ ^[Yy]$ ]]; then
    pkg install -y cloudflared
    echo "  ✓ cloudflared yüklendi"
fi

echo ""
echo "[3/5] Python bağımlılıkları yükleniyor..."
cd "$TRENDCORD_DIR"
pip install -r requirements.txt

echo ""
echo "[4/5] Node.js bağımlılıkları yükleniyor (Tailwind CSS)..."
if command -v npm &> /dev/null; then
    npm install
    echo "  ✓ Node.js bağımlılıkları yüklendi"
else
    echo "  ⚠ npm bulunamadı, Tailwind CSS build atlandı"
fi

echo ""
echo "[5/5] .env dosyası kontrol ediliyor..."
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo "  ⚠ .env dosyası oluşturuldu - DÜZENLEMENİZ GEREKİR!"
    echo " nano .env komutuyla düzenleyin"
else
    echo "  ✓ .env dosyası mevcut"
fi

# Scriptlere izin ver
chmod +x start.sh start_all.sh run.sh healthcheck.sh

# Termux:Boot kurulumu
echo ""
echo "Termux:Boot otomatik başlangıç kuruluyor..."
mkdir -p "$HOME/.termux/boot"
cp "$TRENDCORD_DIR/.termux/boot/trendcord.sh" "$HOME/.termux/boot/"
chmod +x "$HOME/.termux/boot/trendcord.sh"
echo "  ✓ Otomatik başlangıç kuruldu"

# Wake lock
if command -v termux-wake-lock &> /dev/null; then
    termux-wake-lock
    echo "  ✓ Wake lock aktif"
fi

echo ""
echo "========================================="
echo "  Kurulum Tamamlandı!"
echo "========================================="
echo ""
echo "Başlamak için:"
echo "  cd trendcord && bash start.sh"
echo ""
echo "Veya:"
echo "  bash run.sh"
echo ""
echo "Durdurmak için:"
echo "  pkill -f 'python3 main.py'"
echo ""
echo "Otomatik başlangıç için Termux:Boot uygulamasını yükleyin:"
echo "  https://f-droid.org/packages/com.termux.boot/"
echo ""
echo "Logları izlemek için:"
echo "  tail -f logs/bot.log"
echo ""
