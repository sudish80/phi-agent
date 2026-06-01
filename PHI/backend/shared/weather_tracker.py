"""
Weather Tracking System with Advanced Alerts
- Monitor multiple locations for severe weather
- Track temperature, precipitation, wind, lightning
- Generate severity-based alerts
- Support real API (OpenWeather) and mock data
"""

import requests
import sqlite3
import json
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import logging

logger = logging.getLogger(__name__)

# Weather severity thresholds
WEATHER_THRESHOLDS = {
    'lightning': {'risk': 'CRITICAL', 'temp_range': None},
    'tornado': {'risk': 'CRITICAL', 'wind_speed': 100},
    'hurricane': {'risk': 'CRITICAL', 'wind_speed': 74},
    'thunderstorm': {'risk': 'HIGH', 'wind_speed': 40},
    'heavy_rain': {'risk': 'HIGH', 'precipitation': 50},  # mm
    'hail': {'risk': 'HIGH', 'precipitation': 25},
    'extreme_heat': {'risk': 'MEDIUM', 'temp': 40},  # Celsius
    'extreme_cold': {'risk': 'MEDIUM', 'temp': -20},
    'blizzard': {'risk': 'HIGH', 'wind_speed': 35, 'precipitation': 25},
    'fog': {'risk': 'MEDIUM', 'visibility': 100},  # meters
}


class WeatherHandler:
    """Handle real and mock weather data"""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        self.use_mock = not api_key
        self.base_url = "https://api.openweathermap.org/data/2.5"
    
    def get_current_weather(self, city: str, country_code: str = None) -> Dict:
        """Get current weather for a location"""
        if self.use_mock:
            return self._mock_weather(city)
        
        try:
            location = f"{city},{country_code}" if country_code else city
            url = f"{self.base_url}/weather"
            params = {'q': location, 'appid': self.api_key, 'units': 'metric'}
            response = requests.get(url, params=params, timeout=5)
            response.raise_for_status()
            data = response.json()
            
            return {
                'location': city,
                'temp': data['main']['temp'],
                'feels_like': data['main']['feels_like'],
                'temp_min': data['main']['temp_min'],
                'temp_max': data['main']['temp_max'],
                'humidity': data['main']['humidity'],
                'pressure': data['main']['pressure'],
                'description': data['weather'][0]['description'],
                'wind_speed': data['wind']['speed'],
                'wind_gust': data['wind'].get('gust', 0),
                'clouds': data['clouds']['all'],
                'rain': data.get('rain', {}).get('1h', 0),
                'snow': data.get('snow', {}).get('1h', 0),
                'visibility': data.get('visibility', 10000),
                'timestamp': datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Error fetching weather for {city}: {e}")
            return self._mock_weather(city)
    
    def get_forecast(self, city: str, days: int = 5) -> List[Dict]:
        """Get weather forecast"""
        if self.use_mock:
            return self._mock_forecast(city, days)
        
        try:
            url = f"{self.base_url}/forecast"
            params = {'q': city, 'appid': self.api_key, 'units': 'metric'}
            response = requests.get(url, params=params, timeout=5)
            response.raise_for_status()
            data = response.json()
            
            forecast = []
            for item in data['list'][:days * 8]:  # 8 forecasts per day (3-hour intervals)
                forecast.append({
                    'timestamp': item['dt_txt'],
                    'temp': item['main']['temp'],
                    'description': item['weather'][0]['description'],
                    'wind_speed': item['wind']['speed'],
                    'rain': item.get('rain', {}).get('3h', 0),
                    'snow': item.get('snow', {}).get('3h', 0),
                })
            
            return forecast
        except Exception as e:
            logger.error(f"Error fetching forecast for {city}: {e}")
            return self._mock_forecast(city, days)
    
    def _mock_weather(self, city: str) -> Dict:
        """Generate realistic mock weather data"""
        import random
        
        mock_conditions = [
            {'desc': 'Clear sky', 'wind': 5, 'rain': 0, 'temp': 22},
            {'desc': 'Lightning storm approaching', 'wind': 45, 'rain': 30, 'temp': 18},
            {'desc': 'Heavy rain', 'wind': 35, 'rain': 50, 'temp': 15},
            {'desc': 'Thunderstorm', 'wind': 55, 'rain': 40, 'temp': 16},
            {'desc': 'Windy conditions', 'wind': 60, 'rain': 10, 'temp': 20},
            {'desc': 'Extreme heat', 'wind': 8, 'rain': 0, 'temp': 42},
            {'desc': 'Light rain', 'wind': 15, 'rain': 5, 'temp': 18},
        ]
        
        condition = random.choice(mock_conditions)
        
        return {
            'location': city,
            'temp': condition['temp'],
            'feels_like': condition['temp'] - 2,
            'temp_min': condition['temp'] - 3,
            'temp_max': condition['temp'] + 2,
            'humidity': random.randint(40, 95),
            'pressure': random.randint(1000, 1020),
            'description': condition['desc'],
            'wind_speed': condition['wind'],
            'wind_gust': condition['wind'] + 10,
            'clouds': random.randint(0, 100),
            'rain': condition['rain'],
            'snow': 0,
            'visibility': random.randint(500, 10000),
            'timestamp': datetime.now().isoformat()
        }
    
    def _mock_forecast(self, city: str, days: int = 5) -> List[Dict]:
        """Generate realistic mock forecast"""
        import random
        forecast = []
        for i in range(days * 8):
            hours_ahead = i * 3
            timestamp = datetime.now() + timedelta(hours=hours_ahead)
            
            conditions = ['Clear', 'Cloudy', 'Rainy', 'Thunderstorm', 'Windy']
            condition = random.choice(conditions)
            
            forecast.append({
                'timestamp': timestamp.isoformat(),
                'temp': random.randint(10, 30),
                'description': condition,
                'wind_speed': random.randint(0, 50),
                'rain': random.randint(0, 30) if 'rain' in condition.lower() else 0,
                'snow': 0,
            })
        
        return forecast


class WeatherTracker:
    """Track user weather subscriptions and generate alerts"""
    
    def __init__(self, api_key: Optional[str] = None):
        self.handler = WeatherHandler(api_key)
        self.db_path = "phi_audit.db"
        self._init_db()
    
    def _init_db(self):
        """Initialize weather tables"""
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.execute('PRAGMA journal_mode=WAL')
        c = conn.cursor()
        
        c.execute('''
            CREATE TABLE IF NOT EXISTS user_weather_subscriptions (
                id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL,
                city TEXT NOT NULL,
                country_code TEXT,
                alert_level TEXT DEFAULT 'HIGH',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, city, country_code)
            )
        ''')
        
        c.execute('''
            CREATE TABLE IF NOT EXISTS weather_alerts (
                id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL,
                city TEXT NOT NULL,
                alert_type TEXT NOT NULL,
                severity TEXT NOT NULL,
                description TEXT,
                current_data JSON,
                forecast_data JSON,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                read_at TIMESTAMP
            )
        ''')
        
        c.execute('''
            CREATE TABLE IF NOT EXISTS weather_history (
                id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL,
                city TEXT NOT NULL,
                weather_data JSON,
                recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def subscribe_to_location(self, user_id: int, city: str, 
                             country_code: Optional[str] = None,
                             alert_level: str = 'HIGH') -> Tuple[bool, str]:
        """Subscribe to weather alerts for a location"""
        try:
            conn = sqlite3.connect(self.db_path, timeout=10)
            c = conn.cursor()
            
            c.execute('''
                INSERT INTO user_weather_subscriptions 
                (user_id, city, country_code, alert_level)
                VALUES (?, ?, ?, ?)
            ''', (user_id, city, country_code, alert_level))
            
            conn.commit()
            conn.close()
            
            logger.info(f"User {user_id} subscribed to {city} weather")
            return True, f"Subscribed to weather alerts for {city}"
        except sqlite3.IntegrityError:
            return False, f"Already subscribed to {city}"
        except Exception as e:
            logger.error(f"Error subscribing to weather: {e}")
            return False, str(e)
    
    def get_subscriptions(self, user_id: int) -> List[Dict]:
        """Get user's weather subscriptions"""
        conn = sqlite3.connect(self.db_path, timeout=10)
        c = conn.cursor()
        
        c.execute('''
            SELECT id, city, country_code, alert_level 
            FROM user_weather_subscriptions 
            WHERE user_id = ?
        ''', (user_id,))
        
        rows = c.fetchall()
        conn.close()
        
        return [
            {'id': r[0], 'city': r[1], 'country_code': r[2], 'alert_level': r[3]}
            for r in rows
        ]
    
    def analyze_weather(self, weather_data: Dict) -> Tuple[str, str, str]:
        """Analyze weather and return (severity, alert_type, description)"""
        temp = weather_data['temp']
        wind = weather_data['wind_speed']
        rain = weather_data['rain']
        description = weather_data['description'].lower()
        
        # Check for extreme conditions
        if 'lightning' in description or 'thunder' in description:
            return ('CRITICAL', 'lightning_storm', 
                   f"Lightning storm approaching in {weather_data['location']}! "
                   f"Wind: {wind} km/h, Rain: {rain} mm")
        
        if 'tornado' in description:
            return ('CRITICAL', 'tornado', 
                   f"Tornado warning for {weather_data['location']}!")
        
        if 'hurricane' in description or 'cyclone' in description:
            return ('CRITICAL', 'hurricane', 
                   f"Hurricane warning for {weather_data['location']}!")
        
        if 'thunderstorm' in description and wind > 40:
            return ('HIGH', 'severe_thunderstorm',
                   f"Severe thunderstorm in {weather_data['location']}! "
                   f"Wind: {wind} km/h, Rain: {rain} mm")
        
        if rain > 50:
            return ('HIGH', 'heavy_rain',
                   f"Heavy rain alert for {weather_data['location']}! "
                   f"Rainfall: {rain} mm expected")
        
        if temp > 40:
            return ('MEDIUM', 'extreme_heat',
                   f"Extreme heat warning for {weather_data['location']}! "
                   f"Temperature: {temp}°C")
        
        if temp < -20:
            return ('MEDIUM', 'extreme_cold',
                   f"Extreme cold warning for {weather_data['location']}! "
                   f"Temperature: {temp}°C")
        
        if wind > 60:
            return ('MEDIUM', 'extreme_wind',
                   f"Extreme wind alert for {weather_data['location']}! "
                   f"Wind speed: {wind} km/h")
        
        if 'hail' in description or rain > 25:
            return ('MEDIUM', 'hail',
                   f"Hail storm possible in {weather_data['location']}!")
        
        return ('LOW', 'normal', f"Normal weather in {weather_data['location']}")
    
    def check_alerts(self, user_id: int) -> List[Dict]:
        """Check weather for user's subscribed locations and generate alerts"""
        subscriptions = self.get_subscriptions(user_id)
        alerts = []
        
        for sub in subscriptions:
            try:
                # Get current weather
                weather = self.handler.get_current_weather(sub['city'], sub['country_code'])
                
                # Get forecast
                forecast = self.handler.get_forecast(sub['city'], days=1)
                
                # Analyze for alerts
                severity, alert_type, description = self.analyze_weather(weather)
                
                # Check if alert meets user's threshold
                severity_levels = {'LOW': 0, 'MEDIUM': 1, 'HIGH': 2, 'CRITICAL': 3}
                threshold_levels = {'LOW': 0, 'MEDIUM': 1, 'HIGH': 2, 'CRITICAL': 3}
                
                user_threshold = threshold_levels.get(sub['alert_level'], 2)
                alert_severity = severity_levels.get(severity, 0)
                
                # Store alert if meets threshold
                if alert_severity >= user_threshold:
                    conn = sqlite3.connect(self.db_path, timeout=10)
                    c = conn.cursor()
                    
                    c.execute('''
                        INSERT INTO weather_alerts 
                        (user_id, city, alert_type, severity, description, current_data, forecast_data)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    ''', (user_id, sub['city'], alert_type, severity, description, 
                         json.dumps(weather), json.dumps(forecast)))
                    
                    conn.commit()
                    conn.close()
                    
                    alerts.append({
                        'city': sub['city'],
                        'type': alert_type,
                        'severity': severity,
                        'description': description,
                        'current_temp': weather['temp'],
                        'wind_speed': weather['wind_speed'],
                        'forecast': forecast
                    })
            
            except Exception as e:
                logger.error(f"Error checking weather for {sub['city']}: {e}")
        
        return alerts
    
    def unsubscribe(self, user_id: int, city: str) -> Tuple[bool, str]:
        """Unsubscribe from weather alerts"""
        try:
            conn = sqlite3.connect(self.db_path, timeout=10)
            c = conn.cursor()
            
            c.execute('''
                DELETE FROM user_weather_subscriptions 
                WHERE user_id = ? AND city = ?
            ''', (user_id, city))
            
            conn.commit()
            conn.close()
            
            return True, f"Unsubscribed from {city} weather"
        except Exception as e:
            return False, str(e)


# Global instance
weather_tracker = WeatherTracker()
