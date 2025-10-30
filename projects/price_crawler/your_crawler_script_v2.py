"""
Enhanced Commodity & Product Price Crawler

This module provides functionality to automatically search the web for commodity
and product prices. It supports both commodities (Gold, Bitcoin) and specific
products (LG TV OLED65C5AUA). Uses multiple search strategies and APIs for
better results.

Usage:
    crawler = EnhancedPriceCrawler(delay=2.0)
    results = crawler.search_multiple_items(['Gold 1oz', 'LG OLED65C5AUA'])
    crawler.save_to_json()
"""

import json
import time
from datetime import datetime
from typing import Dict, List, Optional
import re
from urllib.parse import quote_plus, urlparse
import csv

import requests
from bs4 import BeautifulSoup


class EnhancedPriceCrawler:
    """
    Enhanced web crawler for discovering commodity and product prices.
    
    This class searches the web using multiple strategies, intelligently extracts
    pricing information from various website formats, and provides comparison
    and export functionality. Supports both commodities and specific products.
    
    Attributes:
        delay (float): Delay between requests in seconds
        max_results (int): Maximum number of URLs to check per item
        headers (dict): HTTP headers for requests
        price_history (list): List of all extracted price data
        
    Example:
        >>> crawler = EnhancedPriceCrawler(delay=2.0)
        >>> results = crawler.search_multiple_items(['Gold 1oz', 'LG OLED65C5AUA'])
        >>> crawler.save_to_json()
    """
    
    def __init__(self, delay: float = 2.0, max_results: int = 15):
        """
        Initialize the enhanced price crawler.
        
        Args:
            delay: Delay between requests in seconds (default: 2.0)
            max_results: Maximum number of URLs to check per item (default: 15)
        """
        self.delay = delay
        self.max_results = max_results
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
        self.price_history = []
        
        # Known commodity/product sites for direct checking
        self.known_sources = {
            'gold': [
                'https://www.kitco.com/gold-price-today-usa/',
                'https://www.bullionvault.com/gold-price-chart.do'
            ],
            'silver': [
                'https://www.kitco.com/silver-price-today-usa/',
                'https://www.bullionvault.com/silver-price-chart.do'
            ],
            'bitcoin': [
                'https://www.coindesk.com/price/bitcoin/',
                'https://coinmarketcap.com/currencies/bitcoin/'
            ],
            'crude oil': [
                'https://www.investing.com/commodities/crude-oil',
                'https://markets.businessinsider.com/commodities/oil-price'
            ]
        }
    
    def extract_price_from_text(self, text: str) -> Optional[float]:
        """
        Extract price from text string with improved regex.
        
        Args:
            text: Text containing price information
            
        Returns:
            Extracted price as float, or None if not found
        """
        # Clean text
        text = text.replace(',', '').replace(' ', '')
        
        # Multiple price patterns
        patterns = [
            r'[\$£€¥]\s*(\d+(?:\.\d{2})?)',  # $1234.56
            r'(\d+(?:\.\d{2})?)\s*[\$£€¥]',  # 1234.56$
            r'USD\s*(\d+(?:\.\d{2})?)',      # USD 1234.56
            r'(\d+(?:\.\d{2})?)\s*USD',      # 1234.56 USD
            r'Price[:\s]+\$?(\d+(?:\.\d{2})?)',  # Price: $1234.56
            r'\$(\d{1,3}(?:,?\d{3})*(?:\.\d{2})?)',  # $1,234.56
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    price_str = match.group(1).replace(',', '')
                    price = float(price_str)
                    # Reasonable price range
                    if 0.01 < price < 10000000:
                        return price
                except (ValueError, AttributeError, IndexError):
                    continue
        return None
    
    def detect_currency(self, text: str) -> str:
        """Detect currency symbol in text"""
        text_upper = text.upper()
        currencies = {
            '$': '$', '£': '£', '€': '€', '¥': '¥',
            'USD': '$', 'GBP': '£', 'EUR': '€', 'JPY': '¥'
        }
        for symbol, display in currencies.items():
            if symbol in text_upper or symbol in text:
                return display
        return '$'  # Default
    
    def search_google_shopping(self, query: str) -> List[str]:
        """
        Search Google Shopping for product URLs.
        
        Args:
            query: Product search query
            
        Returns:
            List of product URLs found
        """
        print(f"  Searching Google Shopping...")
        urls = []
        
        try:
            search_url = f"https://www.google.com/search?q={quote_plus(query)}&tbm=shop"
            response = requests.get(search_url, headers=self.headers, timeout=10)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                # Extract product links
                for link in soup.find_all('a', href=True):
                    href = link['href']
                    if '/url?q=' in href:
                        actual_url = href.split('/url?q=')[1].split('&')[0]
                        if actual_url.startswith('http') and 'google' not in actual_url:
                            urls.append(actual_url)
                            if len(urls) >= 5:
                                break
        except (requests.RequestException, Exception) as e:
            print(f"    ⚠ Google Shopping error: {type(e).__name__}")
        
        return urls
    
    def check_known_source(self, url: str, item_name: str) -> Optional[Dict]:
        """
        Check a known commodity source URL.
        
        Args:
            url: URL to check
            item_name: Name of the item
            
        Returns:
            Price data dictionary or None
        """
        try:
            print(f"  Checking known source: {urlparse(url).netloc}")
            response = requests.get(url, headers=self.headers, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Get all text and search for prices
            page_text = soup.get_text()
            
            # Find all potential prices in the page
            price_candidates = []
            for line in page_text.split('\n'):
                line = line.strip()
                if len(line) > 0 and len(line) < 100:  # Reasonable line length
                    price = self.extract_price_from_text(line)
                    if price:
                        price_candidates.append((price, line))
            
            if price_candidates:
                # Take the first reasonable price (usually the current price)
                for price, line in price_candidates:
                    result = {
                        'item_name': item_name,
                        'title': item_name,
                        'price': price,
                        'currency': self.detect_currency(line),
                        'url': url,
                        'timestamp': datetime.now().isoformat(),
                        'source': urlparse(url).netloc
                    }
                    print(f"    ✓ Found price: {result['currency']}{price}")
                    return result
            
        except requests.RequestException as e:
            print(f"    ✗ Network error: {type(e).__name__}")
        except (AttributeError, KeyError, ValueError) as e:
            print(f"    ✗ Parse error: {type(e).__name__}")
        
        return None
    
    def smart_crawl_url(self, url: str, item_name: str) -> Optional[Dict]:
        """
        Intelligently crawl a URL trying multiple strategies to find price.
        
        Args:
            url: URL to crawl
            item_name: Name of the item being searched
            
        Returns:
            Dictionary with price data or None
        """
        try:
            print(f"  Checking: {urlparse(url).netloc}")
            response = requests.get(url, headers=self.headers, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Strategy 1: Look for common price patterns in meta tags
            price = None
            price_text = ""
            
            meta_selectors = [
                'meta[property="product:price:amount"]',
                'meta[property="og:price:amount"]',
                'meta[name="price"]',
                'meta[itemprop="price"]',
            ]
            
            for selector in meta_selectors:
                meta = soup.select_one(selector)
                if meta and meta.get('content'):
                    price = self.extract_price_from_text(meta.get('content'))
                    if price:
                        price_text = meta.get('content')
                        break
            
            # Strategy 2: Common price CSS selectors
            if not price:
                price_selectors = [
                    '[itemprop="price"]',
                    '.price',
                    '#price',
                    'span.price',
                    '.product-price',
                    '.sale-price',
                    '[class*="price"]',
                    '[data-price]',
                ]
                
                for selector in price_selectors:
                    elements = soup.select(selector)
                    for elem in elements:
                        # Check data attribute first
                        if elem.get('data-price'):
                            price = self.extract_price_from_text(elem.get('data-price'))
                            if price:
                                price_text = elem.get('data-price')
                                break
                        
                        # Check text content
                        text = elem.get_text(strip=True)
                        if text:
                            potential_price = self.extract_price_from_text(text)
                            if potential_price:
                                price = potential_price
                                price_text = text
                                break
                    if price:
                        break
            
            # Strategy 3: Search entire page text
            if not price:
                page_text = soup.get_text()
                lines = [line.strip() for line in page_text.split('\n') if line.strip()]
                
                for line in lines:
                    if len(line) < 200 and ('$' in line or 'price' in line.lower()):
                        potential_price = self.extract_price_from_text(line)
                        if potential_price and 0.01 < potential_price < 100000:
                            price = potential_price
                            price_text = line
                            break
            
            if not price:
                return None
            
            # Extract title
            title = item_name
            title_elem = soup.select_one('h1') or soup.select_one('title')
            if title_elem:
                title = title_elem.get_text(strip=True)[:100]
            
            result = {
                'item_name': item_name,
                'title': title,
                'price': price,
                'currency': self.detect_currency(price_text),
                'url': url,
                'timestamp': datetime.now().isoformat(),
                'source': urlparse(url).netloc
            }
            
            print(f"    ✓ Found price: {result['currency']}{price}")
            return result
            
        except requests.RequestException as e:
            print(f"    ✗ Network error: {type(e).__name__}")
            return None
        except (AttributeError, KeyError, ValueError) as e:
            print(f"    ✗ Parse error: {type(e).__name__}")
            return None
    
    def search_and_crawl(self, item_name: str, search_terms: str = None) -> List[Dict]:
        """
        Search for an item and crawl found pages for prices.
        
        Args:
            item_name: Name of commodity/product to search for
            search_terms: Optional additional search terms
            
        Returns:
            List of successful price extractions
        """
        print(f"\n{'='*60}")
        print(f"Searching for: {item_name}")
        print(f"{'='*60}")
        
        found_prices = []
        
        # Check if this is a known commodity with direct sources
        item_lower = item_name.lower()
        for commodity, urls in self.known_sources.items():
            if commodity in item_lower:
                print(f"  Using known sources for {commodity}")
                for url in urls:
                    price_data = self.check_known_source(url, item_name)
                    if price_data:
                        found_prices.append(price_data)
                        self.price_history.append(price_data)
                    time.sleep(self.delay)
                
                if found_prices:
                    return found_prices
        
        # For products or if known sources failed, search Google Shopping
        print("  Searching for product listings...")
        search_query = f"{item_name} buy price" if not search_terms else f"{item_name} {search_terms}"
        urls = self.search_google_shopping(search_query)
        
        print(f"  Found {len(urls)} URLs to check")
        
        # Crawl found URLs
        for url in urls[:self.max_results]:
            price_data = self.smart_crawl_url(url, item_name)
            
            if price_data:
                found_prices.append(price_data)
                self.price_history.append(price_data)
                
                if len(found_prices) >= 3:
                    break
            
            time.sleep(self.delay)
        
        if not found_prices:
            print(f"  ⚠ No prices found for {item_name}")
        
        return found_prices
    
    def search_multiple_items(self, items: List[str], search_terms: str = None) -> Dict[str, List[Dict]]:
        """
        Search for multiple commodity/product items.
        
        Args:
            items: List of commodity/product names
            search_terms: Optional additional search terms for all items
            
        Returns:
            Dictionary mapping item names to their price results
        """
        all_items_results = {}
        
        for item in items:
            item_results = self.search_and_crawl(item, search_terms)
            all_items_results[item] = item_results
            
            # Longer delay between different searches
            if item != items[-1]:
                time.sleep(self.delay * 3)
        
        return all_items_results
    
    def compare_prices(self, price_results: Dict[str, List[Dict]]) -> Dict:
        """Generate price comparison report"""
        comparison = {}
        
        for item, price_list in price_results.items():
            if not price_list:
                continue
                
            comparison[item] = {
                'prices': [],
                'lowest': None,
                'highest': None,
                'average': None
            }
            
            prices_data = []
            for price_info in price_list:
                comparison[item]['prices'].append({
                    'source': price_info['source'],
                    'price': price_info['price'],
                    'currency': price_info['currency'],
                    'url': price_info['url']
                })
                prices_data.append(price_info['price'])
            
            if prices_data:
                comparison[item]['lowest'] = min(prices_data)
                comparison[item]['highest'] = max(prices_data)
                comparison[item]['average'] = sum(prices_data) / len(prices_data)
        
        return comparison
    
    def print_results(self, price_results: Dict[str, List[Dict]]):
        """Print formatted results"""
        print("\n" + "="*60)
        print("PRICE DISCOVERY RESULTS")
        print("="*60)
        
        for item, price_list in price_results.items():
            print(f"\n{item.upper()}")
            print("-" * 60)
            
            if not price_list:
                print("  ⚠ No prices found")
                continue
            
            for price_data in price_list:
                print(f"  {price_data['source']}")
                print(f"    Price: {price_data['currency']}{price_data['price']}")
                print(f"    URL: {price_data['url'][:60]}...")
        
        # Print comparison
        comparison = self.compare_prices(price_results)
        if comparison:
            print("\n" + "="*60)
            print("PRICE COMPARISON")
            print("="*60)
            
            for item, data in comparison.items():
                if data['lowest']:
                    print(f"\n{item}:")
                    print(f"  Lowest:  ${data['lowest']:.2f}")
                    print(f"  Highest: ${data['highest']:.2f}")
                    print(f"  Average: ${data['average']:.2f}")
                    print(f"  Sources: {len(data['prices'])}")
    
    def save_to_json(self, filename: str = 'price_data.json'):
        """Save price history to JSON"""
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(self.price_history, f, indent=2)
        print(f"\n✓ Saved {len(self.price_history)} records to {filename}")
    
    def save_to_csv(self, filename: str = 'price_data.csv'):
        """Save price history to CSV"""
        if not self.price_history:
            print("  ⚠ No data to save")
            return
        
        keys = self.price_history[0].keys()
        with open(filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            writer.writerows(self.price_history)
        print(f"✓ Saved {len(self.price_history)} records to {filename}")


# Example usage
if __name__ == "__main__":
    # Initialize crawler
    crawler = EnhancedPriceCrawler(delay=2.0, max_results=15)
    
    # Mix of commodities and specific products
    """
    items_to_search = [
        "Gold 1oz",
        "Silver 1oz",
        "Bitcoin",
        "Crude Oil barrel",
        "LG OLED65C5AUA"  # Specific TV model
    ]
    """
    items_to_search = [
        "NN-SN68QB",
        "OLED65C5AUA"  # Specific TV model
    ]
    
    print("="*60)
    print("ENHANCED COMMODITY & PRODUCT PRICE CRAWLER")
    print("="*60)
    print(f"Searching for {len(items_to_search)} items...")
    print("This may take a few minutes...")
    
    # Search and crawl automatically
    results = crawler.search_multiple_items(items_to_search)
    
    # Display results
    crawler.print_results(results)
    
    # Save data
    if crawler.price_history:
        crawler.save_to_json()
        crawler.save_to_csv()
        print("\n✓ All data saved successfully!")
    else:
        print("\n⚠ No prices were found. This may be due to:")
        print("  - Anti-scraping measures on websites")
        print("  - Network issues")
        print("  - Changed website structures")
        print("\nTry running again or check specific websites manually.")
    
    print("\n" + "="*60)