#!/usr/bin/env bash
# ============================================================
# Trendcord — Deploy
# Kullanım:
#   ./deploy.sh                    → değişiklikleri commit'le + deploy et
#   ./deploy.sh "mesaj"            → özel mesajla commit'le + deploy et
#
# Akış: add -A → commit → GitHub'a yedek push → VDS'e push (hook deploy eder)
# ============================================================
set -euo pipefail
cd "$(dirname "$0")"

BRANCH="main"
MSG="${1:-}"

# VDS remote yoksa ilk kurulum yönlendirmesi
if ! git remote get-url vds >/dev/null 2>&1; then
    echo "VDS remote tanımlı değil."
    echo "Önce çalıştır:  bash deploy/setup_vds.sh kullanici@sunucu-ip"
    exit 1
fi

# Değişiklik var mı?
if [ -n "$(git status --porcelain)" ]; then
    if [ -z "$MSG" ]; then
        read -r -p "Commit mesajı: " MSG
        MSG="${MSG:-deploy: $(date +%Y-%m-%d %H:%M)}"
    fi
    git add -A
    git commit -m "$MSG"
else
    echo "Yeni değişiklik yok — mevcut commit yeniden deploy edilecek."
fi

echo "==> GitHub'a yedekleniyor..."
git push origin "$BRANCH" 2>/dev/null || echo "    ! GitHub push başarısız (deploy devam ediyor)"

echo "==> VDS'e deploy ediliyor..."
if git push vds "$BRANCH"; then
    echo ""
    echo "✓ Deploy tamam. Kontrol: ssh <vds> 'systemctl status trendcord'"
    echo "  Sorun varsa: ./rollback.sh"
else
    echo ""
    echo "!! DEPLOY BAŞARISIZ. Sunucu hâlâ önceki sürümü çalıştırıyor."
    echo "   Detaylar için VDS'te: journalctl -u trendcord -n 50"
    exit 1
fi
