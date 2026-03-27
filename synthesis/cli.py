"""Console entrypoint for the Synthesis package."""

from __future__ import annotations

import argparse
import asyncio
import json
from typing import Any

from synthesis import CandidateBundleNextAction, SkillInstallPolicy, SynthesisClient
from synthesis.skill_runtime import DEFAULT_CANONICAL_REPO_SLUG

ACTION_CHOICES = [action.value for action in CandidateBundleNextAction]


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

    inspect_bundle = subparsers.add_parser(
        "inspect-candidate-bundle",
        help="Inspect a miner-produced challenger bundle by path.",
    )
    inspect_bundle.add_argument("path")

    inspect_bundle_detail = subparsers.add_parser(
        "inspect-candidate-bundle-detail",
        help="Return reviewer-facing details for a miner-produced challenger bundle.",
    )
    inspect_bundle_detail.add_argument("path")

    inspect_bundle_review = subparsers.add_parser(
        "inspect-candidate-bundle-review",
        help="Return a compact curator-facing summary for a miner-produced challenger bundle.",
    )
    inspect_bundle_review.add_argument("path")

    inspect_bundle_directory = subparsers.add_parser(
        "inspect-candidate-bundle-directory",
        help="Return a curator-facing review queue for a directory of challenger bundles.",
    )
    inspect_bundle_directory.add_argument("path")
    inspect_bundle_directory.add_argument("--action", choices=ACTION_CHOICES)

    inspect_bundle_blockers = subparsers.add_parser(
        "inspect-candidate-bundle-blockers",
        help="Return only blocked challenger bundles from a directory review queue.",
    )
    inspect_bundle_blockers.add_argument("path")
    inspect_bundle_blockers.add_argument("--action", choices=ACTION_CHOICES)

    review_bundle_directory = subparsers.add_parser(
        "review-candidate-bundle-directory",
        help="Return a compact grouped reviewer report for a directory of challenger bundles.",
    )
    review_bundle_directory.add_argument("path")
    review_bundle_directory.add_argument("--include-ready", action="store_true")

    write_review_report = subparsers.add_parser(
        "write-candidate-bundle-review-report",
        help="Write a grouped reviewer report for a directory of challenger bundles.",
    )
    write_review_report.add_argument("path")
    write_review_report.add_argument("output_path")
    write_review_report.add_argument("--include-ready", action="store_true")

    prepare_bundle_submission = subparsers.add_parser(
        "prepare-candidate-bundle-submission",
        help="Return a PR-ready submission envelope for a miner-produced challenger bundle.",
    )
    prepare_bundle_submission.add_argument("path")

    publish_bundle_directory = subparsers.add_parser(
        "publish-candidate-bundle-directory",
        help="Publish every candidate in a directory selected by one queue action.",
    )
    publish_bundle_directory.add_argument("path")
    publish_bundle_directory.add_argument("--action", choices=ACTION_CHOICES, default="ready_to_publish")
    publish_bundle_directory.add_argument("--open-pull-request", action="store_true")
    publish_bundle_directory.add_argument("--base-branch", default="main")
    publish_bundle_directory.add_argument("--draft-pull-request", action="store_true")
    publish_bundle_directory.add_argument("--label", action="append", default=[])
    publish_bundle_directory.add_argument("--reviewer", action="append", default=[])
    publish_bundle_directory.add_argument("--use-temp-worktree", action="store_true")
    publish_bundle_directory.add_argument("--worktree-root")

    publish_bundle_submission = subparsers.add_parser(
        "publish-candidate-bundle-submission",
        help="Publish a candidate submission envelope into the canonical registry checkout.",
    )
    publish_bundle_submission.add_argument("path")
    publish_bundle_submission.add_argument("--open-pull-request", action="store_true")
    publish_bundle_submission.add_argument("--base-branch", default="main")
    publish_bundle_submission.add_argument("--draft-pull-request", action="store_true")
    publish_bundle_submission.add_argument("--label", action="append", default=[])
    publish_bundle_submission.add_argument("--reviewer", action="append", default=[])
    publish_bundle_submission.add_argument("--use-temp-worktree", action="store_true")
    publish_bundle_submission.add_argument("--worktree-root")

    validate_bundle = subparsers.add_parser(
        "validate-candidate-bundle",
        help="Validate a miner-produced challenger bundle by path.",
    )
    validate_bundle.add_argument("path")

    submit = subparsers.add_parser("submit-skill", help="Prepare a submission for an installed skill.")
    submit.add_argument("name")

    submit_bundle = subparsers.add_parser(
        "submit-candidate-bundle",
        help="Prepare a submission from a miner-produced challenger bundle.",
    )
    submit_bundle.add_argument("path")

    install_bundle = subparsers.add_parser(
        "install-candidate-bundle",
        help="Install a validated challenger bundle into the local host root.",
    )
    install_bundle.add_argument("path")
    install_bundle.add_argument("--allow-drafts", action="store_true")
    install_bundle.add_argument("--allow-challengers", action="store_true")
    install_bundle.add_argument("--block-canonical", action="store_true")
    install_bundle.add_argument("--ignore-packaging-gate", action="store_true")

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

    if args.command == "inspect-candidate-bundle":
        record = client.inspect_candidate_bundle(args.path)
        return (
            record.model_dump()
            if record
            else {"success": False, "error": "candidate bundle not found or invalid"}
        )

    if args.command == "inspect-candidate-bundle-detail":
        detail = client.inspect_candidate_bundle_detail(args.path)
        return (
            detail.model_dump()
            if detail
            else {"success": False, "error": "candidate bundle not found or invalid"}
        )

    if args.command == "inspect-candidate-bundle-review":
        review = client.inspect_candidate_bundle_review(args.path)
        return (
            review.model_dump()
            if review
            else {"success": False, "error": "candidate bundle not found or invalid"}
        )

    if args.command == "inspect-candidate-bundle-directory":
        queue = client.inspect_candidate_bundle_directory(args.path, action=args.action)
        return (
            queue.model_dump()
            if queue
            else {"success": False, "error": "candidate bundle directory not found or invalid"}
        )

    if args.command == "inspect-candidate-bundle-blockers":
        blockers = client.inspect_candidate_bundle_blockers(args.path, action=args.action)
        return (
            blockers.model_dump()
            if blockers
            else {"success": False, "error": "candidate bundle directory not found or invalid"}
        )

    if args.command == "review-candidate-bundle-directory":
        report = client.review_candidate_bundle_directory(
            args.path,
            include_publishable=args.include_ready,
        )
        return (
            report.model_dump()
            if report
            else {"success": False, "error": "candidate bundle directory not found or invalid"}
        )

    if args.command == "write-candidate-bundle-review-report":
        export = client.write_candidate_bundle_review_report(
            args.path,
            args.output_path,
            include_publishable=args.include_ready,
        )
        return (
            export.model_dump()
            if export
            else {"success": False, "error": "candidate bundle directory not found or invalid"}
        )

    if args.command == "prepare-candidate-bundle-submission":
        envelope = client.prepare_candidate_bundle_submission(args.path)
        return (
            envelope.model_dump()
            if envelope
            else {"success": False, "error": "candidate bundle cannot be prepared"}
        )

    if args.command == "publish-candidate-bundle-directory":
        batch = client.publish_candidate_bundle_directory(
            args.path,
            action=args.action,
            open_pull_request=args.open_pull_request,
            base_branch=args.base_branch,
            draft_pull_request=args.draft_pull_request,
            labels=args.label,
            reviewers=args.reviewer,
            use_temp_worktree=args.use_temp_worktree,
            worktree_root=args.worktree_root,
        )
        return (
            batch.model_dump()
            if batch
            else {"success": False, "error": "candidate bundle directory not found or invalid"}
        )

    if args.command == "publish-candidate-bundle-submission":
        result = client.publish_candidate_bundle_submission(
            args.path,
            open_pull_request=args.open_pull_request,
            base_branch=args.base_branch,
            draft_pull_request=args.draft_pull_request,
            labels=args.label,
            reviewers=args.reviewer,
            use_temp_worktree=args.use_temp_worktree,
            worktree_root=args.worktree_root,
        )
        return (
            result.model_dump()
            if result
            else {"success": False, "error": "candidate bundle cannot be published"}
        )

    if args.command == "validate-candidate-bundle":
        return client.validate_candidate_bundle(args.path).model_dump()

    if args.command == "submit-skill":
        submission = client.submit_skill(args.name)
        return (
            submission.model_dump()
            if submission
            else {"success": False, "error": "skill cannot be submitted"}
        )

    if args.command == "submit-candidate-bundle":
        submission = client.submit_candidate_bundle(args.path)
        return (
            submission.model_dump()
            if submission
            else {"success": False, "error": "candidate bundle cannot be submitted"}
        )

    if args.command == "install-candidate-bundle":
        record = client.install_candidate_bundle(
            args.path,
            policy=SkillInstallPolicy(
                allow_drafts=args.allow_drafts,
                allow_challengers=args.allow_challengers,
                allow_canonical=not args.block_canonical,
                require_packaging_allowed=not args.ignore_packaging_gate,
            ),
        )
        return (
            record.model_dump()
            if record
            else {"success": False, "error": "candidate bundle cannot be installed"}
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
