"""Simple OpenAI App-compatible MCP server with a test widget.

Features:
- Tool "setvar" accepts a task string and appends it to tasks.txt
- After rendering, the widget posts a follow-up message after 3 seconds
  using the MCP Apps host bridge (ui/message) with a ChatGPT fallback
  via window.openai.sendFollowUpMessage.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

import mcp.types as types
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from pydantic import BaseModel, ConfigDict, Field, ValidationError

MIME_TYPE = "text/html;profile=mcp-app"


# Server/logger setup
logger = logging.getLogger("setvar-app")
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter("%(levelname)-8s | %(name)s | %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False


BASE_DIR = Path(__file__).resolve().parent
ASSETS_DIR = BASE_DIR / "assets"
TASKS_FILE = BASE_DIR / "tasks.txt"


@dataclass(frozen=True)
class Widget:
    identifier: str
    title: str
    template_uri: str
    invoking: str
    invoked: str


def _load_widget_html() -> str:
    html_path = ASSETS_DIR / "setvar-widget.html"
    if not html_path.exists():
        raise FileNotFoundError(f"Missing widget HTML at {html_path}")
    return html_path.read_text(encoding="utf8")


WIDGET = Widget(
    identifier="subagent-setvar",
    title="Subagent Task Widget",
    template_uri="ui://widget/setvar.v1.html",
    invoking="Submitting task to subagent…",
    invoked="Task submitted",
)


class SetVarInput(BaseModel):
    task: str = Field(..., description="Task text for the subagent")

    model_config = ConfigDict(extra="forbid")


mcp = FastMCP(
    name="setvar-python",
    stateless_http=True,
    transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
)


def _tool_meta(widget: Widget) -> Dict[str, Any]:
    return {
        "openai/outputTemplate": widget.template_uri,
        "openai/toolInvocation/invoking": widget.invoking,
        "openai/toolInvocation/invoked": widget.invoked,
        "openai/widgetAccessible": True,
        "annotations": {
            "destructiveHint": False,
            "openWorldHint": False,
            "readOnlyHint": False,
        },
        # Basic CSP hints (no external fetches required for this widget)
        "ui": {
            "csp": {
                "connectDomains": [],
                "resourceDomains": [],
            }
        },
    }


@mcp._mcp_server.list_tools()
async def _list_tools() -> List[types.Tool]:
    return [
        types.Tool(
            name="setvar",
            title="Submit a subagent task",
            description=(
                "Accepts a task string for a subagent and records it to tasks.txt."
            ),
            inputSchema=SetVarInput.model_json_schema(),
            _meta={
                **_tool_meta(WIDGET),
                # Advertise the UI template for MCP Apps hosts
                "ui": {"resourceUri": WIDGET.template_uri},
            },
        )
    ]


@mcp._mcp_server.list_resources()
async def _list_resources() -> List[types.Resource]:
    return [
        types.Resource(
            name=WIDGET.title,
            title=WIDGET.title,
            uri=WIDGET.template_uri,
            description="Widget template for subagent task flow",
            mimeType=MIME_TYPE,
            _meta=_tool_meta(WIDGET),
        )
    ]


@mcp._mcp_server.list_resource_templates()
async def _list_resource_templates() -> List[types.ResourceTemplate]:
    return [
        types.ResourceTemplate(
            name=WIDGET.title,
            title=WIDGET.title,
            uriTemplate=WIDGET.template_uri,
            description="Widget template for subagent task flow",
            mimeType=MIME_TYPE,
            _meta=_tool_meta(WIDGET),
        )
    ]


async def _handle_read_resource(req: types.ReadResourceRequest) -> types.ServerResult:
    resource_uri = str(req.params.uri)
    if resource_uri != WIDGET.template_uri:
        return types.ServerResult(
            types.ReadResourceResult(
                contents=[], _meta={"error": f"Unknown resource: {resource_uri}"}
            )
        )

    html = _load_widget_html()
    contents = [
        types.TextResourceContents(
            uri=WIDGET.template_uri,
            mimeType=MIME_TYPE,
            text=html,
            title=WIDGET.title,
            _meta=_tool_meta(WIDGET),
        )
    ]
    return types.ServerResult(types.ReadResourceResult(contents=contents))


async def _call_tool_request(req: types.CallToolRequest) -> types.ServerResult:
    args = req.params.arguments or {}
    try:
        payload = SetVarInput.model_validate(args)
    except ValidationError as exc:
        return types.ServerResult(
            types.CallToolResult(
                content=[types.TextContent(type="text", text=str(exc))],
                isError=True,
            )
        )

    # Append the task to tasks.txt with a simple timestamp
    TASKS_FILE.parent.mkdir(parents=True, exist_ok=True)
    from datetime import datetime

    line = f"{datetime.utcnow().isoformat()}\t{payload.task}\n"
    with TASKS_FILE.open("a", encoding="utf8") as f:
        f.write(line)

    # Return a small confirmation; ChatGPT will render the widget referenced via meta
    meta: Dict[str, Any] = {
        "ui": {"resourceUri": WIDGET.template_uri},
        "openai/outputTemplate": WIDGET.template_uri,
        "openai/toolInvocation/invoking": WIDGET.invoking,
        "openai/toolInvocation/invoked": WIDGET.invoked,
        "openai/widgetAccessible": True,
    }

    return types.ServerResult(
        types.CallToolResult(
            content=[
                types.TextContent(
                    type="text", text=f"Task received and saved: {payload.task}"
                )
            ],
            structuredContent={"task": payload.task},
            meta=meta,
        )
    )


# Wire handlers
mcp._mcp_server.request_handlers[types.CallToolRequest] = _call_tool_request
mcp._mcp_server.request_handlers[types.ReadResourceRequest] = _handle_read_resource


# Expose the ASGI app
app = mcp.streamable_http_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app:app", host="0.0.0.0", port=8000)
