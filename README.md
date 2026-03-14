# Trendyol Takip Botu & Web Dashboard

Discord üzerinden Trendyol ürünlerinin fiyatlarını takip etmenizi sağlayan bir bot ve web arayüzü.

## Özellikler

- **Web Dashboard:** Trendyol benzeri modern arayüz ile ürün yönetimi.
- **Discord OAuth2:** Web sitesine Discord hesabınızla güvenli giriş yapın.
- **Bot Yönetimi:** Web üzerinden botu sunucularınıza tek tıkla ekleyin.
- **Akıllı Takip:** `ty.gl` kısa linkleri ve mobil uygulama paylaşımlarını destekler.
- **Anlık Bildirim:** Fiyat düştüğünde veya yükseldiğinde Discord üzerinden bildirim gönderir.
- **Proxy Desteği:** Trendyol engellerine takılmamak için proxy desteği.

## Kurulum

### 1. Gereksinimler
- Python 3.8+
- Discord Developer Portal'dan bir Uygulama (Bot ve OAuth2 için)

### 2. Bağımlılıklar
```bash
pip install -r requirements.txt
```

**Termux (Android) için Not:**
Eğer `pydantic-core` veya `maturin` hatası alıyorsanız, kurulum öncesi şu komutu çalıştırın:
```bash
export ANDROID_API_LEVEL=24
pip install -r requirements.txt
```

### 3. Yapılandırma (`.env`)
Bir `.env` dosyası oluşturun ve aşağıdaki bilgileri girin:
```dotenv
DISCORD_TOKEN=your_bot_token
DISCORD_CLIENT_ID=your_client_id
DISCORD_CLIENT_SECRET=your_client_secret
DISCORD_REDIRECT_URI=http://localhost:8000/auth/callback
SECRET_KEY=a_random_secret_key
CHECK_INTERVAL=3600
PROXY_ENABLED=True
```

### 4. Veritabanı Hazırlama
```bash
python3 migrate_db.py
```

### 5. Çalıştırma
Botu ve Web sunucusunu ayrı terminal pencerelerinde çalıştırın:
```bash
# Terminal 1: Bot
python3 main.py

# Terminal 2: Web Dashboard
python3 app.py
```

## Cloudflare Tunnel (Dış Dünyaya Açma)

Web sitenizi Cloudflare üzerinden internete açmak için:

1. `cloudflared` kurun.
2. `cloudflared tunnel create <tunnel_adi>` ile tünel oluşturun.
3. `cloudflared/config.yml.template` dosyasını `config.yml` olarak kopyalayıp düzenleyin.
4. Tüneli başlatın: `cloudflared tunnel run <tunnel_adi>`.

## Lisans
MIT
