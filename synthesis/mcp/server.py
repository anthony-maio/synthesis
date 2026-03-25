"""MCP management surface for skill-first Synthesis."""

from __future__ import annotations

import json
from typing import Dict, List

from synthesis.client import SynthesisClient
from synthesis.core.models import CandidateBundleNextAction, SkillInstallPolicy

ACTION_ENUM = [action.value for action in CandidateBundleNextAction]


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
                "name": "inspect_candidate_bundle",
                "description": "Inspect a miner-produced challenger bundle by path.",
                "inputSchema": {
                    "type": "object",
                    "properties": {"path": {"type": "string"}},
                    "required": ["path"],
                },
            },
            {
                "name": "inspect_candidate_bundle_detail",
                "description": "Return reviewer-facing details for a miner-produced challenger bundle.",
                "inputSchema": {
                    "type": "object",
                    "properties": {"path": {"type": "string"}},
                    "required": ["path"],
                },
            },
            {
                "name": "inspect_candidate_bundle_review",
                "description": "Return a compact curator-facing summary for a challenger bundle.",
                "inputSchema": {
                    "type": "object",
                    "properties": {"path": {"type": "string"}},
                    "required": ["path"],
                },
            },
            {
                "name": "inspect_candidate_bundle_directory",
                "description": "Return a curator-facing review queue for a directory of challenger bundles.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "action": {"type": "string", "enum": ACTION_ENUM},
                    },
                    "required": ["path"],
                },
            },
            {
                "name": "inspect_candidate_bundle_blockers",
                "description": "Return only blocked challenger bundles from a directory review queue.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "action": {"type": "string", "enum": ACTION_ENUM},
                    },
                    "required": ["path"],
                },
            },
            {
                "name": "prepare_candidate_bundle_submission",
                "description": "Return a PR-ready submission envelope for a challenger bundle.",
                "inputSchema": {
                    "type": "object",
                    "properties": {"path": {"type": "string"}},
                    "required": ["path"],
                },
            },
            {
                "name": "publish_candidate_bundle_submission",
                "description": "Write a challenger bundle into the canonical checkout, commit it, push it, and optionally open a pull request.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "open_pull_request": {"type": "boolean"},
                        "base_branch": {"type": "string"},
                        "draft_pull_request": {"type": "boolean"},
                        "labels": {"type": "array", "items": {"type": "string"}},
                        "reviewers": {"type": "array", "items": {"type": "string"}},
                        "use_temp_worktree": {"type": "boolean"},
                        "worktree_root": {"type": "string"},
                    },
                    "required": ["path"],
                },
            },
            {
                "name": "validate_candidate_bundle",
                "description": "Validate a miner-produced challenger bundle by path.",
                "inputSchema": {
                    "type": "object",
                    "properties": {"path": {"type": "string"}},
                    "required": ["path"],
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
            {
                "name": "submit_candidate_bundle",
                "description": "Prepare a PR-ready submission from a miner-produced challenger bundle.",
                "inputSchema": {
                    "type": "object",
                    "properties": {"path": {"type": "string"}},
                    "required": ["path"],
                },
            },
            {
                "name": "install_candidate_bundle",
                "description": "Install a validated challenger bundle into the local host root.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "allow_drafts": {"type": "boolean"},
                        "allow_challengers": {"type": "boolean"},
                        "allow_canonical": {"type": "boolean"},
                        "require_packaging_allowed": {"type": "boolean"},
                    },
                    "required": ["path"],
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

        if name == "inspect_candidate_bundle":
            bundle_path = str(arguments.get("path", ""))
            record = self.client.inspect_candidate_bundle(bundle_path)
            if not record:
                return json.dumps(
                    {"success": False, "error": f"Candidate bundle '{bundle_path}' not found"}
                )
            return json.dumps(record.model_dump(), indent=2, default=str)

        if name == "inspect_candidate_bundle_detail":
            bundle_path = str(arguments.get("path", ""))
            detail = self.client.inspect_candidate_bundle_detail(bundle_path)
            if not detail:
                return json.dumps(
                    {"success": False, "error": f"Candidate bundle '{bundle_path}' not found"}
                )
            return json.dumps(detail.model_dump(), indent=2, default=str)

        if name == "inspect_candidate_bundle_review":
            bundle_path = str(arguments.get("path", ""))
            review = self.client.inspect_candidate_bundle_review(bundle_path)
            if not review:
                return json.dumps(
                    {"success": False, "error": f"Candidate bundle '{bundle_path}' not found"}
                )
            return json.dumps(review.model_dump(), indent=2, default=str)

        if name == "inspect_candidate_bundle_directory":
            bundles_root = str(arguments.get("path", ""))
            queue = self.client.inspect_candidate_bundle_directory(
                bundles_root,
                action=(str(arguments["action"]) if arguments.get("action") is not None else None),
            )
            if not queue:
                return json.dumps(
                    {
                        "success": False,
                        "error": f"Candidate bundle directory '{bundles_root}' not found",
                    }
                )
            return json.dumps(queue.model_dump(), indent=2, default=str)

        if name == "inspect_candidate_bundle_blockers":
            bundles_root = str(arguments.get("path", ""))
            blockers = self.client.inspect_candidate_bundle_blockers(
                bundles_root,
                action=(str(arguments["action"]) if arguments.get("action") is not None else None),
            )
            if not blockers:
                return json.dumps(
                    {
                        "success": False,
                        "error": f"Candidate bundle directory '{bundles_root}' not found",
                    }
                )
            return json.dumps(blockers.model_dump(), indent=2, default=str)

        if name == "prepare_candidate_bundle_submission":
            bundle_path = str(arguments.get("path", ""))
            envelope = self.client.prepare_candidate_bundle_submission(bundle_path)
            if not envelope:
                return json.dumps(
                    {
                        "success": False,
                        "error": f"Candidate bundle '{bundle_path}' cannot be prepared",
                    }
                )
            return json.dumps(envelope.model_dump(), indent=2, default=str)

        if name == "publish_candidate_bundle_submission":
            bundle_path = str(arguments.get("path", ""))
            result = self.client.publish_candidate_bundle_submission(
                bundle_path,
                open_pull_request=bool(arguments.get("open_pull_request", False)),
                base_branch=str(arguments.get("base_branch", "main")),
                draft_pull_request=bool(arguments.get("draft_pull_request", False)),
                labels=[str(label) for label in arguments.get("labels", [])],
                reviewers=[str(reviewer) for reviewer in arguments.get("reviewers", [])],
                use_temp_worktree=bool(arguments.get("use_temp_worktree", False)),
                worktree_root=(
                    str(arguments["worktree_root"])
                    if arguments.get("worktree_root") is not None
                    else None
                ),
            )
            if not result:
                return json.dumps(
                    {
                        "success": False,
                        "error": f"Candidate bundle '{bundle_path}' cannot be published",
                    }
                )
            return json.dumps(result.model_dump(), indent=2, default=str)

        if name == "validate_candidate_bundle":
            bundle_path = str(arguments.get("path", ""))
            validation = self.client.validate_candidate_bundle(bundle_path)
            return json.dumps(validation.model_dump(), indent=2, default=str)

        if name == "submit_skill":
            skill_name = str(arguments.get("name", ""))
            submission = self.client.submit_skill(skill_name)
            if not submission:
                return json.dumps(
                    {"success": False, "error": f"Skill '{skill_name}' cannot be submitted"}
                )
            return json.dumps(submission.model_dump(), indent=2, default=str)

        if name == "submit_candidate_bundle":
            bundle_path = str(arguments.get("path", ""))
            submission = self.client.submit_candidate_bundle(bundle_path)
            if not submission:
                return json.dumps(
                    {
                        "success": False,
                        "error": f"Candidate bundle '{bundle_path}' cannot be submitted",
                    }
                )
            return json.dumps(submission.model_dump(), indent=2, default=str)

        if name == "install_candidate_bundle":
            bundle_path = str(arguments.get("path", ""))
            record = self.client.install_candidate_bundle(
                bundle_path,
                policy=SkillInstallPolicy(
                    allow_drafts=bool(arguments.get("allow_drafts", False)),
                    allow_challengers=bool(arguments.get("allow_challengers", False)),
                    allow_canonical=bool(arguments.get("allow_canonical", True)),
                    require_packaging_allowed=bool(
                        arguments.get("require_packaging_allowed", True)
                    ),
                ),
            )
            if not record:
                return json.dumps(
                    {
                        "success": False,
                        "error": f"Candidate bundle '{bundle_path}' cannot be installed",
                    }
                )
            return json.dumps(record.model_dump(), indent=2, default=str)

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
