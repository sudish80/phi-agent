"""
Stock Price Tracking System with Advanced Monitoring
- Track stock prices and movements
- Monitor percentage swings (2%+, 5%+, 10%+)
- Generate alerts based on thresholds
- Support real API (Alpha Vantage) and mock data
- Track price history for trend analysis
"""

import requests
import sqlite3
import json
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import logging
import random

logger = logging.getLogger(__name__)

# Stock alert thresholds
STOCK_ALERTS = {
    'extreme_swing': {'percent': 10, 'severity': 'CRITICAL'},  # 10%+ move
    'major_swing': {'percent': 5, 'severity': 'HIGH'},          # 5%+ move
    'significant_swing': {'percent': 2, 'severity': 'MEDIUM'},  # 2%+ move
}


class StockHandler:
    """Handle real and mock stock data"""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        self.use_mock = not api_key
        self.base_url = "https://www.alphavantage.co/query"
        
        # Popular stocks to track
        self.popular_stocks = [
            'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TESLA', 'NVDA', 'META',
            'JPM', 'BAC', 'WFC', 'XOM', 'CVX', 'BRK.B', 'JNJ', 'PG'
        ]
    
    def get_stock_price(self, symbol: str) -> Dict:
        """Get current stock price"""
        if self.use_mock:
            return self._mock_stock_price(symbol)
        
        try:
            params = {
                'function': 'GLOBAL_QUOTE',
                'symbol': symbol,
                'apikey': self.api_key
            }
            response = requests.get(self.base_url, params=params, timeout=5)
            response.raise_for_status()
            data = response.json()
            
            if 'Global Quote' not in data or not data['Global Quote']:
                return self._mock_stock_price(symbol)
            
            quote = data['Global Quote']
            return {
                'symbol': symbol,
                'price': float(quote['05. price']),
                'open': float(quote['02. open']),
                'high': float(quote['03. high']),
                'low': float(quote['04. low']),
                'volume': int(quote['06. volume']),
                'change': float(quote['09. change']),
                'change_percent': float(quote['10. change percent'].rstrip('%')),
                'timestamp': datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Error fetching stock {symbol}: {e}")
            return self._mock_stock_price(symbol)
    
    def get_intraday(self, symbol: str, interval: str = '60min') -> List[Dict]:
        """Get intraday stock data"""
        if self.use_mock:
            return self._mock_intraday(symbol, interval)
        
        try:
            params = {
                'function': f'TIME_SERIES_INTRADAY',
                'symbol': symbol,
                'interval': interval,
                'apikey': self.api_key
            }
            response = requests.get(self.base_url, params=params, timeout=5)
            response.raise_for_status()
            data = response.json()
            
            if 'Error Message' in data:
                return self._mock_intraday(symbol, interval)
            
            series_key = f'Time Series ({interval})'
            if series_key not in data:
                return self._mock_intraday(symbol, interval)
            
            data_points = []
            for timestamp, values in list(data[series_key].items())[:20]:
                data_points.append({
                    'timestamp': timestamp,
                    'open': float(values['1. open']),
                    'high': float(values['2. high']),
                    'low': float(values['3. low']),
                    'close': float(values['4. close']),
                    'volume': int(values['5. volume']),
                })
            
            return data_points
        except Exception as e:
            logger.error(f"Error fetching intraday for {symbol}: {e}")
            return self._mock_intraday(symbol, interval)
    
    def _mock_stock_price(self, symbol: str) -> Dict:
        """Generate realistic mock stock data"""
        # Base prices for popular stocks
        base_prices = {
            'AAPL': 180, 'MSFT': 380, 'GOOGL': 140, 'AMZN': 170,
            'TESLA': 220, 'NVDA': 850, 'META': 480, 'JPM': 190,
            'BAC': 32, 'XOM': 110, 'CVX': 160, 'BRK.B': 385,
        }
        
        base = base_prices.get(symbol.upper(), 100)
        
        # Realistic volatility
        change_percent = random.uniform(-8, 8)  # ±8% move
        open_price = base
        current_price = open_price * (1 + change_percent / 100)
        
        return {
            'symbol': symbol,
            'price': round(current_price, 2),
            'open': round(open_price, 2),
            'high': round(current_price * 1.02, 2),
            'low': round(current_price * 0.98, 2),
            'volume': random.randint(1000000, 50000000),
            'change': round(current_price - open_price, 2),
            'change_percent': round(change_percent, 2),
            'timestamp': datetime.now().isoformat()
        }
    
    def _mock_intraday(self, symbol: str, interval: str) -> List[Dict]:
        """Generate realistic mock intraday data"""
        base_price = self._mock_stock_price(symbol)['price']
        data = []
        
        current_time = datetime.now()
        for i in range(20):
            time_point = current_time - timedelta(minutes=int(interval.rstrip('min')) * (19 - i))
            price = base_price * random.uniform(0.98, 1.02)
            
            data.append({
                'timestamp': time_point.isoformat(),
                'open': round(price * 0.99, 2),
                'high': round(price * 1.01, 2),
                'low': round(price * 0.98, 2),
                'close': round(price, 2),
                'volume': random.randint(500000, 10000000),
            })
        
        return data


class StockTracker:
    """Track user stock subscriptions and generate alerts"""
    
    def __init__(self, api_key: Optional[str] = None):
        self.handler = StockHandler(api_key)
        self.db_path = "phi_audit.db"
        self._init_db()
    
    def _init_db(self):
        """Initialize stock tables"""
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.execute('PRAGMA journal_mode=WAL')
        c = conn.cursor()
        
        c.execute('''
            CREATE TABLE IF NOT EXISTS user_stock_subscriptions (
                id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL,
                symbol TEXT NOT NULL,
                alert_threshold REAL DEFAULT 2.0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, symbol)
            )
        ''')
        
        c.execute('''
            CREATE TABLE IF NOT EXISTS stock_alerts (
                id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL,
                symbol TEXT NOT NULL,
                alert_type TEXT NOT NULL,
                severity TEXT NOT NULL,
                price_change REAL,
                percent_change REAL,
                current_price REAL,
                previous_price REAL,
                description TEXT,
                stock_data JSON,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                read_at TIMESTAMP
            )
        ''')
        
        c.execute('''
            CREATE TABLE IF NOT EXISTS stock_prices_history (
                id INTEGER PRIMARY KEY,
                symbol TEXT NOT NULL,
                price REAL,
                change_percent REAL,
                volume INTEGER,
                recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        c.execute('''
            CREATE TABLE IF NOT EXISTS popular_stocks (
                id INTEGER PRIMARY KEY,
                symbol TEXT UNIQUE NOT NULL,
                current_price REAL,
                change_percent REAL,
                rank INTEGER,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def subscribe_to_stock(self, user_id: int, symbol: str, 
                          alert_threshold: float = 2.0) -> Tuple[bool, str]:
        """Subscribe to stock alerts"""
        try:
            conn = sqlite3.connect(self.db_path, timeout=10)
            c = conn.cursor()
            
            c.execute('''
                INSERT INTO user_stock_subscriptions 
                (user_id, symbol, alert_threshold)
                VALUES (?, ?, ?)
            ''', (user_id, symbol.upper(), alert_threshold))
            
            conn.commit()
            conn.close()
            
            logger.info(f"User {user_id} subscribed to {symbol} stock")
            return True, f"Subscribed to {symbol} stock alerts (threshold: {alert_threshold}%)"
        except sqlite3.IntegrityError:
            return False, f"Already subscribed to {symbol}"
        except Exception as e:
            logger.error(f"Error subscribing to stock: {e}")
            return False, str(e)
    
    def get_subscriptions(self, user_id: int) -> List[Dict]:
        """Get user's stock subscriptions"""
        conn = sqlite3.connect(self.db_path, timeout=10)
        c = conn.cursor()
        
        c.execute('''
            SELECT id, symbol, alert_threshold 
            FROM user_stock_subscriptions 
            WHERE user_id = ?
        ''', (user_id,))
        
        rows = c.fetchall()
        conn.close()
        
        return [
            {'id': r[0], 'symbol': r[1], 'alert_threshold': r[2]}
            for r in rows
        ]
    
    def analyze_stock_movement(self, symbol: str, current_price: Dict, 
                               previous_price: Optional[float] = None) -> Tuple[str, str, str]:
        """Analyze stock movement and return (severity, alert_type, description)"""
        percent_change = current_price['change_percent']
        price = current_price['price']
        
        # Determine severity based on percentage change
        if abs(percent_change) >= 10:
            alert_type = 'extreme_swing'
            severity = 'CRITICAL'
            direction = 'up' if percent_change > 0 else 'down'
            description = (f"🚨 CRITICAL: {symbol} swung {abs(percent_change):.2f}% {direction}! "
                         f"Price: ${price:.2f}")
        
        elif abs(percent_change) >= 5:
            alert_type = 'major_swing'
            severity = 'HIGH'
            direction = 'up' if percent_change > 0 else 'down'
            description = (f"⚠️ MAJOR: {symbol} moved {abs(percent_change):.2f}% {direction}. "
                         f"Price: ${price:.2f}, Volume: {current_price['volume']:,}")
        
        elif abs(percent_change) >= 2:
            alert_type = 'significant_swing'
            severity = 'MEDIUM'
            direction = 'up' if percent_change > 0 else 'down'
            description = f"{symbol} moved {abs(percent_change):.2f}% {direction} to ${price:.2f}"
        
        else:
            alert_type = 'normal'
            severity = 'LOW'
            description = f"{symbol} is stable at ${price:.2f}"
        
        return severity, alert_type, description
    
    def check_alerts(self, user_id: int) -> List[Dict]:
        """Check stocks for user's subscribed symbols and generate alerts"""
        subscriptions = self.get_subscriptions(user_id)
        alerts = []
        
        for sub in subscriptions:
            try:
                # Get current price
                current = self.handler.get_stock_price(sub['symbol'])
                
                # Get intraday data
                intraday = self.handler.get_intraday(sub['symbol'])
                
                # Analyze movement
                severity, alert_type, description = self.analyze_stock_movement(
                    sub['symbol'], current
                )
                
                # Check if alert meets threshold
                severity_levels = {'LOW': 0, 'MEDIUM': 1, 'HIGH': 2, 'CRITICAL': 3}
                if abs(current['change_percent']) >= sub['alert_threshold']:
                    conn = sqlite3.connect(self.db_path, timeout=10)
                    c = conn.cursor()
                    
                    c.execute('''
                        INSERT INTO stock_alerts 
                        (user_id, symbol, alert_type, severity, price_change, percent_change, 
                         current_price, description, stock_data)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (user_id, sub['symbol'], alert_type, severity, current['change'], 
                         current['change_percent'], current['price'], description, 
                         json.dumps({'current': current, 'intraday': intraday})))
                    
                    conn.commit()
                    conn.close()
                    
                    alerts.append({
                        'symbol': sub['symbol'],
                        'type': alert_type,
                        'severity': severity,
                        'description': description,
                        'current_price': current['price'],
                        'percent_change': current['change_percent'],
                        'intraday': intraday
                    })
            
            except Exception as e:
                logger.error(f"Error checking stock {sub['symbol']}: {e}")
        
        return alerts
    
    def get_popular_stocks(self, limit: int = 10) -> List[Dict]:
        """Get top stocks by activity/volatility"""
        stocks = []
        for symbol in self.handler.popular_stocks[:limit]:
            try:
                data = self.handler.get_stock_price(symbol)
                stocks.append({
                    'symbol': symbol,
                    'price': data['price'],
                    'change_percent': data['change_percent'],
                    'volume': data['volume'],
                    'severity': self.analyze_stock_movement(symbol, data)[0]
                })
            except:
                pass
        
        # Sort by absolute change
        stocks.sort(key=lambda x: abs(x['change_percent']), reverse=True)
        return stocks
    
    def unsubscribe(self, user_id: int, symbol: str) -> Tuple[bool, str]:
        """Unsubscribe from stock alerts"""
        try:
            conn = sqlite3.connect(self.db_path, timeout=10)
            c = conn.cursor()
            
            c.execute('''
                DELETE FROM user_stock_subscriptions 
                WHERE user_id = ? AND symbol = ?
            ''', (user_id, symbol.upper()))
            
            conn.commit()
            conn.close()
            
            return True, f"Unsubscribed from {symbol} alerts"
        except Exception as e:
            return False, str(e)


# Global instance
stock_tracker = StockTracker()
