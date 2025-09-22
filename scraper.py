import requests
from bs4 import BeautifulSoup
import re
from config import USER_AGENT
import logging
import json
import time
import random
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from urllib.parse import urlparse, parse_qs

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Request configuration from user's new code
MAX_RETRIES = 3
BACKOFF_FACTOR = 2
TIMEOUT = 15
MIN_DELAY = 1
MAX_DELAY = 3

class TrendyolScraper:
    def __init__(self, use_proxy=False, verify_ssl=True):
        """
        Initializes the scraper.
        Proxy functionality has been removed in favor of a more robust session management.
        """
        self.verify_ssl = verify_ssl

    # --- Core Request and Session Logic (from new code) ---

    def _create_session(self):
        """Create a robust HTTP session with retry strategy."""
        session = requests.Session()
        session.verify = self.verify_ssl
        
        retry_strategy = Retry(
            total=MAX_RETRIES,
            status_forcelist=[429, 500, 502, 503, 504],
            backoff_factor=BACKOFF_FACTOR,
            allowed_methods=["HEAD", "GET", "OPTIONS"]
        )

        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)

        return session

    def _add_random_delay(self):
        """Add random delay between requests to avoid rate limiting."""
        delay = random.uniform(MIN_DELAY, MAX_DELAY)
        time.sleep(delay)
        logger.debug(f"Added {delay:.2f}s delay")

    def _get_full_url(self, url):
        """Follow redirects to get the full URL if it's a shortened link."""
        try:
            self._add_random_delay()
            headers = {
                'User-Agent': USER_AGENT,
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'tr-TR,tr;q=0.8,en-US;q=0.5,en;q=0.3',
                'Accept-Encoding': 'gzip, deflate',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1'
            }
            session = self._create_session()
            response = session.head(url, headers=headers, allow_redirects=True, timeout=TIMEOUT)
            return response.url
        except Exception as e:
            logger.error(f"Error following redirect for {url}: {e}")
            return url

    # --- Compatibility Methods (from old scraper) ---

    def extract_product_id(self, url):
        """Extracts the product ID from a Trendyol URL."""
        try:
            if url.isdigit():
                return url
            parsed_url = urlparse(url)
            path_match = re.search(r'/[^/]+-p-(\d+)', parsed_url.path)
            if path_match:
                return path_match.group(1)
            query_params = parse_qs(parsed_url.query)
            if 'productId' in query_params:
                return query_params['productId'][0]
            numbers = re.findall(r'p-(\d+)', url)
            if numbers:
                return numbers[0]
            return None
        except Exception as e:
            logger.error(f"Error extracting product ID: {e}")
            return None

    def is_valid_url(self, url):
        """Checks if the URL is a valid Trendyol URL or a product ID."""
        if url.isdigit():
            return True
        return bool(re.match(r'https?://(www\.)?(trendyol\.com|ty\.gl|tyml\.gl|trendyol-milla\.com).*', url))

    # --- Main Scraping Logic ---

    def scrape_product(self, url):
        """
        Public method to scrape product info and return it in the expected dictionary format.
        This method orchestrates the scraping process and formats the output.
        """
        product_id = self.extract_product_id(url)
        if not product_id:
            logger.error(f"Could not extract product ID from URL: {url}")
            return {'success': False, 'error': 'Invalid URL or Product ID', 'current_price': None}

        product_url = f"https://www.trendyol.com/any-p-{product_id}" if url.isdigit() else url

        scraped_data = self._scrape_page(product_url)

        if not scraped_data or scraped_data.get("error"):
            return {'success': False, 'error': scraped_data.get("error", "Unknown error"), 'current_price': None}
        
        # Combine scraped data with necessary IDs and URLs
        final_data = {
            'product_id': product_id,
            'name': scraped_data.get('product_name'),
            'url': product_url,
            'image_url': scraped_data.get('image_url'),
            'current_price': scraped_data.get('price'),
            'original_price': scraped_data.get('original_price', scraped_data.get('price')), # Fallback
            'success': True
        }
        return final_data

    def _scrape_page(self, url):
        """
        Performs the actual page scraping, integrating all logic from the new code.
        Returns a dictionary with scraped information.
        """
        last_error = None
        for attempt in range(MAX_RETRIES):
            try:
                logger.info(f"Scraping attempt {attempt + 1}/{MAX_RETRIES} for {url}")
                full_url = self._get_full_url(url)

                if not self.is_valid_url(full_url):
                    return {"error": "URL does not belong to Trendyol"}

                if attempt > 0:
                    delay = BACKOFF_FACTOR ** attempt + random.uniform(1, 3)
                    time.sleep(delay)
                else:
                    self._add_random_delay()

                headers = {'User-Agent': USER_AGENT, 'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8', 'Accept-Language': 'tr-TR,tr;q=0.8,en-US;q=0.5,en;q=0.3', 'Accept-Encoding': 'gzip, deflate', 'Connection': 'keep-alive', 'Upgrade-Insecure-Requests': '1', 'Cache-Control': 'no-cache', 'Pragma': 'no-cache'}
                session = self._create_session()
                response = session.get(full_url, headers=headers, timeout=TIMEOUT)

                if response.status_code != 200:
                    last_error = f"HTTP {response.status_code}"
                    continue

                soup = BeautifulSoup(response.text, 'lxml')
                
                # --- All extraction logic is now called from here ---
                product_name = self._extract_product_name(soup)
                
                if self._is_sold_out(soup):
                    logger.info(f"Product is sold out: {product_name}")
                    return {"product_name": product_name, "price": 0, "original_price": 0, "error": "Tükendi"}

                price, original_price = self._extract_prices(soup)
                image_url = self._extract_image_url(soup)

                if not product_name:
                    return {"error": "Could not extract product name"}
                if price is None:
                    return {"product_name": product_name, "error": "Could not extract price"}

                logger.info(f"Successfully scraped - Product: {product_name}, Price: {price} TL")
                return {
                    "product_name": product_name,
                    "price": price,
                    "original_price": original_price,
                    "image_url": image_url,
                    "error": None
                }

            except Exception as e:
                last_error = f"Unexpected error: {str(e)}"
                logger.warning(f"Unexpected error for {url}, attempt {attempt + 1}: {e}")
        
        return {"error": f"Failed after {MAX_RETRIES} attempts. Last error: {last_error}"}

    # --- Granular Extraction Methods (from new code, made into class methods) ---

    def _extract_price_from_text(self, text):
        """Helper to extract numeric price value from text."""
        if not text: return None
        price_text = text.strip().replace('.', '').replace(',', '.')
        match = re.search(r'(\d+[,.]\d+|\d+)', price_text)
        if match:
            price = float(match.group(1).replace(',', '.'))
            if 0.01 <= price <= 100000: return price
        return None

    def _extract_product_name(self, soup):
        """Extract product name using various methods."""
        h1_tag = soup.find('h1', attrs={'data-testid': 'product-name'})
        if h1_tag: return h1_tag.text.strip()
        if soup.find('h1'): return soup.find('h1').text.strip()
        if soup.find('title'): return soup.find('title').text.split('-')[0].strip()
        return None

    def _is_sold_out(self, soup):
        """Check if the product is sold out using various methods."""
        # Method 1: Add to cart button
        add_to_cart_btn = soup.find('button', attrs={'data-testid': 'add-to-cart-button'})
        if add_to_cart_btn:
            btn_text = add_to_cart_btn.get_text().strip()
            if 'Sepete Ekle' in btn_text: return False
            if 'Tükendi' in btn_text or 'Stok Yok' in btn_text or 'Mevcut Değil' in btn_text: return True

        # Method 2: Buy now button
        buy_now_btn = soup.find('button', class_='buy-now-button')
        if buy_now_btn and 'Şimdi Al' in buy_now_btn.get_text().strip(): return False

        # Method 3: Disabled button
        disabled_buttons = soup.find_all('button', disabled=True)
        for btn in disabled_buttons:
            if any('add-to-cart' in c or 'sepete-ekle' in c for c in btn.get('class', [])): return True

        # Method 4: General out of stock messages
        visible_elements = soup.find_all(['div', 'span', 'p'], class_=lambda x: x and 'stock' in ' '.join(x).lower())
        for element in visible_elements:
            text = element.get_text().strip().lower()
            if any(phrase in text for phrase in ['tükendi', 'stok yok', 'mevcut değil', 'satışta değil']):
                if len(text) < 100 and not any(js_indicator in text for js_indicator in ['window', 'function', 'var ']): return True
        return False

    def _extract_prices(self, soup):
        """Extract both current and original prices using all available methods."""
        price, original_price = None, None

        # Method 1: New - data-testid price search
        price_container = soup.find('div', attrs={'data-testid': 'price'})
        if price_container:
            discounted_span = price_container.find('span', class_='price-view-discounted')
            original_span = price_container.find('span', class_='price-view-original')
            if discounted_span: price = self._extract_price_from_text(discounted_span.text)
            if original_span: original_price = self._extract_price_from_text(original_span.text)
            if not price and original_span: price = original_price # No discount, original is current
            if not price: # Fallback to any span in the container
                for span in price_container.find_all('span'):
                    extracted = self._extract_price_from_text(span.get_text())
                    if extracted: price = extracted; break

        # Method 2 & 3: price-price or prc-dsc
        if not price:
            price_tag = soup.find('div', class_=lambda x: x and 'price-price' in ' '.join(x)) or soup.find('span', class_='prc-dsc')
            if price_tag: price = self._extract_price_from_text(price_tag.text)

        # Method 4: Old structure - campaign-price
        if not price:
            price_tag = soup.find('p', class_='campaign-price')
            if price_tag: price = self._extract_price_from_text(price_tag.text)

        # Method 5: JSON-LD
        if not price:
            for script in soup.find_all('script', type='application/ld+json'):
                try:
                    data = json.loads(script.string)
                    offers = data.get('offers')
                    if isinstance(offers, dict): price = float(offers.get('price'))
                    elif isinstance(offers, list) and offers: price = float(offers[0].get('price'))
                    if price: logger.info(f"Found price via JSON-LD: {price}"); break
                except (json.JSONDecodeError, AttributeError, TypeError): continue

        # Method 6: JavaScript variables
        if not price:
            for script in soup.find_all('script'):
                if not script.string: continue
                if 'winnerVariant' in script.string or 'productDetail' in script.string:
                    for pattern in [r'"price":\s*{\s*[^}]*"value":\s*([0-9.]+)', r'"price":\s*([0-9.]+)', r'"currentPrice":\s*([0-9.]+)', r'"sellingPrice":\s*([0-9.]+)' ]:
                        match = re.search(pattern, script.string)
                        if match: price = float(match.group(1)); logger.info(f"Found price via JavaScript: {price}"); break
                if price: break

        # Method 7: General TL/₺ search
        if not price:
            for element in soup.find_all(string=re.compile(r'\d+[,.]?\d*\s*(TL|₺)')):
                if element.parent.name == 'script': continue
                extracted = self._extract_price_from_text(element)
                if extracted: price = extracted; logger.info(f"Found price via general TL search: {price}"); break

        if not original_price: original_price = price
        return price, original_price

    def _extract_image_url(self, soup):
        """Extract product image URL using multiple methods."""
        try:
            # Method 1: Try to get from 'og:image' meta tag (most reliable)
            og_image = soup.find('meta', property='og:image')
            if og_image and og_image.get('content'):
                return og_image['content']

            # Method 2: New gallery image selector
            gallery_img = soup.select_one('.product-image-gallery-container img')
            if gallery_img and gallery_img.get('src'):
                image_url = gallery_img.get('src')
                return image_url if image_url.startswith('http') else 'https:' + image_url

            # Method 3: Fallback to old selector
            img_tag = soup.select_one('img.ph-gl-img, .product-slide img')
            if img_tag and img_tag.get('src'):
                image_url = img_tag.get('src')
                return image_url if image_url.startswith('http') else 'https:' + image_url
        except Exception as e:
            logger.error(f"Error extracting image URL: {e}")
            return None
        return None
