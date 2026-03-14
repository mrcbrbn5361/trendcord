from scraper import TrendyolScraper
import json

scraper = TrendyolScraper(use_proxy=False)
# Örnek bir Trendyol ürün linki (bu link geçersiz olabilir, gerçek bir tane gerekebilir)
test_url = "https://www.trendyol.com/p-p-1"

print(f"Test ediliyor: {test_url}")
result = scraper.scrape_product(test_url)
print(json.dumps(result, indent=2, ensure_ascii=False))
