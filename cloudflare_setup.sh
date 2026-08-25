#!/data/data/com.termux/files/usr/bin/bash
# Cloudflare DNS Failover Kurulum Yardımcısı

echo "========================================="
echo "  Cloudflare DNS Failover Kurulumu"
echo "========================================="
echo ""

# Cloudflare API Token sayfasını aç
echo "1. API Token sayfası açılıyor..."
echo "   → 'Create Token' tıkla"
echo "   → 'Use template' olarak 'Edit zone DNS' seç"
echo "   → Zone Permissions: miracdeveloper.com.tr seç"
echo "   → Token oluştur ve kopyala"
echo ""
termux-open-url "https://dash.cloudflare.com/profile/api-tokens" 2>/dev/null || xdg-open "https://dash.cloudflare.com/profile/api-tokens" 2>/dev/null
sleep 2

# Cloudflare Zone sayfasını aç
echo "2. Zone ID sayfası açılıyor..."
echo "   → miracdeveloper.com.tr domain'ini seç"
echo "   → Sağ alt köşeden 'Zone ID' kopyala"
echo ""
termux-open-url "https://dash.cloudflare.com" 2>/dev/null || xdg-open "https://dash.cloudflare.com" 2>/dev/null
sleep 2

echo "========================================="
echo "  Değerleri aşağıdaki gibi .env'ye yaz:"
echo "========================================="
echo ""
echo "  CF_API_TOKEN=buraya_token_yapıştır"
echo "  CF_ZONE_ID=buraya_zone_id_yapıştır"
echo ""
echo "Düzenleme için:"
echo "  nano ~/trendcord/.env"
echo ""
echo "========================================="
