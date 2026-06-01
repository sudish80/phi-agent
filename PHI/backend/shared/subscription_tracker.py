"""Video Subscription Tracker - Monitor subscribed channels and video uploads."""

import sqlite3
import os
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import requests
import json

logger = logging.getLogger(__name__)

DB_PATH = os.path.join(os.path.dirname(__file__), '..', '..', 'phi_audit.db')

def init_video_db():
    """Initialize video subscription and tracking database."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    
    with sqlite3.connect(DB_PATH) as conn:
        # User subscriptions
        conn.execute('''
            CREATE TABLE IF NOT EXISTS user_subscriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                channel_id TEXT NOT NULL,
                channel_name TEXT NOT NULL,
                channel_url TEXT,
                platform TEXT DEFAULT 'youtube',
                subscriber_count INTEGER,
                last_checked TEXT,
                subscribed_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id),
                UNIQUE(user_id, channel_id, platform)
            )
        ''')
        
        # Video uploads from subscribed channels
        conn.execute('''
            CREATE TABLE IF NOT EXISTS video_uploads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel_id TEXT NOT NULL,
                channel_name TEXT NOT NULL,
                video_id TEXT UNIQUE NOT NULL,
                video_title TEXT NOT NULL,
                video_url TEXT,
                description TEXT,
                duration_seconds INTEGER,
                view_count INTEGER DEFAULT 0,
                like_count INTEGER DEFAULT 0,
                comment_count INTEGER DEFAULT 0,
                upload_date TEXT NOT NULL,
                platform TEXT DEFAULT 'youtube',
                timestamp_tracked TEXT NOT NULL,
                summary TEXT,
                tags TEXT
            )
        ''')
        
        # User video watches/notifications
        conn.execute('''
            CREATE TABLE IF NOT EXISTS user_video_notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                video_id TEXT NOT NULL,
                channel_name TEXT NOT NULL,
                video_title TEXT NOT NULL,
                notification_sent BOOLEAN DEFAULT 0,
                watched BOOLEAN DEFAULT 0,
                watched_at TEXT,
                notification_sent_at TEXT,
                timestamp TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        ''')
        
        # Video platform credentials (encrypted)
        conn.execute('''
            CREATE TABLE IF NOT EXISTS video_platform_credentials (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                platform TEXT NOT NULL,
                api_key TEXT,
                access_token TEXT,
                refresh_token TEXT,
                expires_at TEXT,
                added_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id),
                UNIQUE(user_id, platform)
            )
        ''')
        
        conn.commit()

class YouTubeHandler:
    """Handle YouTube API interactions."""
    
    def __init__(self, api_key: str = None):
        """Initialize YouTube handler with API key."""
        self.api_key = api_key
        self.base_url = "https://www.googleapis.com/youtube/v3"
        self.session = requests.Session()
    
    def search_channel(self, channel_name: str) -> Optional[Dict]:
        """Search for a channel by name."""
        if not self.api_key:
            return self._mock_channel_data(channel_name)
        
        try:
            params = {
                'key': self.api_key,
                'q': channel_name,
                'part': 'snippet',
                'type': 'channel',
                'maxResults': 1
            }
            
            response = self.session.get(f"{self.base_url}/search", params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            if data.get('items'):
                item = data['items'][0]
                return {
                    'channel_id': item['id']['channelId'],
                    'channel_name': item['snippet']['title'],
                    'description': item['snippet']['description'],
                    'thumbnails': item['snippet']['thumbnails']
                }
        except Exception as e:
            logger.warning(f"YouTube search failed: {e}")
        
        return None
    
    def get_channel_uploads(self, channel_id: str, max_results: int = 10) -> List[Dict]:
        """Get recent uploads from a channel."""
        if not self.api_key:
            return self._mock_video_data(channel_id)
        
        try:
            # Get channel uploads playlist ID
            params = {
                'key': self.api_key,
                'id': channel_id,
                'part': 'contentDetails'
            }
            
            response = self.session.get(f"{self.base_url}/channels", params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            if not data.get('items'):
                return []
            
            uploads_playlist_id = data['items'][0]['contentDetails']['relatedPlaylists']['uploads']
            
            # Get videos from uploads playlist
            params = {
                'key': self.api_key,
                'playlistId': uploads_playlist_id,
                'part': 'snippet',
                'maxResults': max_results
            }
            
            response = self.session.get(f"{self.base_url}/playlistItems", params=params, timeout=10)
            response.raise_for_status()
            
            videos = []
            for item in response.json().get('items', []):
                videos.append({
                    'video_id': item['snippet']['resourceId']['videoId'],
                    'title': item['snippet']['title'],
                    'description': item['snippet']['description'],
                    'upload_date': item['snippet']['publishedAt'],
                    'thumbnail': item['snippet']['thumbnails']['default']['url']
                })
            
            return videos
        except Exception as e:
            logger.warning(f"Failed to get channel uploads: {e}")
            return []
    
    @staticmethod
    def _mock_channel_data(channel_name: str) -> Dict:
        """Return mock channel data (for testing without API key)."""
        return {
            'channel_id': f'UC_{channel_name.replace(" ", "_")}',
            'channel_name': channel_name,
            'description': f'Channel: {channel_name}',
            'thumbnails': {}
        }
    
    @staticmethod
    def _mock_video_data(channel_id: str) -> List[Dict]:
        """Return mock video data (for testing without API key)."""
        return [
            {
                'video_id': 'vid_001',
                'title': 'Introduction to Python',
                'description': 'Learn Python basics',
                'upload_date': datetime.utcnow().isoformat(),
                'thumbnail': ''
            },
            {
                'video_id': 'vid_002',
                'title': 'Advanced Python Techniques',
                'description': 'Deep dive into Python',
                'upload_date': (datetime.utcnow() - timedelta(days=1)).isoformat(),
                'thumbnail': ''
            }
        ]

class SubscriptionManager:
    """Manage video subscriptions and uploads."""
    
    def __init__(self, youtube_api_key: str = None):
        """Initialize subscription manager."""
        init_video_db()
        self.youtube = YouTubeHandler(youtube_api_key)
    
    def subscribe_to_channel(self, user_id: int, channel_identifier: str,
                           platform: str = 'youtube') -> Tuple[bool, str, Dict]:
        """Subscribe user to a channel."""
        try:
            init_video_db()
            
            # Search for channel
            channel_data = self.youtube.search_channel(channel_identifier)
            if not channel_data:
                return (False, "Channel not found", {})
            
            channel_id = channel_data['channel_id']
            channel_name = channel_data['channel_name']
            
            with sqlite3.connect(DB_PATH) as conn:
                try:
                    conn.execute('''
                        INSERT INTO user_subscriptions
                        (user_id, channel_id, channel_name, platform, subscribed_at, last_checked)
                        VALUES (?, ?, ?, ?, ?, ?)
                    ''', (user_id, channel_id, channel_name, platform, 
                          datetime.utcnow().isoformat(), datetime.utcnow().isoformat()))
                    conn.commit()
                except sqlite3.IntegrityError:
                    return (False, "Already subscribed to this channel", {})
            
            logger.info(f"User {user_id} subscribed to {channel_name}")
            
            return (True, f"Subscribed to {channel_name}", {
                'channel_id': channel_id,
                'channel_name': channel_name,
                'platform': platform
            })
        
        except Exception as e:
            logger.error(f"Subscription failed: {e}")
            return (False, str(e), {})
    
    def unsubscribe_from_channel(self, user_id: int, channel_id: str) -> Tuple[bool, str]:
        """Unsubscribe from a channel."""
        try:
            init_video_db()
            
            with sqlite3.connect(DB_PATH) as conn:
                conn.execute('''
                    DELETE FROM user_subscriptions
                    WHERE user_id = ? AND channel_id = ?
                ''', (user_id, channel_id))
                conn.commit()
            
            logger.info(f"User {user_id} unsubscribed from {channel_id}")
            return (True, "Unsubscribed successfully")
        
        except Exception as e:
            logger.error(f"Unsubscribe failed: {e}")
            return (False, str(e))
    
    def get_user_subscriptions(self, user_id: int) -> List[Dict]:
        """Get all subscriptions for a user."""
        try:
            init_video_db()
            
            with sqlite3.connect(DB_PATH) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute('''
                    SELECT * FROM user_subscriptions
                    WHERE user_id = ?
                    ORDER BY subscribed_at DESC
                ''', (user_id,))
                
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Failed to get subscriptions: {e}")
            return []
    
    def fetch_new_uploads(self, user_id: int) -> List[Dict]:
        """Fetch new uploads from subscribed channels."""
        try:
            init_video_db()
            
            # Get user subscriptions
            subscriptions = self.get_user_subscriptions(user_id)
            new_videos = []
            
            for sub in subscriptions:
                channel_id = sub['channel_id']
                channel_name = sub['channel_name']
                
                # Get videos from channel
                videos = self.youtube.get_channel_uploads(channel_id, max_results=5)
                
                for video in videos:
                    # Check if video already tracked
                    with sqlite3.connect(DB_PATH) as conn:
                        cursor = conn.execute('''
                            SELECT id FROM video_uploads
                            WHERE video_id = ?
                        ''', (video['video_id'],))
                        
                        existing = cursor.fetchone()
                        
                        if not existing:
                            # Add new video
                            conn.execute('''
                                INSERT INTO video_uploads
                                (channel_id, channel_name, video_id, video_title, 
                                 video_url, description, upload_date, timestamp_tracked)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                            ''', (channel_id, channel_name, video['video_id'],
                                  video['title'], f"https://youtube.com/watch?v={video['video_id']}",
                                  video['description'], video['upload_date'],
                                  datetime.utcnow().isoformat()))
                            
                            # Create notification for user
                            conn.execute('''
                                INSERT INTO user_video_notifications
                                (user_id, video_id, channel_name, video_title, timestamp)
                                VALUES (?, ?, ?, ?, ?)
                            ''', (user_id, video['video_id'], channel_name, 
                                  video['title'], datetime.utcnow().isoformat()))
                            
                            conn.commit()
                            
                            new_videos.append({
                                'channel_name': channel_name,
                                'video_id': video['video_id'],
                                'title': video['title'],
                                'upload_date': video['upload_date'],
                                'is_new': True
                            })
            
            return new_videos
        
        except Exception as e:
            logger.error(f"Failed to fetch uploads: {e}")
            return []
    
    def get_recent_uploads(self, user_id: int, hours: int = 24, 
                          limit: int = 20) -> List[Dict]:
        """Get recent uploads from subscribed channels."""
        try:
            init_video_db()
            
            with sqlite3.connect(DB_PATH) as conn:
                conn.row_factory = sqlite3.Row
                
                # Get video IDs from subscribed channels
                subscriptions = self.get_user_subscriptions(user_id)
                channel_ids = [sub['channel_id'] for sub in subscriptions]
                
                if not channel_ids:
                    return []
                
                placeholders = ','.join('?' * len(channel_ids))
                cursor = conn.execute(f'''
                    SELECT DISTINCT vu.* FROM video_uploads vu
                    WHERE vu.channel_id IN ({placeholders})
                    AND datetime(vu.timestamp_tracked) > datetime('now', '-' || ? || ' hours')
                    ORDER BY vu.upload_date DESC
                    LIMIT ?
                ''', (*channel_ids, hours, limit))
                
                return [dict(row) for row in cursor.fetchall()]
        
        except Exception as e:
            logger.error(f"Failed to get recent uploads: {e}")
            return []
    
    def mark_video_watched(self, user_id: int, video_id: str) -> bool:
        """Mark a video as watched."""
        try:
            init_video_db()
            
            with sqlite3.connect(DB_PATH) as conn:
                conn.execute('''
                    UPDATE user_video_notifications
                    SET watched = 1, watched_at = ?
                    WHERE user_id = ? AND video_id = ?
                ''', (datetime.utcnow().isoformat(), user_id, video_id))
                conn.commit()
            
            return True
        except Exception as e:
            logger.error(f"Failed to mark video watched: {e}")
            return False
    
    def get_unwatched_videos(self, user_id: int) -> List[Dict]:
        """Get unwatched videos for user."""
        try:
            init_video_db()
            
            with sqlite3.connect(DB_PATH) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute('''
                    SELECT * FROM user_video_notifications
                    WHERE user_id = ? AND watched = 0
                    ORDER BY timestamp DESC
                ''', (user_id,))
                
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Failed to get unwatched videos: {e}")
            return []
    
    def get_channel_stats(self, channel_id: str) -> Dict:
        """Get statistics for a channel."""
        try:
            init_video_db()
            
            with sqlite3.connect(DB_PATH) as conn:
                # Total videos
                total = conn.execute('''
                    SELECT COUNT(*) FROM video_uploads WHERE channel_id = ?
                ''', (channel_id,)).fetchone()[0]
                
                # Total views
                views = conn.execute('''
                    SELECT SUM(view_count) FROM video_uploads WHERE channel_id = ?
                ''', (channel_id,)).fetchone()[0] or 0
                
                # Average likes
                avg_likes = conn.execute('''
                    SELECT AVG(like_count) FROM video_uploads WHERE channel_id = ?
                ''', (channel_id,)).fetchone()[0] or 0
                
                return {
                    'total_videos': total,
                    'total_views': views,
                    'avg_likes': int(avg_likes)
                }
        except Exception as e:
            logger.error(f"Failed to get channel stats: {e}")
            return {}

# Global instance
subscription_manager = SubscriptionManager()
