"""Monitoring Service - Background monitoring for videos and commits."""

import threading
import time
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import sqlite3
import os

from backend.shared.subscription_tracker import subscription_manager, init_video_db
from backend.shared.commit_tracker import commit_tracker, init_git_db
from backend.shared.voice_control import voice_processor
from backend.shared.weather_tracker import weather_tracker
from backend.shared.stocks_tracker import stock_tracker
from backend.shared.news_tracker import news_tracker
from backend.shared.stock_news_correlation import correlation_engine

logger = logging.getLogger(__name__)

DB_PATH = os.path.join(os.path.dirname(__file__), '..', '..', 'phi_audit.db')

class NotificationManager:
    """Manage notifications and reminders for users."""
    
    def __init__(self):
        """Initialize notification manager."""
        init_video_db()
        init_git_db()
    
    def create_notification(self, user_id: int, notification_type: str, 
                          title: str, content: str, source_id: str = None) -> int:
        """Create a notification for user."""
        try:
            with sqlite3.connect(DB_PATH, timeout=10) as conn:
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS notifications (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL,
                        type TEXT NOT NULL,
                        title TEXT NOT NULL,
                        content TEXT,
                        source_id TEXT,
                        read BOOLEAN DEFAULT 0,
                        created_at TEXT NOT NULL,
                        FOREIGN KEY (user_id) REFERENCES users(id)
                    )
                ''')
                
                cursor = conn.execute('''
                    INSERT INTO notifications
                    (user_id, type, title, content, source_id, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (user_id, notification_type, title, content, source_id,
                      datetime.utcnow().isoformat()))
                
                conn.commit()
                return cursor.lastrowid
        except Exception as e:
            logger.error(f"Failed to create notification: {e}")
            return 0
    
    def get_notifications(self, user_id: int, unread_only: bool = False,
                         limit: int = 50) -> List[Dict]:
        """Get notifications for user."""
        try:
            with sqlite3.connect(DB_PATH, timeout=10) as conn:
                conn.row_factory = sqlite3.Row
                
                if unread_only:
                    cursor = conn.execute('''
                        SELECT * FROM notifications
                        WHERE user_id = ? AND read = 0
                        ORDER BY created_at DESC
                        LIMIT ?
                    ''', (user_id, limit))
                else:
                    cursor = conn.execute('''
                        SELECT * FROM notifications
                        WHERE user_id = ?
                        ORDER BY created_at DESC
                        LIMIT ?
                    ''', (user_id, limit))
                
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Failed to get notifications: {e}")
            return []
    
    def mark_notification_read(self, notification_id: int) -> bool:
        """Mark notification as read."""
        try:
            with sqlite3.connect(DB_PATH, timeout=10) as conn:
                conn.execute('''
                    UPDATE notifications SET read = 1 WHERE id = ?
                ''', (notification_id,))
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to mark notification read: {e}")
            return False
    
    def get_unread_count(self, user_id: int) -> int:
        """Get count of unread notifications."""
        try:
            with sqlite3.connect(DB_PATH, timeout=10) as conn:
                cursor = conn.execute('''
                    SELECT COUNT(*) FROM notifications
                    WHERE user_id = ? AND read = 0
                ''', (user_id,))
                return cursor.fetchone()[0]
        except Exception as e:
            logger.error(f"Failed to get unread count: {e}")
            return 0

class ReminderManager:
    """Manage reminders for unwatched videos and unreviewed commits."""
    
    def __init__(self):
        """Initialize reminder manager."""
        init_video_db()
        init_git_db()
    
    def create_reminder(self, user_id: int, reminder_type: str,
                       title: str, description: str, due_date: str = None,
                       priority: str = "normal") -> int:
        """Create a reminder for user."""
        try:
            with sqlite3.connect(DB_PATH, timeout=10) as conn:
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS reminders (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL,
                        type TEXT NOT NULL,
                        title TEXT NOT NULL,
                        description TEXT,
                        due_date TEXT,
                        priority TEXT DEFAULT 'normal',
                        completed BOOLEAN DEFAULT 0,
                        created_at TEXT NOT NULL,
                        FOREIGN KEY (user_id) REFERENCES users(id)
                    )
                ''')
                
                cursor = conn.execute('''
                    INSERT INTO reminders
                    (user_id, type, title, description, due_date, priority, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (user_id, reminder_type, title, description, due_date,
                      priority, datetime.utcnow().isoformat()))
                
                conn.commit()
                return cursor.lastrowid
        except Exception as e:
            logger.error(f"Failed to create reminder: {e}")
            return 0
    
    def get_pending_reminders(self, user_id: int) -> List[Dict]:
        """Get pending reminders for user."""
        try:
            with sqlite3.connect(DB_PATH, timeout=10) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute('''
                    SELECT * FROM reminders
                    WHERE user_id = ? AND completed = 0
                    ORDER BY 
                        CASE WHEN priority = 'high' THEN 1
                             WHEN priority = 'normal' THEN 2
                             ELSE 3 END,
                        due_date ASC
                ''', (user_id,))
                
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Failed to get reminders: {e}")
            return []
    
    def complete_reminder(self, reminder_id: int) -> bool:
        """Mark reminder as complete."""
        try:
            with sqlite3.connect(DB_PATH, timeout=10) as conn:
                conn.execute('''
                    UPDATE reminders SET completed = 1 WHERE id = ?
                ''', (reminder_id,))
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to complete reminder: {e}")
            return False
    
    def generate_video_reminders(self, user_id: int) -> List[str]:
        """Generate reminders for unwatched videos."""
        reminders = []
        try:
            unwatched = subscription_manager.get_unwatched_videos(user_id)
            
            if unwatched:
                count = len(unwatched)
                reminder_msg = f"You have {count} unwatched videos from your subscriptions"
                
                # Create reminder
                self.create_reminder(
                    user_id,
                    "unwatched_videos",
                    f"Unwatched Videos ({count})",
                    reminder_msg,
                    priority="high" if count > 5 else "normal"
                )
                
                reminders.append(reminder_msg)
                
                # Add specific video reminders
                for i, video in enumerate(unwatched[:3]):
                    msg = f"Watch: {video['video_title']} by {video['channel_name']}"
                    reminders.append(msg)
        
        except Exception as e:
            logger.error(f"Failed to generate video reminders: {e}")
        
        return reminders
    
    def generate_commit_reminders(self, user_id: int) -> List[str]:
        """Generate reminders for unreviewed commits."""
        reminders = []
        try:
            recent_commits = commit_tracker.get_recent_commits(user_id, days=7)
            
            if recent_commits:
                # Group by member
                by_member = {}
                for commit in recent_commits:
                    author = commit['author_name']
                    if author not in by_member:
                        by_member[author] = []
                    by_member[author].append(commit)
                
                # Create reminder for each member
                for member, commits in by_member.items():
                    count = len(commits)
                    msg = f"{member} has made {count} commit(s)"
                    
                    self.create_reminder(
                        user_id,
                        "unreviewed_commits",
                        f"Commits from {member} ({count})",
                        msg,
                        priority="high" if count > 3 else "normal"
                    )
                    
                    reminders.append(msg)
        
        except Exception as e:
            logger.error(f"Failed to generate commit reminders: {e}")
        
        return reminders

class MonitoringService:
    """Background service to monitor videos and commits."""
    
    def __init__(self, check_interval: int = 300):
        """
        Initialize monitoring service.
        
        Args:
            check_interval: Check interval in seconds (default 5 minutes)
        """
        self.check_interval = check_interval
        self.running = False
        self.monitor_thread = None
        self.notification_mgr = NotificationManager()
        self.reminder_mgr = ReminderManager()
    
    def start(self):
        """Start the monitoring service."""
        if not self.running:
            self.running = True
            self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
            self.monitor_thread.start()
            logger.info(f"Monitoring service started (check interval: {self.check_interval}s)")
    
    def stop(self):
        """Stop the monitoring service."""
        self.running = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        logger.info("Monitoring service stopped")
    
    def _monitor_loop(self):
        """Main monitoring loop."""
        while self.running:
            try:
                self._check_all_users()
                time.sleep(self.check_interval)
            except Exception as e:
                logger.error(f"Monitor loop error: {e}")
                time.sleep(self.check_interval)
    
    def _check_all_users(self):
        """Check for updates for all users."""
        try:
            with sqlite3.connect(DB_PATH, timeout=10) as conn:
                cursor = conn.execute('SELECT id FROM users')
                users = cursor.fetchall()
            
            for user in users:
                user_id = user[0]
                self._check_user_updates(user_id)
        
        except Exception as e:
            logger.error(f"Failed to check all users: {e}")
    
    def _check_user_updates(self, user_id: int):
        """Check for updates for a specific user."""
        try:
            # Check for new videos
            self._check_new_videos(user_id)
            
            # Check for new commits
            self._check_new_commits(user_id)
            
            # Check for weather alerts
            self._check_weather_alerts(user_id)
            
            # Check for stock alerts
            self._check_stock_alerts(user_id)
            
            # Check for news alerts
            self._check_news_alerts(user_id)
            
            # Generate reminders
            self._generate_reminders(user_id)
        
        except Exception as e:
            logger.error(f"Failed to check updates for user {user_id}: {e}")

    def _check_weather_alerts(self, user_id: int):
        """Check weather alerts and notify."""
        try:
            alerts = weather_tracker.check_alerts(user_id)
            for alert in alerts:
                title = f"Weather Alert: {alert['city']} ({alert['severity']})"
                content = alert['description']
                
                # Create notification
                self.notification_mgr.create_notification(
                    user_id,
                    "weather_alert",
                    title,
                    content,
                    alert['city']
                )
                
                # Create reminder for critical weather
                if alert['severity'] in ['CRITICAL', 'HIGH']:
                    self.reminder_mgr.create_reminder(
                        user_id,
                        "weather_alert",
                        f"Safety check: {alert['city']}",
                        content,
                        priority="high"
                    )
                
                # Voice alert
                self.send_agent_message(user_id, f"Weather alert for {alert['city']}: {content}", "warning")
        except Exception as e:
            logger.error(f"Failed to check weather alerts for {user_id}: {e}")

    def _check_stock_alerts(self, user_id: int):
        """Check stock alerts and notify."""
        try:
            alerts = stock_tracker.check_alerts(user_id)
            for alert in alerts:
                title = f"Stock Alert: {alert['symbol']} ({alert['severity']})"
                content = alert['description']
                
                # Create notification
                self.notification_mgr.create_notification(
                    user_id,
                    "stock_alert",
                    title,
                    content,
                    alert['symbol']
                )
                
                # Create reminder for significant moves
                if alert['severity'] in ['CRITICAL', 'HIGH']:
                    self.reminder_mgr.create_reminder(
                        user_id,
                        "stock_alert",
                        f"Review {alert['symbol']} position",
                        content,
                        priority="high"
                    )
                
                # Voice alert
                self.send_agent_message(user_id, f"Stock movement alert: {content}", "info")
        except Exception as e:
            logger.error(f"Failed to check stock alerts for {user_id}: {e}")

    def _check_news_alerts(self, user_id: int):
        """Check news alerts and run correlation engine."""
        try:
            alerts = news_tracker.check_news(user_id)
            for alert in alerts:
                title = f"News Alert: {alert['title']}"
                content = f"Source: {alert['source']} - {alert['description']}"
                
                # Create notification
                self.notification_mgr.create_notification(
                    user_id,
                    "news_alert",
                    title,
                    content,
                    alert['title']
                )
                
                # Voice alert
                self.send_agent_message(user_id, f"News flash: {alert['title']}", "info")
                
                # Corelate with stocks
                affected_stocks = alert['affected_stocks']
                if affected_stocks:
                    # Run Stock-News Correlation
                    correlations = correlation_engine.correlate_news_to_stocks(user_id, alert, affected_stocks)
                    for pred in correlations:
                        # Cascade Alert
                        cascade_title = f"Market Cascade Prediction: {pred['primary_stock']}"
                        cascade_content = (
                            f"Based on news: {alert['title']}\n"
                            f"Predicted movement for {pred['primary_stock']}: {pred['predicted_move_percent']}% "
                            f"(New target: ${pred['predicted_price']:.2f}).\n"
                            f"Cascade Effects: Tier-2 (suppliers/competitors) predicted move: {pred['multi_tier_analysis']['tiers']['tier_2']['expected_move_percent']}%\n"
                            f"Sector Impact: {pred['multi_tier_analysis']['tiers']['tier_3']['sector']} sector expected to move {pred['multi_tier_analysis']['tiers']['tier_3']['expected_move_percent']}%"
                        )
                        
                        # Create cascade notification
                        self.notification_mgr.create_notification(
                            user_id,
                            "cascade_prediction",
                            cascade_title,
                            cascade_content,
                            pred['primary_stock']
                        )
                        
                        # Create high-priority reminder
                        self.reminder_mgr.create_reminder(
                            user_id,
                            "cascade_prediction",
                            f"Review cascade effect on {pred['primary_stock']}",
                            cascade_content,
                            priority="high"
                        )
                        
                        # Voice alert
                        self.send_agent_message(
                            user_id, 
                            f"Market cascade detected. {pred['primary_stock']} expected to move {pred['predicted_move_percent']}% due to news.",
                            "warning" if abs(pred['predicted_move_percent']) >= 5 else "info"
                        )
        except Exception as e:
            logger.error(f"Failed to check news alerts for {user_id}: {e}")
    
    def _check_new_videos(self, user_id: int):
        """Check for new videos from subscribed channels."""
        try:
            new_videos = subscription_manager.fetch_new_uploads(user_id)
            
            for video in new_videos:
                title = f"New video from {video['channel_name']}"
                content = f"{video['title']}"
                
                # Create notification
                self.notification_mgr.create_notification(
                    user_id,
                    "new_video",
                    title,
                    content,
                    video['video_id']
                )
                
                # Generate audio message
                message = f"New video alert: {video['title']} uploaded by {video['channel_name']}"
                logger.info(f"User {user_id}: {message}")
        
        except Exception as e:
            logger.error(f"Failed to check new videos: {e}")
    
    def _check_new_commits(self, user_id: int):
        """Check for new commits from team members."""
        try:
            new_commits = commit_tracker.fetch_commits(user_id)
            
            for commit in new_commits:
                title = f"New commit from {commit['author']}"
                content = f"{commit['message']}\nSummary: {commit['summary']}"
                
                # Create notification
                self.notification_mgr.create_notification(
                    user_id,
                    "new_commit",
                    title,
                    content,
                    commit['hash']
                )
                
                # Generate message
                message = f"Commit alert: {commit['author']} made changes to {commit['repo_name']}"
                logger.info(f"User {user_id}: {message}")
        
        except Exception as e:
            logger.error(f"Failed to check new commits: {e}")
    
    def _generate_reminders(self, user_id: int):
        """Generate reminders for user."""
        try:
            # Video reminders
            video_reminders = self.reminder_mgr.generate_video_reminders(user_id)
            
            # Commit reminders
            commit_reminders = self.reminder_mgr.generate_commit_reminders(user_id)
            
            # Log all reminders
            for reminder in video_reminders + commit_reminders:
                logger.info(f"Reminder for user {user_id}: {reminder}")
        
        except Exception as e:
            logger.error(f"Failed to generate reminders: {e}")
    
    def send_agent_message(self, user_id: int, message: str, message_type: str = "info"):
        """Send a message to user through agent."""
        try:
            # Store message for agent to pick up
            with sqlite3.connect(DB_PATH, timeout=10) as conn:
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS agent_messages (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL,
                        message TEXT NOT NULL,
                        type TEXT DEFAULT 'info',
                        sent_at TEXT NOT NULL,
                        FOREIGN KEY (user_id) REFERENCES users(id)
                    )
                ''')
                
                conn.execute('''
                    INSERT INTO agent_messages (user_id, message, type, sent_at)
                    VALUES (?, ?, ?, ?)
                ''', (user_id, message, message_type, datetime.utcnow().isoformat()))
                
                conn.commit()
            
            logger.info(f"Agent message queued for user {user_id}: {message}")
            return True
        
        except Exception as e:
            logger.error(f"Failed to send agent message: {e}")
            return False
    
    def get_user_summary(self, user_id: int) -> Dict:
        """Get summary of activities for user."""
        try:
            summary = {
                "timestamp": datetime.utcnow().isoformat(),
                "notifications": {
                    "unread_count": self.notification_mgr.get_unread_count(user_id),
                    "recent": self.notification_mgr.get_notifications(user_id, unread_only=True, limit=5)
                },
                "reminders": {
                    "pending_count": len(self.reminder_mgr.get_pending_reminders(user_id)),
                    "pending": self.reminder_mgr.get_pending_reminders(user_id)[:5]
                },
                "videos": {
                    "unwatched_count": len(subscription_manager.get_unwatched_videos(user_id)),
                    "recent_uploads": subscription_manager.get_recent_uploads(user_id, hours=24, limit=5)
                },
                "commits": {
                    "recent_commits": commit_tracker.get_recent_commits(user_id, days=7, limit=5),
                    "team_activity": commit_tracker.get_team_activity(user_id, days=7)
                },
                "weather": {
                    "subscriptions": weather_tracker.get_subscriptions(user_id),
                    "recent_alerts": [n for n in self.notification_mgr.get_notifications(user_id, limit=10) if n['type'] == 'weather_alert']
                },
                "stocks": {
                    "subscriptions": stock_tracker.get_subscriptions(user_id),
                    "popular": stock_tracker.get_popular_stocks(5),
                    "recent_alerts": [n for n in self.notification_mgr.get_notifications(user_id, limit=10) if n['type'] in ['stock_alert', 'cascade_prediction']]
                },
                "news": {
                    "subscriptions": news_tracker.get_subscriptions(user_id),
                    "breaking": news_tracker.get_breaking_news(5),
                    "recent_alerts": [n for n in self.notification_mgr.get_notifications(user_id, limit=10) if n['type'] == 'news_alert']
                }
            }
            
            return summary
        
        except Exception as e:
            logger.error(f"Failed to get user summary: {e}")
            return {}

# Global instances
notification_manager = NotificationManager()
reminder_manager = ReminderManager()
monitoring_service = MonitoringService(check_interval=300)  # 5 minutes
