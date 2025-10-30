"""
Auto-Discovery Commodity Price Crawler

This module provides functionality to automatically search the web for commodity
prices and extract pricing information from multiple sources. It can search for
items by name, intelligently parse various website formats, and compare prices
across different vendors.

Usage:
    crawler = AutoPriceCrawler(delay=2.0)
    results = crawler.search_multiple_items(['Gold 1oz', 'Silver 1oz'])
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


class AutoPriceCrawler:
    """
    Auto PriceCrawler
    """
    def __init__(self, delay: float = 2.0, max_results: int = 10):
        """
        Initialize the auto-discovery price crawler
        
        Args:
            delay: Delay between requests in seconds
            max_results: Maximum number of search results to check per item
        """
        self.delay = delay
        self.max_results = max_results
        self.headers = {
           'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        self.price_history = []

        # Common price-related CSS selectors to try
        self.price_selectors = [
            '[class*="price"]',
            '[id*="price"]',
            'span.price',
            'div.price',
            'p.price',
            '.product-price',
            '.current-price',
            '.sale-price',
            '[itemprop="price"]',
            'span[class*="amount"]',
            'meta[property="product:price:amount"]',
        ]
    
    def search_web_for_item(self, item_name: str, search_terms: str = None) -> List[str]:
        """
        Search the web for pages about a specific commodity
        
        Args:
            item_name: Name of the commodity
            search_terms: Optional additional search terms (e.g., "buy", "price")
            
        Returns:
            List of URLs found
        """
        if search_terms is None:
            search_terms = f"{item_name} price buy"
        else:
            search_terms = f"{item_name} {search_terms}"
        
        print(f"\nSearching web for: {search_terms}")
        
        # Using DuckDuckGo HTML (no API key needed, respects privacy)
        search_url = f"https://html.duckduckgo.com/html/?q={quote_plus(search_terms)}"
        
        try:
            response = requests.get(search_url, headers=self.headers, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Extract URLs from search results
            urls = []
            for link in soup.select('a.result__a'):
                href = link.get('href')
                if href and href.startswith('http'):
                    # Clean DuckDuckGo redirect
                    if '//duckduckgo.com/l/?' in href:
                        continue
                    urls.append(href)
                    if len(urls) >= self.max_results:
                        break
            
            print(f"  Found {len(urls)} URLs to check")
            return urls
            
        except (requests.RequestException, ConnectionError, TimeoutError) as e:
            print(f"  ✗ Search error: {type(e).__name__}: {e}")
            return []
    
    def extract_price_from_text(self, text: str) -> Optional[float]:
        """Extract price from text string with improved regex"""
        # Handle various price formats
        patterns = [
            r'[\$£€¥]\s*(\d+(?:,\d{3})*(?:\.\d{2})?)',  # $1,234.56
            r'(\d+(?:,\d{3})*(?:\.\d{2})?)\s*[\$£€¥]',  # 1,234.56$
            r'(\d+(?:\.\d{2})?)',  # Simple number
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text.replace(',', ''))
            if match:
                try:
                    return float(match.group(1).replace(',', ''))
                except (ValueError, AttributeError, IndexError):
                    continue
        return None
    
    def detect_currency(self, text: str) -> str:
        """Detect currency symbol in text"""
        currencies = {'$': '$', '£': '£', '€': '€', '¥': '¥', 'USD': '$', 'GBP': '£', 'EUR': '€'}
        for symbol, display in currencies.items():
            if symbol in text:
                return display
        return '$'  # Default
    
    def smart_crawl_url(self, url: str, item_name: str) -> Optional[Dict]:
        """
        Intelligently crawl a URL trying multiple strategies to find price
        
        Args:
            url: URL to crawl
            item_name: Name of the commodity being searched
            
        Returns:
            Dictionary with price data or None
        """
        try:
            print(f"  Checking: {urlparse(url).netloc}")
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Strategy 1: Try common price selectors
            price = None
            price_text = ""
            
            for selector in self.price_selectors:
                elements = soup.select(selector)
                for elem in elements:
                    text = elem.get_text(strip=True)
                    potential_price = self.extract_price_from_text(text)
                    if potential_price and 0.01 < potential_price < 1000000:  # Reasonable range
                        price = potential_price
                        price_text = text
                        break
                if price:
                    break
            
            # Strategy 2: Try meta tags
            if not price:
                meta_price = soup.select_one('meta[property="product:price:amount"]')
                if meta_price and meta_price.get('content'):
                    price = self.extract_price_from_text(meta_price.get('content'))
                    if price:
                        price_text = meta_price.get('content')
            
            # Strategy 3: Search for price patterns in all text
            if not price:
                body_text = soup.get_text()
                # Look for price-like patterns with context
                price_matches = re.finditer(r'(?:price|cost|buy)[\s:]*[\$£€¥]?\s*(\d+(?:,\d{3})*(?:\.\d{2})?)', 
                                           body_text, re.IGNORECASE)
                for match in price_matches:
                    potential_price = self.extract_price_from_text(match.group())
                    if potential_price and 0.01 < potential_price < 1000000:
                        price = potential_price
                        price_text = match.group()
                        break
            
            if not price:
                return None
            
            # Extract title
            title = item_name
            title_elem = soup.select_one('h1') or soup.select_one('title')
            if title_elem:
                title = title_elem.get_text(strip=True)[:100]  # Limit length
            
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
    
    def search_and_crawl(self, item_name: str, search_terms: str = None, 
                         min_results: int = 3) -> List[Dict]:
        """
        Search for an item and crawl found pages for prices
        
        Args:
            item_name: Name of commodity to search for
            search_terms: Optional additional search terms
            min_results: Minimum number of successful results to aim for
            
        Returns:
            List of successful price extractions
        """
        print(f"\n{'='*60}")
        print(f"Searching for: {item_name}")
        print(f"{'='*60}")
        
        # Search the web
        urls = self.search_web_for_item(item_name, search_terms)
        
        if not urls:
            print("  ⚠ No URLs found in search results")
            return []
        
        # Crawl found URLs
        found_prices = []
        for url in urls:
            price_data = self.smart_crawl_url(url, item_name)
            
            if price_data:
                found_prices.append(price_data)
                self.price_history.append(price_data)
                
                # Stop if we have enough results
                if len(found_prices) >= min_results:
                    break
            
            time.sleep(self.delay)
        
        return found_prices
    
    def search_multiple_items(self, items: List[str], search_terms: str = "price") -> Dict[str, List[Dict]]:
        """
        Search for multiple commodity items
        
        Args:
            items: List of commodity names
            search_terms: Additional search terms for all items
            
        Returns:
            Dictionary mapping item names to their price results
        """
        all_items_results  = {}
        
        for item in items:
            found_prices = self.search_and_crawl(item, search_terms)
            all_items_results [item] = found_prices
            
            # Delay between different item searches
            if item != items[-1]:
                time.sleep(self.delay * 2)
        
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
    
    def save_to_json(self, filename: str = 'auto_price_data.json'):
        """Save price history to JSON"""
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(self.price_history, f, indent=2)
        print(f"\n✓ Saved {len(self.price_history)} records to {filename}")
    
    def save_to_csv(self, filename: str = 'auto_price_data.csv'):
        """Save price history to CSV"""
        if not self.price_history:
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
    crawler = AutoPriceCrawler(delay=2.0, max_results=10)
    
    # Just provide the commodity names!
    commodities = [
        "Gold 1oz",
        "Silver 1oz",
        "Crude Oil barrel",
        "Bitcoin"
    ]
    
    print("="*60)
    print("AUTO-DISCOVERY COMMODITY PRICE CRAWLER")
    print("="*60)
    print(f"Searching for {len(commodities)} commodities...")
    
    # Search and crawl automatically
    results = crawler.search_multiple_items(commodities, search_terms="current price")
    
    # Display results
    crawler.print_results(results)
    
    # Save data
    if crawler.price_history:
        crawler.save_to_json()
        crawler.save_to_csv()
        print("\n✓ All data saved successfully!")
    
    print("\n" + "="*60)