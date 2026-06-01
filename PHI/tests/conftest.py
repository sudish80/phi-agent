import pytest


@pytest.fixture
def sample_tools():
    return [
        {"name": "file_read", "description": "Read a file"},
        {"name": "file_write", "description": "Write a file"},
        {"name": "web_search", "description": "Search the web"},
        {"name": "bash_exec", "description": "Execute bash"},
        {"name": "chat", "description": "Chat"},
        {"name": "memory_save", "description": "Save to memory"},
        {"name": "generate_image", "description": "Generate image"},
        {"name": "system_info", "description": "System info"},
        {"name": "send_email", "description": "Send email"},
        {"name": "credential_get", "description": "Get credential"},
    ]
