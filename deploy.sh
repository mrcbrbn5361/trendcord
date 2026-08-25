#!/usr/bin/env bash
# ============================================================
# Trendcord - Deploy (Termux tarafindan)
#   ./deploy.sh            -> commit + GitHub yedek + VDS'e deploy
#   ./deploy.sh "mesaj"    -> ozel mesajla
# ============================================================
set -euo pipefail
cd "$(dirname "$0")"

[ -f .vds ] || { echo "VDS tanimli degil. Once: echo 'kullanici@sunucu-ip' > .vds"; exit 1; }
VDS=$(cat .vds)
MSG="${1:-}"

if [ -n "$(git status --porcelain)" ]; then
    [ -z "$MSG" ] && { read -r -p "Commit mesaji: " MSG; }
    MSG="${MSG:-deploy: $(date +%Y-%m-%d %H:%M)}"
    git add -A && git commit -m "$MSG"
else
    echo "Yeni degisiklik yok - mevcut commit yeniden deploy edilecek."
fi

echo "==> GitHub'a yedekleniyor..."
git push origin main 2>/dev/null || echo "    ! GitHub push basarisiz (deploy devam ediyor)"

echo "==> VDS'e deploy ediliyor..."
ssh "$VDS" "powershell -NoProfile -ExecutionPolicy Bypass -File C:/trendcord/repo/deploy/deploy.ps1"
