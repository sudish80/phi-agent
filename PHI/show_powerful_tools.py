#!/usr/bin/env python
"""Show powerful computer access tools."""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.orchestrator.agent import agent

tools = agent.tools.list_tools()

powerful = [
    'orchestrate_sequence',
    'macro_record_start',
    'macro_run',
    'keyboard_hotkey',
    'mouse_click',
    'mouse_move',
    'keyboard_type',
    'remote_desktop_start',
    'system_settings_control',
    'os_layer_execute',
]

print("\nPOWERFUL COMPUTER ACCESS TOOLS:")
print("="*70)

for tool in tools:
    if tool['name'] in powerful:
        print(f"\n[{tool['name']}]")
        print(f"  Category: {tool['category']}")
        print(f"  Description: {tool['description'][:90]}...")
        params = list(tool['parameters'].get('properties', {}).keys())
        print(f"  Parameters: {params}")

print("\n" + "="*70)
print("SUMMARY: The agent can...")
print("="*70)
print("  [MOUSE]     - Move cursor, click buttons, scroll")
print("  [KEYBOARD]  - Type text, press keys, execute hotkeys (Ctrl+C, etc)")
print("  [MACROS]    - Record and playback automated sequences")
print("  [SYSTEM]    - Control settings, brightness, volume, WiFi")
print("  [SEQUENCE]  - Execute complex multi-step automation")
print("  [REMOTE]    - Connect to other computers via RDP/VNC")
print("  [OS LAYER]  - Execute system commands directly")
