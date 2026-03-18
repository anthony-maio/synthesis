# Synthesis MCP Server v3

The v3 MCP server translates validated Synthesis capabilities into Model Context Protocol tools so
collaborative agents can call them via Claude Desktop or any MCP-aware client. It builds on the
earlier factory prototypes while aligning with the current codebase: the sandbox runtime executes
capabilities, the trust manager gates privileges, and the observatory records every call.

## Design goals

- **Interoperable by default:** wrap capabilities as MCP tools with clear JSON schemas for arguments.
- **Safety-through-stewardship:** enforce trust-aware sandbox execution and return normalized results.
- **Transparent telemetry:** log execution outcomes so partners can trace how a capability behaves.

## Architecture

- `synthesis.mcp.server.SynthesisMCPServer` wires MCP handlers to capability adapters.
- Each adapter discovers the public entrypoint in `implementation_code`, builds a MCP `Tool`, and
  routes `call_tool` requests through `SandboxRuntime` with the current trust level.
- Execution results flow into the `Observatory`, while the `TrustManager` updates promotion metrics.

## Running a server

1. Install the MCP SDK: `pip install mcp`.
2. Synthesize or load capabilities (see `synthesis.core.synthesis.TDDSynthesizer`).
3. Start the server:

```python
import asyncio

from synthesis import CapabilityCategory, SynthesisClient, SynthesisMCPServer
from synthesis.llm import MockLLMProvider


async def main():
    client = SynthesisClient(llm_provider=MockLLMProvider())
    attempt = await client.synthesize(
        "Summarize a string to ten words",
        category=CapabilityCategory.TRANSFORMATION,
    )

    if not attempt.capability:
        raise RuntimeError("Synthesis failed; nothing to serve")

    server = SynthesisMCPServer([attempt.capability])
    await server.run_stdio()
if __name__ == "__main__":
    asyncio.run(main())
```

The server exposes the synthesized capability as a MCP tool, ready for Claude Desktop registration.

## Safety notes

- Trust levels from `TrustManager` travel with each call, keeping untrusted capabilities in stricter
  sandboxes until they earn promotion.
- `Observatory` logging preserves an audit trail for every collaborator to review capability behavior.
- Execution payloads are normalized to simple text responses so MCP clients receive predictable output.
