#!/usr/bin/env python
"""Test script to check if agent has tools loaded."""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.orchestrator.agent import agent

print(f"Agent tools registry size: {len(agent.tools)}")
tools_list = agent.tools.list_tools()
print(f"Tools registered: {len(tools_list)}")

if tools_list:
    print(f"\nFirst 10 tools:")
    for t in tools_list[:10]:
        print(f"  - {t['name']} ({t['category']})")
else:
    print("ERROR: NO TOOLS REGISTERED!")
    sys.exit(1)

print(f"\nTotal tools by category:")
categories = {}
for t in tools_list:
    cat = t.get('category', 'unknown')
    categories[cat] = categories.get(cat, 0) + 1

for cat, count in sorted(categories.items()):
    print(f"  {cat}: {count}")
