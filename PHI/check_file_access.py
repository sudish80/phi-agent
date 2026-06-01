#!/usr/bin/env python
"""Check if agent has file read/write/delete tools."""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.orchestrator.agent import agent

tools = agent.tools.list_tools()

print("\n" + "="*70)
print("FILE OPERATION CAPABILITIES")
print("="*70)

file_ops = [
    'file_read',
    'file_write',
    'file_delete',
    'file_copy',
    'file_move',
    'file_rename',
    'file_touch',
    'dir_create',
    'dir_list',
    'dir_tree',
]

print("\nFILE TOOLS REGISTERED:")
print("-"*70)

for tool in tools:
    if tool['name'] in file_ops:
        params = list(tool['parameters'].get('properties', {}).keys())
        print(f"\n[{tool['name']}]")
        print(f"  Description: {tool['description'][:80]}")
        print(f"  Parameters: {params}")

print("\n" + "="*70)
print("SUMMARY - Agent Can:")
print("="*70)

if any(t['name'] == 'file_read' for t in tools):
    print("  [READ]   - Read file contents (up to 50KB)")
if any(t['name'] == 'file_write' for t in tools):
    print("  [WRITE]  - Write/create files with any content")
if any(t['name'] == 'file_delete' for t in tools):
    print("  [DELETE] - Delete files and directories recursively")
if any(t['name'] == 'file_copy' for t in tools):
    print("  [COPY]   - Copy files to any location")
if any(t['name'] == 'file_move' for t in tools):
    print("  [MOVE]   - Move/rename files")
if any(t['name'] == 'dir_create' for t in tools):
    print("  [CREATE] - Create directories")

print("\n" + "="*70)
