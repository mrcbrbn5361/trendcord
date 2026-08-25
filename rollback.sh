#!/usr/bin/env bash
# ============================================================
# Trendcord - Rollback (Termux tarafindan)
#   ./rollback.sh            -> bir onceki release'e ANINDA don
#   ./rollback.sh <commit>   -> istenen commit'e don
#   ./rollback.sh list       -> release'leri ve yedekleri listele
# ============================================================
set -euo pipefail
cd "$(dirname "$0")"

[ -f .vds ] || { echo "VDS tanimli degil. Once: echo 'kullanici@sunucu-ip' > .vds"; exit 1; }
VDS=$(cat .vds)

case "${1:-}" in
    list) ARG="-List" ;;
    "")   ARG="" ;;
    *)    ARG="-Commit $1" ;;
esac

ssh "$VDS" "powershell -NoProfile -ExecutionPolicy Bypass -File C:/trendcord/repo/deploy/rollback.ps1 $ARG"
