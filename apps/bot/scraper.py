import re
import json
import httpx
from typing import Optional
from selectolax.parser import HTMLParser


class TrendyolScraper:
    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
        }
        self.client = httpx.Client(
            headers=self.headers,
            follow_redirects=True,
            timeout=30.0
        )

    def normalize_url(self, url: str) -> str:
        """Normalize Trendyol URL to product page."""
        # Extract product ID from various URL formats
        patterns = [
            r'-p-(\d+)',
            r'urunler/.*?-(\d+)',
            r'/pd/.*?-(\d+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                product_id = match.group(1)
                return f"https://www.trendyol.com/pd/urun-p-{product_id}"
        
        return url

    def scrape_product(self, url: str) -> Optional[dict]:
        """Scrape product data from Trendyol."""
        try:
            normalized_url = self.normalize_url(url)
            response = self.client.get(normalized_url)
            response.raise_for_status()
            
            html = response.text
            parser = HTMLParser(html)
            
            # Try to extract from JSON-LD
            product_data = self._extract_json_ld(parser, html)
            if product_data:
                return product_data
            
            # Try to extract from __INITIAL_STATE__
            product_data = self._extract_initial_state(parser, html)
            if product_data:
                return product_data
            
            # Try to extract from meta tags
            product_data = self._extract_meta(parser, html)
            if product_data:
                return product_data
            
            return None
            
        except Exception as e:
            print(f"Scrape error: {e}")
            return None

    def _extract_json_ld(self, parser: HTMLParser, html: str) -> Optional[dict]:
        """Extract product data from JSON-LD script."""
        scripts = parser.css('script[type="application/ld+json"]')
        for script in scripts:
            try:
                data = json.loads(script.text())
                if isinstance(data, dict) and data.get("@type") == "Product":
                    offers = data.get("offers", {})
                    if isinstance(offers, list):
                        offers = offers[0] if offers else {}
                    
                    # Handle image - can be string or list
                    image = data.get("image", "")
                    if isinstance(image, list):
                        image = image[0] if image else ""
                    
                    return {
                        "product_id": self._extract_product_id(data.get("url", "")),
                        "name": data.get("name", ""),
                        "url": data.get("url", ""),
                        "image_url": image,
                        "current_price": float(offers.get("price", 0)),
                        "original_price": float(offers.get("price", 0)),
                        "success": True
                    }
            except (json.JSONDecodeError, IndexError):
                continue
        return None

    def _extract_initial_state(self, parser: HTMLParser, html: str) -> Optional[dict]:
        """Extract product data from __INITIAL_STATE__."""
        match = re.search(r'window\["__INITIAL_STATE__"\]\s*=\s*({.*?});', html, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group(1))
                product = data.get("product", {}).get("data", {})
                if product:
                    return {
                        "product_id": str(product.get("id", "")),
                        "name": product.get("name", ""),
                        "url": f"https://www.trendyol.com/pd/urun-p-{product.get('id', '')}",
                        "image_url": product.get("images", [{}])[0].get("url", "") if product.get("images") else "",
                        "current_price": float(product.get("price", {}).get("sellingPrice", 0)),
                        "original_price": float(product.get("price", {}).get("originalPrice", 0)),
                        "success": True
                    }
            except (json.JSONDecodeError, KeyError):
                pass
        return None

    def _extract_meta(self, parser: HTMLParser, html: str) -> Optional[dict]:
        """Extract product data from meta tags."""
        title = parser.css_first("title")
        og_title = parser.css_first('meta[property="og:title"]')
        og_image = parser.css_first('meta[property="og:image"]')
        og_url = parser.css_first('meta[property="og:url"]')
        
        if title and og_title:
            name = og_title.attributes.get("content", title.text())
            
            # Try to find price in HTML
            price_match = re.search(r'"sellingPrice":\s*(\d+\.?\d*)', html)
            price = float(price_match.group(1)) if price_match else 0
            
            return {
                "product_id": self._extract_product_id(og_url.attributes.get("content", "") if og_url else ""),
                "name": name,
                "url": og_url.attributes.get("content", "") if og_url else "",
                "image_url": og_image.attributes.get("content", "") if og_image else "",
                "current_price": price,
                "original_price": price,
                "success": True
            }
        return None

    def _extract_product_id(self, url: str) -> str:
        """Extract product ID from URL."""
        match = re.search(r'-p-(\d+)', url)
        if match:
            return match.group(1)
        return ""

    def close(self):
        self.client.close()
