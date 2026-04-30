"""
ARIA Test Suite
Run with: .\\venv\\Scripts\\python.exe test.py
Loads .env automatically. Tests all layers: tools, memory, LLM routing, MCP servers.
"""

import os
import sys
import json
import time

# ── Load .env ──────────────────────────────────────────────────────────────
from dotenv import load_dotenv
load_dotenv()

# ── Colour helpers (Windows-safe) ──────────────────────────────────────────
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
RESET  = "\033[0m"

passed = []
failed = []
skipped = []

def header(title):
    print(f"\n{CYAN}{'─' * 60}{RESET}")
    print(f"{CYAN}  {title}{RESET}")
    print(f"{CYAN}{'─' * 60}{RESET}")

def ok(label):
    print(f"  {GREEN}[PASS]{RESET} {label}")
    passed.append(label)

def fail(label, reason=""):
    print(f"  {RED}[FAIL]{RESET} {label}")
    if reason:
        print(f"         {RED}→ {reason}{RESET}")
    failed.append(label)

def skip(label, reason=""):
    print(f"  {YELLOW}[SKIP]{RESET} {label}")
    if reason:
        print(f"         {YELLOW}→ {reason}{RESET}")
    skipped.append(label)

def summary():
    print(f"\n{CYAN}{'═' * 60}{RESET}")
    print(f"  Results: {GREEN}{len(passed)} passed{RESET}  "
          f"{RED}{len(failed)} failed{RESET}  "
          f"{YELLOW}{len(skipped)} skipped{RESET}")
    print(f"{CYAN}{'═' * 60}{RESET}\n")


# ══════════════════════════════════════════════════════════════════════════
# LAYER 1 — Direct tool execution
# ══════════════════════════════════════════════════════════════════════════
header("Layer 1 — Direct Tool Execution")

try:
    from actions.system_ops import (
        get_current_time, get_weather, list_directory, create_file, read_file
    )

    result = get_current_time()
    if result and "time" in result.lower():
        ok("get_current_time()")
    else:
        fail("get_current_time()", f"Unexpected output: {result}")

    result = get_weather("Muzaffarabad")
    if result and "°C" in result:
        ok("get_weather('Muzaffarabad')")
    else:
        fail("get_weather()", f"Unexpected output: {result}")

    result = list_directory(os.path.expanduser("~/Desktop"))
    if result and "Contents" in result:
        ok("list_directory(Desktop)")
    else:
        fail("list_directory()", f"Unexpected output: {result}")

    test_path = os.path.join(os.path.expanduser("~/Desktop"), "aria_test_suite.txt")
    result = create_file(test_path, "ARIA test suite marker file.")
    if "Successfully" in result:
        ok("create_file()")
    else:
        fail("create_file()", result)

    result = read_file(test_path)
    if "ARIA test suite" in result:
        ok("read_file()")
    else:
        fail("read_file()", result)

except Exception as e:
    fail("Layer 1 import/execution", str(e))


# ══════════════════════════════════════════════════════════════════════════
# LAYER 2 — Toolkit schema generation
# ══════════════════════════════════════════════════════════════════════════
header("Layer 2 — Toolkit Schema Generation")

try:
    from actions.system_ops import tools

    schemas = tools.get_json_schemas()
    native_tool_names = [s['function']['name'] for s in schemas]
    expected = [
        "get_current_time", "get_weather", "take_screenshot",
        "open_application", "close_application", "play_spotify_media",
        "control_spotify", "change_system_volume", "list_directory",
        "read_file", "create_file"
    ]
    missing = [t for t in expected if t not in native_tool_names]
    if not missing:
        ok(f"All 11 native tools registered ({len(schemas)} total schemas)")
    else:
        fail("Native tool registration", f"Missing: {missing}")

except Exception as e:
    fail("Toolkit schema generation", str(e))


# ══════════════════════════════════════════════════════════════════════════
# LAYER 3 — MCP server registration
# ══════════════════════════════════════════════════════════════════════════
header("Layer 3 — MCP Server Registration")

try:
    from actions.mcp_tools import load_mcp_tools
    load_mcp_tools()

    schemas_after = tools.get_json_schemas()
    all_tool_names = [s['function']['name'] for s in schemas_after]
    total = len(schemas_after)

    print(f"  Total tools after MCP registration: {total}")

    mcp_checks = {
        "fetch_mcp":           "fetch",
        "sequential_thinking": "sequentialthinking",
        "tavily_search":       "tavily_search",
        "firecrawl_mcp":       "firecrawl_scrape",
    }

    for server, probe_tool in mcp_checks.items():
        if probe_tool in all_tool_names:
            ok(f"{server} → '{probe_tool}' registered")
        else:
            env_gates = {
                "firecrawl_mcp": "FIRECRAWL_API_KEY",
                "tavily_search": "TAVILY_API_KEY",
            }
            gate = env_gates.get(server)
            if gate and not os.getenv(gate):
                skip(f"{server}", f"{gate} not set in .env")
            else:
                fail(f"{server}", f"'{probe_tool}' not found in registered tools")

except Exception as e:
    fail("MCP registration", str(e))


# ══════════════════════════════════════════════════════════════════════════
# LAYER 4 — Memory persistence
# ══════════════════════════════════════════════════════════════════════════
header("Layer 4 — Memory Persistence")

try:
    from brain.llm_router import memory

    before = len(memory.get_memory())
    memory.add({"role": "user", "content": "__aria_test_marker__"})
    after = len(memory.get_memory())
    last = memory.get_memory()[-1]

    if after == before + 1 and last.get("content") == "__aria_test_marker__":
        ok("memory.add() writes correctly")
    else:
        fail("memory.add()", f"Count before={before} after={after} last={last}")

    # Reload memory from disk in a subprocess to verify persistence
    import subprocess
    result = subprocess.run(
        [sys.executable, "-c",
         "from dotenv import load_dotenv; load_dotenv(); "
         "from brain.llm_router import memory; "
         "msgs = memory.get_memory(); "
         "print(msgs[-1]['content'])"],
        capture_output=True, text=True
    )
    if "__aria_test_marker__" in result.stdout:
        ok("Memory persists across process restart")
    else:
        fail("Memory persistence", result.stderr or result.stdout)

except Exception as e:
    fail("Memory layer", str(e))


# ══════════════════════════════════════════════════════════════════════════
# LAYER 5 — LLM routing + single tool call
# ══════════════════════════════════════════════════════════════════════════
header("Layer 5 — LLM Routing (single tool)")

try:
    from brain.llm_router import ask_aria

    response = ask_aria("what time is it right now")
    if response and len(response) > 3:
        ok(f"Single tool call → '{response[:60]}...'")
    else:
        fail("Single tool call", f"Response: {response}")

except Exception as e:
    fail("LLM single tool call", str(e))


# ══════════════════════════════════════════════════════════════════════════
# LAYER 6 — Parallel tool calls
# ══════════════════════════════════════════════════════════════════════════
header("Layer 6 — Parallel Tool Calls")

try:
    response = ask_aria("what is the time and what is the weather in Islamabad")
    if response and len(response) > 3:
        ok(f"Parallel tool call → '{response[:60]}...'")
    else:
        fail("Parallel tool call", f"Response: {response}")

except Exception as e:
    fail("Parallel tool call", str(e))


# ══════════════════════════════════════════════════════════════════════════
# LAYER 7 — Conversation memory (cross-turn recall)
# ══════════════════════════════════════════════════════════════════════════
header("Layer 7 — Conversation Memory (cross-turn recall)")

try:
    ask_aria("my favourite city is Muzaffarabad")
    time.sleep(1)
    response = ask_aria("what is my favourite city")
    if "muzaffarabad" in response.lower():
        ok(f"Cross-turn memory recall → '{response[:60]}'")
    else:
        fail("Cross-turn recall", f"Response did not contain 'Muzaffarabad': {response}")

except Exception as e:
    fail("Cross-turn memory", str(e))


# ══════════════════════════════════════════════════════════════════════════
# LAYER 8 — MCP fetch tool via LLM
# ══════════════════════════════════════════════════════════════════════════
header("Layer 8 — MCP fetch tool (via LLM)")

try:
    response = ask_aria("fetch the content from https://httpbin.org/json and tell me what it contains")
    if response and len(response) > 5:
        ok(f"MCP fetch → '{response[:80]}...'")
    else:
        fail("MCP fetch", f"Response: {response}")

except Exception as e:
    fail("MCP fetch", str(e))


# ══════════════════════════════════════════════════════════════════════════
# LAYER 9 — Tavily search via LLM
# ══════════════════════════════════════════════════════════════════════════
header("Layer 9 — Tavily Search (via LLM)")

if not os.getenv("TAVILY_API_KEY"):
    skip("Tavily search", "TAVILY_API_KEY not set in .env")
else:
    try:
        response = ask_aria("search the web for latest news about artificial intelligence")
        if response and len(response) > 5:
            ok(f"Tavily search → '{response[:80]}...'")
        else:
            fail("Tavily search", f"Response: {response}")
    except Exception as e:
        fail("Tavily search", str(e))


# ══════════════════════════════════════════════════════════════════════════
# LAYER 10 — Firecrawl scrape via LLM
# ══════════════════════════════════════════════════════════════════════════
header("Layer 10 — Firecrawl Scrape (via LLM)")

if not os.getenv("FIRECRAWL_API_KEY"):
    skip("Firecrawl scrape", "FIRECRAWL_API_KEY not set in .env")
else:
    try:
        response = ask_aria("scrape the content from https://example.com and summarize it")
        if response and len(response) > 5:
            ok(f"Firecrawl scrape → '{response[:80]}...'")
        else:
            fail("Firecrawl scrape", f"Response: {response}")
    except Exception as e:
        fail("Firecrawl scrape", str(e))


# ══════════════════════════════════════════════════════════════════════════
# LAYER 11 — File system round-trip via LLM
# ══════════════════════════════════════════════════════════════════════════
header("Layer 11 — File System Round-Trip (via LLM)")

try:
    desktop = os.path.join(os.path.expanduser("~"), "Desktop", "aria_llm_test.txt")
    ask_aria(f"create a file at {desktop} with the content: LLM file write confirmed")
    time.sleep(1)
    response = ask_aria(f"read the file at {desktop}")
    if "LLM file write confirmed" in response or "confirmed" in response.lower():
        ok("LLM file create + read round-trip")
    else:
        fail("LLM file round-trip", f"Response: {response}")
except Exception as e:
    fail("LLM file round-trip", str(e))


# ══════════════════════════════════════════════════════════════════════════
# SUMMARY
# ══════════════════════════════════════════════════════════════════════════
summary()
