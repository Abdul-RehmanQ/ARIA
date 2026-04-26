import asyncio
import os
import sys
from agentscope.mcp import HttpStatelessClient, StdIOStatefulClient

# This imports the SAME Toolkit instance that system_ops.py already built.
# All MCP tools register into the same tool list ARIA uses.
from actions.system_ops import tools

# ── MCP Server Registry ────────────────────────────────────────────────────
# Add servers here as you need them.
# Format: (name, transport_type, url_or_command)
#
# HTTP servers:  ("name", "http", "http://localhost:PORT/mcp")
# StdIO servers: use command arrays and optional required env keys.

HTTP_SERVERS = [
    # ("web_fetch", "http://localhost:8000/mcp"),
]

STDIO_SERVERS = [
    {
        "name": "fetch_mcp",
        "command": [sys.executable, "-m", "mcp_server_fetch"],
        "required_env": [],
    },
    {
        "name": "sequential_thinking",
        "command": ["cmd", "/c", "npx", "-y", "@modelcontextprotocol/server-sequential-thinking"],
        "required_env": [],
    },
    {
        "name": "tavily_search",
        "command": ["cmd", "/c", "npx", "-y", "mcp-remote", "__TAVILY_REMOTE_URL__"],
        "required_env": [],
    },
    {
        "name": "firecrawl_mcp",
        "command": ["cmd", "/c", "npx", "-y", "firecrawl-mcp"],
        "required_env": ["FIRECRAWL_API_KEY"],
    },
]

_MCP_LOADED = False


def _build_server_env(required_env):
    values = {key: os.getenv(key) for key in required_env if os.getenv(key)}
    if not required_env:
        return None
    if len(values) != len(required_env):
        return None
    return {**os.environ, **values}


def _resolve_tavily_remote_url():
    explicit_url = os.getenv("TAVILY_MCP_URL")
    if explicit_url:
        return explicit_url

    api_key = os.getenv("TAVILY_API_KEY")
    if api_key:
        return f"https://mcp.tavily.com/mcp/?tavilyApiKey={api_key}"

    return None


def _make_stdio_tool_callable(server_name, command, tool_name, server_env):
    async def _invoke_with_temp_client(kwargs):
        client = StdIOStatefulClient(
            name=server_name,
            command=command[0],
            args=command[1:],
            env=server_env,
        )
        await client.connect()
        try:
            func = await client.get_callable_function(func_name=tool_name)
            return await func(**kwargs)
        finally:
            try:
                await client.close()
            except Exception:
                pass

    if tool_name == "fetch":
        async def fetch(url: str, max_length: int = 5000, start_index: int = 0, raw: bool = False):
            return await _invoke_with_temp_client({
                "url": url,
                "max_length": max_length,
                "start_index": start_index,
                "raw": raw,
            })

        fetch.__name__ = "fetch"
        fetch.__doc__ = (
            "Fetches a URL via MCP and returns extracted content. "
            "Required argument: url."
        )
        return fetch

    async def _tool_callable(**kwargs):
        return await _invoke_with_temp_client(kwargs)

    _tool_callable.__name__ = tool_name
    _tool_callable.__doc__ = f"MCP tool '{tool_name}' from stdio server '{server_name}'."
    return _tool_callable

# ── Registration Logic ─────────────────────────────────────────────────────

async def _register_http_servers():
    for name, url in HTTP_SERVERS:
        try:
            client = HttpStatelessClient(
                name=name,
                transport="streamable_http",
                url=url
            )
            mcp_tool_list = await client.list_tools()
            for tool in mcp_tool_list:
                tool_name = getattr(tool, "name", tool)
                func = await client.get_callable_function(func_name=tool_name)
                tools.register_tool_function(func)
            print(f"[MCP] Registered {len(mcp_tool_list)} tools from '{name}'")
        except Exception as e:
            print(f"[MCP] Failed to connect to HTTP server '{name}': {e}")


async def _register_stdio_servers():
    for server in STDIO_SERVERS:
        name = server["name"]
        command = list(server["command"])
        required_env = server.get("required_env", [])
        server_env = _build_server_env(required_env)

        if "__TAVILY_REMOTE_URL__" in command:
            tavily_url = _resolve_tavily_remote_url()
            if not tavily_url:
                print("[MCP] Skipping 'tavily_search' - missing required env: TAVILY_MCP_URL or TAVILY_API_KEY")
                continue
            command = [tavily_url if part == "__TAVILY_REMOTE_URL__" else part for part in command]

        if required_env and server_env is None:
            missing = [key for key in required_env if not os.getenv(key)]
            print(f"[MCP] Skipping '{name}' - missing required env: {', '.join(missing)}")
            continue

        try:
            client = StdIOStatefulClient(
                name=name,
                command=command[0],
                args=command[1:],
                env=server_env,
            )
            await client.connect()
            mcp_tool_list = await client.list_tools()
            for tool in mcp_tool_list:
                tool_name = getattr(tool, "name", tool)
                func = _make_stdio_tool_callable(name, command, tool_name, server_env)
                tools.register_tool_function(func)
            print(f"[MCP] Registered {len(mcp_tool_list)} tools from '{name}'")
        except Exception as e:
            print(f"[MCP] Failed to connect to StdIO server '{name}': {e}")
        finally:
            try:
                await client.close()
            except Exception:
                pass


async def _register_all():
    await _register_http_servers()
    await _register_stdio_servers()


def load_mcp_tools():
    """Synchronous entry point. Call this once at startup before get_json_schemas()."""
    global _MCP_LOADED

    if _MCP_LOADED:
        return

    if not HTTP_SERVERS and not STDIO_SERVERS:
        print("[MCP] No servers configured. Skipping MCP registration.")
        _MCP_LOADED = True
        return

    asyncio.run(_register_all())
    _MCP_LOADED = True
