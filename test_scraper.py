from scraper import TrendyolScraper
import json

def test():
    scraper = TrendyolScraper()
    urls = [
        "https://www.trendyol.com/apple/airpods-pro-2-p-733066806",
    ]
    
    for url in urls:
        print(f"\nTest ediliyor: {url}")
        result = scraper.scrape_product(url)
        if result:
            print(f"Başarılı!")
            print(f"Ürün: {result.get('name')}")
            print(f"Fiyat: {result.get('current_price')} TL")
        else:
            print("Başarısız!")

if __name__ == "__main__":
    test()
