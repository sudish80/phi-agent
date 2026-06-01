"""
File Converter using Microsoft Markitdown
Converts PDF, DOCX, PPTX, Excel, Images, Audio, HTML, CSV, JSON, XML, EPUB, YouTube URLs to Markdown
"""

import os
import sqlite3
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

DB_PATH = os.path.join(os.path.dirname(__file__), '..', '..', 'phi_audit.db')
CONVERTED_DIR = os.path.join(os.path.dirname(DB_PATH), 'converted')
os.makedirs(CONVERTED_DIR, exist_ok=True)

SUPPORTED_FORMATS = {
    'pdf': 'PDF Document',
    'pptx': 'PowerPoint Presentation',
    'docx': 'Word Document',
    'xlsx': 'Excel Spreadsheet',
    'jpg': 'Image (EXIF + OCR)',
    'jpeg': 'Image (EXIF + OCR)',
    'png': 'Image (EXIF + OCR)',
    'gif': 'Image (EXIF + OCR)',
    'bmp': 'Image (EXIF + OCR)',
    'webp': 'Image (EXIF + OCR)',
    'tiff': 'Image (EXIF + OCR)',
    'tif': 'Image (EXIF + OCR)',
    'mp3': 'Audio (EXIF + Transcription)',
    'wav': 'Audio (EXIF + Transcription)',
    'm4a': 'Audio (EXIF + Transcription)',
    'flac': 'Audio (EXIF + Transcription)',
    'ogg': 'Audio (EXIF + Transcription)',
    'html': 'HTML Document',
    'htm': 'HTML Document',
    'csv': 'CSV Data',
    'json': 'JSON Data',
    'xml': 'XML Data',
    'zip': 'ZIP Archive',
    'epub': 'EPUB eBook',
    'txt': 'Plain Text',
    'md': 'Markdown',
    'py': 'Python Source',
    'js': 'JavaScript Source',
    'ts': 'TypeScript Source',
    'yaml': 'YAML Data',
    'yml': 'YAML Data',
}


class FileConverter:
    """Converts files to Markdown using Microsoft Markitdown"""

    def __init__(self):
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(DB_PATH, timeout=10)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS file_conversions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                file_path TEXT NOT NULL,
                file_type TEXT,
                output_path TEXT,
                content_length INTEGER,
                status TEXT DEFAULT 'pending',
                error TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        conn.close()

    def convert(self, file_path: str, user_id: int = 0) -> Dict:
        """Convert a file to Markdown using markitdown"""
        if not os.path.exists(file_path):
            return {'status': 'error', 'error': 'File not found'}

        ext = os.path.splitext(file_path)[1].lower().lstrip('.')
        filename = os.path.basename(file_path)
        output_filename = f"{os.path.splitext(filename)[0]}.md"
        output_path = os.path.join(CONVERTED_DIR, output_filename)

        try:
            from markitdown import MarkItDown
            md = MarkItDown()
            result = md.convert(file_path)
            content = result.text_content

            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(content)

            conn = sqlite3.connect(DB_PATH, timeout=10)
            conn.execute(
                "INSERT INTO file_conversions (user_id, file_path, file_type, output_path, content_length, status) "
                "VALUES (?, ?, ?, ?, ?, 'completed')",
                (user_id, file_path, ext, output_path, len(content))
            )
            conn.commit()
            conn.close()

            logger.info(f"Converted {file_path} -> {output_path} ({len(content)} chars)")

            return {
                'status': 'success',
                'file': filename,
                'type': SUPPORTED_FORMATS.get(ext, ext),
                'output_file': output_filename,
                'output_path': output_path,
                'content_length': len(content),
                'preview': content[:2000],
                'converted_at': datetime.utcnow().isoformat()
            }

        except ImportError:
            return {'status': 'error', 'error': 'Markitdown not installed. Run: pip install markitdown'}
        except Exception as e:
            logger.error(f"Conversion error for {file_path}: {e}")
            conn = sqlite3.connect(DB_PATH, timeout=10)
            conn.execute(
                "INSERT INTO file_conversions (user_id, file_path, file_type, status, error) "
                "VALUES (?, ?, ?, 'error', ?)",
                (user_id, file_path, ext, str(e))
            )
            conn.commit()
            conn.close()
            return {'status': 'error', 'error': str(e)}

    def convert_url(self, url: str, user_id: int = 0) -> Dict:
        """Convert a URL (YouTube, webpage) to Markdown"""
        try:
            from markitdown import MarkItDown
            md = MarkItDown()
            result = md.convert(url)
            content = result.text_content

            parsed = urlparse(url)
            safe_name = parsed.netloc.replace('.', '_') + parsed.path.replace('/', '_')
            output_filename = f"url_{safe_name}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.md"
            output_path = os.path.join(CONVERTED_DIR, output_filename)

            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(content)

            conn = sqlite3.connect(DB_PATH, timeout=10)
            conn.execute(
                "INSERT INTO file_conversions (user_id, file_path, file_type, output_path, content_length, status) "
                "VALUES (?, ?, 'url', ?, ?, 'completed')",
                (user_id, url, output_path, len(content))
            )
            conn.commit()
            conn.close()

            return {
                'status': 'success',
                'url': url,
                'output_file': output_filename,
                'content_length': len(content),
                'preview': content[:2000]
            }

        except Exception as e:
            return {'status': 'error', 'error': str(e)}

    def list_conversions(self, user_id: int, limit: int = 20) -> List[Dict]:
        """List conversion history"""
        conn = sqlite3.connect(DB_PATH, timeout=10)
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(
            "SELECT * FROM file_conversions WHERE user_id=? ORDER BY created_at DESC LIMIT ?",
            (user_id, limit)
        )
        rows = [dict(r) for r in cursor.fetchall()]
        conn.close()
        return rows

    def get_supported_formats(self) -> Dict:
        """Return dict of supported file extensions -> descriptions"""
        return SUPPORTED_FORMATS

    def read_converted(self, output_path: str) -> Optional[str]:
        """Read converted markdown content"""
        try:
            with open(output_path, 'r', encoding='utf-8') as f:
                return f.read()
        except:
            return None


# Global instance
file_converter = FileConverter()
