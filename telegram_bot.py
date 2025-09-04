# telegram_bot.py

import logging
import os
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

from database import Database
from scraper import TrendyolScraper

# .env dosyasını yükle
load_dotenv()

# Logging yapılandırması
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Environment variables
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
ADMIN_CHAT_ID = os.getenv('ADMIN_CHAT_ID')
CHECK_INTERVAL = int(os.getenv('CHECK_INTERVAL', 3600))
DATABASE_PATH = os.getenv('DATABASE_PATH', 'data/trendyol_tracker.sqlite')

# Global nesneler
db = Database(db_name=DATABASE_PATH)
scraper = TrendyolScraper()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/start komutu için handler."""
    await update.message.reply_text(
        'Merhaba! Ben Trendyol Fiyat Takip Botu.\n'
        'Ürün eklemek için /ekle <Trendyol URL> komutunu kullanabilirsiniz.\n'
        'Yardım için /yardim komutunu kullanabilirsiniz.'
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/yardim komutu için handler."""
    help_text = (
        " İşte kullanabileceğiniz komutlar:\n"
        " /start - Botu başlatır.\n"
        " /yardim - Bu yardım mesajını gösterir.\n"
        " /ekle <URL> - Takip etmek için yeni bir ürün ekler.\n"
        " /listele - Takip ettiğiniz ürünleri listeler.\n"
        " /sil <Ürün ID> - Bir ürünü takipten çıkarır.\n"
        " /bilgi <Ürün ID> - Bir ürün hakkında detaylı bilgi verir.\n"
        " /guncelle <Ürün ID> - Bir ürünün fiyatını manuel olarak günceller.\n"
    )
    if str(update.message.chat_id) == ADMIN_CHAT_ID:
        help_text += "\n--- Admin Komutları ---\n"
        help_text += "/admin_listele_tumunu - Tüm kullanıcıların ürünlerini listeler.\n"
    await update.message.reply_text(help_text)

async def ekle(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/ekle komutu için handler."""
    chat_id = str(update.message.chat_id)
    user_id = str(update.message.from_user.id)

    if not context.args:
        await update.message.reply_text("Lütfen bir Trendyol ürün URL'si girin. Örnek: /ekle <URL>")
        return

    url = context.args[0]

    if not scraper.is_valid_url(url):
        await update.message.reply_text("❌ Geçersiz Trendyol URL'si.")
        return

    await update.message.reply_text("Ürün bilgileri alınıyor, lütfen bekleyin...")

    product_data = scraper.scrape_product(url)
    if not product_data or not product_data.get('success', False):
        await update.message.reply_text("❌ Ürün bilgileri alınamadı. URL'yi kontrol edin.")
        return

    if product_data.get('current_price') is None:
        await update.message.reply_text("❌ Ürün fiyat bilgisi alınamadı. Stokta olmayabilir.")
        return

    if db.add_product(product_data, chat_id, user_id):
        message = (
            f"✅ *Ürün Takibe Alındı*\n\n"
            f"*{product_data['name']}*\n\n"
            f"Mevcut Fiyat: *{product_data.get('current_price', 0):.2f} TL*\n"
            f"[Trendyol'da Görüntüle]({product_data['url']})"
        )
        if product_data.get('image_url'):
            await update.message.reply_photo(
                photo=product_data['image_url'],
                caption=message,
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(message, parse_mode='Markdown')
    else:
        await update.message.reply_text("❌ Bu ürün zaten takip listenizde.")

async def listele(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/listele komutu için handler."""
    chat_id = str(update.message.chat_id)
    products = db.get_all_products(chat_id=chat_id)

    if not products:
        await update.message.reply_text("📋 Takip edilen ürün bulunmuyor.")
        return

    message = f"📋 *Takip Edilen Ürünler* ({len(products)} adet)\n\n"
    for product in products:
        message += (
            f"📦 *{product['name']}*\n"
            f"🆔 ID: `{product['product_id']}`\n"
            f"💰 Fiyat: {product.get('current_price', 0):.2f} TL\n\n"
        )

    await update.message.reply_text(message, parse_mode='Markdown')

async def sil(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/sil komutu için handler."""
    chat_id = str(update.message.chat_id)

    if not context.args:
        await update.message.reply_text("Lütfen bir ürün ID'si girin. Örnek: /sil <Ürün ID>")
        return

    product_id = context.args[0]
    product = db.get_product(product_id)

    if not product or product.get('chat_id') != chat_id:
        await update.message.reply_text("❌ Bu ID'ye sahip bir ürün takip listenizde bulunamadı.")
        return

    if db.delete_product(product_id, chat_id=chat_id):
        await update.message.reply_text(f"✅ *{product['name']}* adlı ürün takip listesinden silindi.", parse_mode='Markdown')
    else:
        await update.message.reply_text("❌ Ürün silinirken bir hata oluştu.")

async def bilgi(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/bilgi komutu için handler."""
    if not context.args:
        await update.message.reply_text("Lütfen bir ürün ID'si girin. Örnek: /bilgi <Ürün ID>")
        return

    product_id = context.args[0]
    product = db.get_product(product_id)

    if not product:
        await update.message.reply_text("❌ Bu ID'ye sahip bir ürün bulunamadı.")
        return

    history = db.get_price_history(product_id, limit=5)
    message = (
        f"📦 *{product['name']}*\n\n"
        f"🆔 ID: `{product['product_id']}`\n"
        f"💰 Mevcut Fiyat: {product.get('current_price', 0):.2f} TL\n"
        f"🔗 [Trendyol'da Görüntüle]({product['url']})\n\n"
        f"📜 *Fiyat Geçmişi (Son 5):*\n"
    )
    if history:
        for item in history:
            message += f"- {item['date']}: {item['price']:.2f} TL\n"
    else:
        message += "Fiyat geçmişi bulunmuyor.\n"

    if product.get('image_url'):
        await update.message.reply_photo(
            photo=product['image_url'],
            caption=message,
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text(message, parse_mode='Markdown')

async def guncelle(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/guncelle komutu için handler."""
    if not context.args:
        await update.message.reply_text("Lütfen bir ürün ID'si girin. Örnek: /guncelle <Ürün ID>")
        return

    product_id = context.args[0]
    product = db.get_product(product_id)

    if not product:
        await update.message.reply_text("❌ Bu ID'ye sahip bir ürün bulunamadı.")
        return

    await update.message.reply_text(f"*{product['name']}* için bilgiler güncelleniyor...", parse_mode='Markdown')

    new_data = scraper.scrape_product(product['url'])
    if not new_data or not new_data.get('success', False) or new_data.get('current_price') is None:
        await update.message.reply_text("❌ Ürün bilgileri güncellenemedi.")
        return

    old_price = product['current_price']
    new_price = new_data['current_price']

    db.update_product_price(product_id, new_price)

    message = (
        f"✅ *Ürün Güncellendi*\n\n"
        f"*{product['name']}*\n"
        f"Eski Fiyat: {old_price:.2f} TL\n"
        f"Yeni Fiyat: {new_price:.2f} TL"
    )
    await update.message.reply_text(message, parse_mode='Markdown')

async def admin_listele_tumunu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/admin_listele_tumunu komutu için handler."""
    chat_id = str(update.message.chat_id)
    if chat_id != ADMIN_CHAT_ID:
        await update.message.reply_text("Bu komutu kullanma yetkiniz yok.")
        return

    products = db.get_all_products()

    if not products:
        await update.message.reply_text("📋 Veritabanında hiç ürün bulunmuyor.")
        return

    message = f"📋 *Tüm Kullanıcıların Ürünleri* ({len(products)} adet)\n\n"
    for product in products:
        message += (
            f"📦 *{product['name']}*\n"
            f"🆔 ID: `{product['product_id']}`\n"
            f"💰 Fiyat: {product.get('current_price', 0):.2f} TL\n"
            f"👤 Ekleyen Chat ID: `{product['chat_id']}`\n\n"
        )

    # Mesaj çok uzun olabileceğinden, parçalara ayırarak gönder
    for i in range(0, len(message), 4096):
        await update.message.reply_text(message[i:i+4096], parse_mode='Markdown')

async def check_prices(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Fiyatları periyodik olarak kontrol eder ve değişiklikleri bildirir."""
    logger.info("Fiyat kontrolü başlıyor...")
    products = db.get_all_products()

    if not products:
        logger.info("Takip edilen ürün bulunamadı.")
        return

    logger.info(f"Toplam {len(products)} ürün kontrol edilecek.")

    for product in products:
        try:
            product_data = scraper.scrape_product(product['url'])

            if not product_data or not product_data.get('success', False) or product_data.get('current_price') is None:
                logger.warning(f"Ürün bilgileri alınamadı: {product.get('product_id','Bilinmeyen ID')}")
                continue

            old_price = product['current_price']
            new_price = product_data['current_price']

            if old_price != new_price:
                db.update_product_price(product['product_id'], new_price)

                chat_id = product.get('chat_id')
                message = (
                    f"💸 *Fiyat Değişimi Bildirimi*\n\n"
                    f"*{product['name']}*\n\n"
                    f"Eski Fiyat: {old_price:.2f} TL\n"
                    f"Yeni Fiyat: *{new_price:.2f} TL*\n\n"
                    f"[Trendyol'da Görüntüle]({product['url']})"
                )

                if product.get('image_url'):
                    await context.bot.send_photo(
                        chat_id=chat_id,
                        photo=product['image_url'],
                        caption=message,
                        parse_mode='Markdown'
                    )
                else:
                    await context.bot.send_message(
                        chat_id=chat_id,
                        text=message,
                        parse_mode='Markdown'
                    )
                logger.info(f"Fiyat değişimi bildirimi gönderildi: {product['name']} -> {chat_id}")

        except Exception as e:
            logger.error(f"Ürün kontrolünde hata: {product.get('product_id','Bilinmeyen ID')} - {e}")
            continue
    logger.info("Fiyat kontrolü tamamlandı.")

def main() -> None:
    """Botu başlatır."""
    if not TELEGRAM_TOKEN:
        logger.error("TELEGRAM_TOKEN bulunamadı! Lütfen .env dosyasını kontrol edin.")
        return

    # Application oluştur
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    # Komut handler'larını ekle
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("yardim", help_command))
    application.add_handler(CommandHandler("ekle", ekle))
    application.add_handler(CommandHandler("listele", listele))
    application.add_handler(CommandHandler("sil", sil))
    application.add_handler(CommandHandler("bilgi", bilgi))
    application.add_handler(CommandHandler("guncelle", guncelle))
    application.add_handler(CommandHandler("admin_listele_tumunu", admin_listele_tumunu))

    # Fiyat kontrol döngüsünü başlat
    job_queue = application.job_queue
    job_queue.run_repeating(check_prices, interval=CHECK_INTERVAL, first=10)

    # Botu çalıştır
    application.run_polling()

if __name__ == '__main__':
    main()
