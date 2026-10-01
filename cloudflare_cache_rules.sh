#!/data/data/com.termux/files/usr/bin/bash
# ============================================================
# Trendcord - Cloudflare Edge Cache Kurallari
#
#   ./cloudflare_cache_rules.sh            -> uygula (idempotent)
#   ./cloudflare_cache_rules.sh --dry-run  -> sadece mevcut durumu goster
#   ./cloudflare_cache_rules.sh --delete   -> bu betigin olusturdugu kurallari sil
#
# Gerekli: .env icinde gercek CF_API_TOKEN ve CF_ZONE_ID
#
# NEDEN BU KURALLAR:
#   Cloudflare varsayilaninda /static/ altindaki .css/.js/.woff2/.svg dosyalari
#   zaten kenarda cache'lenir. Buradaki iki kural bunu acikca tanimlar ve
#   Tiered Cache ile birden fazla POP'a yayarak origin isteklerini azaltir.
#
#   HTML ise KASTEN hicbir zaman cache'lenmez. Her anonim GET bir `session`
#   cookie'si yolluyor ve CSRF belirteci bu oturum kimliginden HMAC ile
#   turetiyor. Cache'lenen HTML, sonraki ziyaretciye baska bir kullanicinin
#   belirtecini tasir; `Set-Cookie` ile belirtec eslesmez ve CSRF korumasi
#   bosluga cevirilir. Origin zaten `Cache-Control: private, no-store`
#   gonderiyor; asagidaki bypass kurali bunu bir savunma derinligi olarak
#   tekrarlar.
# ============================================================
set -euo pipefail
cd "$(dirname "$0")"

[ -f .env ] || { echo "HATA: .env yok"; exit 1; }
set -a; . ./.env; set +a

MODE="${1:-apply}"
RULE_NAME="trendcord-edge-cache"
RULESET_PHASE="http_request_cache_settings"

if [ -z "${CF_API_TOKEN:-}" ] || [ -z "${CF_ZONE_ID:-}" ]; then
    echo "HATA: CF_API_TOKEN veya CF_ZONE_ID tanimli degil (.env)"; exit 1
fi
# .env.example degerleri placeholder'dir; gercek token olmadan API cagrisi yapilamaz.
case "$CF_API_TOKEN" in
    your_*|"") echo "HATA: CF_API_TOKEN hala .env.example placeholder'i."; exit 1 ;;
esac
case "$CF_ZONE_ID" in
    your_*|"") echo "HATA: CF_ZONE_ID hala .env.example placeholder'i."; exit 1 ;;
esac

API="https://api.cloudflare.com/client/v4/zones/$CF_ZONE_ID"
AUTH=(-H "Authorization: Bearer $CF_API_TOKEN" -H "Content-Type: application/json")

cf() { curl -s "${AUTH[@]}" "$@"; }
jqp() { python3 -c "import sys,json;d=json.load(sys.stdin);
print(json.dumps(d.get('result'),ensure_ascii=False) if d.get('success') else 'HATA: '+str(d.get('errors')))"; }

# --- ruleset id (zone seviyesinde olustur) ---
ruleset_json=$(cf "$API/rulesets/$RULESET_PHASE")
ruleset_id=$(printf '%s' "$ruleset_json" | python3 -c "import sys,json;d=json.load(sys.stdin);r=d.get('result');print(r['id'] if isinstance(r,dict) and 'id' in r else '')" 2>/dev/null || true)

if [ "$MODE" = "--delete" ]; then
    if [ -n "$ruleset_id" ]; then
        ids=$(cf "$API/rulesets/$ruleset_id/rules" | python3 -c "
import sys,json
d=json.load(sys.stdin)
print(' '.join(r['id'] for r in (d.get('result') or []) if r.get('description')=='$RULE_NAME'))" 2>/dev/null || true)
        for id in $ids; do
            echo "==> siliniyor: $id"
            cf -X DELETE "$API/rulesets/$ruleset_id/rules/$id" > /dev/null
        done
    fi
    echo "Silme tamam."
    exit 0
fi

echo "========================================="
echo " Mevcut zone ayarlari"
echo "========================================="
for s in tiered_cache brotli cache_level browser_cache_ttl; do
    v=$(cf "$API/settings/$s" | python3 -c "import sys,json;d=json.load(sys.stdin);print(d.get('result',{}).get('value'))" 2>/dev/null || echo "?")
    printf "  %-20s %s\n" "$s" "$v"
done

echo
echo "========================================="
echo " Mevcut cache kurallari"
echo "========================================="
if [ -n "$ruleset_id" ]; then
    cf "$API/rulesets/$ruleset_id/rules" | python3 -c "
import sys,json
d=json.load(sys.stdin)
for r in (d.get('result') or []):
    print(f\"  [{r.get('action')}] {r.get('description','(aciklama yok)')}\")
    print(f\"      if: {r.get('expression')}\")" 2>/dev/null || echo "  (okunamadi)"
else
    echo "  (zone seviyesinde cache ruleset yok)"
fi

[ "$MODE" = "--dry-run" ] && { echo; echo "Dry run bitti, degisiklik yapilmadi."; exit 0; }

RULES='{
  "description": "trendcord-edge-cache",
  "rules": [
    {
      "description": "trendcord-edge-cache",
      "action": "set_cache_settings",
      "action_parameters": {
        "cache": {"eligibility": "bypass_cache"}
      },
      "expression": "not http.request.uri.path starts_with \"/static/\"",
      "enabled": true
    },
    {
      "description": "trendcord-edge-cache",
      "action": "set_cache_settings",
      "action_parameters": {
        "cache": {"eligibility": "eligible_for_cache", "edge_ttl": 31536000, "browser_ttl": 31536000}
      },
      "expression": "http.request.uri.path starts_with \"/static/\"",
      "enabled": true
    }
  ]
}'

echo
echo "==> Bu kural yaziliyor: statik = edge cache (1 yil), diger her sey = bypass"
if [ -n "$ruleset_id" ]; then
    out=$(cf -X PUT "$API/rulesets/$ruleset_id/rules" -d "$RULES" | jqp)
else
    out=$(cf -X POST "$API/rulesets" \
        -d "{\"name\":\"$RULE_NAME\",\"kind\":\"$RULESET_PHASE\",\"phase\":\"$RULESET_PHASE\"}" | jqp)
    ruleset_id=$(printf '%s' "$out" | python3 -c "import sys,json;print(json.load(sys.stdin).get('id','') or '')" 2>/dev/null || true)
    if [ -z "$ruleset_id" ]; then
        out=$(cf -X POST "$API/rulesets/$ruleset_id/rules" -d "$RULES" | jqp)
    fi
fi
printf '  %s\n' "$out"

# --- Tiered Cache acik mi? ---
echo
echo "==> tiered_cache kontrolu"
cur=$(cf "$API/settings/tiered_cache" | python3 -c "import sys,json;d=json.load(sys.stdin);print(d.get('result',{}).get('value'))" 2>/dev/null || echo "?")
if [ "$cur" != "smart" ] && [ "$cur" != "on" ]; then
    echo "    smart olarak aciliyor..."
    cf -X PATCH "$API/settings/tiered_cache" -d '{"value":"smart"}' | jqp | head -c 200; echo
fi
echo
echo "Tamam. Dogrulama: canli HTML icin 'cf-cache-status: DYNAMIC',"
echo "statik dosya icin 'cf-cache-status: HIT' beklenir."
