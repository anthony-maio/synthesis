"""Model Context Protocol server for synthesized capabilities.

This module adapts Synthesis capabilities into a running MCP server that can be
consumed by Claude Desktop or any MCP-compatible client. It is intentionally
minimal but functional, aligning with the v3 design goal of having a reliable
path from synthesized capability to an interoperable tool endpoint.
"""

import ast
import json
from dataclasses import dataclass
from typing import Dict, List, Optional

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from synthesis.core.models import Capability, ExecutionResult, ExecutionStatus
from synthesis.observatory.logger import Observatory
from synthesis.sandbox.runtime import SandboxRuntime, TrustManager


def _discover_entrypoint(capability: Capability) -> str:
    """Return the first public function name in a capability's implementation."""
    tree = ast.parse(capability.implementation_code)
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and not node.name.startswith("_"):
            return node.name
    raise ValueError(
        f"No callable entrypoint found in capability {capability.id}: "
        "define at least one function"
    )


@dataclass
class CapabilityTool:
    """Adapter that executes a capability within sandbox constraints."""

    capability: Capability
    entrypoint: str
    sandbox: SandboxRuntime
    observatory: Observatory
    trust_manager: TrustManager

    @classmethod
    def from_capability(
        cls,
        capability: Capability,
        sandbox: SandboxRuntime,
        observatory: Observatory,
        trust_manager: TrustManager,
    ) -> "CapabilityTool":
        return cls(
            capability=capability,
            entrypoint=_discover_entrypoint(capability),
            sandbox=sandbox,
            observatory=observatory,
            trust_manager=trust_manager,
        )

    def to_tool(self) -> Tool:
        """Create an MCP Tool definition from a capability."""
        input_schema = self.capability.parameters.model_dump() or {"type": "object"}
        return Tool(
            name=self.capability.name,
            description=self.capability.description,
            inputSchema=input_schema,
        )

    async def execute(self, arguments: Dict[str, object]) -> ExecutionResult:
        """Execute the capability and record observability + trust signals."""
        trust_level = self.trust_manager.get_trust_level(self.capability.id)
        result = await self.sandbox.execute(
            code=self.capability.implementation_code,
            function_name=self.entrypoint,
            arguments=arguments,
            capability_id=self.capability.id,
            trust_level=trust_level,
        )

        self._normalize_output(result)
        self.trust_manager.record_execution(
            self.capability.id,
            success=result.status == ExecutionStatus.SUCCESS,
            execution_time_ms=result.execution_time_ms,
        )
        self.observatory.record_execution_result(result)
        return result

    def _normalize_output(self, result: ExecutionResult) -> None:
        """Align sandbox payloads with MCP expectations."""
        if result.status != ExecutionStatus.SUCCESS:
            return

        if isinstance(result.output, dict):
            if result.output.get("success") is False:
                result.status = ExecutionStatus.FAILED
                result.error = result.output.get("error", "Capability reported failure")
                result.output = None
                return

            if "result" in result.output:
                result.output = result.output["result"]


class SynthesisMCPServer:
    """Composable MCP server that exposes Synthesis capabilities as tools."""

    def __init__(
        self,
        capabilities: List[Capability],
        *,
        server_name: str = "synthesis-mcp-v3",
        sandbox: Optional[SandboxRuntime] = None,
        observatory: Optional[Observatory] = None,
        trust_manager: Optional[TrustManager] = None,
    ):
        self.server = Server(server_name)
        self.sandbox = sandbox or SandboxRuntime()
        self.observatory = observatory or Observatory()
        self.trust_manager = trust_manager or TrustManager()

        self._tools_by_name: Dict[str, CapabilityTool] = {}
        failed_capabilities = []
        for cap in capabilities:
            try:
                self._tools_by_name[cap.name] = CapabilityTool.from_capability(
                    capability=cap,
                    sandbox=self.sandbox,
                    observatory=self.observatory,
                    trust_manager=self.trust_manager,
                )
            except (SyntaxError, ValueError) as e:
                failed_capabilities.append((cap.name, str(e)))

        if failed_capabilities:
            # Log warning about failed capabilities
            msg = "The following capabilities failed to load:\n"
            for name, err in failed_capabilities:
                msg += f"  - {name}: {err}\n"
            if self.observatory:
                self.observatory.warning(msg)
            else:
                print(msg)
        self._register_handlers()

    def _register_handlers(self) -> None:
        """Register MCP handlers for tools lifecycle."""

        @self.server.list_tools()
        async def list_tools() -> List[Tool]:
            return [tool.to_tool() for tool in self._tools_by_name.values()]

        @self.server.call_tool()
        async def call_tool(name: str, arguments: Dict[str, object]) -> List[TextContent]:
            tool = self._tools_by_name.get(name)
            if not tool:
                return [
                    TextContent(
                        type="text",
                        text=f"Capability '{name}' is not registered on this server.",
                    )
                ]

            result = await tool.execute(arguments)
            if result.status == ExecutionStatus.SUCCESS:
                payload = (
                    result.output
                    if isinstance(result.output, (str, int, float))
                    else json.dumps(result.output, indent=2)
                )
                return [TextContent(type="text", text=str(payload))]

            message = result.error or "Capability execution failed"
            return [TextContent(type="text", text=message)]

    async def run_stdio(self) -> None:
        """Start the MCP server over stdio for Claude Desktop integration."""
        async with stdio_server() as (read_stream, write_stream):
            await self.server.run(read_stream, write_stream)

    async def serve_forever(self) -> None:
        """Convenience alias for running the stdio server."""
        await self.run_stdio()

