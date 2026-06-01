"""
News Tracking System with Keyword Detection
- Monitor breaking news from multiple sources
- Filter by keywords, topics, severity
- Detect market-moving news
- Support real API (NewsAPI) and mock data
- Track news sentiment and impact
"""

import requests
import sqlite3
import json
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import logging
import random

logger = logging.getLogger(__name__)

# News keywords for market-moving content
MARKET_KEYWORDS = {
    'stocks': ['stock market', 'earnings', 'IPO', 'acquisition', 'merger', 'bankruptcy'],
    'crypto': ['bitcoin', 'ethereum', 'cryptocurrency', 'blockchain', 'NFT', 'crypto'],
    'tech': ['AI', 'machine learning', 'startup', 'tech', 'software', 'data breach'],
    'finance': ['interest rate', 'inflation', 'recession', 'Fed', 'central bank', 'bond'],
    'commodities': ['oil', 'gold', 'natural gas', 'wheat', 'copper'],
    'geopolitics': ['war', 'sanctions', 'trade war', 'tariff', 'regulation'],
}

COMPANY_STOCKS = {
    'apple': 'AAPL', 'microsoft': 'MSFT', 'google': 'GOOGL', 'amazon': 'AMZN',
    'tesla': 'TESLA', 'nvidia': 'NVDA', 'meta': 'META', 'facebook': 'META',
    'jpmorgan': 'JPM', 'bank of america': 'BAC', 'exxon': 'XOM', 'chevron': 'CVX',
}


class NewsHandler:
    """Handle real and mock news data"""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        self.use_mock = not api_key
        self.base_url = "https://newsapi.org/v2"
    
    def get_top_headlines(self, query: str = None, category: str = None, 
                         language: str = 'en', limit: int = 20) -> List[Dict]:
        """Get top headlines"""
        if self.use_mock:
            return self._mock_headlines(query, limit)
        
        try:
            url = f"{self.base_url}/top-headlines"
            params = {
                'language': language,
                'pageSize': limit,
                'apiKey': self.api_key
            }
            
            if query:
                params['q'] = query
            if category:
                params['category'] = category
            
            response = requests.get(url, params=params, timeout=5)
            response.raise_for_status()
            data = response.json()
            
            if data['status'] != 'ok':
                return self._mock_headlines(query, limit)
            
            headlines = []
            for article in data.get('articles', [])[:limit]:
                headlines.append({
                    'title': article['title'],
                    'description': article.get('description', ''),
                    'source': article['source']['name'],
                    'url': article['url'],
                    'image': article.get('urlToImage', ''),
                    'published_at': article['publishedAt'],
                    'content': article.get('content', ''),
                })
            
            return headlines
        except Exception as e:
            logger.error(f"Error fetching news: {e}")
            return self._mock_headlines(query, limit)
    
    def search_news(self, query: str, sort_by: str = 'publishedAt', 
                   limit: int = 20) -> List[Dict]:
        """Search for news articles"""
        if self.use_mock:
            return self._mock_search_results(query, limit)
        
        try:
            url = f"{self.base_url}/everything"
            params = {
                'q': query,
                'sortBy': sort_by,
                'pageSize': limit,
                'apiKey': self.api_key,
                'language': 'en'
            }
            
            response = requests.get(url, params=params, timeout=5)
            response.raise_for_status()
            data = response.json()
            
            if data['status'] != 'ok':
                return self._mock_search_results(query, limit)
            
            articles = []
            for article in data.get('articles', [])[:limit]:
                articles.append({
                    'title': article['title'],
                    'description': article.get('description', ''),
                    'source': article['source']['name'],
                    'url': article['url'],
                    'image': article.get('urlToImage', ''),
                    'published_at': article['publishedAt'],
                    'content': article.get('content', ''),
                    'author': article.get('author', 'Unknown'),
                })
            
            return articles
        except Exception as e:
            logger.error(f"Error searching news: {e}")
            return self._mock_search_results(query, limit)
    
    def _mock_headlines(self, query: str = None, limit: int = 20) -> List[Dict]:
        """Generate realistic mock news headlines"""
        mock_headlines = [
            {
                'title': 'Tesla Stock Surges 6% on New Battery Technology Announcement',
                'description': 'Tesla announced a breakthrough in battery technology that could extend vehicle range by 20%.',
                'source': 'Reuters',
                'impact': 'Tesla'
            },
            {
                'title': 'Lightning Storm Warning: Major Cities Face Severe Weather Tomorrow',
                'description': 'Meteorologists warn of severe thunderstorms and lightning across the Northeast.',
                'source': 'WeatherNews',
                'impact': 'Weather'
            },
            {
                'title': 'Tech Giant Reports Record Earnings, Stock Up 4%',
                'description': 'Major technology company beats earnings expectations.',
                'source': 'CNBC',
                'impact': 'AAPL'
            },
            {
                'title': 'Oil Prices Spike 3% Following Geopolitical Tensions',
                'description': 'Crude oil prices jump due to supply concerns from Middle East.',
                'source': 'Bloomberg',
                'impact': 'XOM'
            },
            {
                'title': 'AI Regulation Bill Passes Senate Committee',
                'description': 'Major AI regulation bill advances, affecting tech stocks.',
                'source': 'TechNews',
                'impact': 'NVDA'
            },
            {
                'title': 'Fed Signals Potential Rate Cuts in 2024',
                'description': 'Federal Reserve hints at lower interest rates, boosting market sentiment.',
                'source': 'MarketWatch',
                'impact': 'Market'
            },
            {
                'title': 'Cryptocurrency Market Rallies 5% on Institutional Investment News',
                'description': 'Bitcoin and Ethereum surge as major institutions announce positions.',
                'source': 'CoinDesk',
                'impact': 'Crypto'
            },
            {
                'title': 'Supply Chain Disruptions Impact Consumer Prices',
                'description': 'Global supply chain issues continue to affect inflation.',
                'source': 'Reuters',
                'impact': 'Market'
            },
        ]
        
        # Filter by query if provided
        if query:
            query_lower = query.lower()
            mock_headlines = [h for h in mock_headlines 
                            if query_lower in h['title'].lower() or 
                               query_lower in h['description'].lower()]
        
        # Return requested limit
        results = []
        for headline in mock_headlines[:limit]:
            results.append({
                'title': headline['title'],
                'description': headline['description'],
                'source': headline['source'],
                'url': f"https://example.com/news/{headline['title'].replace(' ', '-')}",
                'image': f"https://example.com/images/news-{random.randint(1, 100)}.jpg",
                'published_at': (datetime.now() - timedelta(hours=random.randint(0, 24))).isoformat(),
                'content': headline['description'],
                'author': 'Editorial Team',
            })
        
        return results
    
    def _mock_search_results(self, query: str, limit: int = 20) -> List[Dict]:
        """Generate mock search results"""
        return self._mock_headlines(query, limit)


class NewsTracker:
    """Track news and detect market-moving content"""
    
    def __init__(self, api_key: Optional[str] = None):
        self.handler = NewsHandler(api_key)
        self.db_path = "phi_audit.db"
        self._init_db()
    
    def _init_db(self):
        """Initialize news tables"""
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.execute('PRAGMA journal_mode=WAL')
        c = conn.cursor()
        
        c.execute('''
            CREATE TABLE IF NOT EXISTS user_news_subscriptions (
                id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL,
                topic TEXT NOT NULL,
                keywords TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, topic)
            )
        ''')
        
        c.execute('''
            CREATE TABLE IF NOT EXISTS news_alerts (
                id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                source TEXT,
                severity TEXT,
                impact_type TEXT,
                affected_stocks TEXT,
                keywords TEXT,
                article_url TEXT,
                news_data JSON,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                read_at TIMESTAMP
            )
        ''')
        
        c.execute('''
            CREATE TABLE IF NOT EXISTS news_cache (
                id INTEGER PRIMARY KEY,
                query TEXT UNIQUE NOT NULL,
                articles JSON,
                cached_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        c.execute('''
            CREATE TABLE IF NOT EXISTS market_moving_news (
                id INTEGER PRIMARY KEY,
                title TEXT UNIQUE NOT NULL,
                affected_stocks TEXT,
                severity TEXT,
                impact_score REAL,
                discovered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def subscribe_to_topic(self, user_id: int, topic: str, 
                          keywords: Optional[List[str]] = None) -> Tuple[bool, str]:
        """Subscribe to news topic"""
        try:
            keywords_str = ','.join(keywords) if keywords else ''
            
            conn = sqlite3.connect(self.db_path, timeout=10)
            c = conn.cursor()
            
            c.execute('''
                INSERT INTO user_news_subscriptions 
                (user_id, topic, keywords)
                VALUES (?, ?, ?)
            ''', (user_id, topic, keywords_str))
            
            conn.commit()
            conn.close()
            
            logger.info(f"User {user_id} subscribed to {topic} news")
            return True, f"Subscribed to {topic} news"
        except sqlite3.IntegrityError:
            return False, f"Already subscribed to {topic}"
        except Exception as e:
            logger.error(f"Error subscribing to news: {e}")
            return False, str(e)
    
    def get_subscriptions(self, user_id: int) -> List[Dict]:
        """Get user's news subscriptions"""
        conn = sqlite3.connect(self.db_path, timeout=10)
        c = conn.cursor()
        
        c.execute('''
            SELECT id, topic, keywords 
            FROM user_news_subscriptions 
            WHERE user_id = ?
        ''', (user_id,))
        
        rows = c.fetchall()
        conn.close()
        
        return [
            {'id': r[0], 'topic': r[1], 'keywords': r[2].split(',') if r[2] else []}
            for r in rows
        ]
    
    def detect_market_moving_news(self, article: Dict) -> Tuple[bool, str, List[str], str]:
        """Detect if article is market-moving and return (is_moving, severity, affected_stocks, impact_type)"""
        title = article['title'].lower()
        description = article['description'].lower() if article.get('description') else ''
        content = f"{title} {description}"
        
        affected_stocks = []
        impact_type = 'general'
        severity = 'LOW'
        
        # Check for company mentions
        for company, symbol in COMPANY_STOCKS.items():
            if company in content:
                affected_stocks.append(symbol)
        
        # Check for keyword matches
        for keyword_type, keywords in MARKET_KEYWORDS.items():
            for keyword in keywords:
                if keyword.lower() in content:
                    impact_type = keyword_type
                    
                    # Determine severity based on impact type
                    if keyword_type in ['earnings', 'acquisition', 'bankruptcy']:
                        severity = 'CRITICAL'
                    elif keyword_type in ['regulation', 'war', 'sanctions']:
                        severity = 'HIGH'
                    elif keyword_type in ['interest rate', 'inflation']:
                        severity = 'MEDIUM'
                    
                    # It's market-moving if we found keywords
                    return True, severity, affected_stocks, impact_type
        
        return False, severity, affected_stocks, impact_type
    
    def check_news(self, user_id: int) -> List[Dict]:
        """Check news for user's subscribed topics"""
        subscriptions = self.get_subscriptions(user_id)
        alerts = []
        
        for sub in subscriptions:
            try:
                # Get news for this topic
                articles = self.handler.search_news(sub['topic'], limit=10)
                
                for article in articles:
                    is_moving, severity, stocks, impact = self.detect_market_moving_news(article)
                    
                    # Create alert for market-moving or matching keyword news
                    if is_moving or any(kw.lower() in f"{article['title']} {article['description']}".lower() 
                                       for kw in sub['keywords']):
                        conn = sqlite3.connect(self.db_path, timeout=10)
                        c = conn.cursor()
                        
                        stocks_str = ','.join(stocks)
                        
                        c.execute('''
                            INSERT OR IGNORE INTO news_alerts 
                            (user_id, title, description, source, severity, impact_type, 
                             affected_stocks, keywords, article_url, news_data)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (user_id, article['title'], article['description'], 
                             article['source'], severity, impact, stocks_str,
                             sub['topic'], article.get('url', ''),
                             json.dumps(article)))
                        
                        conn.commit()
                        conn.close()
                        
                        alerts.append({
                            'title': article['title'],
                            'description': article['description'],
                            'source': article['source'],
                            'severity': severity,
                            'impact_type': impact,
                            'affected_stocks': stocks,
                            'url': article.get('url', ''),
                            'published_at': article.get('published_at', '')
                        })
            
            except Exception as e:
                logger.error(f"Error checking news for {sub['topic']}: {e}")
        
        return alerts
    
    def get_breaking_news(self, limit: int = 10) -> List[Dict]:
        """Get breaking/top news stories"""
        try:
            articles = self.handler.get_top_headlines(limit=limit)
            
            results = []
            for article in articles:
                is_moving, severity, stocks, impact = self.detect_market_moving_news(article)
                
                results.append({
                    'title': article['title'],
                    'description': article['description'],
                    'source': article['source'],
                    'url': article['url'],
                    'severity': severity,
                    'impact': impact,
                    'affected_stocks': stocks,
                    'is_market_moving': is_moving,
                    'published_at': article['published_at']
                })
            
            # Sort by market-moving first
            results.sort(key=lambda x: (x['is_market_moving'], 
                                       {'CRITICAL': 3, 'HIGH': 2, 'MEDIUM': 1, 'LOW': 0}.get(x['severity'], 0)), 
                        reverse=True)
            
            return results
        except Exception as e:
            logger.error(f"Error getting breaking news: {e}")
            return []
    
    def unsubscribe(self, user_id: int, topic: str) -> Tuple[bool, str]:
        """Unsubscribe from news topic"""
        try:
            conn = sqlite3.connect(self.db_path, timeout=10)
            c = conn.cursor()
            
            c.execute('''
                DELETE FROM user_news_subscriptions 
                WHERE user_id = ? AND topic = ?
            ''', (user_id, topic))
            
            conn.commit()
            conn.close()
            
            return True, f"Unsubscribed from {topic} news"
        except Exception as e:
            return False, str(e)


# Global instance
news_tracker = NewsTracker()
