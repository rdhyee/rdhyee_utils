#!/usr/bin/env python3
"""
macOS Apps MCP Server - Control LLM desktop apps via AppleScript bridge.

Provides access to:
- Dia (OpenAI's macOS app) - Native SwiftUI with Accessibility APIs
- Atlas (ChatGPT desktop) - Chromium-based with PyAutoGUI
- Comet (Perplexity desktop) - Chromium-based with JavaScript injection

Uses the efficient 3-tool pattern (list_services, get_service_help, execute)
to minimize context overhead.

Usage:
  python -m rdhyee_utils.applescript_bridge.mcp_server

Configure in Claude Code's .claude/mcp.json:
  {
    "mcpServers": {
      "macos-apps": {
        "command": "python",
        "args": ["-m", "rdhyee_utils.applescript_bridge.mcp_server"]
      }
    }
  }
"""

import asyncio
import json
import logging
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# Import app bindings
from .apps.dia import Dia
from .apps.atlas import Atlas
from .apps.comet import Comet

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('macos-apps-mcp')

app = Server("macos-apps")

# =============================================================================
# SERVICE REGISTRY
# =============================================================================

SERVICE_REGISTRY = {
    "dia": {
        "description": "OpenAI Dia - Native macOS LLM app with SwiftUI sidebar",
        "methods": {
            "ask": {
                "fn": lambda **kw: _dia_ask(**kw),
                "params": {
                    "question": {"type": "str", "required": True, "desc": "Question to send to Dia"}
                },
                "desc": "Send a question to Dia's AI sidebar"
            },
            "ask_and_wait": {
                "fn": lambda **kw: _dia_ask_and_wait(**kw),
                "params": {
                    "question": {"type": "str", "required": True, "desc": "Question to send"},
                    "timeout": {"type": "float", "default": 30.0, "desc": "Max seconds to wait"}
                },
                "desc": "Send question and wait for response"
            },
            "read_response": {
                "fn": lambda **kw: _dia_read_response(**kw),
                "params": {
                    "timeout": {"type": "float", "default": 30.0, "desc": "Max seconds to wait"}
                },
                "desc": "Read the latest AI response from Dia"
            },
            "is_generating": {
                "fn": lambda **kw: _dia_is_generating(**kw),
                "params": {},
                "desc": "Check if Dia is currently generating a response"
            },
            "list_windows": {
                "fn": lambda **kw: _dia_list_windows(**kw),
                "params": {},
                "desc": "List all Dia windows and tabs"
            }
        }
    },
    "atlas": {
        "description": "ChatGPT Atlas - OpenAI's Chromium-based desktop app",
        "methods": {
            "ask": {
                "fn": lambda **kw: _atlas_ask(**kw),
                "params": {
                    "question": {"type": "str", "required": True, "desc": "Question to send to ChatGPT"}
                },
                "desc": "Send a question to ChatGPT sidebar"
            },
            "ask_and_wait": {
                "fn": lambda **kw: _atlas_ask_and_wait(**kw),
                "params": {
                    "question": {"type": "str", "required": True, "desc": "Question to send"},
                    "timeout": {"type": "float", "default": 30.0, "desc": "Max seconds to wait"}
                },
                "desc": "Send question and wait for response"
            },
            "read_response": {
                "fn": lambda **kw: _atlas_read_response(**kw),
                "params": {
                    "timeout": {"type": "float", "default": 30.0, "desc": "Max seconds to wait"}
                },
                "desc": "Read the latest ChatGPT response"
            },
            "is_generating": {
                "fn": lambda **kw: _atlas_is_generating(**kw),
                "params": {},
                "desc": "Check if ChatGPT is currently generating"
            },
            "list_windows": {
                "fn": lambda **kw: _atlas_list_windows(**kw),
                "params": {},
                "desc": "List all Atlas windows and tabs"
            },
            "execute_js": {
                "fn": lambda **kw: _atlas_execute_js(**kw),
                "params": {
                    "javascript": {"type": "str", "required": True, "desc": "JavaScript to execute"}
                },
                "desc": "Execute JavaScript in active tab"
            }
        }
    },
    "comet": {
        "description": "Perplexity Comet - Chromium-based desktop app with JS injection",
        "methods": {
            "ask": {
                "fn": lambda **kw: _comet_ask(**kw),
                "params": {
                    "question": {"type": "str", "required": True, "desc": "Question to send to Perplexity"},
                    "wait_for_response": {"type": "bool", "default": True, "desc": "Wait for response"}
                },
                "desc": "Send a question to Perplexity"
            },
            "list_windows": {
                "fn": lambda **kw: _comet_list_windows(**kw),
                "params": {},
                "desc": "List all Comet windows and tabs"
            },
            "execute_js": {
                "fn": lambda **kw: _comet_execute_js(**kw),
                "params": {
                    "javascript": {"type": "str", "required": True, "desc": "JavaScript to execute"}
                },
                "desc": "Execute JavaScript in active tab"
            },
            "get_page_content": {
                "fn": lambda **kw: _comet_get_page_content(**kw),
                "params": {},
                "desc": "Get the text content of the current page"
            }
        }
    }
}


# =============================================================================
# DIA IMPLEMENTATIONS
# =============================================================================

def _dia_ask(question: str) -> dict:
    """Send a question to Dia."""
    try:
        dia = Dia()
        return dia.ask_dia(question)
    except Exception as e:
        return {"success": False, "error": str(e)}


def _dia_ask_and_wait(question: str, timeout: float = 30.0) -> dict:
    """Send a question to Dia and wait for response."""
    try:
        dia = Dia()
        return dia.ask_dia_and_wait(question, timeout=timeout)
    except Exception as e:
        return {"success": False, "error": str(e)}


def _dia_read_response(timeout: float = 30.0) -> dict:
    """Read the latest response from Dia."""
    try:
        dia = Dia()
        return dia.read_dia_response(timeout=timeout)
    except Exception as e:
        return {"success": False, "error": str(e)}


def _dia_is_generating() -> dict:
    """Check if Dia is generating."""
    try:
        dia = Dia()
        return {"success": True, "generating": dia.is_generating()}
    except Exception as e:
        return {"success": False, "error": str(e)}


def _dia_list_windows() -> dict:
    """List Dia windows and tabs."""
    try:
        dia = Dia()
        windows = []
        for w in dia.windows:
            windows.append({
                "id": w.id,
                "name": w.name,
                "tabs": [{"title": t.title, "url": t.url} for t in w.tabs]
            })
        return {"success": True, "windows": windows}
    except Exception as e:
        return {"success": False, "error": str(e)}


# =============================================================================
# ATLAS IMPLEMENTATIONS
# =============================================================================

def _atlas_ask(question: str) -> dict:
    """Send a question to Atlas."""
    try:
        atlas = Atlas()
        return atlas.ask_atlas(question)
    except Exception as e:
        return {"success": False, "error": str(e)}


def _atlas_ask_and_wait(question: str, timeout: float = 30.0) -> dict:
    """Send a question to Atlas and wait for response."""
    try:
        atlas = Atlas()
        return atlas.ask_atlas_and_wait(question, timeout=timeout)
    except Exception as e:
        return {"success": False, "error": str(e)}


def _atlas_read_response(timeout: float = 30.0) -> dict:
    """Read the latest response from Atlas."""
    try:
        atlas = Atlas()
        return atlas.read_atlas_response(timeout=timeout)
    except Exception as e:
        return {"success": False, "error": str(e)}


def _atlas_is_generating() -> dict:
    """Check if Atlas is generating."""
    try:
        atlas = Atlas()
        return {"success": True, "generating": atlas.is_generating()}
    except Exception as e:
        return {"success": False, "error": str(e)}


def _atlas_list_windows() -> dict:
    """List Atlas windows and tabs."""
    try:
        atlas = Atlas()
        windows = []
        for w in atlas.windows:
            windows.append({
                "id": w.id,
                "name": w.name,
                "tabs": [{"title": t.title, "url": t.url} for t in w.tabs]
            })
        return {"success": True, "windows": windows}
    except Exception as e:
        return {"success": False, "error": str(e)}


def _atlas_execute_js(javascript: str) -> dict:
    """Execute JavaScript in Atlas active tab."""
    try:
        atlas = Atlas()
        if not atlas.windows:
            return {"success": False, "error": "No Atlas windows open"}
        tab = atlas.windows[0].active_tab
        result = tab.execute(javascript)
        return {"success": True, "result": result}
    except Exception as e:
        return {"success": False, "error": str(e)}


# =============================================================================
# COMET IMPLEMENTATIONS
# =============================================================================

def _comet_ask(question: str, wait_for_response: bool = True) -> dict:
    """Send a question to Perplexity via Comet."""
    try:
        comet = Comet()
        return comet.ask_perplexity(question, wait_for_response=wait_for_response)
    except Exception as e:
        return {"success": False, "error": str(e)}


def _comet_list_windows() -> dict:
    """List Comet windows and tabs."""
    try:
        comet = Comet()
        windows = []
        for w in comet.windows:
            windows.append({
                "id": w.id,
                "name": w.name,
                "tabs": [{"title": t.title, "url": t.url} for t in w.tabs]
            })
        return {"success": True, "windows": windows}
    except Exception as e:
        return {"success": False, "error": str(e)}


def _comet_execute_js(javascript: str) -> dict:
    """Execute JavaScript in Comet active tab."""
    try:
        comet = Comet()
        if not comet.windows:
            return {"success": False, "error": "No Comet windows open"}
        tab = comet.windows[0].active_tab
        result = tab.execute(javascript)
        return {"success": True, "result": result}
    except Exception as e:
        return {"success": False, "error": str(e)}


def _comet_get_page_content() -> dict:
    """Get the text content of the current Comet page."""
    try:
        comet = Comet()
        if not comet.windows:
            return {"success": False, "error": "No Comet windows open"}
        tab = comet.windows[0].active_tab
        content = tab.execute("document.body.innerText")
        return {"success": True, "content": content, "url": tab.url, "title": tab.title}
    except Exception as e:
        return {"success": False, "error": str(e)}


# =============================================================================
# MCP TOOL DEFINITIONS
# =============================================================================

@app.list_tools()
async def list_tools() -> list[Tool]:
    """List the 3 efficient tools."""
    return [
        Tool(
            name="list_services",
            description="""List available macOS LLM app services.

Returns available apps (dia, atlas, comet) with descriptions.
Use get_service_help to see methods for each app.""",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        Tool(
            name="get_service_help",
            description="""Get available methods for a macOS LLM app.

Args:
  service (str): App name (dia, atlas, comet)

Returns: Methods with parameters and descriptions.""",
            inputSchema={
                "type": "object",
                "properties": {
                    "service": {
                        "type": "string",
                        "description": "App name",
                        "enum": list(SERVICE_REGISTRY.keys())
                    }
                },
                "required": ["service"]
            }
        ),
        Tool(
            name="execute",
            description="""Execute a method on a macOS LLM app.

Args:
  service (str): App name (dia, atlas, comet)
  method (str): Method name (use get_service_help to see available)
  params (object): Method parameters

Examples:
  - Ask Dia: service="dia", method="ask", params={"question": "Hello"}
  - Ask and wait: service="dia", method="ask_and_wait", params={"question": "What is 2+2?"}
  - Read Perplexity: service="comet", method="ask", params={"question": "Latest news"}""",
            inputSchema={
                "type": "object",
                "properties": {
                    "service": {
                        "type": "string",
                        "description": "App name",
                        "enum": list(SERVICE_REGISTRY.keys())
                    },
                    "method": {
                        "type": "string",
                        "description": "Method name"
                    },
                    "params": {
                        "type": "object",
                        "description": "Method parameters",
                        "additionalProperties": True
                    }
                },
                "required": ["service", "method"]
            }
        )
    ]


@app.call_tool()
async def call_tool(name: str, arguments: Any) -> list[TextContent]:
    """Handle tool invocations."""
    logger.info(f"Tool called: {name} with args: {arguments}")

    try:
        if name == "list_services":
            result = {
                service: info["description"]
                for service, info in SERVICE_REGISTRY.items()
            }

        elif name == "get_service_help":
            service = arguments.get("service")
            if service not in SERVICE_REGISTRY:
                result = {"error": f"Unknown service: {service}. Available: {list(SERVICE_REGISTRY.keys())}"}
            else:
                service_info = SERVICE_REGISTRY[service]
                result = {
                    "service": service,
                    "description": service_info["description"],
                    "methods": {
                        method_name: {
                            "description": method_info["desc"],
                            "params": {
                                param_name: param_info["desc"]
                                for param_name, param_info in method_info["params"].items()
                            }
                        }
                        for method_name, method_info in service_info["methods"].items()
                    }
                }

        elif name == "execute":
            service = arguments.get("service")
            method = arguments.get("method")
            params = arguments.get("params", {})

            if service not in SERVICE_REGISTRY:
                result = {"error": f"Unknown service: {service}"}
            elif method not in SERVICE_REGISTRY[service]["methods"]:
                result = {"error": f"Unknown method '{method}' for '{service}'. Use get_service_help."}
            else:
                method_info = SERVICE_REGISTRY[service]["methods"][method]
                fn = method_info["fn"]

                # Build kwargs with defaults
                kwargs = {}
                for param_name, param_info in method_info["params"].items():
                    if param_name in params:
                        kwargs[param_name] = params[param_name]
                    elif "default" in param_info:
                        kwargs[param_name] = param_info["default"]
                    elif param_info.get("required"):
                        result = {"error": f"Missing required parameter: {param_name}"}
                        return [TextContent(type="text", text=json.dumps(result, indent=2))]

                # Execute synchronously (these are GUI operations, not async)
                result = fn(**kwargs)
        else:
            result = {"error": f"Unknown tool: {name}"}

        return [TextContent(type="text", text=json.dumps(result, indent=2, ensure_ascii=False))]

    except Exception as e:
        logger.error(f"Error executing {name}: {e}", exc_info=True)
        return [TextContent(type="text", text=json.dumps({
            "error": str(e),
            "error_type": type(e).__name__
        }, indent=2))]


# =============================================================================
# SERVER ENTRY POINT
# =============================================================================

async def main():
    """Start the MCP server."""
    logger.info("Starting macOS Apps MCP Server (dia, atlas, comet)")
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


def cli():
    """Sync entry point for console script."""
    asyncio.run(main())


if __name__ == "__main__":
    cli()
