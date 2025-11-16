# Trendyol Takip Botu

Discord üzerinden Trendyol ürünlerinin fiyatlarını takip etmenizi sağlayan bir bot.

## Özellikler

- Trendyol ürünlerini takip etme
- Fiyat değişikliklerinde otomatik bildirim gönderme
- Ürün fiyat geçmişini izleme
- Proxy desteği ile istekleri yönetme
- Discord üzerinden kolay kullanılabilir komutlar
- Modern web kontrol paneli ile takip edilen ürünleri görselleştirme
- Kullanıcı ve admin rolleri için giriş sistemi

## Kurulum

Bu botu çalıştırmak için bilgisayarınızda Python 3.8 veya üzeri bir sürümün kurulu olması gerekmektedir.

**Önemli Not:** Bu projenin dosyaları, bir yapay zeka tarafından oluşturulmuş veya düzenlenmiş olabilir. Bu nedenle, ana proje klasörünüzün adı (`trendyol`) içinde, aşağıda listelenen bazı ek dosyalarla karşılaşabilirsiniz. Bu döküman, bu olası durumu da göz önünde bulundurarak hazırlanmıştır.

**Ön Hazırlıklar:**

1.  **Python Kurulumu:**
    *   Eğer Python kurulu değilse, [python.org](https://www.python.org/downloads/) adresinden işletim sisteminize uygun sürümü indirip kurun. Kurulum sırasında "Add Python to PATH" seçeneğini işaretlemeyi unutmayın.
    *   Kurulumu doğrulamak için komut satırına (Terminal veya Komut İstemi) `python --version` veya `python3 --version` yazın.

2.  **Proje Dosyalarını Edinme:**
    *   Proje dosyalarını içeren `trendyol` klasörünü bilgisayarınıza indirin (örneğin, ZIP olarak) ve istediğiniz bir konuma çıkartın.
    *   Komut satırı/terminal üzerinden `trendyol` klasörünün içine gidin. Örneğin: `cd /path/to/trendyol` veya `cd C:\path\to\trendyol`.

**Kurulum Adımları:**

1.  **(Önerilen) Sanal Ortam Oluşturma ve Aktifleştirme:**
    Proje bağımlılıklarını sistem genelindeki Python paketlerinden ayırmak için bir sanal ortam oluşturmanız önerilir.
    ```bash
    # trendyol klasörünün içindeyken:
    python -m venv venv
    # veya macOS/Linux üzerinde python3 kullanıyorsanız:
    # python3 -m venv venv
    ```
    Sanal ortamı aktifleştirin:
    *   **Windows (Komut İstemi veya PowerShell):**
        ```cmd
        venv\Scripts\activate
        ```
    *   **macOS / Linux (Terminal):**
        ```bash
        source venv/bin/activate
        ```
    Bundan sonraki komutları bu aktif sanal ortamda çalıştıracaksınız.

2.  **Gerekli Paketleri Yükleme:**
    `trendyol` klasörünüzde `requirements.txt` dosyası bulunmalıdır. Aşağıdaki komut ile gerekli Python paketlerini yükleyin:
    ```bash
    pip install -r requirements.txt
    ```
    **Not**: Windows'ta Türkçe karakter içeren bir yolda kurulum yapıyorsanız ve sorun yaşıyorsanız, alternatif olarak şu komutu kullanabilirsiniz (eğer `requirements_fix.txt` dosyası projenizde mevcutsa):
    ```bash
    pip install -r requirements_fix.txt
    ```
    Eğer `trendyol` klasörünüzde `install_requirements.py` gibi bir dosya varsa, bu alternatif bir kurulum scripti olabilir. Genellikle yukarıdaki `pip install -r ...` komutları yeterli olacaktır. `req.txt` dosyası da benzer şekilde alternatif bir bağımlılık listesi olabilir.

3.  **Veritabanını Oluşturma:**
    `trendyol` klasörünüzde `init_db.py` adlı bir script bulunmalıdır. Bu scripti çalıştırarak veritabanını oluşturun:
    ```bash
    python init_db.py
    # veya macOS/Linux üzerinde python3 kullanıyorsanız:
    # python3 init_db.py
    ```
    Eğer `trendyol` klasörünüzde `create_database_sqlite.py` gibi bir dosya varsa, bu `init_db.py`'ye alternatif bir veritabanı oluşturma scripti olabilir. Öncelikle `init_db.py`'yi deneyin.

4.  **`.env` Yapılandırma Dosyasını Oluşturma ve Düzenleme:**
    `trendyol` klasörünün ana dizininde (`/path/to/trendyol` veya `C:\path\to\trendyol`) `.env` adında bir dosya oluşturun ve aşağıdaki içeriği kendi bilgilerinize göre düzenleyerek içine yapıştırın:
    ```dotenv
    # Discord Bot Token - Discord Developer Portal'dan alınacak
    DISCORD_TOKEN=buraya_discord_tokeninizi_ekleyin

    # Bot Ayarları
    PREFIX=!
    CHECK_INTERVAL=3600 # Her saatte bir fiyat kontrolü (saniye cinsinden)
    PROXY_ENABLED=True # Proxy kullanımını etkinleştir

    # Veritabanı Ayarları
    DATABASE_PATH=data/trendyol_tracker.sqlite # Ana veritabanı dosyası
    BACKUP_DATABASE_PATH=data/database.sqlite # Yedek veritabanı dosyası (eğer kullanılıyorsa)
    ```
    *   `DISCORD_TOKEN`: Discord Developer Portal üzerinden oluşturduğunuz botunuza ait token'ı buraya girin.

5.  **Botu Çalıştırma:**
    Sanal ortamınızın aktif olduğundan emin olun.
    ```bash
    python main.py
    # veya macOS/Linux üzerinde python3 kullanıyorsanız:
    # python3 main.py
    ```
    Botunuz artık Discord sunucunuzda aktif olmalıdır.

## Web Kontrol Paneli

Trendyol botunu yönetmek ve takip edilen ürünleri görselleştirmek için FastAPI tabanlı yeni bir web arayüzü eklenmiştir.

### Gerekli Ortam Değişkenleri

`.env` dosyanıza aşağıdaki değerleri ekleyerek yönetici hesabının otomatik oluşturulmasını sağlayabilirsiniz:

```dotenv
WEB_SECRET_KEY=rasgele_ve_uzun_bir_anahtar
WEB_ADMIN_USERNAME=admin
WEB_ADMIN_EMAIL=admin@example.com
WEB_ADMIN_PASSWORD=guclu_sifreniz
WEB_ADMIN_DISCORD_ID=1234567890 # Opsiyonel, kullanıcıya ait Discord ID'si
WEB_SESSION_COOKIE=trendcord_session
WEB_SESSION_MAX_AGE=604800
WEB_COOKIE_SECURE=False
```

- `WEB_ADMIN_PASSWORD` belirtilmezse varsayılan `admin123` şifresi kullanılır. Güvenlik için kendi güçlü şifrenizi tanımlayın.
- `WEB_SECRET_KEY` değeri oturum imzalama için kullanılır ve kesinlikle gizli tutulmalıdır.

### Paneli Başlatma

1. Bağımlılıkların yüklü olduğundan emin olun: `pip install -r requirements.txt`
2. Veritabanı oluşturulduktan sonra aşağıdaki komutla web sunucusunu çalıştırın:

```bash
uvicorn webapp.main:app --host 0.0.0.0 --port 8000 --reload
```

3. Tarayıcıdan `http://localhost:8000/login` adresine giderek yönetim paneline erişebilirsiniz.

### Panel Özellikleri

- **Gösterge Paneli:** Toplam ürün sayısı, aktif sunucular ve son fiyat güncellemeleri tek ekranda.
- **Kullanıcı Yönetimi:** Adminler yeni kullanıcılar oluşturabilir, rolleri belirleyebilir ve Discord ID eşleştirmesi yapabilir.
- **Ürün Detayları:** Her ürün için fiyat geçmişi grafiği ve temel metrikler görüntülenir.

## Komutlar

- `!ekle <Trendyol Linki>` - Takip edilecek ürün ekler
- `!takiptekiler` - Takip edilen ürünleri listeler
- `!bilgi <Ürün ID veya URL>` - Belirtilen ürün hakkında detaylı bilgi verir
- `!sil <Ürün ID>` - Takip edilen bir ürünü listeden çıkarır
- `!güncelle <Ürün ID>` - Ürün bilgilerini manuel olarak günceller
- `!yardım` - Yardım mesajını gösterir

## Proje Yapısı

`trendyol` klasörünüzün içeriği genel olarak aşağıdaki gibi olacaktır. Bazı dosyalar AI tarafından eklenmiş alternatifler veya ek notlar olabilir:

- `main.py` - Ana bot dosyası
- `database.py` - Veritabanı işlemleri
- `scraper.py` - Trendyol ürün bilgilerini çekme işlemleri
- `cogs/product_commands.py` - Bot komutları
- `.env` - Konfigürasyon dosyası (sizin oluşturmanız gerekir)
- `proxies.txt` - Proxy listesi (isteğe bağlı, proxy kullanılacaksa oluşturulur)
- `requirements.txt` - Gerekli Python paketleri
- `init_db.py` - Veritabanını başlatan script
- `data/` - Veritabanı dosyalarının saklandığı klasör
  - `trendyol_tracker.sqlite` - Ana veritabanı dosyası
  - `database.sqlite` - Yedek veritabanı dosyası (veya `BACKUP_DATABASE_PATH` ile belirtilen dosya)

**AI Tarafından Oluşturulmuş Olabilecek Ek Dosyalar (`trendyol` klasörü içinde):**

- `create_database_sqlite.py`: Muhtemelen `init_db.py`'ye alternatif bir veritabanı oluşturma scripti.
- `database_alt.py`: Muhtemelen `database.py`'ye alternatif bir veritabanı modülü.
- `install_requirements.py`: `pip install -r requirements.txt` komutuna alternatif bir Python scripti ile paket yükleme denemesi olabilir.
- `manuel_kurulum.txt`: Manuel kurulum adımlarını veya ek notları içeren bir metin dosyası olabilir. İncelemenizde fayda var.
- `req.txt`: `requirements.txt`'ye alternatif veya farklı bir bağımlılık listesi olabilir.
- `scraper_alt.py`: Muhtemelen `scraper.py`'ye alternatif bir ürün bilgisi çekme modülü.
- `requirements_fix.txt`: Windows'ta Türkçe karakter sorunları için hazırlanmış alternatif bir bağımlılık listesi.

## Sorun Giderme

- **Python veya pip komutu bulunamadı hatası**: Python kurulumu sırasında "Add Python to PATH" seçeneğini işaretlediğinizden emin olun. Değilse, Python'ı PATH'e manuel olarak eklemeniz veya tam yolunu (örn: `C:\Python39\python.exe`) kullanarak komutları çalıştırmanız gerekebilir.
- **Windows'ta pip kurulum sorunu**: Türkçe karakter içeren dizinlerde pip kurulumu sorun çıkarabilir. Bu durumda, eğer mevcutsa `requirements_fix.txt` kullanın veya projeyi `C:\projects\bot` gibi basit bir yola taşıyın.
- **Sanal ortam hataları**: Sanal ortamı doğru oluşturup aktifleştirdiğinizden emin olun. Komut satırınızın başında `(venv)` gibi bir ifade görmelisiniz.
- **Veritabanı bağlantı hatası**: Eğer veritabanıyla ilgili sorun yaşıyorsanız, `data` klasörünün var olduğundan ve yazma izinlerine sahip olduğunuzdan emin olun. `init_db.py` (veya alternatif olarak `create_database_sqlite.py`) scriptini çalıştırarak yeni bir veritabanı oluşturmayı deneyebilirsiniz.
- **Proxy bağlantı sorunları**:
  - `.env` dosyasında `PROXY_ENABLED=False` ayarını kullanarak proxy kullanımını tamamen devre dışı bırakabilirsiniz.
  - Alternatif olarak kendi çalışan proxy'lerinizi `proxies.txt` dosyasına ekleyebilirsiniz.
  - Proxy sorunları genellikle "Max retries exceeded" veya "Connection timed out" gibi hatalarla görünür.

## Proxy Kullanımı

Bot, (eğer etkinleştirilmişse) `proxies.txt` dosyasındaki proxy listesini kullanır. Kendi proxylerinizi kullanmak isterseniz:

1. `trendyol` klasörünün ana dizininde `proxies.txt` adında bir dosya oluşturun (eğer yoksa).
2. Her satıra bir proxy `IP:PORT` formatında ekleyin (örn: `123.456.789.012:8080`).
3. Yorum satırlarını `#` ile başlatabilirsiniz.
4. `.env` dosyasında `PROXY_ENABLED=True` olduğundan emin olun.

Eğer aşağıdaki gibi bir hata mesajı görürseniz:
```
Max retries exceeded with url: ... (Caused by ProxyError('Unable to connect to proxy', ConnectTimeoutError(...)))
```
Bu, proxy'nin yanıt vermediği anlamına gelir. Bu durumda:
1. `.env` dosyasında `PROXY_ENABLED=False` ayarlayarak proxy'leri devre dışı bırakabilirsin, veya
2. `proxies.txt` dosyasına daha güvenilir ve çalışan proxy'ler ekleyebilirsin.

## Lisans

Bu proje MIT lisansı altında lisanslanmıştır. Daha fazla bilgi için proje içerisindeki `LICENSE` dosyasına (eğer varsa) bakın.