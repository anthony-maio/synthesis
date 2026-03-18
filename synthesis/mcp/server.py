"""MCP management surface for skill-first Synthesis."""

from __future__ import annotations

import json
from typing import Dict, List

from synthesis.client import SynthesisClient


class SynthesisMCPServer:
    """Expose Synthesis skill acquisition and inspection as MCP tools."""

    def __init__(self, client: SynthesisClient, server_name: str = "synthesis-skills-v1"):
        self.client = client
        self.server_name = server_name

    async def list_tools(self) -> List[Dict]:
        """List the skill management tools exposed by this server."""
        return [
            {
                "name": "acquire_skill",
                "description": "Search, install, compose, or synthesize a skill for an intent.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "intent": {"type": "string"},
                        "requirements": {"type": "string"},
                    },
                    "required": ["intent"],
                },
            },
            {
                "name": "list_installed_skills",
                "description": "List installed skills in the host root.",
                "inputSchema": {"type": "object", "properties": {}},
            },
            {
                "name": "inspect_skill",
                "description": "Inspect one installed or canonical skill by name.",
                "inputSchema": {
                    "type": "object",
                    "properties": {"name": {"type": "string"}},
                    "required": ["name"],
                },
            },
            {
                "name": "submit_skill",
                "description": "Prepare a PR-ready submission for an installed skill.",
                "inputSchema": {
                    "type": "object",
                    "properties": {"name": {"type": "string"}},
                    "required": ["name"],
                },
            },
        ]

    async def call_tool(self, name: str, arguments: Dict[str, object]) -> str:
        """Handle one MCP tool invocation."""
        if name == "acquire_skill":
            intent = str(arguments.get("intent", ""))
            requirements = str(arguments.get("requirements", ""))
            result = await self.client.acquire_skill(intent=intent, requirements=requirements)
            return json.dumps(result.to_dict(), indent=2, default=str)

        if name == "list_installed_skills":
            payload = [skill.model_dump() for skill in self.client.list_installed_skills()]
            return json.dumps(payload, indent=2, default=str)

        if name == "inspect_skill":
            skill_name = str(arguments.get("name", ""))
            record = self.client.inspect_skill(skill_name)
            if not record:
                return json.dumps({"success": False, "error": f"Skill '{skill_name}' not found"})
            return json.dumps(record.model_dump(), indent=2, default=str)

        if name == "submit_skill":
            skill_name = str(arguments.get("name", ""))
            submission = self.client.submit_skill(skill_name)
            if not submission:
                return json.dumps(
                    {"success": False, "error": f"Skill '{skill_name}' cannot be submitted"}
                )
            return json.dumps(submission.model_dump(), indent=2, default=str)

        return json.dumps({"success": False, "error": f"Unknown tool '{name}'"})

    async def run_stdio(self) -> None:
        """Start the MCP server over stdio."""
        try:
            from mcp.server import Server
            from mcp.server.stdio import stdio_server
            from mcp.types import TextContent, Tool

            server = Server(self.server_name)

            @server.list_tools()
            async def handle_list_tools() -> List[Tool]:
                return [Tool(**tool) for tool in await self.list_tools()]

            @server.call_tool()
            async def handle_call_tool(name: str, arguments: Dict[str, object]) -> List[TextContent]:
                result = await self.call_tool(name, arguments)
                return [TextContent(type="text", text=result)]

            async with stdio_server() as (read_stream, write_stream):
                await server.run(read_stream, write_stream)
        except ImportError as exc:
            raise ImportError("MCP package required for stdio server. Install with: pip install mcp") from exc

    async def serve_forever(self) -> None:
        """Convenience alias for stdio serving."""
        await self.run_stdio()
