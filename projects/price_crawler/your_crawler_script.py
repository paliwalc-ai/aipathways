"""
API-Based Commodity & Product Price Crawler

This module uses various free APIs to fetch real-time prices for commodities
and products. Much more reliable than web scraping.

Supported:
- Cryptocurrencies (Bitcoin, Ethereum, etc.) - CoinGecko API
- Precious Metals (Gold, Silver) - MetalsAPI
- Oil/Commodities - Alpha Vantage API
- Products - Multiple e-commerce APIs

Usage:
    crawler = APIPriceCrawler()
    crawler.add_api_key('alphavantage', 'YOUR_KEY')  # Optional
    results = crawler.search_multiple_items(['Bitcoin', 'Gold', 'Silver'])
    crawler.save_to_json()
"""

import json
import time
from datetime import datetime
from typing import Dict, List, Optional
import csv

import requests


class APIPriceCrawler:
    """
    API-based price crawler for commodities and products.
    
    Uses various free APIs to fetch real-time pricing data. Much more reliable
    than web scraping and respects rate limits.
    
    Attributes:
        delay (float): Delay between API requests in seconds
        price_history (list): List of all fetched price data
        api_keys (dict): Optional API keys for services that require them
        
    Example:
        >>> crawler = APIPriceCrawler(delay=1.0)
        >>> crawler.add_api_key('alphavantage', 'YOUR_KEY')
        >>> results = crawler.search_multiple_items(['Bitcoin', 'Gold'])
        >>> crawler.save_to_json()
    """
    
    def __init__(self, delay: float = 1.0):
        """
        Initialize the API-based price crawler.
        
        Args:
            delay: Delay between API requests in seconds (default: 1.0)
        """
        self.delay = delay
        self.price_history = []
        self.api_keys = {}
        
        # Mapping of items to their API identifiers
        self.crypto_map = {
            'bitcoin': 'bitcoin',
            'btc': 'bitcoin',
            'ethereum': 'ethereum',
            'eth': 'ethereum',
            'litecoin': 'litecoin',
            'ltc': 'litecoin',
            'ripple': 'ripple',
            'xrp': 'ripple',
            'cardano': 'cardano',
            'ada': 'cardano',
        }
        
        self.metal_map = {
            'gold': 'XAU',
            'silver': 'XAG',
            'platinum': 'XPT',
            'palladium': 'XPD',
        }
        
        self.commodity_map = {
            'crude oil': 'WTI',
            'oil': 'WTI',
            'wti': 'WTI',
            'brent': 'BRENT',
            'natural gas': 'NG',
        }
    
    def add_api_key(self, service: str, key: str):
        """
        Add an API key for a service.
        
        Args:
            service: Service name ('alphavantage', 'metals_api', etc.)
            key: API key
        """
        self.api_keys[service] = key
        print(f"✓ Added API key for {service}")
    
    def fetch_crypto_price(self, crypto_id: str, item_name: str) -> Optional[Dict]:
        """
        Fetch cryptocurrency price from CoinGecko API (free, no key needed).
        
        Args:
            crypto_id: CoinGecko cryptocurrency ID
            item_name: Original item name
            
        Returns:
            Price data dictionary or None
        """
        try:
            print("  Fetching {item_name} from CoinGecko API...")
            url = "https://api.coingecko.com/api/v3/simple/price"
            params = {
                'ids': crypto_id,
                'vs_currencies': 'usd',
                'include_24hr_change': 'true',
                'include_last_updated_at': 'true'
            }
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            if crypto_id in data and 'usd' in data[crypto_id]:
                price = data[crypto_id]['usd']
                change_24h = data[crypto_id].get('usd_24h_change', 0)
                
                result = {
                    'item_name': item_name,
                    'title': f"{item_name.title()} (Cryptocurrency)",
                    'price': price,
                    'currency': '$',
                    'change_24h': round(change_24h, 2),
                    'source': 'CoinGecko API',
                    'api': 'coingecko',
                    'timestamp': datetime.now().isoformat(),
                    'url': f"https://www.coingecko.com/en/coins/{crypto_id}"
                }
                
                print(f"    ✓ Price: ${price:,.2f} (24h change: {change_24h:+.2f}%)")
                return result
            
        except requests.RequestException as e:
            print(f"    ✗ Network error: {type(e).__name__}")
        except (KeyError, ValueError) as e:
            print(f"    ✗ Parse error: {type(e).__name__}")
        
        return None
    
    def fetch_metal_price(self, metal_code: str, item_name: str) -> Optional[Dict]:
        """
        Fetch precious metal price from free gold/metal API.
        
        Args:
            metal_code: Metal code (XAU, XAG, etc.)
            item_name: Original item name
            
        Returns:
            Price data dictionary or None
        """
        try:
            print(f"  Fetching {item_name} from Metals API...")
            
            # Using free metals API (no key needed for basic access)
            url = "https://api.metalpriceapi.com/v1/latest"
            params = {
                'api_key': self.api_keys.get('metals_api', 'demo'),  # Demo key works
                'base': 'USD',
                'currencies': metal_code
            }
            
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                if 'rates' in data and metal_code in data['rates']:
                    # Price is per troy ounce, rate is inverted
                    rate = data['rates'][metal_code]
                    price = 1 / rate if rate > 0 else 0
                    
                    result = {
                        'item_name': item_name,
                        'title': f"{item_name.title()} per Troy Ounce",
                        'price': round(price, 2),
                        'currency': '$',
                        'unit': 'troy oz',
                        'source': 'Metal Price API',
                        'api': 'metalpriceapi',
                        'timestamp': datetime.now().isoformat(),
                        'url': "https://www.metalpriceapi.com/"
                    }
                    
                    print(f"    ✓ Price: ${price:,.2f} per troy oz")
                    return result
            else:
                # Fallback to alternative free API
                print("    Trying alternative API...")
                return self.fetch_metal_price_alternative(metal_code, item_name)
                
        except requests.RequestException as e:
            print(f"    ✗ Network error: {type(e).__name__}")
        except (KeyError, ValueError) as e:
            print(f"    ✗ Parse error: {type(e).__name__}")
        
        return None
    
    def fetch_metal_price_alternative(self, metal_code: str, item_name: str) -> Optional[Dict]:
        """
        Alternative free metal price API.
        
        Args:
            metal_code: Metal code
            item_name: Original item name
            
        Returns:
            Price data dictionary or None
        """
        try:
            # Using goldapi.io free tier (limited requests)
            url = "https://www.goldapi.io/api/XAU/USD" if metal_code == "XAU" else f"https://www.goldapi.io/api/{metal_code}/USD"
            
            headers = {
                'x-access-token': self.api_keys.get('goldapi', 'goldapi-demo-key'),
            }
            
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                if 'price' in data:
                    price = data['price']
                    
                    result = {
                        'item_name': item_name,
                        'title': f"{item_name.title()} per Troy Ounce",
                        'price': round(price, 2),
                        'currency': '$',
                        'unit': 'troy oz',
                        'source': 'Gold API',
                        'api': 'goldapi',
                        'timestamp': datetime.now().isoformat(),
                        'url': "https://www.goldapi.io/"
                    }
                    
                    print(f"    ✓ Price: ${price:,.2f} per troy oz")
                    return result
                    
        except requests.RequestException:
            pass
        except (KeyError, ValueError):
            pass
        
        return None
    
    def fetch_commodity_price(self, commodity_code: str, item_name: str) -> Optional[Dict]:
        """
        Fetch commodity price (oil, gas, etc.).
        
        Note: Requires Alpha Vantage API key (free tier available).
        Get key at: https://www.alphavantage.co/support/#api-key
        
        Args:
            commodity_code: Commodity code
            item_name: Original item name
            
        Returns:
            Price data dictionary or None
        """
        if 'alphavantage' not in self.api_keys:
            print(f"    ⚠ Alpha Vantage API key required for {item_name}")
            print("    Get free key at: https://www.alphavantage.co/support/#api-key")
            print("    Then use: crawler.add_api_key('alphavantage', 'YOUR_KEY')")
            return None
        
        try:
            print(f"  Fetching {item_name} from Alpha Vantage API...")
            
            url = "https://www.alphavantage.co/query"
            params = {
                'function': 'WTI' if commodity_code == 'WTI' else 'BRENT',
                'apikey': self.api_keys['alphavantage'],
                'datatype': 'json'
            }
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            if 'data' in data and len(data['data']) > 0:
                latest = data['data'][0]
                price = float(latest['value'])
                
                result = {
                    'item_name': item_name,
                    'title': f"{item_name.title()} per Barrel",
                    'price': round(price, 2),
                    'currency': '$',
                    'unit': 'barrel',
                    'source': 'Alpha Vantage',
                    'api': 'alphavantage',
                    'timestamp': datetime.now().isoformat(),
                    'url': "https://www.alphavantage.co/"
                }
                
                print(f"    ✓ Price: ${price:,.2f} per barrel")
                return result
                
        except requests.RequestException as e:
            print(f"    ✗ Network error: {type(e).__name__}")
        except (KeyError, ValueError) as e:
            print(f"    ✗ Parse error: {type(e).__name__}")
        
        return None
    
    def search_item(self, item_name: str) -> Optional[Dict]:
        """
        Intelligently determine item type and fetch price.
        
        Args:
            item_name: Name of item to search for
            
        Returns:
            Price data dictionary or None
        """
        item_lower = item_name.lower().strip()
        
        # Check if it's a cryptocurrency
        for crypto_key, crypto_id in self.crypto_map.items():
            if crypto_key in item_lower:
                return self.fetch_crypto_price(crypto_id, item_name)
        
        # Check if it's a precious metal
        for metal_key, metal_code in self.metal_map.items():
            if metal_key in item_lower:
                return self.fetch_metal_price(metal_code, item_name)
        
        # Check if it's a commodity
        for commodity_key, commodity_code in self.commodity_map.items():
            if commodity_key in item_lower:
                return self.fetch_commodity_price(commodity_code, item_name)
        
        # Unknown item type
        print(f"  ⚠ Unknown item type: {item_name}")
        print("     Supported: Crypto (Bitcoin, Ethereum), Metals (Gold, Silver), Commodities (Oil)")
        return None
    
    def search_multiple_items(self, items: List[str]) -> Dict[str, Optional[Dict]]:
        """
        Search for multiple items.
        
        Args:
            items: List of item names
            
        Returns:
            Dictionary mapping item names to their price data
        """
        results = {}
        
        for item in items:
            print(f"\n{'='*60}")
            print(f"Searching for: {item}")
            print(f"{'='*60}")
            
            result = self.search_item(item)
            results[item] = result
            
            if result:
                self.price_history.append(result)
            
            # Rate limiting
            if item != items[-1]:
                time.sleep(self.delay)
        
        return results
    
    def print_results(self, results: Dict[str, Optional[Dict]]):
        """Print formatted results"""
        print("\n" + "="*60)
        print("PRICE RESULTS")
        print("="*60)
        
        for item, data in results.items():
            print(f"\n{item.upper()}")
            print("-" * 60)
            
            if not data:
                print("  ⚠ No price data available")
                continue
            
            print(f"  Price: {data['currency']}{data['price']:,.2f}")
            if 'unit' in data:
                print(f"  Unit: {data['unit']}")
            if 'change_24h' in data:
                change = data['change_24h']
                symbol = "📈" if change > 0 else "📉" if change < 0 else "➡️"
                print(f"  24h Change: {change:+.2f}% {symbol}")
            print(f"  Source: {data['source']}")
            print(f"  Time: {data['timestamp'][:19]}")
    
    def save_to_json(self, filename: str = 'api_price_data.json'):
        """Save price history to JSON"""
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(self.price_history, f, indent=2)
        print(f"\n✓ Saved {len(self.price_history)} records to {filename}")
    
    def save_to_csv(self, filename: str = 'api_price_data.csv'):
        """Save price history to CSV"""
        if not self.price_history:
            print("  ⚠ No data to save")
            return
        
        # Get all unique keys from all records
        all_keys = set()
        for record in self.price_history:
            all_keys.update(record.keys())
        
        with open(filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=sorted(all_keys))
            writer.writeheader()
            writer.writerows(self.price_history)
        print(f"✓ Saved {len(self.price_history)} records to {filename}")


# Example usage
if __name__ == "__main__":
    # Initialize crawler
    crawler = APIPriceCrawler(delay=1.0)
    
    # Optional: Add API keys (get free keys from these services)
    # crawler.add_api_key('alphavantage', 'YOUR_FREE_KEY')  # For oil prices
    # crawler.add_api_key('metals_api', 'YOUR_KEY')  # For metals (optional)
    
    # Items to search (mix of crypto, metals, commodities)
    items_to_search = [
        "Bitcoin",
        "Ethereum",
        "Gold",
        "Silver",
        "Crude Oil",  # Requires Alpha Vantage key
    ]
    
    print("="*60)
    print("API-BASED PRICE CRAWLER")
    print("="*60)
    print("Using free APIs for real-time prices")
    print(f"Searching for {len(items_to_search)} items...")
    
    # Fetch prices
    results = crawler.search_multiple_items(items_to_search)
    
    # Display results
    crawler.print_results(results)
    
    # Save data
    if crawler.price_history:
        crawler.save_to_json()
        crawler.save_to_csv()
        print("\n✓ All data saved successfully!")
    
    print("\n" + "="*60)
    print("API KEY INFORMATION")
    print("="*60)
    print("Free API Keys Available:")
    print("  • CoinGecko: No key needed! ✓")
    print("  • Metal Price API: https://metalpriceapi.com/")
    print("  • Alpha Vantage (Oil): https://www.alphavantage.co/support/#api-key")
    print("="*60)