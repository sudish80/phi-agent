"""
Stock-News Correlation Engine
- Links breaking news to affected stocks
- Multi-tier impact analysis (direct → related → sector → market)
- Predictive alerts based on news sentiment
- Calculate cascade effects through related securities
"""

import sqlite3
import json
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import logging

logger = logging.getLogger(__name__)

# Stock relationships (what stocks are affected by what)
STOCK_RELATIONSHIPS = {
    'TESLA': {
        'direct': ['TSLA'],
        'suppliers': ['NVDA', 'GOOGL'],  # Chip suppliers, tech
        'competitors': ['GM', 'F', 'TM'],  # Auto competitors
        'sector': 'EV/Auto',
        'market': ['SPY', 'QQQ']  # S&P 500, Nasdaq
    },
    'AAPL': {
        'direct': ['AAPL'],
        'suppliers': ['TSMC', 'NVDA', 'QCOM'],  # Taiwan Semi, Nvidia, Qualcomm
        'competitors': ['MSFT', 'GOOGL'],
        'sector': 'Tech',
        'market': ['SPY', 'QQQ', 'XLK']
    },
    'MSFT': {
        'direct': ['MSFT'],
        'suppliers': ['NVDA', 'QCOM'],
        'competitors': ['AAPL', 'GOOGL'],
        'sector': 'Tech/Cloud',
        'market': ['SPY', 'QQQ']
    },
    'XOM': {
        'direct': ['XOM'],
        'competitors': ['CVX', 'COP'],
        'sector': 'Energy',
        'market': ['SPY', 'XLE']
    },
    'JPM': {
        'direct': ['JPM'],
        'competitors': ['BAC', 'WFC'],
        'sector': 'Finance',
        'market': ['SPY', 'XLF']
    }
}

# News impact multipliers
IMPACT_MULTIPLIERS = {
    'earnings': {'direct': 2.5, 'suppliers': 1.2, 'competitors': 0.8, 'sector': 1.5},
    'acquisition': {'direct': 3.0, 'suppliers': 1.5, 'competitors': 1.0, 'sector': 1.8},
    'bankruptcy': {'direct': 4.0, 'suppliers': 2.0, 'competitors': 0.5, 'sector': 2.5},
    'regulation': {'direct': 2.0, 'suppliers': 1.0, 'competitors': 1.0, 'sector': 2.0},
    'product_launch': {'direct': 1.8, 'suppliers': 1.2, 'competitors': 0.9, 'sector': 1.2},
    'security_breach': {'direct': 2.5, 'suppliers': 0.8, 'competitors': 0.5, 'sector': 1.0},
    'profit_warning': {'direct': 3.5, 'suppliers': 1.5, 'competitors': 0.7, 'sector': 1.8},
    'award': {'direct': 1.2, 'suppliers': 0.8, 'competitors': 0.3, 'sector': 0.8},
}


class StockNewsCorrelation:
    """Correlate news with stock impacts"""
    
    def __init__(self):
        self.db_path = "phi_audit.db"
        self._init_db()
    
    def _init_db(self):
        """Initialize correlation tables"""
        conn = sqlite3.connect(self.db_path, timeout=10)
        c = conn.cursor()
        
        c.execute('''
            CREATE TABLE IF NOT EXISTS stock_news_correlations (
                id INTEGER PRIMARY KEY,
                news_id INTEGER,
                primary_stock TEXT,
                affected_stocks TEXT,
                impact_type TEXT,
                impact_score REAL,
                direct_impact REAL,
                secondary_impact REAL,
                cascade_impact REAL,
                prediction_confidence REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        c.execute('''
            CREATE TABLE IF NOT EXISTS impact_analysis (
                id INTEGER PRIMARY KEY,
                stock TEXT,
                trigger_news TEXT,
                tier_1_impact REAL,
                tier_2_impact REAL,
                tier_3_impact REAL,
                tier_4_impact REAL,
                total_cascade REAL,
                analysis_data JSON,
                predicted_move_percent REAL,
                confidence REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        c.execute('''
            CREATE TABLE IF NOT EXISTS cascade_predictions (
                id INTEGER PRIMARY KEY,
                user_id INTEGER,
                trigger_stock TEXT,
                affected_tier_1 TEXT,
                affected_tier_2 TEXT,
                affected_tier_3 TEXT,
                total_estimate REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def extract_keywords_from_news(self, title: str, description: str) -> Tuple[str, List[str]]:
        """Extract impact type and keywords from news"""
        content = f"{title} {description}".lower()
        
        impact_keywords = {
            'earnings': ['earnings', 'profit', 'revenue', 'beat', 'miss', 'guidance', 'EPS'],
            'acquisition': ['acquire', 'acquisition', 'buyout', 'takeover', 'deal'],
            'bankruptcy': ['bankrupt', 'liquidation', 'restructuring', 'chapter 11'],
            'regulation': ['regulate', 'regulation', 'law', 'sanctions', 'compliance', 'SEC'],
            'product_launch': ['launch', 'release', 'introduce', 'new product', 'innovation'],
            'security_breach': ['breach', 'hack', 'cyberattack', 'data breach', 'security'],
            'profit_warning': ['warning', 'slump', 'decline', 'downturn', 'weak'],
            'award': ['award', 'recognition', 'achievement', 'milestone', 'success'],
        }
        
        detected_impact = 'general'
        found_keywords = []
        
        for impact_type, keywords in impact_keywords.items():
            for keyword in keywords:
                if keyword.lower() in content:
                    detected_impact = impact_type
                    found_keywords.append(keyword)
        
        return detected_impact, found_keywords
    
    def find_affected_stocks(self, title: str, description: str) -> List[Dict]:
        """Find which stocks are affected by news"""
        content = f"{title} {description}".lower()
        affected = []
        
        for stock, relationships in STOCK_RELATIONSHIPS.items():
            # Check if company name mentioned
            company_name = stock.lower()
            if company_name in content or stock in title:
                affected.append({
                    'stock': stock,
                    'relationship': 'direct',
                    'confidence': 0.95
                })
        
        return affected
    
    def calculate_multi_tier_impact(self, primary_stock: str, impact_type: str, 
                                    severity: str = 'HIGH') -> Dict:
        """Calculate impact across 4 tiers:
        Tier 1: Direct impact on primary stock
        Tier 2: Impact on suppliers and competitors
        Tier 3: Sector-wide impact
        Tier 4: Market-wide impact
        """
        
        if primary_stock not in STOCK_RELATIONSHIPS:
            return {}
        
        relationships = STOCK_RELATIONSHIPS[primary_stock]
        impact_mult = IMPACT_MULTIPLIERS.get(impact_type, {})
        
        # Severity multiplier
        severity_mult = {'CRITICAL': 2.0, 'HIGH': 1.5, 'MEDIUM': 1.0, 'LOW': 0.5}.get(severity, 1.0)
        
        analysis = {
            'primary_stock': primary_stock,
            'impact_type': impact_type,
            'severity': severity,
            'tiers': {}
        }
        
        # Tier 1: Direct impact (usually 5-15% move)
        tier_1_move = impact_mult.get('direct', 1.0) * severity_mult
        tier_1_move = min(15, max(2, tier_1_move))  # Clamp 2-15%
        analysis['tiers']['tier_1'] = {
            'stocks': relationships['direct'],
            'expected_move_percent': tier_1_move,
            'affected_count': len(relationships['direct']),
            'total_cascade': tier_1_move
        }
        
        # Tier 2: Suppliers and competitors (usually 1-5% move)
        all_tier_2 = relationships.get('suppliers', []) + relationships.get('competitors', [])
        tier_2_move = impact_mult.get('suppliers', 1.0) * severity_mult * 0.6  # Dampened
        tier_2_move = min(5, max(0.5, tier_2_move))
        analysis['tiers']['tier_2'] = {
            'stocks': all_tier_2,
            'expected_move_percent': tier_2_move,
            'affected_count': len(all_tier_2),
            'total_cascade': tier_2_move * len(all_tier_2)
        }
        
        # Tier 3: Sector (usually 0.5-3% move)
        tier_3_move = impact_mult.get('sector', 1.0) * severity_mult * 0.3
        tier_3_move = min(3, max(0.3, tier_3_move))
        analysis['tiers']['tier_3'] = {
            'sector': relationships.get('sector', 'Unknown'),
            'expected_move_percent': tier_3_move,
            'total_cascade': tier_3_move
        }
        
        # Tier 4: Market (usually <1% move)
        tier_4_move = severity_mult * 0.1
        tier_4_move = min(1, max(0.1, tier_4_move))
        analysis['tiers']['tier_4'] = {
            'index': relationships.get('market', ['SPY']),
            'expected_move_percent': tier_4_move,
            'total_cascade': tier_4_move
        }
        
        # Total estimated cascade
        analysis['total_cascade_estimate'] = (
            analysis['tiers']['tier_1']['total_cascade'] +
            analysis['tiers']['tier_2']['total_cascade'] +
            analysis['tiers']['tier_3']['total_cascade'] +
            analysis['tiers']['tier_4']['total_cascade']
        )
        
        return analysis
    
    def predict_market_move(self, primary_stock: str, impact_type: str, 
                           severity: str, current_price: float) -> Dict:
        """Predict market move for the stock"""
        
        analysis = self.calculate_multi_tier_impact(primary_stock, impact_type, severity)
        
        if not analysis:
            return {}
        
        tier_1 = analysis['tiers']['tier_1']
        predicted_move = tier_1['expected_move_percent']
        
        # Direction based on impact type
        positive_impacts = ['earnings', 'product_launch', 'award']
        negative_impacts = ['bankruptcy', 'security_breach', 'profit_warning']
        
        direction = 'up' if impact_type in positive_impacts else 'down' if impact_type in negative_impacts else 'uncertain'
        
        if direction == 'down':
            predicted_move = -predicted_move
        elif direction == 'uncertain':
            predicted_move = abs(predicted_move) * 0.5  # Reduce uncertainty
        
        new_price = current_price * (1 + predicted_move / 100)
        
        return {
            'primary_stock': primary_stock,
            'current_price': current_price,
            'predicted_move_percent': round(predicted_move, 2),
            'predicted_price': round(new_price, 2),
            'direction': direction,
            'confidence': 0.75,
            'multi_tier_analysis': analysis,
            'cascade_affected': {
                'tier_1': len(analysis['tiers']['tier_1']['stocks']),
                'tier_2': analysis['tiers']['tier_2']['affected_count'],
                'tier_3': 1,  # One sector
                'tier_4': len(analysis['tiers']['tier_4']['index'])
            }
        }
    
    def correlate_news_to_stocks(self, user_id: int, article: Dict, 
                                 affected_stocks: List[str]) -> List[Dict]:
        """Full correlation: news → primary stocks → cascade effects"""
        
        correlations = []
        
        for stock in affected_stocks:
            try:
                title = article.get('title', '')
                description = article.get('description', '')
                
                # Extract impact type
                impact_type, keywords = self.extract_keywords_from_news(title, description)
                
                # Determine severity
                severity = 'HIGH' if any(kw in ['earnings', 'bankruptcy', 'warning'] 
                                        for kw in keywords) else 'MEDIUM'
                
                # Calculate multi-tier impact
                analysis = self.calculate_multi_tier_impact(stock, impact_type, severity)
                
                if analysis:
                    # Get current stock price (mock for now)
                    current_price = 100.0  # Default, would fetch real price
                    
                    # Predict move
                    prediction = self.predict_market_move(stock, impact_type, severity, current_price)
                    
                    # Store correlation
                    conn = sqlite3.connect(self.db_path, timeout=10)
                    c = conn.cursor()
                    
                    affected_stocks_str = ','.join(
                        analysis['tiers']['tier_1']['stocks'] + 
                        analysis['tiers']['tier_2']['stocks']
                    )
                    
                    c.execute('''
                        INSERT INTO stock_news_correlations 
                        (primary_stock, affected_stocks, impact_type, impact_score, 
                         direct_impact, secondary_impact, cascade_impact, prediction_confidence)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (stock, affected_stocks_str, impact_type, 
                         prediction.get('predicted_move_percent', 0),
                         analysis['tiers']['tier_1']['total_cascade'],
                         analysis['tiers']['tier_2']['total_cascade'],
                         analysis['total_cascade_estimate'],
                         prediction.get('confidence', 0.75)))
                    
                    conn.commit()
                    conn.close()
                    
                    correlations.append(prediction)
            
            except Exception as e:
                logger.error(f"Error correlating {stock} with news: {e}")
        
        return correlations


# Global instance
correlation_engine = StockNewsCorrelation()
