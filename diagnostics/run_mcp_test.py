import os
import sys
from contextlib import redirect_stderr, redirect_stdout

from dotenv import load_dotenv


LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
LOG_PATH = os.path.join(LOG_DIR, "mcp_test_output.log")


def main():
    os.makedirs(LOG_DIR, exist_ok=True)
    load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))

    from brain.llm_router import ask_aria

    query = (
        "Use the fetch tool to retrieve https://httpbin.org/json and "
        "summarize title and slideshow author."
    )

    with open(LOG_PATH, "w", encoding="utf-8") as log_file:
        with redirect_stdout(log_file), redirect_stderr(log_file):
            print("[MCP] Starting MCP fetch validation run")
            print(f"[MCP] Writing output to {LOG_PATH}")
            result = ask_aria(query)
            print(result)

    print(f"MCP test output saved to {LOG_PATH}")


if __name__ == "__main__":
    sys.exit(main())