import re
import json
import time
import random
import logging
from urllib.parse import urlparse, parse_qs

logger = logging.getLogger("Trendcord.Scraper")

USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:127.0) Gecko/20100101 Firefox/127.0',
]

def safe_float(val):
    if val is None: return None
    if isinstance(val, (int, float)): return float(val)
    if isinstance(val, dict):
        for key in ['value', 'amount', 'price', 'sellingPrice', 'currentPrice']:
            if key in val:
                return safe_float(val[key])
        return None
    if isinstance(val, list):
        return safe_float(val[0]) if val else None
    s = str(val).replace('TL', '').replace('₺', '').upper().replace('SEPETTE', '').strip()
    s = re.sub(r'[^\d.,]', '', s)
    if not s: return None
    if '.' in s and ',' in s:
        s = s.replace('.', '').replace(',', '.')
    elif ',' in s:
        parts = s.split(',')
        if len(parts) == 2 and len(parts[1]) <= 3 and parts[1].replace('.', '').isdigit():
            s = s.replace(',', '.')
        else:
            s = s.replace(',', '')
    try: return float(s)
    except: return None


def extract_pid(url):
    """Extract the LAST product ID from a Trendyol URL"""
    all_pids = re.findall(r'(?:^|[/-])p-(\d+)', url)
    if not all_pids:
        all_pids = re.findall(r'p-(\d+)', url)
    return all_pids[-1] if all_pids else None


def normalize_url(url):
    """Normalize Trendyol URLs to canonical /pd/ format"""
    url = str(url).strip()

    if 'ty.gl' in url or 'adj.st' in url:
        try:
            import requests as req
            r = req.get(url, headers={'User-Agent': USER_AGENTS[0]}, allow_redirects=True, timeout=10)
            url = r.url
        except:
            pass
        return url

    if '/pd/' in url:
        return url.split('?')[0]

    pid = extract_pid(url)
    if pid:
        return f'https://www.trendyol.com/pd/urun-p-{pid}'
    return url


class TrendyolScraper:
    def __init__(self):
        self.session_curl = None
        self.session_requests = None
        self._last_ping = 0
        self._init_sessions()

    def _init_sessions(self):
        try:
            from curl_cffi import requests as curl_req
            self.session_curl = curl_req
            self._ping_trendyol()
        except Exception as e:
            logger.warning(f"curl_cffi baslatilamadi: {e}")
            self.session_curl = None

        import requests as std_req
        self.session_requests = std_req.Session()
        self.session_requests.headers.update({
            'User-Agent': random.choice(USER_AGENTS),
            'Accept-Language': 'tr-TR,tr;q=0.9',
        })

    def _ping_trendyol(self):
        """Keep session warm by pinging homepage periodically"""
        if not self.session_curl: return
        now = time.time()
        if now - self._last_ping < 120: return
        try:
            self.session_curl.get(
                'https://www.trendyol.com/',
                impersonate='chrome110', timeout=10, verify=False,
            )
            self._last_ping = now
            logger.debug("Session ping: OK")
        except Exception as e:
            logger.debug(f"Session ping failed: {e}")

    def _headers(self, referer=None):
        h = {
            'User-Agent': random.choice(USER_AGENTS),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'tr-TR,tr;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate',
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
        }
        if referer: h['Referer'] = referer
        return h

    def fetch(self, url, timeout=25):
        """Fetch HTML with retry logic across multiple engines"""
        last_error = None

        for attempt in range(2):
            # Method 1: curl_cffi with Chrome impersonation
            if self.session_curl:
                try:
                    self._ping_trendyol()
                    resp = self.session_curl.get(
                        url, headers=self._headers(),
                        impersonate='chrome110', timeout=timeout, verify=False,
                    )
                    if resp.status_code == 200 and len(resp.text) > 500:
                        return resp.text, resp.status_code, resp.url
                    elif resp.status_code == 404 or resp.status_code == 410:
                        # Product deleted, try anyway with whatever we got
                        if len(resp.text) > 1000:
                            return resp.text, resp.status_code, resp.url
                except Exception as e:
                    last_error = f"curl_cffi: {e}"
                    logger.debug(f"fetch attempt {attempt+1} curl_cffi: {e}")

            # Method 2: cloudscraper
            try:
                import importlib
                cloudscraper = importlib.import_module('cloudscraper')
                cs = cloudscraper.create_scraper(browser={
                    'browser': 'chrome', 'platform': 'windows', 'desktop': True,
                })
                resp = cs.get(url, headers=self._headers(), timeout=timeout)
                if resp.status_code == 200:
                    return resp.text, resp.status_code, resp.url
            except Exception as e:
                if not last_error: last_error = f"cloudscraper: {e}"

            # Method 3: plain requests
            try:
                resp = self.session_requests.get(url, headers=self._headers(), timeout=timeout)
                if resp.status_code == 200 and len(resp.text) > 500:
                    return resp.text, resp.status_code, resp.url
            except Exception as e:
                if not last_error: last_error = f"requests: {e}"

            if attempt == 0:
                logger.debug(f"Retrying fetch for {url[:60]}... ({last_error})")
                time.sleep(1.5)

        logger.warning(f"Tum fetch yontemleri basarisiz: {url[:80]} -> {last_error}")
        return None, 0, url

    def extract_product_id(self, url):
        return extract_pid(url)

    def extract_name_from_og(self, name):
        for suffix in [' Fiyatı, Yorumları - Trendyol', ' - Trendyol', ' Fiyatı', ' Fiyatları']:
            if name.endswith(suffix):
                name = name[:-len(suffix)]
        return name.strip()

    def is_product_url(self, url):
        if not (re.search(r'p-\d+', url) or 'ty.gl' in url or 'adj.st' in url):
            return False
        if '/sr?' in url or '/sepet' in url or '/kategori' in url or '/kupon' in url:
            return False
        return True

    def scrape_product(self, url):
        url = str(url).strip()

        if not self.is_product_url(url):
            logger.debug(f"Atlandi (product URL degil): {url}")
            return None

        normalized = normalize_url(url)
        if normalized != url:
            logger.info(f"URL normalize: {url[:80]} -> {normalized}")
            url = normalized

        time.sleep(random.uniform(0.3, 0.8))

        html, status, final_url = self.fetch(url)
        if not html:
            logger.warning(f"Fetch bos dondu: {url[:80]} (status={status})")
            return None

        pid = self.extract_product_id(final_url) or self.extract_product_id(url) or '0'

        strategies = [
            ('envoy_pricing', lambda: self._parse_envoy_pricing(html, final_url, pid)),
            ('init_state', lambda: self._parse_initial_state(html, final_url, pid)),
            ('jsonld', lambda: self._parse_jsonld(html, final_url, pid)),
            ('meta', lambda: self._parse_meta(html, final_url, pid)),
            ('og_only', lambda: self._parse_og_only(html, final_url, pid)),
            ('regex_fallback', lambda: self._parse_regex_fallback(html, final_url, pid)),
        ]

        for name, strategy in strategies:
            try:
                result = strategy()
                if result:
                    result['url'] = final_url
                    img = result.get('image_url', '')
                    if isinstance(img, list):
                        result['image_url'] = img[0] if img else ''
                    elif isinstance(img, dict):
                        result['image_url'] = img.get('contentUrl') or img.get('url', '')
                        if isinstance(result['image_url'], list):
                            result['image_url'] = result['image_url'][0] if result['image_url'] else ''
                    logger.debug(f"Strateji '{name}' ile veri bulundu: pid={pid}, price={result.get('current_price')}")
                    return result
            except Exception as e:
                logger.debug(f"Strateji '{name}' hata: {e}")

        logger.warning(f"Tum stratejiler basarisiz: pid={pid}, url={url[:60]}")
        return None

    # ---- Parsing Strategies ----

    def _parse_jsonld(self, html, url, pid):
        for m in re.finditer(r'<script type="application/ld\+json">(.*?)</script>', html, re.DOTALL):
            try:
                data = json.loads(m.group(1))
                if isinstance(data, list):
                    data = data[0]
                if data.get('@type') != 'Product':
                    continue
                offers = data.get('offers', {})
                if isinstance(offers, list):
                    offers = offers[0] if offers else {}
                price = safe_float(offers.get('lowPrice')) or safe_float(offers.get('price'))
                original_price = safe_float(offers.get('highPrice')) or safe_float(offers.get('price'))
                if not price:
                    continue
                img = data.get('image')
                if isinstance(img, dict):
                    img = img.get('contentUrl') or img.get('url', '')
                if isinstance(img, list):
                    img = img[0] if img else ''
                name = data.get('name', '')
                basket = price
                if name and price:
                    return {
                        'product_id': pid, 'name': name.strip(),
                        'current_price': price,
                        'basket_price': basket,
                        'original_price': original_price or price,
                        'discount_pct': 0,
                        'campaign_name': '', 'campaign_type': '', 'campaign_end': '',
                        'image_url': img or '',
                        'url': url, 'success': True,
                    }
            except:
                continue
        return None

    def _parse_initial_state(self, html, url, pid):
        m = re.search(r'window\.__INITIAL_STATE__\s*=\s*({.*?});', html)
        if m:
            try:
                data = json.loads(m.group(1))
                p = data.get('product', {})
                if p.get('name'):
                    price_obj = p.get('price', {})
                    price = safe_float(price_obj.get('sellingPrice'))
                    if not price:
                        sp = price_obj.get('sellingPrice')
                        if isinstance(sp, dict):
                            price = safe_float(sp.get('value'))
                    original_price = safe_float(price_obj.get('originalPrice'))
                    if not original_price:
                        op = price_obj.get('originalPrice')
                        if isinstance(op, dict):
                            original_price = safe_float(op.get('value'))
                    img = p.get('images', [None])[0]
                    if img and not img.startswith('http'):
                        img = 'https://cdn.dsmcdn.com' + img
                    if price:
                        return {
                            'product_id': str(p.get('id', pid)),
                            'name': p.get('name', '').strip(),
                            'current_price': price,
                            'basket_price': price,
                            'original_price': original_price or price,
                            'discount_pct': 0,
                            'campaign_name': '', 'campaign_type': '', 'campaign_end': '',
                            'image_url': img or '',
                            'url': url, 'success': True,
                        }
            except:
                pass
        return None

    def _parse_envoy_pricing(self, html, url, pid):
        """Extract price from Trendyol's envoy SHARED_PROPS — targeted extraction"""
        m = re.search(r'window\["__envoy__SHARED_PROPS"\]\s*=\s*', html)
        if not m:
            return None
        try:
            start = m.end()
            depth = 0
            i = start
            while i < len(html) and i < start + 200000:
                if html[i] == '{': depth += 1
                elif html[i] == '}':
                    depth -= 1
                    if depth == 0:
                        data = json.loads(html[start:i+1])
                        return self._extract_from_shared_props(data, url, pid)
                i += 1
        except:
            pass
        return None

    def _extract_from_shared_props(self, data, url, pid):
        """Extract winnerVariant.price + promotions from parsed SHARED_PROPS"""
        product = data.get('product', {})
        name = product.get('name', '')
        ml = product.get('merchantListing', {})
        winner = ml.get('winnerVariant', {})
        price_obj = winner.get('price', {})

        if not price_obj:
            return None

        selling = safe_float(price_obj.get('sellingPrice'))
        discounted = safe_float(price_obj.get('discountedPrice'))
        original = safe_float(price_obj.get('originalPrice'))
        discount_pct = safe_float(price_obj.get('discountPercentage'))

        if not selling:
            return None

        # Sepette fiyat = discountedPrice (satış fiyatından düşükse)
        basket = discounted if discounted and discounted < selling else selling

        # Kampanya bilgileri
        promotions = ml.get('promotions', [])
        active_promos = []
        for promo in promotions:
            if promo.get('isApplied') and promo.get('promotionDiscountType') == 'DiscountOnBasket':
                active_promos.append(promo)

        campaign_name = ''
        campaign_type = ''
        campaign_end = ''
        if active_promos:
            best = active_promos[0]
            campaign_name = best.get('name', '')
            campaign_type = best.get('promotionDiscountType', '')
            campaign_end = best.get('promotionEndDate', '')

        # Görsel
        images = product.get('images', [])
        img = ''
        if images and isinstance(images[0], str):
            img = 'https://cdn.dsmcdn.com' + images[0] if not images[0].startswith('http') else images[0]
        elif images and isinstance(images[0], dict):
            img = images[0].get('url', '')

        return {
            'product_id': pid,
            'name': name.strip() if name else 'Trendyol Ürünü',
            'current_price': selling,
            'basket_price': basket,
            'original_price': original or selling,
            'discount_pct': discount_pct or 0,
            'campaign_name': campaign_name,
            'campaign_type': campaign_type,
            'campaign_end': campaign_end,
            'image_url': img,
            'url': url, 'success': True,
        }

    def _parse_meta(self, html, url, pid):
        """Extract from OG meta tags"""
        og_title = re.search(r'<meta\s+property="og:title"\s+content="([^"]+)"', html)
        og_img = re.search(r'<meta\s+property="og:image"\s+content="([^"]+)"', html)
        og_desc = re.search(r'<meta\s+property="og:description"\s+content="([^"]+)"', html)

        if og_title:
            name = self.extract_name_from_og(og_title.group(1))
            img = og_img.group(1) if og_img else ''
            price = None
            original_price = None
            if og_desc:
                pm = re.search(r'([0-9 ,.]+)\s*(?:TL|₺)', og_desc.group(1))
                if pm:
                    price = safe_float(pm.group(1))
            if not price:
                price, original_price = self._find_price_in_html(html)
            if name:
                return {
                    'product_id': pid, 'name': name,
                    'current_price': price or 0,
                    'basket_price': price or 0,
                    'original_price': original_price or price or 0,
                    'discount_pct': 0,
                    'campaign_name': '', 'campaign_type': '', 'campaign_end': '',
                    'image_url': img,
                    'url': url, 'success': True,
                }
        return None

    def _parse_og_only(self, html, url, pid):
        """Last resort: OG meta only"""
        og_title = re.search(r'<meta\s+property="og:title"\s+content="([^"]+)"', html)
        og_img = re.search(r'<meta\s+property="og:image"\s+content="([^"]+)"', html)
        if og_title:
            name = self.extract_name_from_og(og_title.group(1))
            img = og_img.group(1) if og_img else ''
            price, original_price = self._find_price_in_html(html)
            return {
                'product_id': pid, 'name': name,
                'current_price': price or 0,
                'basket_price': price or 0,
                'original_price': original_price or price or 0,
                'discount_pct': 0,
                'campaign_name': '', 'campaign_type': '', 'campaign_end': '',
                'image_url': img,
                'url': url, 'success': True,
            }
        return None

    def _parse_regex_fallback(self, html, url, pid):
        """Regex-based fallback to find ANY product data in the HTML"""
        h1 = re.search(r'<h1[^>]*>(.*?)</h1>', html, re.DOTALL)
        title = re.search(r'<title>(.*?)</title>', html)
        price, original_price = self._find_price_in_html(html)

        name = None
        if h1:
            from bs4 import BeautifulSoup
            name = BeautifulSoup(h1.group(1), 'html.parser').get_text(strip=True)
        if not name and title:
            name = title.group(1).replace(' - Trendyol', '').replace(' Fiyatı, Yorumları', '').strip()
        if not name:
            name = f'Trendyol Ürünü #{pid}'

        return {
            'product_id': pid, 'name': name,
            'current_price': price or 0,
            'basket_price': price or 0,
            'original_price': original_price or price or 0,
            'discount_pct': 0,
            'campaign_name': '', 'campaign_type': '', 'campaign_end': '',
            'image_url': '',
            'url': url, 'success': True,
        }

    def _find_price_in_html(self, html):
        """Regex search for price patterns in HTML"""
        patterns = [
            (r'"sellingPrice"\s*:\s*\{"value"\s*:\s*(\d+)', 'selling'),
            (r'"discountedPrice"\s*:\s*\{"value"\s*:\s*(\d+)', 'selling'),
            (r'"sellingPrice"\s*:\s*"?(\d+\.?\d*)"?', 'selling'),
            (r'"discountedPrice"\s*:\s*"?(\d+\.?\d*)"?', 'selling'),
            (r'"salePrice"\s*:\s*"?(\d+\.?\d*)"?', 'selling'),
            (r'"currentPrice"\s*:\s*"?(\d+\.?\d*)"?', 'selling'),
            (r'"priceValue"\s*:\s*"?(\d+\.?\d*)"?', 'selling'),
            (r'"price"\s*:\s*"?(\d+\.?\d*)"?', 'selling'),
            (r'"originalPrice"\s*:\s*\{"value"\s*:\s*(\d+)', 'original'),
            (r'"originalPrice"\s*:\s*"?(\d+\.?\d*)"?', 'original'),
            (r'"listPrice"\s*:\s*"?(\d+\.?\d*)"?', 'original'),
            (r'"priceText"\s*:\s*"([^"]*(\d+)[^"]*)"', 'selling'),
            (r'(\d{2,}[.,]\d{2})\s*(?:TL|₺)', 'selling'),
        ]
        selling = None
        original = None
        for pattern, kind in patterns:
            m = re.search(pattern, html)
            if m:
                val = m.group(1).strip()
                p = safe_float(val)
                if p and p > 0:
                    if kind == 'selling' and not selling:
                        selling = p
                    elif kind == 'original' and not original:
                        original = p
                if selling:
                    break
        return selling, original
