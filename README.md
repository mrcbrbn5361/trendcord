# Trendcord Ürün Takip API Entegrasyonu

Bu belge, Trendcord'daki ürün takip sisteminin harici istemcilerden (Discord botu,
mobil uygulama vb.) nasıl kullanılacağını açıklar.

## Genel Bakış

Trendcord, Trendyol ürünlerini veritabanına kaydeder, saatte bir fiyatlarını
kontrol eder, fiyat değişimlerini kanala bildirir ve hedef fiyat alarmları kurar.
Bu özelliklerin tamamı `/api/v1` REST API'si üzerinden de erişilebilir.

Sistem zaten iki katman sunar:

1. **Discord bot komutları** (`cogs/product_commands.py`) — sunucu içinden
   `/ekle`, `/takiptekiler`, `/sil`, `/alarm` ile ürün takibi.
2. **REST API** (`web/api_mobile.py`) — `/api/v1` altında, isteğe bağlı
   kullanıcı bağlamlı ürün yönetimi.

Aşağıdaki akış, API'yi kullanarak ürün ekleme/silme işini **normal bota**
entegre etmenin yoludur.

## Kurulum

```bash
pip install -r requirements.txt
cp .env.example .env   # token ve OWNER_ID dahil doldur
python main.py
```

Gerekli env değişkenleri:

| Değişken       | Açıklama                                   |
|----------------|--------------------------------------------|
| `DISCORD_TOKEN`| Discord bot token'i                         |
| `PORT`         | Web/API portu (varsayılan 8000)            |
| `OWNER_ID`     | Bot sahibinin Discord ID'si                 |
| `CLIENT_ID`, `CLIENT_SECRET`, `REDIRECT_URI` | Dashboard OAuth için |

## API Endpoint'leri

Temel URL: `https://trendcord.miracdeveloper.com.tr` (yerelde `http://localhost:8000`)

Kimlik doğrulama: `Authorization: Bearer <token>` başlığı. Token gerektiren
uçlar aşağıda `🔒` ile işaretlidir.

### Ürün sorgu (public — token gerektirmez)

| Metot | Path | Açıklama |
|-------|------|----------|
| GET | `/api/v1/products?guild_id=<id>&limit=50&offset=0` | Sunucudaki ürünler |
| GET | `/api/v1/products?mine=true` | 🔒 İstekçinin ürünleri |
| GET | `/api/v1/products/<product_id>` | Ürün detayı + fiyat geçmişi |
| GET | `/api/v1/guilds` | Tracklenen sunucuların listesi |
| GET | `/api/v1/guilds/<guild_id>` | Sunucu detayı (üretici kullanıcılar vb.) |
| GET | `/api/v1/users/<user_id>` | Kullanıcı profili + toplam kazanç |
| GET | `/api/v1/stats` | Genel istatistikler |

### Ürün yönetimi (token gerekir)

| Metot | Path | Açıklama |
|-------|------|----------|
| POST | `/api/v1/products` | Yeni ürünü takibe alır (URL taranır) |
| DELETE | `/api/v1/products/<product_id>` | Takibi kaldırır (sahip veya OWNER_ID) |

### Alarmlar (token gerekir)

| Metot | Path | Açıklama |
|-------|------|----------|
| GET | `/api/v1/alerts` | Kullanıcının alarmları |
| POST | `/api/v1/alerts` | Alarm oluşturur (ürün sahibi olmalı) |
| DELETE | `/api/v1/alerts/<id>` | Alarm siler |

### Auth

| Metot | Path | Açıklama |
|-------|------|----------|
| POST | `/api/v1/auth/login` | Discord OAuth `code` ile token alır |
| POST | `/api/v1/auth/logout` | Token'i iptal eder |
| GET | `/api/v1/me` | 🔒 Token sahibi profili + ürün sayısı |

## Token Üretme

Harici istemci için bearer token, sunucudaki DB'nin yanında çalıştırılır:

```bash
python issue_token.py <discord_user_id> [gün]
# örn: 30 günlük token
python issue_token.py 123456789012345678 30
```

Çıktı tek satır raw token'dır; DB'de yalnızca SHA-256 hash'i saklanır.

## POST /api/v1/products — Atıf Kuralları

```jsonc
{
  "url": "https://www.trendyol.com/urun-linki",
  "guild_id": "1504574003594137680",
  "channel_id": "1511681240418484224",   // isteğe bağlı
  "discord_id": "987654321012345678",    // isteğe bağlı
  "username": "kullanici_adi",
  "avatar_url": "https://cdn.discordapp.com/.../a.png"
}
```

- `discord_id` **belirtilmezse**: ürün token sahibine (requesting user) atanır.
- `discord_id` **belirtilirse**: yalnızca token sahibi `OWNER_ID` ise ürün o
  Discord kullanıcısına atanır; aksi halde `403 not_authorized`. Bu, sunucudaki
  diğer üyelerin komutla eklediği ürünlerin **kendi profillerinde** görünmesini,
  yabancıların başkası adına ürün ekleyememesini sağlar.

Örnek (curl):

```bash
curl -X POST https://trendcord.miracdeveloper.com.tr/api/v1/products \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"url":"https://www.trendyol.com/...","guild_id":"1504574003594137680","discord_id":"987654321012345678","username":"kisi"}'
```

Yanıt: takibi başlayan ürünün `product` nesnesi (ad, fiyat, sepet fiyatı,
indirim, kampanya, `product_id`, URL).

## Normal Bota Komut Ekleme

`cogs/product_commands.py` içindeki mevcut `/ekle` komutu bot'un kendi
scraper'ını kullanır. API üzerinden ekleme yapmak istiyorsan aynı düzende
bir komut ekleyebilirsin:

```python
import aiohttp

ADD_URL = "https://trendcord.miracdeveloper.com.tr/api/v1/products"
TOKEN = "issue_token.py ile üretilen token"

@commands.hybrid_command(name="takip", description="Ürünü takibe al")
async def takip(self, ctx, url: str):
    if isinstance(ctx, discord.Interaction):
        await ctx.response.defer()
    payload = {
        "url": url,
        "guild_id": str(ctx.guild_id),
        "channel_id": str(ctx.channel_id),
        "discord_id": str(ctx.user.id),
        "username": str(ctx.user.name),
        "avatar_url": str(ctx.user.display_avatar.url) if ctx.user.display_avatar else "",
    }
    async with aiohttp.ClientSession() as s:
        async with s.post(ADD_URL, json=payload,
                          headers={"Authorization": f"Bearer {TOKEN}"}) as r:
            data = await r.json()
    if r.status != 200:
        await ctx.followup.send(f"❌ Takip eklenemedi: {data.get('detail','hata')}")
        return
    p = data["product"]
    embed = discord.Embed(title="✅ Takip Başlatıldı", url=p["url"],
                          color=0xF27A1A)
    embed.add_field(name="Ürün", value=p["name"][:100], inline=False)
    embed.add_field(name="Fiyat", value=f"**{p['current_price']:.2f} TL**", inline=True)
    embed.add_field(name="ID", value=f"`{p['product_id']}`", inline=True)
    await ctx.followup.send(embed=embed)
```

Not: `/ekle`, `/takiptekiler`, `/sil`, `/alarm` zaten mevcut; API aynı
işlemleri harici istemciler ve yeni/ek bota komutları için kullanıma açar.

## Güvenlik Notları

- Raw token yalnızca `issue_token.py` çıktısında görünür; DB'de hash saklanır.
- Rate limit: `/api/v1` için IP başına 120 istek/dk, token başına 240 istek/dk
  (Redis; Redis yoksa fail-open).
- Kurulum `rate_limit` Redis gerektirir. Redis başlatılmazsa sistem yine
  çalışır (sınırlama devre dışı kalır).

## Deploy

```bash
./deploy.sh "api: ürün yönetim endpointleri + issue_token"
```