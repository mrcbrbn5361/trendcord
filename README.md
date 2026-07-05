# Trendcord v2.0

Trendcord, Trendyol ürünlerini takip eden, fiyat değişimlerini gerçek zamanlı algılayan ve Discord sunucularına anlık bildirim gönderen profesyonel bir SaaS uygulamasıdır.

## 🚀 Özellikler

- **7/24 Fiyat Takibi**: Trendyol ürünlerini sürekli izler
- **Gerçek Zamanlı Bildirimler**: Fiyat değişikliklerini anında Discord'a iletir
- **Modern Dashboard**: Kullanıcı dostu web arayüzü
- **Çoklu Sunucu Desteği**: Birden fazla Discord sunucusunu yönetir
- **Tema Desteği**: Aydınlık ve koyu tema seçenekleri
- **Yüksek Performans**: Async mimari ve Redis caching

## 🏗️ Mimari

```
trendcord-v2/
├── apps/
│   ├── web/          # Next.js 14 frontend
│   ├── api/          # FastAPI backend
│   └── bot/          # Discord bot
├── packages/
│   ├── shared/       # Paylaşılan tipler
│   ├── db/           # Veritabanı şemaları
│   └── config/       # Paylaşılan yapılandırmalar
├── docker/           # Docker dosyaları
└── docker-compose.yml
```

## 🛠️ Teknoloji Yığını

### Frontend
- **Framework**: Next.js 14 (React 18, TypeScript)
- **Styling**: Tailwind CSS + shadcn/ui
- **State**: Zustand + TanStack Query
- **Animation**: Framer Motion
- **Theme**: next-themes

### Backend
- **Framework**: FastAPI (Python 3.11+)
- **ORM**: SQLAlchemy 2.0 (async)
- **Validation**: Pydantic V2
- **Migration**: Alembic
- **Background Jobs**: Celery + Redis
- **HTTP Client**: httpx

### Database
- **Primary**: PostgreSQL 16
- **Cache**: Redis 7
- **Search**: Meilisearch (opsiyonel)

### DevOps
- **Container**: Docker + Docker Compose
- **Reverse Proxy**: Caddy (HTTPS, HTTP/3)
- **CI/CD**: GitHub Actions
- **Monitoring**: Prometheus + Grafana

## 🚀 Başlangıç

### Ön Gereksinimler

- Docker ve Docker Compose
- Node.js 20+
- Python 3.11+
- PostgreSQL 16+
- Redis 7+

### Kurulum

1. **Repository'yi klonlayın**:
   ```bash
   git clone https://github.com/your-username/trendcord-v2.git
   cd trendcord-v2
   ```

2. **Ortam değişkenlerini ayarlayın**:
   ```bash
   cp .env.example .env
   # .env dosyasını düzenleyin
   ```

3. **Docker ile başlatın**:
   ```bash
   docker-compose up -d
   ```

4. **Veritabanı migrasyonlarını çalıştırın**:
   ```bash
   docker-compose exec api alembic upgrade head
   ```

### Geliştirme Modu

```bash
# Terminal 1 - Backend
cd apps/api
pip install -r requirements/dev.txt
uvicorn app.main:app --reload --port 8000

# Terminal 2 - Frontend
cd apps/web
pnpm install
pnpm dev

# Terminal 3 - Bot
cd apps/bot
pip install -r requirements.txt
python main.py
```

## 📝 Komutlar

### Discord Bot Komutları

- `!ekle <url>` - Ürün ekle
- `!takiptekiler` - Takip edilen ürünleri listele
- `!sil <id>` - Ürün sil
- `!yardım` - Yardım menüsü
- `!istatistik` - Sistem istatistikleri (sadece bot sahibi)

### API Endpointleri

- `GET /api/v1/auth/login` - Discord OAuth2 ile giriş
- `GET /api/v1/products/` - Ürünleri listele
- `POST /api/v1/products/` - Ürün ekle
- `GET /api/v1/products/{id}` - Ürün detayı
- `PUT /api/v1/products/{id}` - Ürün güncelle
- `DELETE /api/v1/products/{id}` - Ürün sil

## 🔧 Yapılandırma

Ortam değişkenleri `.env` dosyasında tanımlanır:

| Değişken | Açıklama | Varsayılan |
|----------|----------|------------|
| `DATABASE_URL` | PostgreSQL bağlantı URL'i | `postgresql+asyncpg://trendcord:trendcord@localhost:5432/trendcord` |
| `REDIS_URL` | Redis bağlantı URL'i | `redis://localhost:6379/0` |
| `DISCORD_TOKEN` | Discord bot token'ı | - |
| `CLIENT_ID` | Discord OAuth2 client ID | - |
| `CLIENT_SECRET` | Discord OAuth2 client secret | - |
| `SECRET_KEY` | JWT secret key | - |

## 🚢 Deployment

### Production

```bash
# Production compose dosyasını kullanın
docker-compose -f docker-compose.prod.yml up -d
```

### Cloud Deploy

- **Frontend**: Vercel / Cloudflare Pages
- **Backend**: Railway / Fly.io / Hetzner
- **Database**: Supabase / Neon
- **Cache**: Upstash / Redis Cloud

## 📊 Monitoring

- **Metrics**: Prometheus (port 9090)
- **Dashboards**: Grafana (port 3001)
- **Logs**: Loki
- **Uptime**: Uptime Kuma

## 🔒 Güvenlik

- HTTPS (Let's Encrypt / Caddy)
- Rate limiting (slowapi)
- CORS policy
- CSP headers
- Secure cookies (HttpOnly, Secure, SameSite)
- JWT with short expiry

## 📄 Lisans

MIT License

## 🤝 Katkıda Bulunma

1. Forklayın
2. Feature branch oluşturun (`git checkout -b feature/amazing-feature`)
3. Commit edin (`git commit -m 'Add amazing feature'`)
4. Push edin (`git push origin feature/amazing-feature`)
5. Pull Request oluşturun

## 📞 İletişim

- Discord: [Trendcord Discord](https://discord.gg/trendcord)
- Email: info@trendcord.com
