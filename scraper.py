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
    def __init__(self, use_proxy=True, timeout=5, max_retries=3, verify_ssl=False):
        """
        Trendyol ürün bilgilerini kazıyıcı sınıf.
        
        Args:
            use_proxy (bool): Proxy kullanımını etkinleştirir.
            timeout (int): İstek zaman aşımı süresi (saniye cinsinden)
            max_retries (int): Maksimum yeniden deneme sayısı
            verify_ssl (bool): SSL sertifikalarını doğrulayıp doğrulamama
        """
        self.use_proxy = use_proxy
        self.proxies = []
        self.working_proxies = []  # Çalışan proxyleri sakla
        self.bad_proxies = {} # Kötü proxyleri sakla {proxy: timestamp}
        self.bad_proxy_timeout = 1800 # 30 dakika
        self.timeout = timeout
        self.max_retries = max_retries
        self.verify_ssl = verify_ssl
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept-Language': 'tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br, zstd'
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
                        # Yorum satırlarını ve boş satırları atla
                        if line and not line.startswith('#'):
                            self.proxies.append(line)
                logger.info(f"{len(self.proxies)} proxy yüklendi.")
            else:
                logger.warning("proxies.txt dosyası bulunamadı!")
        except Exception as e:
            logger.error(f"Proxy yüklenirken hata oluştu: {e}")
    
    def clean_bad_proxies(self):
        """Zaman aşımına uğramış kötü proxyleri temizler."""
        now = time.time()
        expired = [p for p, t in self.bad_proxies.items() if now - t > self.bad_proxy_timeout]
        for p in expired:
            del self.bad_proxies[p]
            import logging
            logging.getLogger(__name__).info(f"Proxy tekrar aktif edildi: {p}")

    def get_random_proxy(self):
        """Rastgele bir proxy döndürür. Önce çalışan proxylerden denenir."""
        self.clean_bad_proxies()

        if not self.proxies and not self.working_proxies:
            return None
        
        # Sadece kötü olmayan proxyleri seç
        available_proxies = [p for p in self.proxies if p not in self.bad_proxies]

        # Önce çalışan proxylerden seç (eğer varsa ve kötü değilse)
        available_working = [p for p in self.working_proxies if p not in self.bad_proxies]

        if available_working:
            proxy = random.choice(available_working)
        elif available_proxies:
            proxy = random.choice(available_proxies)
        else:
            return None
            
        return {
            'http': f'http://{proxy}',
            'https': f'http://{proxy}'
        }
    
    def extract_product_id(self, url):
        """URL'den ürün ID'sini çıkarır."""
        try:
            # Eğer doğrudan ürün ID girilmişse
            if url.isdigit():
                return url
                
            # URL'yi ayrıştır
            parsed_url = urlparse(url)
            
            # Eğer path'de ürün ID'si varsa (örn: "/kalem-p-123456789")
            path_match = re.search(r'/[^/]+-p-(\d+)', parsed_url.path)
            if path_match:
                return path_match.group(1)
            
            # Eğer query string'de varsa (örn: "?boutiqueId=123&merchantId=456&productId=789")
            query_params = parse_qs(parsed_url.query)
            if 'productId' in query_params:
                return query_params['productId'][0]
                
            # Son çare olarak URL içindeki tüm sayıları ara
            numbers = re.findall(r'p-(\d+)', url)
            if numbers:
                return numbers[0]
                
            return None
        except Exception as e:
            logger.error(f"Ürün ID çıkarılırken hata: {e}")
            return None
    
    def scrape_product(self, url):
        """
        Ürün bilgilerini çeker.
        
        Args:
            url (str): Trendyol ürün URL'si veya ürün ID'si.
            
        Returns:
            dict: Ürün bilgilerini içeren sözlük. Başarısız olursa None.
        """
        product_id = self.extract_product_id(url)
        if not product_id:
            logger.error(f"Geçerli bir ürün ID'si bulunamadı: {url}")
            return None
        
        # Ürün URL'sini oluştur
        if url.isdigit():
            product_url = f"https://www.trendyol.com/sr?pi={url}"
        else:
            product_url = url
        
        # Geçici olarak proxy kullanımını devre dışı bırak
        # İlk başta direkt proxy olmadan dene
        result = self._scrape_without_proxy(product_url)
        
        # Eğer başarısız olursa ve proxy kullanımı etkinse, proxy ile dene
        if result is None and self.use_proxy and (self.proxies or self.working_proxies):
            return self._try_with_proxy(product_url)
        return result
    
    def _try_with_proxy(self, product_url):
        """Proxy kullanarak ürün bilgilerini çekmeyi dener."""
        retries = 0
        while retries < self.max_retries:
            # İstek için proxy seç
            proxy = self.get_random_proxy()
            if not proxy:
                logger.warning("Kullanılabilir proxy kalmadı, proxysiz deneniyor.")
                return self._scrape_without_proxy(product_url)
            
            try:
                logger.info(f"Proxy kullanılıyor: {proxy} (Deneme {retries+1}/{self.max_retries})")
                response = requests.get(product_url, headers=self.headers, proxies=proxy, timeout=self.timeout, verify=self.verify_ssl)
                response.raise_for_status()
                
                # Proxy çalıştı, çalışan listesine ekle
                proxy_str = proxy['http'].replace('http://', '')
                if proxy_str not in self.working_proxies:
                    self.working_proxies.append(proxy_str)
                
                # Ürün verilerini çıkar
                return self._extract_product_data(response, product_url)
            
            except requests.exceptions.RequestException as e:
                logger.error(f"Proxy bağlantı hatası: {e}")
                # Proxy'yi kötü listesine ekle
                proxy_str = proxy['http'].replace('http://', '')
                self.bad_proxies[proxy_str] = time.time()
                
                if proxy_str in self.working_proxies:
                    self.working_proxies.remove(proxy_str)
                    
                logger.warning(f"Kötü proxy işaretlendi: {proxy_str}")
                
                retries += 1
                # Kısa bir bekleme
                time.sleep(1)
        
        # Tüm proxyler başarısız oldu, proxysiz dene
        logger.warning("Tüm proxy denemeleri başarısız oldu, proxysiz deneniyor...")
        return self._scrape_without_proxy(product_url)
    
    def _scrape_without_proxy(self, product_url):
        """Proxy kullanmadan ürün bilgilerini çekmeyi dener."""
        try:
            logger.info("Proxysiz istek yapılıyor...")
            response = requests.get(product_url, headers=self.headers, timeout=self.timeout, verify=self.verify_ssl)
            response.raise_for_status()
            return self._extract_product_data(response, product_url)
        except requests.exceptions.RequestException as e:
            logger.error(f"Proxysiz istek hatası: {e}")
            return None
        except Exception as e:
            logger.error(f"Ürün çekilirken hata: {e}")
            return None
    
    def _extract_product_data(self, response, product_url):
        """HTML yanıtından ürün verilerini çıkarır."""
        try:
            soup = BeautifulSoup(response.text, 'html.parser')
            product_id = self.extract_product_id(product_url)
            
            # 1. Yöntem: JSON State'den çekme (En sağlamı)
            state_script = None
            for script in soup.find_all('script'):
                if script.string and '__PRODUCT_DETAIL_APP_INITIAL_STATE__' in script.string:
                    state_script = script
                    break
                if script.text and '__PRODUCT_DETAIL_APP_INITIAL_STATE__' in script.text:
                    state_script = script
                    break

            if state_script:
                try:
                    script_content = state_script.string or state_script.text
                    json_match = re.search(r'__PRODUCT_DETAIL_APP_INITIAL_STATE__\s*=\s*({.*?});', script_content, re.DOTALL)
                    if json_match:
                        json_text = json_match.group(1)
                        state_data = json.loads(json_text)

                        product = state_data.get('product', {})
                        product_name = product.get('name') or product.get('nameWithProductCode')

                        # Fiyatı bul
                        price_data = product.get('price', {})
                        current_price = None
                        original_price = None

                        if price_data:
                            current_price = price_data.get('sellingPrice', {}).get('value')
                            original_price = price_data.get('originalPrice', {}).get('value')

                        # Resimler
                        images = product.get('images', [])
                        image_url = images[0] if images else None
                        if image_url and not image_url.startswith('http'):
                            image_url = 'https://www.trendyol.com' + image_url

                        if product_name and current_price:
                            return {
                                'product_id': product_id,
                                'name': product_name,
                                'url': product_url,
                                'image_url': image_url,
                                'current_price': float(current_price),
                                'original_price': float(original_price or current_price),
                                'success': True
                            }
                except Exception as e:
                    logger.warning(f"JSON state parse hatası: {e}")

            # 2. Yöntem: CSS Selectors (Fallback)
            try:
                product_name = soup.select_one('h1.pr-new-br').text.strip()
            except:
                try:
                    product_name = soup.select_one('h1.product-name').text.strip()
                except:
                    product_name = None
            
            try:
                current_price_elem = soup.select_one('.prc-dsc')
                current_price = float(current_price_elem.text.strip().replace('TL', '').replace('.', '').replace(',', '.').strip())
            except:
                current_price = None
            
            try:
                original_price_elem = soup.select_one('.prc-org')
                original_price = float(original_price_elem.text.strip().replace('TL', '').replace('.', '').replace(',', '.').strip())
            except:
                original_price = current_price
            
            try:
                image_url = soup.select_one('img.ph-gl-img, .product-slide img').get('src')
                if image_url and not image_url.startswith('http'):
                    image_url = 'https:' + image_url
            except:
                image_url = None
            
            if product_name and current_price:
                return {
                    'product_id': product_id,
                    'name': product_name,
                    'url': product_url,
                    'image_url': image_url,
                    'current_price': current_price,
                    'original_price': original_price,
                    'success': True
                }
            
            return None
        except Exception as e:
            logger.error(f"Ürün verisi çıkarılırken hata: {e}")
            return None
    
    def is_valid_url(self, url):
        """URL'nin Trendyol URL'si olup olmadığını kontrol eder."""
        if url.isdigit():  # Eğer sadece ürün ID ise
            return True
            
        try:
            parsed_url = urlparse(url)
            return "trendyol.com" in parsed_url.netloc
        except:
            return False 
