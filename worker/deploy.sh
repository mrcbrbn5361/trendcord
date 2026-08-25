#!/data/data/com.termux/files/usr/bin/bash
# Cloudflare Worker Deploy - Trendcord Maintenance

set -e
WORKER_NAME="trendcord-maintenance"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
WORKER_FILE="$SCRIPT_DIR/worker.js"

if [ -z "$CLOUDFLARE_API_TOKEN" ]; then
    echo "❌ HATA: CLOUDFLARE_API_TOKEN gerekli!"
    echo "1. https://dash.cloudflare.com/profile/api-tokens"
    echo "2. Create Token → 'Edit Cloudflare Workers'"
    echo "3. Zone: miracdeveloper.com.tr → Read"
    echo "   Account: Workers Scripts → Edit"
    echo "4. Token'ı kopyala, sonra çalıştır:"
    echo ""
    echo "   CLOUDFLARE_API_TOKEN='token_buraya' bash $0"
    exit 1
fi

ACCOUNT_ID=$(curl -s https://api.cloudflare.com/client/v4/accounts \
    -H "Authorization: Bearer $CLOUDFLARE_API_TOKEN" \
    | python3 -c "import sys,json; print(json.load(sys.stdin)['result'][0]['id'])")
echo "✅ Account: $ACCOUNT_ID"

# Deploy worker
echo "📦 Worker deploy..."
curl -s -X PUT "https://api.cloudflare.com/client/v4/accounts/$ACCOUNT_ID/workers/scripts/$WORKER_NAME" \
    -H "Authorization: Bearer $CLOUDFLARE_API_TOKEN" \
    -H "Content-Type: application/javascript" \
    --data-binary "@$WORKER_FILE" | python3 -c "import sys,json; print('OK' if json.load(sys.stdin).get('success') else 'FAIL')"

# Route ekle
echo "🔗 Route ekleniyor..."
curl -s -X POST "https://api.cloudflare.com/client/v4/accounts/$ACCOUNT_ID/workers/scripts/$WORKER_NAME/routes" \
    -H "Authorization: Bearer $CLOUDFLARE_API_TOKEN" \
    -H "Content-Type: application/json" \
    -d "{\"pattern\": \"trendcord.miracdeveloper.com.tr/*\", \"script\": \"$WORKER_NAME\"}" \
    | python3 -c "import sys,json; print('OK' if json.load(sys.stdin).get('success') else 'FAIL')"

echo ""
echo "✅ Worker aktif! Artık site düşünce bakım sayfası gösterir."
echo "   https://trendcord.miracdeveloper.com.tr"
