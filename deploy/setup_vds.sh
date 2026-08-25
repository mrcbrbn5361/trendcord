#!/usr/bin/env bash
# ============================================================
# Trendcord — VDS tek seferlik kurulum
# Kullanım: bash deploy/setup_vds.sh kullanici@sunucu-ip
#
# Yapılanlar:
#   1) SSH anahtarı yoksa üret, sunucuya yükle, ANAHTARLA girişi test et
#   2) Sunucuda /srv/trendcord yapısını ve bare repo'yu oluştur
#   3) post-receive hook'u ve systemd servisini kur
#   4) (Onayla) SSH parola girişini kapat — SADECE anahtar testi başarılıysa
# ============================================================
set -euo pipefail

HOST="${1:?Kullanım: bash deploy/setup_vds.sh kullanici@sunucu-ip}"
KEY="$HOME/.ssh/id_ed25519"
BASE="/srv/trendcord"
REPO="/opt/trendcord.git"

echo "==> [1/5] SSH anahtarı kontrol ediliyor..."
if [ ! -f "$KEY" ]; then
    ssh-keygen -t ed25519 -f "$KEY" -N "" -C "trendcord-termux"
fi
echo "---- BU PUBLIC KEY'İ SUNUCUYA TANIYORUZ ----"
ssh-copy-id -i "$KEY.pub" "$HOST"

echo "==> [2/5] Anahtarla şifresiz giriş test ediliyor..."
if ! ssh -i "$KEY" -o BatchMode=yes -o PasswordAuthentication=no -o ConnectTimeout=10 "$HOST" "echo ok" >/dev/null 2>&1; then
    echo "HATA: Anahtarla giriş başarısız! Sunucuda ssh-copy-id çıktısını kontrol et."
    exit 1
fi
echo "    ✓ Şifresiz giriş çalışıyor"

echo "==> [3/5] Sunucu dizinleri ve bare repo oluşturuluyor..."
ssh -i "$KEY" "$HOST" "
    set -e
    sudo mkdir -p $BASE/releases $BASE/shared/data $BASE/backups /opt/trendcord.git
    sudo chown -R \$(whoami) $BASE /opt/trendcord.git
    if [ ! -d $REPO/HEAD ]; then
        git init --bare $REPO >/dev/null
    fi
    mkdir -p ~/.config/systemd 2>/dev/null || true
"

echo "==> [4/5] Hook ve systemd birimi yükleniyor..."
scp -i "$KEY" -q "$(dirname "$0")/post-receive" "$HOST:/tmp/trendcord-hook"
scp -i "$KEY" -q "$(dirname "$0")/trendcord.service" "$HOST:/tmp/trendcord.service"
ssh -i "$KEY" "$HOST" "
    set -e
    install -m 755 /tmp/trendcord-hook $REPO/hooks/post-receive
    sed \"s/__DEPLOY_USER__/\$(whoami)/\" /tmp/trendcord.service > /tmp/trendcord.service.final
    sudo install -m 644 /tmp/trendcord.service.final /etc/systemd/system/trendcord.service
    sudo systemctl daemon-reload
    sudo systemctl enable trendcord >/dev/null 2>&1 || true
    rm -f /tmp/trendcord-hook /tmp/trendcord.service /tmp/trendcord.service.final
    # shared/.env yoksa yerelden kopyalanacak; burada boş şablon oluşturma:
    [ -f $BASE/shared/.env ] || echo '# Trendcord .env — yerelden doldurulacak' > $BASE/shared/.env
    chmod 600 $BASE/shared/.env
"
echo "    ✓ Kurulum tamam"

# .env'i yerelden güvenli taşı (varsa)
if [ -f ".env" ]; then
    echo "==> Yerel .env sunucuya taşınıyor (scp, 600 yetki)..."
    scp -i "$KEY" -q .env "$HOST:$BASE/shared/.env"
fi

# deploy.sh'in ilk kurulumda remote ekleyebilmesi için bilgi yaz
echo ""
echo "============================================================"
echo " VDS hazır!"
echo "   Deploy : ./deploy.sh \"commit mesajı\""
echo "   Rollback: ./rollback.sh"
echo ""
echo " Sonraki adım (ÖNERİLEN): SSH parola girişini kapatmak."
echo "   Anahtar girişi test edildiği için güvenli."
echo "   Onaylıyorsan aşağıya 'evet' yaz:"
read -r -p "Parola girişi kapatılsın mı? (evet/hayır): " ANSWER
if [ "$ANSWER" = "evet" ]; then
    echo "==> sshd yapılandırması güncelleniyor..."
    ssh -i "$KEY" "$HOST" "
        set -e
        sudo cp /etc/ssh/sshd_config /etc/ssh/sshd_config.bak-\$(date +%s)
        sudo sed -i 's/^#\?PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config
        sudo sed -i 's/^#\?PermitRootLogin.*/PermitRootLogin prohibit-password/' /etc/ssh/sshd_config
        sudo sed -i 's/^#\?PubkeyAuthentication.*/PubkeyAuthentication yes/' /etc/ssh/sshd_config
        sudo sshd -t && sudo systemctl reload sshd
        echo '    ✓ Parola girişi kapalı — bu oturumu KAPATMA, yeni bağlantıyı ayrı terminalde test et!'
    "
else
    echo "Atlandı — parola girişi açık kaldı."
fi
echo "============================================================"
