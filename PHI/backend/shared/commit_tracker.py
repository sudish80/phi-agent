"""Git Commit Tracker - Monitor commits from team members."""

import sqlite3
import os
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import subprocess
import json
import re

logger = logging.getLogger(__name__)

DB_PATH = os.path.join(os.path.dirname(__file__), '..', '..', 'phi_audit.db')

def init_git_db():
    """Initialize git tracking database."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    
    with sqlite3.connect(DB_PATH) as conn:
        # Git repositories
        conn.execute('''
            CREATE TABLE IF NOT EXISTS git_repositories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                repo_name TEXT NOT NULL,
                repo_path TEXT NOT NULL,
                repo_url TEXT,
                platform TEXT DEFAULT 'github',
                added_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id),
                UNIQUE(user_id, repo_path)
            )
        ''')
        
        # Team members
        conn.execute('''
            CREATE TABLE IF NOT EXISTS team_members (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                member_name TEXT NOT NULL,
                member_email TEXT,
                github_username TEXT,
                added_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id),
                UNIQUE(user_id, member_email)
            )
        ''')
        
        # Git commits
        conn.execute('''
            CREATE TABLE IF NOT EXISTS git_commits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                repo_id INTEGER NOT NULL,
                commit_hash TEXT UNIQUE NOT NULL,
                author_name TEXT NOT NULL,
                author_email TEXT,
                commit_message TEXT NOT NULL,
                commit_date TEXT NOT NULL,
                files_changed INTEGER DEFAULT 0,
                insertions INTEGER DEFAULT 0,
                deletions INTEGER DEFAULT 0,
                summary TEXT,
                branch TEXT,
                timestamp_tracked TEXT NOT NULL,
                FOREIGN KEY (repo_id) REFERENCES git_repositories(id)
            )
        ''')
        
        # User commit notifications
        conn.execute('''
            CREATE TABLE IF NOT EXISTS user_commit_notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                commit_id INTEGER NOT NULL,
                member_name TEXT NOT NULL,
                repo_name TEXT NOT NULL,
                notification_sent BOOLEAN DEFAULT 0,
                notification_sent_at TEXT,
                timestamp TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (commit_id) REFERENCES git_commits(id)
            )
        ''')
        
        # Team member activities
        conn.execute('''
            CREATE TABLE IF NOT EXISTS member_activities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                member_name TEXT NOT NULL,
                activity_type TEXT,
                activity_description TEXT,
                repo_name TEXT,
                activity_date TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        ''')
        
        conn.commit()

class GitHandler:
    """Handle Git operations."""
    
    @staticmethod
    def get_commits(repo_path: str, author_name: str = None, 
                   days: int = 7, limit: int = 50) -> List[Dict]:
        """Get commits from a repository."""
        try:
            # Change to repo directory
            original_cwd = os.getcwd()
            os.chdir(repo_path)
            
            try:
                # Build git log command
                cmd = ['git', 'log', '--all', '--pretty=format:%H|%an|%ae|%s|%ai|%b']
                
                if author_name:
                    cmd.extend(['--author', author_name])
                
                cmd.extend(['--since', f'{days} days ago'])
                cmd.extend(['--max-count', str(limit)])
                
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
                
                if result.returncode != 0:
                    logger.warning(f"Git log failed: {result.stderr}")
                    return []
                
                commits = []
                for line in result.stdout.strip().split('\n'):
                    if not line:
                        continue
                    
                    parts = line.split('|', 5)
                    if len(parts) >= 5:
                        commit_hash = parts[0]
                        author = parts[1]
                        email = parts[2]
                        message = parts[3]
                        date = parts[4]
                        body = parts[5] if len(parts) > 5 else ""
                        
                        # Get file changes
                        diff_cmd = ['git', 'diff-tree', '--no-commit-id', '--name-status', '-r', commit_hash]
                        diff_result = subprocess.run(diff_cmd, capture_output=True, text=True)
                        files_changed = len(diff_result.stdout.strip().split('\n')) if diff_result.stdout else 0
                        
                        # Get insertions/deletions
                        stat_cmd = ['git', 'show', '--numstat', '--pretty=format:', commit_hash]
                        stat_result = subprocess.run(stat_cmd, capture_output=True, text=True)
                        insertions = 0
                        deletions = 0
                        
                        for stat_line in stat_result.stdout.strip().split('\n'):
                            if stat_line:
                                try:
                                    add, remove = stat_line.split('\t')[:2]
                                    insertions += int(add) if add.isdigit() else 0
                                    deletions += int(remove) if remove.isdigit() else 0
                                except:
                                    pass
                        
                        commits.append({
                            'hash': commit_hash,
                            'author': author,
                            'email': email,
                            'message': message,
                            'date': date,
                            'body': body,
                            'files_changed': files_changed,
                            'insertions': insertions,
                            'deletions': deletions
                        })
                
                return commits
            
            finally:
                os.chdir(original_cwd)
        
        except Exception as e:
            logger.error(f"Failed to get commits: {e}")
            return []
    
    @staticmethod
    def get_branch_info(repo_path: str) -> Dict:
        """Get current branch info."""
        try:
            original_cwd = os.getcwd()
            os.chdir(repo_path)
            
            try:
                # Get current branch
                result = subprocess.run(['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
                                      capture_output=True, text=True)
                current_branch = result.stdout.strip()
                
                # Get remote URL
                result = subprocess.run(['git', 'config', '--get', 'remote.origin.url'],
                                      capture_output=True, text=True)
                remote_url = result.stdout.strip()
                
                return {
                    'current_branch': current_branch,
                    'remote_url': remote_url
                }
            
            finally:
                os.chdir(original_cwd)
        
        except Exception as e:
            logger.error(f"Failed to get branch info: {e}")
            return {}

class CommitTracker:
    """Track git commits from team members."""
    
    def __init__(self):
        """Initialize commit tracker."""
        init_git_db()
        self.git = GitHandler()
    
    def add_repository(self, user_id: int, repo_name: str, repo_path: str,
                      repo_url: str = None) -> Tuple[bool, str]:
        """Add a repository to track."""
        try:
            # Verify repo path exists
            if not os.path.isdir(os.path.join(repo_path, '.git')):
                return (False, "Not a valid git repository")
            
            init_git_db()
            
            with sqlite3.connect(DB_PATH) as conn:
                try:
                    conn.execute('''
                        INSERT INTO git_repositories
                        (user_id, repo_name, repo_path, repo_url, added_at)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (user_id, repo_name, repo_path, repo_url, 
                          datetime.utcnow().isoformat()))
                    conn.commit()
                except sqlite3.IntegrityError:
                    return (False, "Repository already added")
            
            logger.info(f"Repository added: {repo_name}")
            return (True, f"Repository '{repo_name}' added successfully")
        
        except Exception as e:
            logger.error(f"Failed to add repository: {e}")
            return (False, str(e))
    
    def add_team_member(self, user_id: int, member_name: str, 
                       member_email: str, github_username: str = None) -> Tuple[bool, str]:
        """Add a team member to track."""
        try:
            init_git_db()
            
            with sqlite3.connect(DB_PATH) as conn:
                try:
                    conn.execute('''
                        INSERT INTO team_members
                        (user_id, member_name, member_email, github_username, added_at)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (user_id, member_name, member_email, github_username,
                          datetime.utcnow().isoformat()))
                    conn.commit()
                except sqlite3.IntegrityError:
                    return (False, "Team member already added")
            
            logger.info(f"Team member added: {member_name}")
            return (True, f"Team member '{member_name}' added successfully")
        
        except Exception as e:
            logger.error(f"Failed to add team member: {e}")
            return (False, str(e))
    
    def fetch_commits(self, user_id: int) -> List[Dict]:
        """Fetch new commits from tracked repositories."""
        try:
            init_git_db()
            
            new_commits = []
            
            with sqlite3.connect(DB_PATH) as conn:
                # Get user repositories
                cursor = conn.execute('''
                    SELECT * FROM git_repositories WHERE user_id = ?
                ''', (user_id,))
                repos = cursor.fetchall()
                
                # Get team members
                cursor = conn.execute('''
                    SELECT * FROM team_members WHERE user_id = ?
                ''', (user_id,))
                members = cursor.fetchall()
            
            member_names = [m[2] for m in members]  # Extract member names
            
            # Process each repository
            for repo in repos:
                repo_id = repo[0]
                repo_name = repo[2]
                repo_path = repo[3]
                
                # Get commits from team members
                commits = self.git.get_commits(repo_path, days=7, limit=50)
                
                with sqlite3.connect(DB_PATH) as conn:
                    for commit in commits:
                        author = commit['author']
                        
                        # Check if team member
                        is_team_member = author in member_names
                        
                        if not is_team_member:
                            continue
                        
                        # Check if commit already tracked
                        cursor = conn.execute('''
                            SELECT id FROM git_commits WHERE commit_hash = ?
                        ''', (commit['hash'],))
                        
                        existing = cursor.fetchone()
                        
                        if not existing:
                            # Generate summary
                            summary = self._generate_summary(commit['message'], commit['body'])
                            
                            # Add commit
                            cursor = conn.execute('''
                                INSERT INTO git_commits
                                (repo_id, commit_hash, author_name, author_email,
                                 commit_message, commit_date, files_changed,
                                 insertions, deletions, summary, timestamp_tracked)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            ''', (repo_id, commit['hash'], author, commit['email'],
                                  commit['message'], commit['date'],
                                  commit['files_changed'], commit['insertions'],
                                  commit['deletions'], summary,
                                  datetime.utcnow().isoformat()))
                            
                            commit_id = cursor.lastrowid
                            
                            # Create notification
                            conn.execute('''
                                INSERT INTO user_commit_notifications
                                (user_id, commit_id, member_name, repo_name, timestamp)
                                VALUES (?, ?, ?, ?, ?)
                            ''', (user_id, commit_id, author, repo_name,
                                  datetime.utcnow().isoformat()))
                            
                            conn.commit()
                            
                            new_commits.append({
                                'repo_name': repo_name,
                                'author': author,
                                'message': commit['message'],
                                'summary': summary,
                                'date': commit['date'],
                                'insertions': commit['insertions'],
                                'deletions': commit['deletions'],
                                'files_changed': commit['files_changed']
                            })
            
            return new_commits
        
        except Exception as e:
            logger.error(f"Failed to fetch commits: {e}")
            return []
    
    def _generate_summary(self, message: str, body: str = "") -> str:
        """Generate a summary from commit message."""
        # Use first line of message
        summary = message.split('\n')[0][:100]
        
        # Extract key changes
        if body:
            lines = body.split('\n')
            key_items = [l.strip() for l in lines if l.strip().startswith('-') or l.strip().startswith('*')]
            if key_items:
                summary += f" ({len(key_items)} changes)"
        
        return summary
    
    def get_recent_commits(self, user_id: int, days: int = 7, 
                          limit: int = 20) -> List[Dict]:
        """Get recent commits from team members."""
        try:
            init_git_db()
            
            with sqlite3.connect(DB_PATH) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute('''
                    SELECT gc.*, gr.repo_name FROM git_commits gc
                    JOIN git_repositories gr ON gc.repo_id = gr.id
                    WHERE gr.user_id = ?
                    AND datetime(gc.commit_date) > datetime('now', '-' || ? || ' days')
                    ORDER BY gc.commit_date DESC
                    LIMIT ?
                ''', (user_id, days, limit))
                
                return [dict(row) for row in cursor.fetchall()]
        
        except Exception as e:
            logger.error(f"Failed to get recent commits: {e}")
            return []
    
    def get_team_activity(self, user_id: int, days: int = 7) -> List[Dict]:
        """Get team activity summary."""
        try:
            init_git_db()
            
            with sqlite3.connect(DB_PATH) as conn:
                conn.row_factory = sqlite3.Row
                
                # Get commits by member
                cursor = conn.execute('''
                    SELECT author_name, COUNT(*) as commit_count,
                           SUM(insertions) as total_insertions,
                           SUM(deletions) as total_deletions,
                           SUM(files_changed) as total_files
                    FROM git_commits gc
                    JOIN git_repositories gr ON gc.repo_id = gr.id
                    WHERE gr.user_id = ?
                    AND datetime(gc.commit_date) > datetime('now', '-' || ? || ' days')
                    GROUP BY author_name
                    ORDER BY commit_count DESC
                ''', (user_id, days))
                
                return [dict(row) for row in cursor.fetchall()]
        
        except Exception as e:
            logger.error(f"Failed to get team activity: {e}")
            return []
    
    def get_member_commits(self, user_id: int, member_name: str, 
                          days: int = 7, limit: int = 20) -> List[Dict]:
        """Get commits from a specific team member."""
        try:
            init_git_db()
            
            with sqlite3.connect(DB_PATH) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute('''
                    SELECT gc.*, gr.repo_name FROM git_commits gc
                    JOIN git_repositories gr ON gc.repo_id = gr.id
                    WHERE gr.user_id = ?
                    AND gc.author_name = ?
                    AND datetime(gc.commit_date) > datetime('now', '-' || ? || ' days')
                    ORDER BY gc.commit_date DESC
                    LIMIT ?
                ''', (user_id, member_name, days, limit))
                
                return [dict(row) for row in cursor.fetchall()]
        
        except Exception as e:
            logger.error(f"Failed to get member commits: {e}")
            return []
    
    def get_repositories(self, user_id: int) -> List[Dict]:
        """Get tracked repositories."""
        try:
            init_git_db()
            
            with sqlite3.connect(DB_PATH) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute('''
                    SELECT * FROM git_repositories WHERE user_id = ?
                    ORDER BY added_at DESC
                ''', (user_id,))
                
                return [dict(row) for row in cursor.fetchall()]
        
        except Exception as e:
            logger.error(f"Failed to get repositories: {e}")
            return []
    
    def get_team_members(self, user_id: int) -> List[Dict]:
        """Get tracked team members."""
        try:
            init_git_db()
            
            with sqlite3.connect(DB_PATH) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute('''
                    SELECT * FROM team_members WHERE user_id = ?
                    ORDER BY added_at DESC
                ''', (user_id,))
                
                return [dict(row) for row in cursor.fetchall()]
        
        except Exception as e:
            logger.error(f"Failed to get team members: {e}")
            return []
    
    def get_repository_stats(self, repo_id: int, days: int = 30) -> Dict:
        """Get statistics for a repository."""
        try:
            init_git_db()
            
            with sqlite3.connect(DB_PATH) as conn:
                # Total commits
                total = conn.execute('''
                    SELECT COUNT(*) FROM git_commits 
                    WHERE repo_id = ?
                    AND datetime(commit_date) > datetime('now', '-' || ? || ' days')
                ''', (repo_id, days)).fetchone()[0]
                
                # Total insertions/deletions
                stats = conn.execute('''
                    SELECT SUM(insertions) as ins, SUM(deletions) as dels,
                           SUM(files_changed) as files
                    FROM git_commits 
                    WHERE repo_id = ?
                    AND datetime(commit_date) > datetime('now', '-' || ? || ' days')
                ''', (repo_id, days)).fetchone()
                
                return {
                    'total_commits': total,
                    'total_insertions': stats[0] or 0,
                    'total_deletions': stats[1] or 0,
                    'total_files_changed': stats[2] or 0
                }
        
        except Exception as e:
            logger.error(f"Failed to get repository stats: {e}")
            return {}

# Global instance
commit_tracker = CommitTracker()
