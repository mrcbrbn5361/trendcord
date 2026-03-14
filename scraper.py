import requests
import random
import re
import json
import os
from bs4 import BeautifulSoup
from urllib.parse import urlparse, parse_qs
import logging
import time
import ssl
import urllib3

# SSL uyarılarını devre dışı bırak
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class TrendyolScraper:
    def __init__(self, use_proxy=True, timeout=10, max_retries=3, verify_ssl=False):
        """
        Trendyol ürün bilgilerini kazıyıcı sınıf.
        """
        self.use_proxy = use_proxy
        self.proxies = []
        self.working_proxies = []
        self.timeout = timeout
        self.max_retries = max_retries
        self.verify_ssl = verify_ssl
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept-Language': 'tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache'
        }
        
        if use_proxy:
            self.load_proxies()
    
    def load_proxies(self):
        """Proxy'leri proxies.txt dosyasından yükler."""
        try:
            if os.path.exists("proxies.txt"):
                with open("proxies.txt", "r") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#'):
                            self.proxies.append(line)
                logger.info(f"{len(self.proxies)} proxy yüklendi.")
        except Exception as e:
            logger.error(f"Proxy yüklenirken hata oluştu: {e}")
    
    def get_random_proxy(self):
        if not self.proxies and not self.working_proxies:
            return None
        proxy = random.choice(self.working_proxies or self.proxies)
        return {'http': f'http://{proxy}', 'https': f'http://{proxy}'}
    
    def resolve_url(self, url):
        """Kısa linkleri ve yönlendirmeleri çözer."""
        if not url.startswith('http'):
            return url

        try:
            # ty.gl veya diğer yönlendirmeler için
            response = requests.head(url, headers=self.headers, allow_redirects=True, timeout=self.timeout, verify=self.verify_ssl)
            return response.url
        except Exception as e:
            logger.error(f"URL çözümlenirken hata: {e}")
            return url

    def extract_product_id(self, url):
        """URL'den ürün ID'sini çıkarır."""
        try:
            if url.isdigit():
                return url

            # URL'yi temizle (query parametrelerini ayır)
            parsed_url = urlparse(url)
            path = parsed_url.path
            
            # Standart: /...-p-12345
            match = re.search(r'-p-(\d+)', path)
            if match:
                return match.group(1)
            
            # Query: ?productId=12345
            query_params = parse_qs(parsed_url.query)
            if 'productId' in query_params:
                return query_params['productId'][0]
                
            return None
        except Exception as e:
            logger.error(f"Ürün ID çıkarılırken hata: {e}")
            return None
    
    def scrape_product(self, url):
        """Ürün bilgilerini çeker."""
        resolved_url = self.resolve_url(url)
        product_id = self.extract_product_id(resolved_url)
        
        if not product_id:
            logger.error(f"Geçerli bir ürün ID'si bulunamadı: {url}")
            return None
        
        # Canonical URL
        product_url = f"https://www.trendyol.com/p-p-{product_id}"
        
        result = self._scrape_without_proxy(product_url)
        if result is None and self.use_proxy:
            result = self._try_with_proxy(product_url)

        if result:
            result['url'] = product_url # Her zaman temiz URL'yi kaydet
        return result
    
    def _try_with_proxy(self, product_url):
        for i in range(self.max_retries):
            proxy = self.get_random_proxy()
            if not proxy: break
            try:
                response = requests.get(product_url, headers=self.headers, proxies=proxy, timeout=self.timeout, verify=self.verify_ssl)
                response.raise_for_status()
                return self._extract_product_data(response, product_url)
            except Exception as e:
                logger.error(f"Proxy hatası: {e}")
                time.sleep(1)
        return None
    
    def _scrape_without_proxy(self, product_url):
        try:
            response = requests.get(product_url, headers=self.headers, timeout=self.timeout, verify=self.verify_ssl)
            response.raise_for_status()
            return self._extract_product_data(response, product_url)
        except Exception as e:
            logger.error(f"İstek hatası: {e}")
            return None
    
    def _extract_product_data(self, response, product_url):
        try:
            soup = BeautifulSoup(response.text, 'html.parser')
            product_id = self.extract_product_id(product_url)
            
            # Farklı seçicileri dene
            name_selectors = ['h1.pr-new-br', 'h1.product-name', 'h1.pr-in-nm', '.product-name-container h1']
            product_name = None
            for selector in name_selectors:
                element = soup.select_one(selector)
                if element:
                    product_name = element.get_text(strip=True)
                    break
            
            price_selectors = ['.prc-dsc', '.product-price', '.pr-in-at-pr-dsc', '.featured-fiyat']
            current_price = None
            for selector in price_selectors:
                element = soup.select_one(selector)
                if element:
                    price_str = element.get_text(strip=True).replace('TL', '').replace(' ', '').replace('.', '').replace(',', '.')
                    try:
                        current_price = float(re.findall(r"\d+\.\d+|\d+", price_str)[0])
                        break
                    except: continue

            original_price_selectors = ['.prc-org', '.product-price-old', '.pr-in-at-pr-org']
            original_price = current_price
            for selector in original_price_selectors:
                element = soup.select_one(selector)
                if element:
                    price_str = element.get_text(strip=True).replace('TL', '').replace(' ', '').replace('.', '').replace(',', '.')
                    try:
                        original_price = float(re.findall(r"\d+\.\d+|\d+", price_str)[0])
                        break
                    except: continue
            
            image_selectors = ['img.ph-gl-img', '.product-slide img', '.base-product-image img']
            image_url = None
            for selector in image_selectors:
                element = soup.select_one(selector)
                if element:
                    image_url = element.get('src')
                    if image_url and not image_url.startswith('http'):
                        image_url = 'https:' + image_url
                    break
            
            if not product_name or current_price is None:
                # Script içinden çekmeyi dene (window.__PRODUCT_DETAIL_APP_INITIAL_STATE__)
                scripts = soup.find_all('script')
                for script in scripts:
                    if 'window.__PRODUCT_DETAIL_APP_INITIAL_STATE__' in script.text:
                        try:
                            json_text = script.text.split('window.__PRODUCT_DETAIL_APP_INITIAL_STATE__ = ')[1].split(';')[0]
                            data = json.loads(json_text)
                            product = data['product']
                            product_name = product['name']
                            current_price = product['price']['sellingPrice']['value']
                            original_price = product['price']['originalPrice']['value']
                            image_url = "https://cdn.dsmcdn.com" + product['images'][0]
                            break
                        except: continue

            return {
                'product_id': product_id,
                'name': product_name,
                'url': product_url,
                'image_url': image_url,
                'current_price': current_price,
                'original_price': original_price,
                'success': True if product_name and current_price else False
            }
        except Exception as e:
            logger.error(f"Veri çıkarma hatası: {e}")
            return None
    
    def is_valid_url(self, url):
        if url.isdigit(): return True
        parsed = urlparse(url)
        return "trendyol.com" in parsed.netloc or "ty.gl" in parsed.netloc
