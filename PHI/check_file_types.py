#!/usr/bin/env python
"""Check what file types the agent can read."""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.orchestrator.agent import agent

tools = agent.tools.list_tools()

print("\n" + "="*70)
print("FILE TYPE READING CAPABILITIES")
print("="*70)

# Categorize tools by file type they can read
categories = {
    "Text Files": {
        "tools": ["file_read"],
        "types": [".txt", ".py", ".js", ".json", ".xml", ".csv", ".md", ".html", ".css"],
    },
    "Images": {
        "tools": ["color_analyze_local_image", "detect_emotion_face", "analyze_face_attributes", "detect_faces_image"],
        "types": [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff"],
    },
    "Audio": {
        "tools": ["audio_trim", "audio_concatenate", "audio_split_by_silence", "audio_noise_reduce"],
        "types": [".mp3", ".wav", ".flac", ".ogg", ".aac"],
    },
    "PDFs": {
        "tools": ["pdf_enhance_file", "pdf_enhance_images"],
        "types": [".pdf"],
    },
    "Archives": {
        "tools": ["file_decompress"],
        "types": [".zip", ".tar", ".tar.gz", ".7z"],
    },
    "Binary": {
        "tools": ["file_hash"],
        "types": [".exe", ".dll", ".so", ".bin"],
    },
}

for category, info in categories.items():
    print(f"\n{category}:")
    print("-" * 70)
    
    found_tools = []
    for tool_name in info["tools"]:
        for tool in tools:
            if tool["name"] == tool_name:
                found_tools.append(tool)
                break
    
    if found_tools:
        print(f"  File types: {', '.join(info['types'])}")
        print(f"  Tools available:")
        for tool in found_tools:
            print(f"    - {tool['name']}: {tool['description'][:60]}")
    else:
        print(f"  Tools: NOT FOUND")

print("\n" + "="*70)
print("LIMITATIONS")
print("="*70)

print("""
file_read() limitations:
  - Opens files in TEXT mode with UTF-8 encoding
  - Binary files will be CORRUPTED when read as text
  - Max 50,000 bytes per read
  - Will fail or show garbage for binary formats

Examples of what happens:
  - .exe file: Shows corrupted binary garbage
  - .jpg image: Shows corrupted binary data (not readable)
  - .pdf: May show some text but structure lost
  - .docx: Binary format, won't display properly
""")

print("\n" + "="*70)
print("VERDICT")
print("="*70)
print("""
file_read() can read: TEXT FILES ONLY
  [YES] .txt, .py, .js, .json, .xml, .csv, .html, .css, .md, .log, .conf

For BINARY FILES, agent has specialized tools:
  - Images: color_analyze_local_image, detect_faces_image
  - Audio: audio_trim, audio_concatenate
  - Archives: file_decompress
  - Hashing: file_hash (any file type)

IMPORTANT: Binary files opened with file_read() = CORRUPTED/UNREADABLE
""")
