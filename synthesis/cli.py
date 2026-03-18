"""Console entrypoint for the Synthesis package."""

from __future__ import annotations

import argparse
import asyncio
import json
from typing import Any

from synthesis import SynthesisClient
from synthesis.skill_runtime import DEFAULT_CANONICAL_REPO_SLUG


def build_parser() -> argparse.ArgumentParser:
    """Create the top-level CLI parser."""
    parser = argparse.ArgumentParser(
        prog="synthesis",
        description="Search, compose, and synthesize agent skills.",
    )
    parser.add_argument(
        "--canonical-repo",
        dest="canonical_repo_path",
        help=f"Override the local checkout used for the canonical registry ({DEFAULT_CANONICAL_REPO_SLUG}).",
    )
    parser.add_argument("--host-root", dest="host_root")
    parser.add_argument("--provider", default="mock", dest="provider_type")

    subparsers = parser.add_subparsers(dest="command", required=True)

    acquire = subparsers.add_parser("acquire-skill", help="Acquire or synthesize a skill.")
    acquire.add_argument("intent")
    acquire.add_argument("--requirements", default="")

    inspect = subparsers.add_parser("inspect-skill", help="Inspect a skill by name.")
    inspect.add_argument("name")

    submit = subparsers.add_parser("submit-skill", help="Prepare a submission for an installed skill.")
    submit.add_argument("name")

    subparsers.add_parser("list-installed-skills", help="List installed skills.")
    return parser


async def run_command(args: argparse.Namespace) -> Any:
    """Execute one CLI command."""
    client = SynthesisClient(
        provider_type=args.provider_type,
        canonical_repo_path=args.canonical_repo_path,
        host_root=args.host_root,
    )

    if args.command == "acquire-skill":
        result = await client.acquire_skill(args.intent, requirements=args.requirements)
        return result.to_dict()

    if args.command == "list-installed-skills":
        return [skill.model_dump() for skill in client.list_installed_skills()]

    if args.command == "inspect-skill":
        record = client.inspect_skill(args.name)
        return record.model_dump() if record else {"success": False, "error": "skill not found"}

    if args.command == "submit-skill":
        submission = client.submit_skill(args.name)
        return (
            submission.model_dump()
            if submission
            else {"success": False, "error": "skill cannot be submitted"}
        )

    raise ValueError(f"Unknown command: {args.command}")


def main() -> int:
    """Entry point for the `synthesis` console script."""
    parser = build_parser()
    args = parser.parse_args()
    payload = asyncio.run(run_command(args))
    print(json.dumps(payload, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
