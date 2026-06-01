"""Interactive REPL for PHI Agent — direct chat, no server needed."""

import sys, asyncio, time, signal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "PHI"))

from backend.orchestrator.agent import agent

session_id = "repl"

async def repl():
    print("PHI Agent — type 'exit' to quit, 'reset' to clear session\n")
    while True:
        try:
            msg = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not msg:
            continue
        if msg.lower() == "exit":
            break
        if msg.lower() == "reset":
            agent.reset_session(session_id)
            print("PHI: Session reset.\n")
            continue

        start = time.time()
        result = await agent.process(msg, session_id=session_id)
        elapsed = time.time() - start
        reply = result.get("reply", "")
        actions = result.get("actions_taken", [])
        print(f"PHI: {reply}")
        if actions:
            print(f"     [tools: {', '.join(actions)}]")
        print(f"     [{elapsed:.1f}s]\n")

if __name__ == "__main__":
    asyncio.run(repl())
