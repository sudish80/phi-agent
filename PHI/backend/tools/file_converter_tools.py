"""Tool wrappers for File Converter (Markitdown)"""
import logging
from backend.shared.file_converter import file_converter

logger = logging.getLogger(__name__)

def convert_file(file_path: str, user_id: int = 0) -> dict:
    return file_converter.convert(file_path, user_id)

def convert_url(url: str, user_id: int = 0) -> dict:
    return file_converter.convert_url(url, user_id)

def list_conversions(user_id: int = 0, limit: int = 20) -> dict:
    items = file_converter.list_conversions(user_id, limit)
    return {"conversions": items, "count": len(items)}

def get_supported_formats() -> dict:
    formats = file_converter.get_supported_formats()
    return {"formats": formats, "count": len(formats)}

def read_converted(output_path: str) -> dict:
    content = file_converter.read_converted(output_path)
    if content is None:
        return {"status": "error", "message": "File not found or unreadable"}
    return {"status": "success", "content": content, "length": len(content)}

def get_file_converter_tools():
    from backend.orchestrator.agent import Tool
    return [
        Tool(name="convert_file", description="Convert a local file (PDF, DOCX, PPTX, XLSX, image, audio, HTML, CSV, JSON, ZIP, EPUB, text) to Markdown using Markitdown", parameters={"type": "object", "properties": {"file_path": {"type": "string", "description": "Path to the file to convert"}, "user_id": {"type": "integer", "description": "User ID (default 0)"}}, "required": ["file_path"]}, handler=convert_file, category="utility"),
        Tool(name="convert_url", description="Convert a URL (YouTube video, webpage, etc.) to Markdown using Markitdown", parameters={"type": "object", "properties": {"url": {"type": "string", "description": "URL to convert (YouTube, webpage, etc.)"}, "user_id": {"type": "integer", "description": "User ID (default 0)"}}, "required": ["url"]}, handler=convert_url, category="utility"),
        Tool(name="list_conversions", description="List recent file conversion history", parameters={"type": "object", "properties": {"user_id": {"type": "integer", "description": "User ID (default 0)"}, "limit": {"type": "integer", "description": "Max results (default 20)"}}, "required": []}, handler=list_conversions, category="utility"),
        Tool(name="get_supported_formats", description="List all supported file formats for conversion", parameters={"type": "object", "properties": {}, "required": []}, handler=get_supported_formats, category="utility"),
        Tool(name="read_converted", description="Read the content of a converted markdown file", parameters={"type": "object", "properties": {"output_path": {"type": "string", "description": "Path to the converted markdown file"}}, "required": ["output_path"]}, handler=read_converted, category="utility"),
    ]
