"""Duyuru metinleri — tek kaynak (/duyuru-gonder ile gonderilir).

`LATEST_UPDATE` su anki son calismalarin ozetidir; yeni surum icin metni
guncelleyip komutu calistirmak yeterlidir.
"""

TITLE = "🚀 Trendcord Güncelleme"

LATEST_UPDATE = """**Arkadaşlar, kısa bir özet — neler değişti:**

🔐 **Güvenlik & Gizlilik**
• Web panelinde statik dosyalar artık oturum çerezi üretmiyor — hızlı ve güvenli.
• Güvenlik başlıkları, CSRF koruması ve SVG ikon sistemi yenilendi.
• Gizli kanallara erişim sızıntısı kapatıldı; @everyone'a açık izin verilmiyor.

📺 **Sunucu Kurulumu**
• Bot eklendiği sunucularda tüm yapı otomatik kuruluyor: kategoriler, kanallar, roller.
• Kanal izinleri rol bazlı (Üye / Bot / Mod / Staff) ve her sunucuya göre analiz ediliyor.
• Kanallara açık @everyone/Üye erişimi kapatıldı — artık sadece botun yönettiği yerler açık.
• Silinen kanallar `/setup repair` ile geri geliyor; `/setup-kaldir` yalnızca bize ait olanları temizliyor.
• AutoMod kuralları (spam, toplu mention, davet linki, phishing) artık gerçekten uygulanıyor.

🛡️ **Yeni: Trendcord Bot Owner**
• Trendcord'un kurduğu her sunucuya özel bir **Trendcord Bot Owner** rolü açılıyor.
• Bu rol, **sadece Trendcord'un oluşturduğu kanallarda** tam yetkiye sahip; sunucunun başka hiçbir yerinde etkisi yok.
• Rol yalnızca bot sahibine verilir. Başka biri rolü alırsa otomatik geri alınır. Rol görünmez ve etiketlenemez, yanlışlıkla dağıtılamaz.

🎫 **Destek**
• Destek talepleri artık **yalnızca Trendcord Resmi Sunucusu**'nda açılabiliyor.
• Diğer sunucularda destek kanalı resmi sunucuya yönlendirir.

📱 **Mobil & Arayüz**
• Dashboard, karşılaştırma, alarmlar ve ürün kartları mobilde yeniden düzenlendi.
• Grafikler ve OG görseli düzeltildi; artık taşma/kirpılma yok.

💡 **Daha fazlası**
• Ürün detay sayfası, fiyat geçmişi grafiği, SEO ve sitemap yenilendi.
• Fiyat alarmları ve bildirimler sorunsuz çalışıyor; 404/410 ürünler otomatik arşivleniyor.

📢 Sunucunuzda `#duyurular` kanalını takipte kalın; her değişiklik orada bildirilir.

— Trendcord Ekibi"""

# Eski surumler icin saklama alani
ARCHIVE = []