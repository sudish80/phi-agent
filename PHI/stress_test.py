"""Stress test: runs all tools with schema-derived args, results to CSV.

Uses 8 parallel worker processes. Each worker uses JSON Schema to generate
appropriate test arguments for every tool, so it works for ALL tools — even
massive_tools generated modules with 10,000+ entries.
"""

import asyncio
import csv
import json
import logging
import os
import random
import shutil
import string
import sys
import time
import traceback
import types
from datetime import datetime
from multiprocessing import Process, Queue, freeze_support

logging.basicConfig(level=logging.ERROR)
BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)

TEST_COUNT = 100
CSV_PATH = os.path.join(BASE, "stress_test_results.csv")
MAX_WORKERS = 8


def _gen_value_for_schema(props, required=False):
    """Generate a plausible test value from a JSON Schema property definition."""
    val = None
    schema_type = props.get("type", "string")
    desc = (props.get("description") or "").lower()

    if schema_type == "string":
        if "email" in desc:
            val = "test@example.com"
        elif "url" in desc or "uri" in desc:
            val = "https://example.com"
        elif "ip" in desc or "ipv4" in desc:
            val = "192.168.1.1"
        elif "phone" in desc:
            val = "+1-555-123-4567"
        elif "hex" in desc and ("color" in desc or "#" in desc):
            val = "#3498db"
        elif "path" in desc or "file" in desc:
            val = "/tmp/test.txt"
        elif "password" in desc or "secret" in desc or "token" in desc or "key" in desc:
            val = "test_secret_key_123"
        elif "date" in desc:
            val = "2024-01-15"
        elif "time" in desc:
            val = "12:00:00"
        elif "json" in desc or "payload" in desc or "data" in desc or "object" in desc:
            val = json.dumps({"key": "value"})
        elif "separator" in desc or "delimiter" in desc or "sep" in desc:
            val = ","
        elif "pattern" in desc or "regex" in desc:
            val = r"\d+"
        elif "method" in desc:
            val = "GET"
        elif "origin" in desc:
            val = "*"
        elif "tag" in desc:
            val = "div"
        elif "country" in desc:
            val = "US"
        elif "code" in desc:
            val = "200"
        elif "hash" in desc:
            val = "abc123"
        elif "operator" in desc or "op" in desc:
            val = "eq"
        elif "format" in desc:
            val = "%Y-%m-%d"
        elif "color" in desc or "hex" in desc:
            val = "#ff0000"
        elif "query" in desc:
            val = "test query"
        else:
            val = "test"
    elif schema_type == "integer":
        if "port" in desc:
            val = 8080
        elif "count" in desc or "limit" in desc or "max" in desc:
            val = 5
        elif "width" in desc or "length" in desc:
            val = 100
        elif "age" in desc:
            val = 30
        elif "year" in desc:
            val = 2024
        elif "size" in desc or "chunk" in desc:
            val = 2
        elif "total" in desc:
            val = 100
        elif "level" in desc:
            val = 1
        elif "status" in desc:
            val = 200
        elif "angle" in desc:
            val = 90
        elif "sides" in desc:
            val = 6
        else:
            val = 42
    elif schema_type == "number":
        val = 42.5
    elif schema_type == "boolean":
        val = True
    elif schema_type == "array":
        items = props.get("items", {})
        item_type = items.get("type", "string")
        if item_type == "integer":
            val = json.dumps([1, 2, 3, 4, 5])
        elif item_type == "number":
            val = json.dumps([1.5, 2.5, 3.5])
        elif item_type == "string":
            val = json.dumps(["a", "b", "c"])
        else:
            val = json.dumps([{"a": 1}, {"b": 2}])
    elif schema_type == "object":
        val = json.dumps({"key": "value"})
    else:
        val = "test"

    return val


def _generate_tool_args(tool_info):
    """Generate test arguments for a tool from its parameter schema."""
    params = tool_info.get("parameters", {})
    if not params or not isinstance(params, dict):
        return {}

    properties = params.get("properties", {})
    required = params.get("required", [])

    args = {}
    for name, prop in properties.items():
        args[name] = _gen_value_for_schema(prop, name in required)

    return args


def worker(tool_infos_batch, queue, count):
    """Worker process: runs tests for a batch of tools."""
    sys.path.insert(0, BASE)
    os.environ["PHI_SKIP_INIT"] = "1"

    results = []
    for tool_info in tool_infos_batch:
        tool_name = tool_info["name"]
        try:
            import importlib
            mod = importlib.import_module("backend.orchestrator.agent")
            agent = mod.agent

            tool = agent.tools.get(tool_name)
            if not tool:
                results.append((tool_name, "ERROR", "tool not found", "", datetime.now().isoformat()))
                continue

            is_async = asyncio.iscoroutinefunction(tool.handler)

            successes = 0
            failures = 0
            total_time = 0.0

            for i in range(count):
                try:
                    args = _generate_tool_args(tool_info)
                    t0 = time.perf_counter()
                    if is_async:
                        result = asyncio.run(tool.handler(**args))
                    else:
                        result = tool.handler(**args)
                    elapsed = (time.perf_counter() - t0) * 1000
                    total_time += elapsed
                    successes += 1
                except Exception as e:
                    failures += 1
                    if i < 2:
                        results.append((tool_name, "fail", "0", str(e)[:200], datetime.now().isoformat()))

                if (i + 1) % 250 == 0:
                    print(f"[PID {os.getpid()}] {tool_name}: {i+1}/{count}")

            avg_ms = total_time / count if count > 0 else 0
            fail_rate = (failures / count) * 100
            results.append((
                tool_name, "SUMMARY",
                f"count={count}, pass={successes}, fail={failures}, avg={avg_ms:.2f}ms, fail_rate={fail_rate:.1f}%",
                "", datetime.now().isoformat()
            ))

            queue.put(("tool_done", tool_name, successes, failures, avg_ms))

        except Exception as e:
            results.append((tool_name, "FATAL", str(e)[:200], traceback.format_exc()[:500], datetime.now().isoformat()))
            queue.put(("tool_done", tool_name, 0, count, 0))

    queue.put(("batch_done", results, os.getpid()))


def main():
    start_time = time.time()
    os.makedirs(os.path.dirname(CSV_PATH) or ".", exist_ok=True)

    print("=" * 70)
    total_tool_count_target = 10_000
    print(f"STRESS TEST: {TEST_COUNT:,} iterations per tool (schema-derived args)")
    print(f"Target tool count: {total_tool_count_target:,}")
    print("=" * 70)

    print("\nLoading tools...")
    import backend.orchestrator.agent
    all_tools = backend.orchestrator.agent.agent.tools.list_tools()
    print(f"Loaded {len(all_tools)} tools")

    total_iterations = TEST_COUNT * len(all_tools)
    print(f"Total iterations: {total_iterations:,}")
    print(f"Workers: {MAX_WORKERS}")

    batch_size = max(1, len(all_tools) // MAX_WORKERS)
    batches = [all_tools[i:i + batch_size] for i in range(0, len(all_tools), batch_size)]

    queue = Queue()
    processes = []
    for batch in batches:
        p = Process(target=worker, args=(batch, queue, TEST_COUNT))
        processes.append(p)
        p.start()

    all_results = []
    total_pass = 0
    total_fail = 0
    tool_stats = []
    batches_remaining = len(batches)

    print(f"\nRunning stress test across {MAX_WORKERS} workers...\n")

    while batches_remaining > 0:
        msg = queue.get()
        if msg[0] == "tool_done":
            _, tool_name, s, f, avg = msg
            total_pass += s
            total_fail += f
            fr = (f / TEST_COUNT) * 100 if TEST_COUNT > 0 else 0
            tool_stats.append((tool_name, s, f, avg, fr))
            status = "OK" if fr == 0 else f"WARN({fr:.0f}%)"
            print(f"  [{status}] {tool_name}: {s}/{TEST_COUNT} pass, avg {avg:.2f}ms")
        elif msg[0] == "batch_done":
            _, batch_results, pid = msg
            all_results.extend(batch_results)
            batches_remaining -= 1
            print(f"  Batch from PID {pid} complete ({len(batch_results)} rows)")

    for p in processes:
        p.join()

    elapsed = time.time() - start_time

    print(f"\nWriting {len(all_results)} rows to {CSV_PATH}...")
    with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["tool_name", "result", "detail", "error", "timestamp"])
        for row in all_results:
            writer.writerow(row)

        writer.writerow([])
        writer.writerow(["TOOL", "PASS", "FAIL", "AVG(ms)", "FAIL_RATE(%)", "TARGET_ITERATIONS"])
        for name, s, f, avg, fr in tool_stats:
            writer.writerow([name, s, f, f"{avg:.2f}", f"{fr:.2f}", TEST_COUNT])

    print(f"\n{'=' * 70}")
    print(f"STRESS TEST COMPLETE")
    print(f"  Tools: {len(all_tools)}")
    print(f"  Iterations: {total_pass + total_fail:,}")
    print(f"  Pass: {total_pass:,}  Fail: {total_fail:,}")
    fr_total = (total_fail / (total_pass + total_fail)) * 100 if (total_pass + total_fail) > 0 else 0
    print(f"  Fail rate: {fr_total:.2f}%")
    print(f"  Duration: {elapsed:.1f}s")
    if (total_pass + total_fail) > 0:
        print(f"  Throughput: {(total_pass + total_fail) / elapsed:.0f} iter/s")
    print(f"  Results: {CSV_PATH}")
    print(f"{'=' * 70}")

    # Cleanup test artifacts
    print("\nCleaning up test artifacts...")
    for fname in os.listdir(BASE):
        if fname.startswith("test_export.") or fname.startswith("test_schema."):
            try:
                os.remove(os.path.join(BASE, fname))
                print(f"  Removed: {fname}")
            except:
                pass
    print("Done.")


if __name__ == "__main__":
    freeze_support()
    main()
