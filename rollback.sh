#!/usr/bin/env bash
# ============================================================
# Trendcord — Rollback
# Kullanım:
#   ./rollback.sh                → bir önceki release'e ANINDA dön (saniyeler içinde)
#   ./rollback.sh <commit-hash>  → istediğin commit'i yeni release olarak kur ve aktif et
#   ./rollback.sh list           → sunucudaki release'leri ve veri yedeklerini listele
# ============================================================
set -euo pipefail
cd "$(dirname "$0")"

BASE="/srv/trendcord"
KEY="${TRENDCORD_SSH_KEY:-$HOME/.ssh/id_ed25519}"

VDS_HOST="$(git remote get-url vds 2>/dev/null | sed -E 's#.*@([^:]+):.*#\1#')"
VDS_USER="$(git remote get-url vds 2>/dev/null | sed -E 's#^(ssh://)?([^@]+)@.*#\2#')"
SSH="ssh -i $KEY $VDS_USER@$VDS_HOST"

run() { $SSH "$@"; }

case "${1:-}" in
    list)
        echo "=== Releases (yeni → eski) ==="
        run "ls -1t $BASE/releases"
        echo ""
        echo "=== Aktif ==="
        run "readlink -f $BASE/current | xargs basename"
        echo ""
        echo "=== Veri yedekleri ==="
        run "ls -1t $BASE/backups 2>/dev/null | head -10 || echo yok"
        ;;

    "" )
        echo "==> Önceki release'e dönülüyor..."
        run "
            set -e
            PREV=\$(ls -1t $BASE/releases | grep -A1 \"\$(basename \$(readlink -f $BASE/current))\" | tail -1)
            if [ -z \"\$PREV\" ]; then
                # aktif sürüm listede yoksa (ör. elle silinmiş): en yeni diğerini al
                PREV=\$(ls -1t $BASE/releases | sed -n 2p)
            fi
            [ -n \"\$PREV\" ] || { echo 'Geri alınacak başka release yok!'; exit 1; }
            ln -sfn $BASE/releases/\$PREV $BASE/.current.tmp && mv -Tf $BASE/.current.tmp $BASE/current
            sudo systemctl restart trendcord
            sleep 4
            systemctl is-active --quiet trendcord && echo \"✓ Rollback tamam: \$PREV aktif\" \
                || { echo '!! Servis kalkmadı:'; journalctl -u trendcord -n 20 --no-pager; exit 1; }
        "
        ;;

    * )
        COMMIT="$1"
        git cat-file -e "$COMMIT^{commit}" 2>/dev/null || { echo "Commit bulunamadı: $COMMIT"; exit 1; }
        STAMP="$(date -u +%Y%m%d-%H%M%S)-rb"
        echo "==> Commit $COMMIT yeni release olarak kuruluyor ($STAMP)..."
        git archive "$COMMIT" | run "mkdir -p $BASE/releases/$STAMP && tar -x -C $BASE/releases/$STAMP"
        run "
            set -e
            REL=$BASE/releases/$STAMP
            ln -sfn $BASE/shared/.env \$REL/.env
            ln -sfn $BASE/shared/data \$REL/data
            python3 -m venv \$REL/venv
            \$REL/venv/bin/pip install -r \$REL/requirements.txt --quiet
            \$REL/venv/bin/python -m py_compile \$REL/main.py
            ln -sfn \$REL $BASE/.current.tmp && mv -Tf $BASE/.current.tmp $BASE/current
            sudo systemctl restart trendcord
            sleep 4
            systemctl is-active --quiet trendcord && echo \"✓ \$STAMP aktif ($COMMIT)\" \
                || { echo '!! Servis kalkmadı — önceki duruma dönmek için tekrar ./rollback.sh'; exit 1; }
        "
        ;;
esac
