#!/usr/bin/env python3
"""
cli.py - Command Line Interface for Synthesis v2
=================================================

Provides a comprehensive CLI for interacting with the Synthesis framework.
Allows users and AI agents to synthesize, test, publish, and evolve capabilities
from the command line.
"""

import click
import asyncio
import json
from pathlib import Path
from typing import Optional
from tabulate import tabulate

from synthesis_v2.core import (
    CapabilityType, TrustLevel,
    EnhancedTDDSynthesizer, SecureRuntime,
    CapabilityRepository
)
from synthesis_v2.evolution import EvolutionEngine
from synthesis_v2.mcp import MCPServerFactory


@click.group()
@click.version_option(version='2.0.0')
def cli():
    """
    Synthesis v2 - Evolution Engine for AI Model Agency
    
    A framework for AI models to create, test, share, and evolve their own tools.
    """
    pass


@cli.command()
@click.option('--requirement', '-r', required=True, help='Natural language requirement')
@click.option('--type', '-t', 
              type=click.Choice(['data_transform', 'api_client', 'computation', 'text_analysis', 'custom']),
              default='custom', help='Capability type')
@click.option('--examples', '-e', help='Path to JSON file with examples')
@click.option('--output', '-o', help='Output path for capability')
@click.option('--max-iterations', default=5, help='Maximum synthesis iterations')
def synthesize(requirement, type, examples, output, max_iterations):
    """Synthesize a new capability from requirements."""
    
    click.echo(f"🔬 Synthesizing capability: {requirement[:50]}...")
    
    # Load examples if provided
    examples_data = None
    if examples:
        with open(examples, 'r') as f:
            examples_data = json.load(f)
    
    # Initialize synthesizer (would need LLM provider in production)
    synthesizer = EnhancedTDDSynthesizer(max_iterations=max_iterations)
    
    # Run synthesis
    async def run_synthesis():
        result = await synthesizer.synthesize(
            requirement=requirement,
            capability_type=CapabilityType[type.upper()],
            examples=examples_data
        )
        return result
    
    result = asyncio.run(run_synthesis())
    
    if result.success:
        click.echo(f"✅ Synthesis successful!")
        click.echo(f"   Iterations: {result.iterations}")
        click.echo(f"   Pass Rate: {result.final_pass_rate:.1%}")
        click.echo(f"   Capability ID: {result.capability.metadata.id}")
        
        if output:
            # Save capability to file
            output_path = Path(output)
            output_path.write_text(json.dumps(result.capability.to_dict(), indent=2))
            click.echo(f"   Saved to: {output}")
    else:
        click.echo(f"❌ Synthesis failed after {result.iterations} iterations")
        if result.error_patterns:
            click.echo(f"   Error patterns: {', '.join(result.error_patterns)}")


@cli.command()
@click.argument('capability_file')
@click.option('--inputs', '-i', help='JSON string of inputs')
@click.option('--docker/--no-docker', default=False, help='Use Docker isolation')
def execute(capability_file, inputs, docker):
    """Execute a capability with security constraints."""
    
    click.echo(f"🔒 Loading capability from {capability_file}...")
    
    # Load capability
    from synthesis_v2.core import Capability
    with open(capability_file, 'r') as f:
        capability_data = json.load(f)
    capability = Capability.from_dict(capability_data)
    
    # Parse inputs
    input_data = json.loads(inputs) if inputs else {}
    
    # Initialize runtime
    runtime = SecureRuntime(prefer_docker=docker)
    
    # Execute
    async def run_execution():
        result = await runtime.execute(capability, input_data)
        return result
    
    result = asyncio.run(run_execution())
    
    if result['success']:
        click.echo(f"✅ Execution successful!")
        click.echo(f"   Result: {json.dumps(result['result'], indent=2)}")
    else:
        click.echo(f"❌ Execution failed!")
        click.echo(f"   Error: {result['error']}")
    
    click.echo(f"   Execution time: {result['execution_time_ms']:.1f}ms")
    click.echo(f"   Trust level: {result['trust_level']}")


@cli.group()
def repo():
    """Manage the capability repository."""
    pass


@repo.command('publish')
@click.argument('capability_file')
@click.option('--author', '-a', default='cli_user', help='Author ID')
@click.option('--tags', '-t', multiple=True, help='Tags for discovery')
def publish_capability(capability_file, author, tags):
    """Publish a capability to the repository."""
    
    click.echo(f"📚 Publishing capability...")
    
    # Load capability
    from synthesis_v2.core import Capability
    with open(capability_file, 'r') as f:
        capability_data = json.load(f)
    capability = Capability.from_dict(capability_data)
    
    # Initialize repository
    repository = CapabilityRepository()
    
    # Publish
    cap_id = repository.publish(capability, author_id=author, tags=list(tags))
    
    click.echo(f"✅ Published successfully!")
    click.echo(f"   Capability ID: {cap_id}")
    click.echo(f"   Author: {author}")
    click.echo(f"   Tags: {', '.join(tags)}")


@repo.command('search')
@click.option('--query', '-q', help='Search query')
@click.option('--type', '-t', help='Capability type')
@click.option('--verified-only', is_flag=True, help='Only show verified capabilities')
@click.option('--limit', default=10, help='Maximum results')
def search_repository(query, type, verified_only, limit):
    """Search for capabilities in the repository."""
    
    repository = CapabilityRepository()
    
    # Search
    results = repository.search(
        query=query,
        capability_type=CapabilityType[type.upper()] if type else None,
        verified_only=verified_only,
        limit=limit
    )
    
    if not results:
        click.echo("No capabilities found.")
        return
    
    # Format results as table
    table_data = []
    for entry in results:
        table_data.append([
            entry.capability.metadata.id[:12],
            entry.capability.metadata.name[:30],
            entry.capability.metadata.capability_type.value,
            f"{entry.usage_metrics.success_rate:.1%}",
            entry.usage_metrics.total_downloads,
            f"{entry.average_rating:.1f}⭐",
            entry.capability.metadata.trust_level.name
        ])
    
    headers = ["ID", "Name", "Type", "Success", "Downloads", "Rating", "Trust"]
    click.echo(tabulate(table_data, headers=headers, tablefmt="grid"))


@repo.command('stats')
def repository_stats():
    """Show repository statistics."""
    
    repository = CapabilityRepository()
    stats = repository.get_statistics()
    
    click.echo("\n📊 Repository Statistics")
    click.echo("=" * 50)
    click.echo(f"Total Capabilities: {stats['total_capabilities']}")
    click.echo(f"Verified Capabilities: {stats['verified_capabilities']}")
    click.echo(f"Total Downloads: {stats['total_downloads']}")
    click.echo(f"Total Executions: {stats['total_executions']}")
    click.echo(f"Average Success Rate: {stats['average_success_rate']:.1%}")
    click.echo(f"Total Forks: {stats['total_forks']}")
    click.echo(f"Users Who Rated: {stats['users_who_rated']}")
    click.echo(f"Average Rating: {stats['average_rating']:.1f}⭐")
    
    click.echo("\nCapabilities by Type:")
    for cap_type, count in stats['by_type'].items():
        click.echo(f"  {cap_type}: {count}")


@cli.group()
def mcp():
    """Manage MCP servers."""
    pass


@mcp.command('create')
@click.argument('capability_ids', nargs=-1, required=True)
@click.option('--name', '-n', help='Server name')
@click.option('--description', '-d', help='Server description')
def create_mcp_server(capability_ids, name, description):
    """Create an MCP server from capabilities."""
    
    click.echo(f"🚀 Creating MCP server with {len(capability_ids)} capabilities...")
    
    # Load capabilities from repository
    repository = CapabilityRepository()
    capabilities = []
    
    for cap_id in capability_ids:
        cap = repository.download(cap_id, "cli_user")
        if cap:
            capabilities.append(cap)
            click.echo(f"   Loaded: {cap.metadata.name}")
        else:
            click.echo(f"   ⚠️ Not found: {cap_id}")
    
    if not capabilities:
        click.echo("❌ No valid capabilities found.")
        return
    
    # Create MCP server
    factory = MCPServerFactory()
    config = factory.create_server(
        capabilities=capabilities,
        server_name=name,
        server_description=description
    )
    
    click.echo(f"✅ MCP Server created!")
    click.echo(f"   Server ID: {config.server_id}")
    click.echo(f"   Name: {config.name}")
    click.echo(f"   Command: {config.command} {' '.join(config.args)}")
    
    # Register with Claude if possible
    if factory.register_with_claude(config):
        click.echo(f"   ✅ Registered with Claude Desktop")
        click.echo(f"   Restart Claude Desktop to use the new tools")


@mcp.command('list')
def list_mcp_servers():
    """List all MCP servers."""
    
    factory = MCPServerFactory()
    servers = factory.list_servers()
    
    if not servers:
        click.echo("No MCP servers found.")
        return
    
    click.echo("\n📦 MCP Servers")
    click.echo("=" * 60)
    
    for server in servers:
        click.echo(f"\n{server.name}")
        click.echo(f"  ID: {server.server_id}")
        click.echo(f"  Description: {server.description}")
        click.echo(f"  Capabilities: {len(server.capabilities)}")
        click.echo(f"  Process: {'Running' if server.process_id else 'Stopped'}")


@cli.group()
def evolve():
    """Manage capability evolution."""
    pass


@evolve.command('analyze')
@click.option('--min-executions', default=10, help='Minimum executions to consider')
def analyze_evolution_candidates(min_executions):
    """Analyze capabilities that need evolution."""
    
    click.echo("🔍 Analyzing evolution candidates...")
    
    # Initialize components
    repository = CapabilityRepository()
    synthesizer = EnhancedTDDSynthesizer()
    runtime = SecureRuntime()
    engine = EvolutionEngine(repository, synthesizer, runtime)
    
    # Find candidates
    async def find_candidates():
        candidates = await engine._identify_candidates()
        return candidates
    
    candidates = asyncio.run(find_candidates())
    
    if not candidates:
        click.echo("No evolution candidates found.")
        return
    
    click.echo(f"\nFound {len(candidates)} candidates:\n")
    
    # Format as table
    table_data = []
    for c in candidates[:10]:
        table_data.append([
            c.capability_id[:12],
            c.trigger.name,
            c.priority,
            f"{c.current_metrics.get('success_rate', 0):.1%}",
            f"{c.improvement_needed():.1f}x"
        ])
    
    headers = ["Capability", "Trigger", "Priority", "Success Rate", "Improvement Needed"]
    click.echo(tabulate(table_data, headers=headers, tablefmt="grid"))


@evolve.command('run')
@click.option('--continuous', is_flag=True, help='Run continuously')
@click.option('--interval', default=3600, help='Check interval in seconds')
def run_evolution(continuous, interval):
    """Run the evolution engine."""
    
    click.echo("🧬 Starting evolution engine...")
    
    # Initialize components
    repository = CapabilityRepository()
    synthesizer = EnhancedTDDSynthesizer()
    runtime = SecureRuntime()
    engine = EvolutionEngine(repository, synthesizer, runtime)
    
    if continuous:
        click.echo(f"Running continuously with {interval}s interval...")
        click.echo("Press Ctrl+C to stop.")
        
        async def run_continuous():
            await engine.monitor_and_evolve(interval)
        
        try:
            asyncio.run(run_continuous())
        except KeyboardInterrupt:
            click.echo("\nEvolution engine stopped.")
    else:
        click.echo("Running single evolution cycle...")
        
        async def run_once():
            candidates = await engine._identify_candidates()
            if candidates:
                result = await engine.evolve_capability(candidates[0])
                return result
            return None
        
        result = asyncio.run(run_once())
        
        if result:
            if result.success:
                click.echo(f"✅ Evolution successful!")
                click.echo(f"   Original: {result.original_capability_id}")
                click.echo(f"   Evolved: {result.evolved_capability_id}")
                click.echo(f"   Improvement: {result.improvement_percentage:.1f}%")
            else:
                click.echo(f"❌ Evolution failed")
        else:
            click.echo("No capabilities to evolve.")


@cli.command()
def demo():
    """Run the complete Synthesis v2 demonstration."""
    
    click.echo("🎭 Starting Synthesis v2 demonstration...")
    
    from synthesis_v2.demo import main as demo_main
    asyncio.run(demo_main())


if __name__ == '__main__':
    cli()
